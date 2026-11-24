import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
OWNER_ID = int(os.getenv("OWNER_ID", "0"))

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN не задан в .env")
if not OWNER_ID:
    raise RuntimeError("OWNER_ID не задан в .env")

DB_PATH = "/data/bot.db"
TZ = "Europe/Moscow"
