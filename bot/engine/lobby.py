import asyncio
import random
from datetime import datetime, timedelta
from bot.config import (
    MIN_PLAYERS, LOBBY_TIMER_SECONDS, BALL_CALL_INTERVAL,
    VERIFICATION_WINDOW, ENTRY_FEE_CENTS, HOUSE_CUT_PERCENTAGE
)
from bot.engine.win_check import check_for_win

class GameState:
    def __init__(self):
        self.active_connections = {}  # user_id -> websocket/listener
        self.pending_bingo = {}  # round_id -> {user_id: sequence}
        self.false_bingo_users = set()
        self.winners = {}
        self.verification_active = False
        self.current_round = None

game_state = GameState()

class LobbyManager:
    def __init__(self, db_pool, bot):
        self.db_pool = db_pool
        self.bot = bot
        self.running = False
    
    async def start(self):
        self.running = True
        while self.running:
            await self.run_round()
    
    async def run_round(self):
        async with self.db_pool.acquire() as db:
            # Create round
            round_id = await db.fetchval(
                "INSERT INTO rounds (status, started_at) VALUES ('lobby', $1) RETURNING id",
                datetime.now()
            )
            game_state.current_round = round_id
            game_state.pending_bingo = {}
            game_state.false_bingo_users = set()
            game_state.winners = {}
            game_state.verification_active = False
            
            await db.execute(
                "UPDATE rounds SET status = 'lobby', started_at = $1 WHERE id = $2",
                datetime.now(), round_id
            )
            
            # Wait lobby timer
            for remaining in range(LOBBY_TIMER_SECONDS, 0, -10):
                await asyncio.sleep(10)
                players_count = await db.fetchval(
                    "SELECT COUNT(*) FROM round_players WHERE round_id = $1", round_id
                )
                # Broadcast countdown via SSE/WebSocket would go here
            
            await asyncio.sleep(LOBBY_TIMER_SECONDS % 10 or 0)
            
            # Check players
            players = await db.fetch(
                "SELECT rp.*, u.telegram_id, u.full_name FROM round_players rp "
                "JOIN users u ON rp.user_id = u.id WHERE rp.round_id = $1",
                round_id
            )
            
            if len(players) < MIN_PLAYERS:
                # Refund
                for p in players:
                    await db.execute(
                        "UPDATE users SET balance_cents = balance_cents + $1 WHERE id = $2",
                        ENTRY_FEE_CENTS, p['user_id']
                    )
                    await db.execute(
                        "INSERT INTO transactions (user_id, type, amount_cents, status) "
                        "VALUES ($1, 'refund', $2, 'approved')",
                        p['user_id'], ENTRY_FEE_CENTS
                    )
                await db.execute(
                    "UPDATE rounds SET status = 'cancelled', ended_at = $1 WHERE id = $2",
                    datetime.now(), round_id
                )
                return
            
            # Start drawing
            await db.execute("UPDATE rounds SET status = 'drawing' WHERE id = $1", round_id)
            
            # Generate balls
            balls = []
            for letter, nums in [('B', range(1,16)), ('I', range(16,31)),
                                  ('N', range(31,46)), ('G', range(46,61)),
                                  ('O', range(61,76))]:
                for n in nums:
                    balls.append(f"{letter}{n}")
            random.shuffle(balls)
            
            called_balls = set()
            
            for seq, ball in enumerate(balls):
                if game_state.winners:
                    break
                
                called_balls.add(ball)
                await db.execute(
                    "INSERT INTO balls (round_id, sequence, ball) VALUES ($1, $2, $3)",
                    round_id, seq, ball
                )
                
                # Ball is broadcast via SSE polling - handled by API
                await asyncio.sleep(BALL_CALL_INTERVAL)
                
                # Check pending BINGO presses for this ball
                if round_id in game_state.pending_bingo:
                    for user_id, press_seq in list(game_state.pending_bingo[round_id].items()):
                        if press_seq == seq and user_id not in game_state.false_bingo_users:
                            # Validate
                            player = await db.fetchrow(
                                "SELECT rp.*, u.telegram_id, u.full_name FROM round_players rp "
                                "JOIN users u ON rp.user_id = u.id "
                                "WHERE rp.round_id = $1 AND rp.user_id = $2",
                                round_id, user_id
                            )
                            if player:
                                card_data = await db.fetchval(
                                    "SELECT card_data FROM bingo_cards WHERE card_number = $1",
                                    player['card_number']
                                )
                                import ast
                                card_grid = ast.literal_eval(card_data)
                                is_win, win_type = check_for_win(card_grid, called_balls)
                                
                                if is_win:
                                    game_state.winners[user_id] = {
                                        'user_id': user_id,
                                        'full_name': player['full_name'],
                                        'telegram_id': player['telegram_id'],
                                        'win_type': win_type,
                                        'card_number': player['card_number'],
                                        'card_data': card_data
                                    }
                                    await db.execute(
                                        "UPDATE round_players SET bingo_pressed = TRUE, "
                                        "bingo_pressed_at_sequence = $1 "
                                        "WHERE round_id = $2 AND user_id = $3",
                                        seq, round_id, user_id
                                    )
                                else:
                                    game_state.false_bingo_users.add(user_id)
                                    await db.execute(
                                        "UPDATE round_players SET false_bingo = TRUE "
                                        "WHERE round_id = $1 AND user_id = $2",
                                        round_id, user_id
                                    )
                
                if game_state.winners:
                    break
            
            # Resolve
            total_pot = await db.fetchval(
                "SELECT total_pot_cents FROM rounds WHERE id = $1", round_id
            )
            
            if game_state.winners:
                prize_pool = int(total_pot * (1 - HOUSE_CUT_PERCENTAGE / 100))
                house_cut = total_pot - prize_pool
                payout = prize_pool // len(game_state.winners)
                
                for uid, winner in game_state.winners.items():
                    await db.execute(
                        "UPDATE round_players SET is_winner = TRUE, payout_cents = $1 "
                        "WHERE round_id = $2 AND user_id = $3",
                        payout, round_id, uid
                    )
                    await db.execute(
                        "UPDATE users SET balance_cents = balance_cents + $1 WHERE id = $2",
                        payout, uid
                    )
                    await db.execute(
                        "INSERT INTO transactions (user_id, type, amount_cents, status) "
                        "VALUES ($1, 'win', $2, 'approved')",
                        uid, payout
                    )
                
                game_state.verification_active = True
                await db.execute(
                    "UPDATE rounds SET status = 'finished', prize_pool_cents = $1, "
                    "house_cut_cents = $2, winning_ball_sequence = $3, ended_at = $4, "
                    "display_winner_card_until = $5 WHERE id = $6",
                    prize_pool, house_cut, seq, datetime.now(),
                    datetime.now() + timedelta(seconds=VERIFICATION_WINDOW), round_id
                )
                
                await asyncio.sleep(VERIFICATION_WINDOW)
                game_state.verification_active = False
            else:
                await db.execute(
                    "UPDATE rounds SET status = 'finished', total_pot_cents = $1, "
                    "prize_pool_cents = 0, house_cut_cents = $1, drawing_completed = TRUE, "
                    "ended_at = $2 WHERE id = $3",
                    total_pot, datetime.now(), round_id
                )
                await asyncio.sleep(3)
            
            # Unblock false bingo users
            game_state.false_bingo_users.clear()
            game_state.winners = {}
    
    async def stop(self):
        self.running = False
