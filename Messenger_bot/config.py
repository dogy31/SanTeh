from dotenv import load_dotenv
import os

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
MAX_TOKEN = os.getenv("MAX_TOKEN")

if MAX_TOKEN == "your_max_bot_token":
    MAX_TOKEN = None