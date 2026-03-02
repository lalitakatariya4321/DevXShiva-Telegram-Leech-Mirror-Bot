import motor.motor_asyncio
from bot.config import Config

class Database:
    def __init__(self, uri, database_name):
        # MongoDB Client initialization
        self._client = motor.motor_asyncio.AsyncIOMotorClient(uri)
        self._db = self._client[database_name]
        
        # Collections
        self._users = self._db.users
        self._tasks = self._db.tasks  # Task tracking collection

    # --- User Features ---
    async def is_user_exist(self, user_id):
        """Check karta hai ki user DB mein hai ya nahi."""
        user = await self._users.find_one({'_id': user_id})
        return True if user else False

    async def add_user(self, user_id, name):
        """User ko DB mein register karta hai agar wo naya hai."""
        user = {
            "_id": user_id,
            "name": name,
            "tasks_count": 0,
            "thumb": None,          # Permanent Thumbnail storage
            "upload_mode": "Media", # Default Upload Mode (Media/Document)
            "cookies": None         # Naya: Per-user cookies.txt storage
        }
        try:
            await self._users.insert_one(user)
        except:
            # Agar user pehle se hai toh sirf uska naam update kar do
            await self._users.update_one({"_id": user_id}, {"$set": {"name": name}})

    async def get_all_users(self):
        """Broadcast ke liye sabhi users ki list nikalta hai."""
        return self._users.find({})

    async def total_users_count(self):
        """Stats ke liye total users count karta hai."""
        return await self._users.count_documents({})

    async def increment_task_stat(self, user_id):
        """User ki total history mein task count badhata hai."""
        await self._users.update_one({"_id": user_id}, {"$inc": {"tasks_count": 1}})

    # --- Thumbnail & Settings Features ---
    async def set_thumb(self, user_id, file_id):
        """User ka custom thumbnail save ya update karta hai."""
        await self._users.update_one({"_id": user_id}, {"$set": {"thumb": file_id}})

    async def get_thumb(self, user_id):
        """User ka saved thumbnail file_id nikalta hai."""
        user = await self._users.find_one({"_id": user_id})
        return user.get("thumb", None) if user else None

    async def set_upload_mode(self, user_id, mode):
        """User ka upload preference (Media ya Document) set karta hai."""
        await self._users.update_one({"_id": user_id}, {"$set": {"upload_mode": mode}})

    async def get_upload_mode(self, user_id):
        """User ka current upload mode nikalta hai (Default: Media)."""
        user = await self._users.find_one({"_id": user_id})
        return user.get("upload_mode", "Media") if user else "Media"

    # --- Cookies Features (Naya Logic) ---
    async def set_cookies(self, user_id, cookie_text):
        """User ka cookies.txt file ka text save karta hai."""
        await self._users.update_one({"_id": user_id}, {"$set": {"cookies": cookie_text}})

    async def get_cookies(self, user_id):
        """User ka saved cookies text nikalta hai."""
        user = await self._users.find_one({"_id": user_id})
        return user.get("cookies", None) if user else None

    # --- Real-time Task Features (Purana Logic Intact) ---
    async def add_task(self, tid, user_id, name):
        """Task shuru hote hi DB mein entry banata hai."""
        import time 
        task_data = {
            "_id": tid,
            "user_id": user_id,
            "file_name": name,
            "status": "Running",
            "start_time": time.time()
        }
        try:
            await self._tasks.insert_one(task_data)
        except:
            pass

    async def rm_task(self, tid):
        """Task khatam ya cancel hote hi DB se entry delete kar deta hai."""
        await self._tasks.delete_one({"_id": tid})

    async def get_active_tasks_count(self, user_id):
        """Check karta hai ki user ke kitne tasks abhi chal rahe hain."""
        return await self._tasks.count_documents({"user_id": user_id})

    async def clear_all_tasks(self):
        """Bot restart hone par purane latke huye tasks saaf karne ke liye."""
        await self._tasks.delete_many({})

# Initialize DB with Config values
db = Database(Config.MONGO_URL, "LeechBotPro")
