import asyncio
import ast
from aiogram import Bot, Dispatcher
from bot.config import BOT_TOKEN, DATABASE_URL, MINI_APP_URL
from bot.database import init_db, close_db, pool
from bot.handlers import registration, wallet, game, menu
from bot.engine.lobby import LobbyManager
import asyncpg

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

dp.include_router(registration.router)
dp.include_router(wallet.router)
dp.include_router(game.router)
dp.include_router(menu.router)

async def main():
    global pool
    
    pool = await asyncpg.create_pool(DATABASE_URL)
    await init_db()
    
    # Seed cards
    async with pool.acquire() as conn:
        count = await conn.fetchval("SELECT COUNT(*) FROM bingo_cards")
        if count == 0:
            import json
            with open("data/bingo_cards.json") as f:
                cards = json.load(f)
            for card in cards:
                await conn.execute(
                    "INSERT INTO bingo_cards (card_number, card_data) VALUES ($1, $2)",
                    card['card_number'], str(card['grid'])
                )
            print(f"Seeded {len(cards)} cards")
    
    # Start lobby
    lobby = LobbyManager(pool, bot)
    asyncio.create_task(lobby.start())
    
    print("Bot starting...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
