import asyncpg
from bot.config import DATABASE_URL

pool = None

async def init_db():
    global pool
    if pool is None:
        pool = await asyncpg.create_pool(DATABASE_URL, min_size=2, max_size=10)
    
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                telegram_id BIGINT UNIQUE NOT NULL,
                username TEXT,
                full_name TEXT NOT NULL,
                phone TEXT UNIQUE NOT NULL,
                language TEXT DEFAULT 'en' NOT NULL,
                balance_cents INTEGER DEFAULT 0 NOT NULL,
                is_banned BOOLEAN DEFAULT FALSE NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
            );
            
            CREATE TABLE IF NOT EXISTS transactions (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id),
                type TEXT NOT NULL,
                amount_cents INTEGER NOT NULL,
                status TEXT DEFAULT 'pending' NOT NULL,
                reference TEXT,
                method TEXT,
                payout_account TEXT,
                admin_id INTEGER,
                note TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
                decided_at TIMESTAMP
            );
            
            CREATE TABLE IF NOT EXISTS rounds (
                id SERIAL PRIMARY KEY,
                status TEXT DEFAULT 'lobby' NOT NULL,
                started_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                ended_at TIMESTAMP,
                total_pot_cents INTEGER DEFAULT 0 NOT NULL,
                prize_pool_cents INTEGER DEFAULT 0 NOT NULL,
                house_cut_cents INTEGER DEFAULT 0 NOT NULL,
                winning_ball_sequence INTEGER,
                drawing_completed BOOLEAN DEFAULT FALSE,
                display_winner_card_until TIMESTAMP
            );
            
            CREATE TABLE IF NOT EXISTS round_players (
                round_id INTEGER NOT NULL REFERENCES rounds(id),
                user_id INTEGER NOT NULL REFERENCES users(id),
                card_number INTEGER NOT NULL,
                is_winner BOOLEAN DEFAULT FALSE NOT NULL,
                payout_cents INTEGER DEFAULT 0 NOT NULL,
                bingo_pressed BOOLEAN DEFAULT FALSE,
                bingo_pressed_at_sequence INTEGER,
                false_bingo BOOLEAN DEFAULT FALSE,
                PRIMARY KEY (round_id, user_id)
            );
            
            CREATE TABLE IF NOT EXISTS balls (
                round_id INTEGER NOT NULL REFERENCES rounds(id),
                sequence INTEGER NOT NULL,
                ball TEXT NOT NULL,
                PRIMARY KEY (round_id, sequence)
            );
            
            CREATE TABLE IF NOT EXISTS admin_actions (
                id SERIAL PRIMARY KEY,
                admin_id BIGINT NOT NULL,
                action TEXT NOT NULL,
                target_type TEXT NOT NULL,
                target_id INTEGER NOT NULL,
                payload_json TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
            );
            
            CREATE TABLE IF NOT EXISTS bingo_cards (
                card_number INTEGER PRIMARY KEY,
                card_data TEXT NOT NULL
            );
            
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY NOT NULL,
                value TEXT
            );
        """)
        
        await conn.execute("""
            INSERT INTO settings (key, value) VALUES 
            ('min_players', '2'),
            ('lobby_timer_seconds', '120'),
            ('ball_call_interval', '2'),
            ('entry_fee_cents', '1000'),
            ('house_cut_percentage', '20'),
            ('signup_bonus_cents', '2000')
            ON CONFLICT (key) DO NOTHING;
        """)

async def close_db():
    global pool
    if pool:
        await pool.close()
        pool = None
