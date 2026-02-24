import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    API_ID = int(os.getenv("API_ID"))
    API_HASH = os.getenv("API_HASH")
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    MONGO_URL = os.getenv("MONGO_URL")
    DUMP_CHAT_ID = int(os.getenv("DUMP_CHAT_ID"))
    FSUB_CHANNEL = os.getenv("FSUB_CHANNEL", "devXvoid") # Without @

    OWNER_ID = int(os.getenv("OWNER_ID"))
