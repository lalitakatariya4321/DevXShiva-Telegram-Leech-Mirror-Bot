import os

class Config:
    # --- API CREDENTIALS ---
    API_ID = int(os.environ.get("API_ID", "sample api"))
    API_HASH = os.environ.get("API_HASH", "your_api_hash_here")
    BOT_TOKEN = os.environ.get("BOT_TOKEN", "your_bot_token_here")
    
    # --- DATABASE ---
    MONGO_URL = os.environ.get("MONGO_URL", "your_mongodb_url_here")
    
    # --- ADMIN SETTINGS ---
    # 1. OWNER_ID mein apni ID dalo (Sirf number, bina quotes ke)
    OWNER_ID = int(os.environ.get("OWNER_ID", 5298223577)) # <-- Apni ID yahan dalo

    # 2. ADMINS list mein OWNER_ID aur baaki admins ki ID dalo
    # Isse /stats aur /broadcast command kaam karenge
    ADMINS = [OWNER_ID] 

    # --- LOGS & DUMP ---
    # Log channel ID dalo (-100 se shuru honi chahiye)
    LOG_CHANNEL = int(os.environ.get("LOG_CHANNEL", -1002686058050))
    DUMP_CHAT_ID = int(os.environ.get("DUMP_CHAT_ID", LOG_CHANNEL))
