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

# Commands
@app.on_message(filters.command("start"))
async def start_msg(c, m):
    await m.reply_text(f"👋 **Welcome {m.from_user.first_name}!**\nI am a Pro Leech Bot.\n\n`/yt -n FileName URL`\n`/status` - Check Tasks")

@app.on_message(filters.command("yt"))
async def yt_cmd(c, m):
    if not await check_fsub(c, m): return
    
    # User Limit Check
    u_tasks = [t for t in ACTIVE_TASKS.values() if t['user_id'] == m.from_user.id]
    if len(u_tasks) >= 2: return await m.reply("❌ Limit: 2 tasks per user!")

    parts = m.text.split(None, 1)
    if len(parts) < 2: return await m.reply("Send link with /yt")
    
    name, url = "default", parts[1]
    if "-n " in parts[1]:
        try:
            data = parts[1].split("-n ", 1)[1].split(None, 1)
            name, url = data[0], data[1]
        except: pass

    tid = str(int(time.time()))
    asyncio.create_task(leech_logic(c, m, tid, url, name))
    await m.reply(f"⏳ **Added to Queue.** Check /status\nCancel: `/cancel_{tid}`")

@app.on_message(filters.command("status"))
async def status_cmd(c, m):
    await m.reply(await get_status_msg(ACTIVE_TASKS))

@app.on_message(filters.regex(r"^/cancel_"))
async def cancel_handler(c, m):
    tid = m.text.split("_")[1]
    if tid in ACTIVE_TASKS:
        if ACTIVE_TASKS[tid]['user_id'] == m.from_user.id or m.from_user.id == Config.OWNER_ID:
            STOP_TASKS.append(tid)
            await m.reply("Trying to cancel task...")
        else:
            await m.reply("Not your task!")
    else:
        await m.reply("Task not found.")

async def run():
    threading.Thread(target=lambda: web_app.run(host="0.0.0.0", port=10000), daemon=True).start()
    await app.start()
    print("Bot Started!")
    await idle()

if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(run())