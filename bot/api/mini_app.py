import ast
import hashlib
import hmac
import json
from datetime import datetime
from fastapi import APIRouter, HTTPException, Request, Query
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
from bot.database import pool
from bot.config import (
    BOT_TOKEN, MINI_APP_URL, ENTRY_FEE_CENTS, LOBBY_TIMER_SECONDS,
    BALL_CALL_INTERVAL, VERIFICATION_WINDOW
)
from bot.engine.lobby import game_state
from bot.engine.win_check import check_for_win

router = APIRouter(prefix="/api", tags=["mini-app"])

# ==================== Auth ====================
def verify_telegram_data(init_data: str) -> dict:
    """Verify Telegram WebApp initData"""
    parsed = {}
    for pair in init_data.split("&"):
        if "=" in pair:
            key, value = pair.split("=", 1)
            parsed[key] = value
    
    received_hash = parsed.pop("hash", "")
    data_check_string = "\n".join(
        f"{k}={v}" for k, v in sorted(parsed.items())
    )
    
    secret_key = hmac.new(
        b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256
    ).digest()
    
    calculated_hash = hmac.new(
        secret_key, data_check_string.encode(), hashlib.sha256
    ).hexdigest()
    
    if calculated_hash != received_hash:
        raise HTTPException(403, "Invalid Telegram data")
    
    return json.loads(parsed.get("user", "{}"))

# ==================== Models ====================
class BingoPress(BaseModel):
    initData: str
    round_id: int
    sequence: int

class CardSelect(BaseModel):
    initData: str
    card_number: int

# ==================== Lobby Info ====================
@router.get("/lobby-state")
async def get_lobby_state():
    """Get current lobby state for mini app."""
    async with pool.acquire() as db:
        current_round = await db.fetchrow(
            "SELECT * FROM rounds WHERE status = 'lobby' ORDER BY started_at DESC LIMIT 1"
        )
        
        if not current_round:
            return JSONResponse({
                "status": "no_lobby",
                "message": "Waiting for next round..."
            })
        
        taken = await db.fetch(
            "SELECT card_number FROM round_players WHERE round_id = $1",
            current_round['id']
        )
        taken_cards = [r['card_number'] for r in taken]
        players_count = len(taken_cards)
        
        elapsed = (datetime.now() - current_round['started_at']).total_seconds()
        time_left = max(0, LOBBY_TIMER_SECONDS - int(elapsed))
        
        return JSONResponse({
            "status": "lobby",
            "round_id": current_round['id'],
            "players_count": players_count,
            "time_left": time_left,
            "taken_cards": taken_cards
        })

@router.get("/game-state")
async def get_game_state():
    """Get current game state for mini app."""
    async with pool.acquire() as db:
        current_round = game_state.current_round
        if not current_round:
            return JSONResponse({"status": "no_game"})
        
        round_data = await db.fetchrow(
            "SELECT * FROM rounds WHERE id = $1", current_round
        )
        
        if not round_data or round_data['status'] == 'lobby':
            return JSONResponse({"status": "lobby"})
        
        if round_data['status'] == 'cancelled':
            return JSONResponse({"status": "cancelled"})
        
        # Get called balls
        balls = await db.fetch(
            "SELECT sequence, ball FROM balls WHERE round_id = $1 ORDER BY sequence",
            current_round
        )
        called_balls = [{"seq": b['sequence'], "ball": b['ball']} for b in balls]
        called_set = {b['ball'] for b in balls}
        
        # Winners info
        winners_list = []
        if game_state.winners:
            for uid, w in game_state.winners.items():
                card_grid = ast.literal_eval(w['card_data'])
                winners_list.append({
                    "name": w['full_name'],
                    "win_type": w['win_type'],
                    "card_number": w['card_number'],
                    "card": format_card_for_web(card_grid, called_set)
                })
        
        return JSONResponse({
            "status": round_data['status'],
            "round_id": current_round,
            "called_balls": called_balls,
            "winners": winners_list,
            "verification_active": game_state.verification_active,
            "last_ball_seq": len(balls) - 1 if balls else -1
        })

def format_card_for_web(grid, called_balls):
    """Format card for web display."""
    result = []
    for r in range(5):
        row = []
        for c in range(5):
            letter, num = grid[r][c]
            if num is None:
                row.append({"value": "FREE", "called": True, "is_free": True})
            else:
                ball = f"{letter}{num}"
                row.append({"value": ball, "called": ball in called_balls, "is_free": False})
        result.append(row)
    return result

# ==================== Card Selection ====================
@router.post("/select-card")
async def select_card(data: CardSelect, request: Request):
    """Player selects a card for the current lobby."""
    try:
        user = verify_telegram_data(data.initData)
    except:
        raise HTTPException(403, "Invalid auth")
    
    telegram_id = user.get("id")
    
    async with pool.acquire() as db:
        user_db = await db.fetchrow(
            "SELECT * FROM users WHERE telegram_id = $1", telegram_id
        )
        if not user_db:
            raise HTTPException(404, "User not registered")
        
        if user_db['is_banned']:
            raise HTTPException(403, "You are banned")
        
        if user_db['balance_cents'] < ENTRY_FEE_CENTS:
            raise HTTPException(400, f"Insufficient balance. Need {ENTRY_FEE_CENTS/100} ETB")
        
        current_round = await db.fetchrow(
            "SELECT * FROM rounds WHERE status = 'lobby' ORDER BY started_at DESC LIMIT 1"
        )
        if not current_round:
            raise HTTPException(400, "No active lobby")
        
        # Check already joined
        existing = await db.fetchrow(
            "SELECT id FROM round_players WHERE round_id = $1 AND user_id = $2",
            current_round['id'], user_db['id']
        )
        if existing:
            raise HTTPException(400, "Already joined")
        
        # Check card availability
        taken = await db.fetchrow(
            "SELECT id FROM round_players WHERE round_id = $1 AND card_number = $2",
            current_round['id'], data.card_number
        )
        if taken:
            raise HTTPException(400, "Card already taken")
        
        # Deduct and join
        await db.execute(
            "UPDATE users SET balance_cents = balance_cents - $1 WHERE id = $2",
            ENTRY_FEE_CENTS, user_db['id']
        )
        await db.execute(
            "INSERT INTO transactions (user_id, type, amount_cents, status) "
            "VALUES ($1, 'bet', $2, 'approved')",
            user_db['id'], ENTRY_FEE_CENTS
        )
        await db.execute(
            "INSERT INTO round_players (round_id, user_id, card_number) "
            "VALUES ($1, $2, $3)",
            current_round['id'], user_db['id'], data.card_number
        )
        await db.execute(
            "UPDATE rounds SET total_pot_cents = total_pot_cents + $1 WHERE id = $2",
            ENTRY_FEE_CENTS, current_round['id']
        )
        
        return JSONResponse({"success": True, "message": f"Joined with card #{data.card_number}"})

# ==================== BINGO Press ====================
@router.post("/bingo-press")
async def bingo_press(data: BingoPress, request: Request):
    """Player presses BINGO button."""
    try:
        user = verify_telegram_data(data.initData)
    except:
        raise HTTPException(403, "Invalid auth")
    
    telegram_id = user.get("id")
    
    async with pool.acquire() as db:
        user_db = await db.fetchrow(
            "SELECT * FROM users WHERE telegram_id = $1", telegram_id
        )
        if not user_db:
            raise HTTPException(404, "User not registered")
        
        # Check if blocked
        if user_db['id'] in game_state.false_bingo_users:
            return JSONResponse({
                "success": False,
                "reason": "blocked",
                "message": "You are blocked from BINGO for this round."
            })
        
        # Check if already won
        if user_db['id'] in game_state.winners:
            return JSONResponse({
                "success": False,
                "reason": "already_won",
                "message": "You already won!"
            })
        
        # Record the press
        if data.round_id not in game_state.pending_bingo:
            game_state.pending_bingo[data.round_id] = {}
        game_state.pending_bingo[data.round_id][user_db['id']] = data.sequence
        
        # Validate
        player = await db.fetchrow(
            "SELECT * FROM round_players WHERE round_id = $1 AND user_id = $2",
            data.round_id, user_db['id']
        )
        if not player:
            return JSONResponse({"success": False, "reason": "not_in_round"})
        
        card_data = await db.fetchval(
            "SELECT card_data FROM bingo_cards WHERE card_number = $1",
            player['card_number']
        )
        card_grid = ast.literal_eval(card_data)
        
        called = await db.fetch(
            "SELECT ball FROM balls WHERE round_id = $1 AND sequence <= $2",
            data.round_id, data.sequence
        )
        called_balls = {r['ball'] for r in called}
        
        is_win, win_type = check_for_win(card_grid, called_balls)
        
        if is_win:
            return JSONResponse({
                "success": True,
                "is_win": True,
                "win_type": win_type,
                "message": f"BINGO! {win_type}!"
            })
        else:
            game_state.false_bingo_users.add(user_db['id'])
            return JSONResponse({
                "success": True,
                "is_win": False,
                "message": "No win detected. You are blocked for this round."
            })

# ==================== Get My Card ====================
@router.get("/my-card")
async def get_my_card(initData: str = Query(...)):
    """Get the player's card for the current round."""
    try:
        user = verify_telegram_data(initData)
    except:
        raise HTTPException(403, "Invalid auth")
    
    telegram_id = user.get("id")
    
    async with pool.acquire() as db:
        user_db = await db.fetchrow(
            "SELECT * FROM users WHERE telegram_id = $1", telegram_id
        )
        if not user_db:
            raise HTTPException(404, "User not registered")
        
        current_round = game_state.current_round
        if not current_round:
            return JSONResponse({"has_card": False})
        
        player = await db.fetchrow(
            "SELECT * FROM round_players WHERE round_id = $1 AND user_id = $2",
            current_round, user_db['id']
        )
        
        if not player:
            return JSONResponse({"has_card": False})
        
        card_data = await db.fetchval(
            "SELECT card_data FROM bingo_cards WHERE card_number = $1",
            player['card_number']
        )
        card_grid = ast.literal_eval(card_data)
        
        # Get called balls
        balls = await db.fetch(
            "SELECT ball FROM balls WHERE round_id = $1 ORDER BY sequence",
            current_round
        )
        called_set = {b['ball'] for b in balls}
        
        return JSONResponse({
            "has_card": True,
            "card_number": player['card_number'],
            "card": format_card_for_web(card_grid, called_set),
            "is_blocked": user_db['id'] in game_state.false_bingo_users,
            "has_won": player['is_winner']
        })
