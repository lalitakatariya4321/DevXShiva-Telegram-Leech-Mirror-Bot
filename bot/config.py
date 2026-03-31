import os

class Config:
    # --- API CREDENTIALS ---
    API_ID = int(os.environ.get("API_ID", "35462505"))
    API_HASH = os.environ.get("API_HASH", "25406f5972566384cc0eb2bcbbf78c5f")
    BOT_TOKEN = os.environ.get("BOT_TOKEN", "8756435098:AAHK1orFAdYsjE6FSN-_TtFCDe-tiRP3qEU")
    
    # --- DATABASE ---
    MONGO_URL = os.environ.get("MONGO_URL", "mongodb+srv://mundazaini2003:mundazaini2003@cluster0.fk4blnt.mongodb.net/?appName=Cluster0")
    
    # --- ADMIN SETTINGS ---
    # 1. OWNER_ID mein apni ID dalo (Sirf number, bina quotes ke)
    OWNER_ID = int(os.environ.get("OWNER_ID", 6409036872)) # <-- Apni ID yahan dalo

    # 2. ADMINS list mein OWNER_ID aur baaki admins ki ID dalo
    # Isse /stats aur /broadcast command kaam karenge
    ADMINS = [OWNER_ID] 

    # --- LOGS & DUMP ---
    # Log channel ID dalo (-100 se shuru honi chahiye)
    LOG_CHANNEL = int(os.environ.get("LOG_CHANNEL", -1003753826888))
    DUMP_CHAT_ID = int(os.environ.get("DUMP_CHAT_ID", LOG_CHANNEL))
    FSUB_CHANNEL = "-1003627956964"
