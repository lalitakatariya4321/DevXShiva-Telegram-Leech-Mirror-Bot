import asyncio, threading, time
from pyrogram import Client, filters, idle, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from bot.config import Config
from bot.helpers.fsub import check_fsub
from bot.helpers.database import db
from bot.plugins.leech import leech_logic, direct_download_logic, ACTIVE_TASKS, STOP_TASKS
from bot.helpers.progress import get_status_msg
from flask import Flask

app = Client("leech_bot", Config.API_ID, Config.API_HASH, bot_token=Config.BOT_TOKEN)
web_app = Flask(__name__)

# --- CONFIGURATION ---
START_IMG = "LOGO.png" # Apna Image URL yahan dalein
LOG_CHANNEL = -1002686058050 # Apna Log Channel ID yahan dalein

@web_app.route('/')
def home(): return "Alive", 200

# --- UI HELPERS ---
def get_start_buttons():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("Settings ⚙️", callback_data="settings_menu"),
            InlineKeyboardButton("Help 🛠️", callback_data="help")
        ],
        [InlineKeyboardButton("Toggle Mode: Media/File 📂", callback_data="toggle_mode")]
    ])

# --- LOG SYSTEM ---
async def send_log(c, text):
    if LOG_CHANNEL:
        try: await c.send_message(LOG_CHANNEL, text)
        except: pass

# --- LIMIT CHECKS ---
async def can_start_task(c, m):
    if not await check_fsub(c, m): return False
    if len(ACTIVE_TASKS) >= 5:
        await m.reply_text("⚠️ **Bot Overloaded!**")
        return False
    u_tasks = [t for t in ACTIVE_TASKS.values() if t['user_id'] == m.from_user.id]
    if len(u_tasks) >= 2: 
        await m.reply("❌ **Limit Exceeded!**")
        return False
    return True

# --- START COMMAND ---
@app.on_message(filters.command("start") & filters.private)
async def start_msg(c, m):
    if not await check_fsub(c, m): return
    
    # User Logging
    if not await db.is_user_exist(m.from_user.id):
        await db.add_user(m.from_user.id, m.from_user.first_name)
        await send_log(c, f"🆕 **New User Started Bot**\n👤 {m.from_user.mention}\n🆔 `{m.from_user.id}`")

    welcome_text = (
        f"<b>👋 Hi {m.from_user.mention}!</b>\n\n"
        "I am a powerful **Pro Leech Bot**.\n\n"
        "🚀 **Commands:**\n"
        "• `/yt URL -n Name` : Social Media Leech\n"
        "• `/l URL -n Name` : Direct Link Leech\n"
        "• `/status` : Check Tasks"
    )
    await m.reply_photo(photo=START_IMG, caption=welcome_text, reply_markup=get_start_buttons())

# --- CALLBACK HANDLER (Edit Only Logic) ---
@app.on_callback_query()
async def cb_handler(c, query):
    user_id = query.from_user.id
    
    if query.data == "settings_menu":
        mode = await db.get_upload_mode(user_id) or "Media"
        thumb = await db.get_thumb(user_id)
        thumb_status = "✅ Set" if thumb else "❌ Not Set"
        
        settings_text = (
            f"<b>⚙️ Bot Configuration</b>\n\n"
            f"<b>Upload Mode:</b> <code>{mode}</code>\n"
            f"<b>Custom Thumb:</b> <code>{thumb_status}</code>\n\n"
            "• /set_thumb : Reply to photo\n"
            "• /del_thumb : Clear thumb"
        )
        await query.message.edit_caption(caption=settings_text, reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("Back 🔙", callback_data="back_start")]
        ]))

    elif query.data == "toggle_mode":
        curr = await db.get_upload_mode(user_id) or "Media"
        new = "Document" if curr == "Media" else "Media"
        await db.set_upload_mode(user_id, new)
        await query.answer(f"✅ Mode: {new}", show_alert=True)
        # Re-trigger settings menu to show updated mode
        query.data = "settings_menu"
        await cb_handler(c, query)

    elif query.data == "back_start":
        welcome_text = (
            f"<b>👋 Hi {query.from_user.mention}!</b>\n\n"
            "I am a powerful **Pro Leech Bot**.\n\n"
            "🚀 **Commands:**\n"
            "• `/yt URL -n Name` : Social Media Leech\n"
            "• `/l URL -n Name` : Direct Link Leech\n"
        )
        await query.message.edit_caption(caption=welcome_text, reply_markup=get_start_buttons())

    elif query.data == "help":
        await query.message.edit_caption(
            caption="<b>🛠 Help Menu</b>\n\nUse `/yt` or `/l` with `-n` for custom name.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Back 🔙", callback_data="back_start")]])
        )

# --- ADMIN COMMANDS ---
@app.on_message(filters.command("stats") & filters.user(Config.ADMINS))
async def stats_cmd(c, m):
    total = await db.total_users_count()
    await m.reply_text(f"📊 **Total Users:** `{total}`")

@app.on_message(filters.command("broadcast") & filters.user(Config.ADMINS))
async def broadcast_handler(c, m):
    if not m.reply_to_message: return await m.reply("Reply to a message.")
    users = await db.get_all_users()
    count = 0
    async for user in users:
        try:
            await m.reply_to_message.copy(user['id'])
            count += 1
        except: pass
    await m.reply(f"✅ Broadcast Done! Sent to `{count}` users.")

# --- LEECH COMMANDS ---
@app.on_message(filters.command("yt"))
async def yt_cmd(c, m):
    if not await can_start_task(c, m): return
    parts = m.text.split(None, 1)
    if len(parts) < 2: return await m.reply("❌ Provide URL")
    
    raw = parts[1]
    name, url = ("default", raw.split("-n ")[0].strip()) if "-n " not in raw else (raw.split("-n ")[1].strip(), raw.split("-n ")[0].strip())
    
    tid = str(int(time.time()))
    await send_log(c, f"🎬 **YT Leech Started**\n👤 {m.from_user.first_name}\n🔗 {url}")
    asyncio.create_task(leech_logic(c, m, tid, url, name))

@app.on_message(filters.command("l"))
async def direct_cmd(c, m):
    if not await can_start_task(c, m): return
    parts = m.text.split(None, 1)
    if len(parts) < 2: return await m.reply("❌ Provide URL")
    
    raw = parts[1]
    name, url = ("default", raw.split("-n ")[0].strip()) if "-n " not in raw else (raw.split("-n ")[1].strip(), raw.split("-n ")[0].strip())
    
    tid = str(int(time.time()))
    await send_log(c, f"🚀 **Direct Leech Started**\n👤 {m.from_user.first_name}\n🔗 {url}")
    asyncio.create_task(direct_download_logic(c, m, tid, url, name))

# --- THUMBNAIL ---
@app.on_message(filters.command("set_thumb") & filters.private)
async def set_thumb_cmd(c, m):
    if m.reply_to_message and m.reply_to_message.photo:
        await db.set_thumb(m.from_user.id, m.reply_to_message.photo.file_id)
        await m.reply("✅ Thumb Saved!")
    else: await m.reply("Reply to a photo.")

@app.on_message(filters.command("del_thumb") & filters.private)
async def del_thumb_cmd(c, m):
    await db.set_thumb(m.from_user.id, None)
    await m.reply("🗑️ Thumb Deleted!")

# --- Runner ---
async def run():
    threading.Thread(target=lambda: web_app.run(host="0.0.0.0", port=10000), daemon=True).start()
    await app.start()
    await idle()

if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(run())


