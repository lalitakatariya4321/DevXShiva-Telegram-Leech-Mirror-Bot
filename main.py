import asyncio, threading, time
from pyrogram import Client, filters, idle
from bot.config import Config
from bot.helpers.fsub import check_fsub
from bot.plugins.leech import leech_logic, ACTIVE_TASKS, STOP_TASKS
from bot.helpers.progress import get_status_msg
from flask import Flask

app = Client("leech_bot", Config.API_ID, Config.API_HASH, bot_token=Config.BOT_TOKEN)
web_app = Flask(__name__)

@web_app.route('/')
def home(): return "Alive", 200

# --- Commands ---

@app.on_message(filters.command("start"))
async def start_msg(c, m):
    await m.reply_text(f"👋 **Welcome {m.from_user.first_name}!**\nI am a Pro Leech Bot.\n\n`/yt -n FileName URL` - Leech Files\n`/status` - Check Current Tasks")

@app.on_message(filters.command("yt"))
async def yt_cmd(c, m):
    # 1. Force Subscription Check
    if not await check_fsub(c, m): return
    
    # 2. GLOBAL LIMIT CHECK (Max 5 Tasks Globally)
    if len(ACTIVE_TASKS) >= 5:
        return await m.reply_text("⚠️ **Bot is Overloaded!**\nGlobally 5 tasks are already running. Please try again in a few minutes.")
    
    # 3. USER LIMIT CHECK (Max 2 Tasks per User)
    u_tasks = [t for t in ACTIVE_TASKS.values() if t['user_id'] == m.from_user.id]
    if len(u_tasks) >= 2: 
        return await m.reply("❌ **Limit Exceeded:** You can only have 2 active tasks at a time!")

    # 4. PRIVACY: Delete the /yt command message
    try:
        await m.delete()
    except Exception as e:
        print(f"Delete Error: {e}") # Bot must be admin in groups

    # 5. Parsing URL and Name
    parts = m.text.split(None, 1)
    if len(parts) < 2: 
        # Agar command delete ho gayi hai toh user ko PM ya temporary msg bhej sakte hain
        return await c.send_message(m.chat.id, "❌ Error: Please send link with /yt command.")
    
    name, url = "default", parts[1]
    if "-n " in parts[1]:
        try:
            data = parts[1].split("-n ", 1)[1].split(None, 1)
            name, url = data[0], data[1]
        except: pass

    # 6. Start Leech Process
    tid = str(int(time.time()))
    asyncio.create_task(leech_logic(c, m, tid, url, name))
    # Note: "Added to Queue" message hata diya hai, ab seedha leech.py ka live status bar aayega.

@app.on_message(filters.command("status"))
async def status_cmd(c, m):
    # status_handler helper function ko call kar rahe hain jo humne banaya tha
    from bot.plugins.status import status_handler
    await status_handler(c, m, ACTIVE_TASKS)

@app.on_message(filters.regex(r"^/cancel_"))
async def cancel_handler(c, m):
    tid = m.text.split("_")[1]
    if tid in ACTIVE_TASKS:
        # Permission check: Owner or the User who started the task
        if ACTIVE_TASKS[tid]['user_id'] == m.from_user.id or m.from_user.id == Config.OWNER_ID:
            if tid not in STOP_TASKS:
                STOP_TASKS.append(tid)
                await m.reply("🛑 **Cancellation request received.** Stopping the task...")
            else:
                await m.reply("Already trying to cancel this task.")
        else:
            await m.reply("⚠️ This is not your task!")
    else:
        await m.reply("❌ Task not found or already finished.")

# --- Bot Runner ---

async def run():
    # Start Flask in background
    threading.Thread(target=lambda: web_app.run(host="0.0.0.0", port=10000), daemon=True).start()
    await app.start()
    print("🚀 Bot Started Successfully!")
    await idle()

if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(run())
