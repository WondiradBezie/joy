import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_TELEGRAM_ID = int(os.getenv("ADMIN_TELEGRAM_ID", "0"))
DATABASE_URL = os.getenv("DATABASE_URL")
MINI_APP_URL = os.getenv("MINI_APP_URL", "http://localhost:8000")

MIN_PLAYERS = int(os.getenv("MIN_PLAYERS", "2"))
LOBBY_TIMER_SECONDS = int(os.getenv("LOBBY_TIMER_SECONDS", "120"))
BALL_CALL_INTERVAL = int(os.getenv("BALL_CALL_INTERVAL", "2"))
VERIFICATION_WINDOW = int(os.getenv("VERIFICATION_WINDOW", "6"))
ENTRY_FEE_CENTS = int(os.getenv("ENTRY_FEE_CENTS", "1000"))
HOUSE_CUT_PERCENTAGE = int(os.getenv("HOUSE_CUT_PERCENTAGE", "20"))
MIN_DEPOSIT_CENTS = int(os.getenv("MIN_DEPOSIT_CENTS", "2000"))
MIN_WITHDRAWAL_CENTS = int(os.getenv("MIN_WITHDRAWAL_CENTS", "10000"))
MIN_BALANCE_TO_PLAY_CENTS = int(os.getenv("MIN_BALANCE_TO_PLAY_CENTS", "1000"))
SIGNUP_BONUS_CENTS = int(os.getenv("SIGNUP_BONUS_CENTS", "2000"))

PAYMENT_ACCOUNTS = {
    "telebirr": os.getenv("TELEBIRR_ACCOUNT", "+251948813201"),
    "cbebirr": os.getenv("CBEBIRR_ACCOUNT", "+251948813201"),
    "mpesa": os.getenv("MPESA_ACCOUNT", "+251704813201"),
    "telebirr_name": os.getenv("TELEBIRR_NAME", "Wondirad"),
    "cbebirr_name": os.getenv("CBEBIRR_NAME", "Wondirad"),
    "mpesa_name": os.getenv("MPESA_NAME", "Wondirad"),
}
