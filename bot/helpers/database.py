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
    async def add_user(self, user_id, name):
        """User ko DB mein register karta hai agar wo naya hai."""
        user = {
            "_id": user_id,
            "name": name,
            "tasks_count": 0
        }
        try:
            await self._users.insert_one(user)
        except:
            # Agar user pehle se hai toh sirf uska naam update kar do
            await self._users.update_one({"_id": user_id}, {"$set": {"name": name}})

    async def increment_task_stat(self, user_id):
        """User ki total history mein task count badhata hai."""
        await self._users.update_one({"_id": user_id}, {"$inc": {"tasks_count": 1}})

    # --- Real-time Task Features (For Auto-Clean & Sync) ---
    async def add_task(self, tid, user_id, name):
        """Task shuru hote hi DB mein entry banata hai."""
        task_data = {
            "_id": tid,
            "user_id": user_id,
            "file_name": name,
            "status": "Running",
            "start_time":  Config.time.time() if hasattr(Config, 'time') else 0 
        }
        try:
            await self._tasks.insert_one(task_data)
        except:
            pass

    async def rm_task(self, tid):
        """Task khatam ya cancel hote hi DB se entry delete kar deta hai (Auto-Clean)."""
        await self._tasks.delete_one({"_id": tid})

    async def get_active_tasks_count(self, user_id):
        """Check karta hai ki user ke kitne tasks abhi chal rahe hain."""
        return await self._tasks.count_documents({"user_id": user_id})

    async def clear_all_tasks(self):
        """Bot restart hone par purane latke huye tasks saaf karne ke liye."""
        await self._tasks.delete_many({})

# Initialize DB with Config values
db = Database(Config.MONGO_URL, "LeechBotPro")