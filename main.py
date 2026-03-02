import asyncio, threading, time, os
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
START_IMG = "LOGO.png" 
LOG_CHANNEL = Config.LOG_CHANNEL 

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

# --- LIMIT & PM CHECKS ---
async def can_start_task(c, m):
    user_id = m.from_user.id
    if not await check_fsub(c, m): return False
    
    if m.chat.type != enums.ChatType.PRIVATE:
        try:
            await c.send_chat_action(user_id, enums.ChatAction.TYPING)
        except:
            await m.reply_text(
                f"❌ {m.from_user.mention}, please start me in Private first to receive files!",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("Start Bot in PM 🤖", url=f"https://t.me/{(await c.get_me()).username}?start=help")
                ]])
            )
            return False

    if len(ACTIVE_TASKS) >= 5:
        await m.reply_text("⚠️ **Bot Overloaded! Max 5 global tasks.**")
        return False
        
    u_tasks = [t for t in ACTIVE_TASKS.values() if t.get('user_id') == user_id]
    if len(u_tasks) >= 2: 
        await m.reply("❌ **Limit Exceeded! You can run only 2 tasks at a time.**")
        return False
    return True

# --- START COMMAND ---
@app.on_message(filters.command("start"))
async def start_msg(c, m):
    if not await db.is_user_exist(m.from_user.id):
        await db.add_user(m.from_user.id, m.from_user.first_name)
        await send_log(c, f"🆕 **New User Started Bot**\n👤 {m.from_user.mention}\n🆔 `{m.from_user.id}`")

    if not await check_fsub(c, m): return

    welcome_text = (
        f"<b>👋 Hi {m.from_user.mention}!</b>\n\n"
        "I am a powerful **Pro Leech Bot**.\n\n"
        "🚀 **Commands:**\n"
        "• `/yt URL -n Name` : Social Media Leech (Auto-Best)\n"
        "• `/l URL -n Name` : Direct Link Leech (Auto-Merge)\n"
        "• `/l URL -e` : Extract Mode (Episode-wise)\n"
        "• `/user` : Custom Settings & Cookies\n"
        "• `/status` : Check Tasks\n"
        "• `/cancel ID` : Stop Task"
    )
    
    if m.chat.type == enums.ChatType.PRIVATE:
        try:
            await m.reply_photo(photo=START_IMG, caption=welcome_text, reply_markup=get_start_buttons())
        except:
            await m.reply_text(welcome_text, reply_markup=get_start_buttons())
    else:
        await m.reply_text("Bot is alive! Send commands or use me in Private.")

# --- USER SETTINGS DASHBOARD ---
@app.on_message(filters.command("user") & filters.private)
async def user_dashboard(c, m):
    user_id = m.from_user.id
    mode = await db.get_upload_mode(user_id) or "Media"
    thumb = "✅ Set" if await db.get_thumb(user_id) else "❌ Not Set"
    cook = "✅ Set" if await db.get_cookies(user_id) else "❌ Not Set"

    settings_text = (
        f"👤 **User Dashboard: {m.from_user.first_name}**\n\n"
        f"📂 **Upload Mode:** `{mode}`\n"
        f"🖼 **Thumbnail:** `{thumb}`\n"
        f"🍪 **Cookies.txt:** `{cook}`\n\n"
        f"**To update settings:**\n"
        "• Use `/set_thumb` (Reply to photo)\n"
        "• Send a `.txt` file for Cookies"
    )

    buttons = [
        [InlineKeyboardButton(f"Mode: {mode}", callback_data="toggle_mode")],
        [InlineKeyboardButton("Upload Cookies 🍪", callback_data="ask_cookies")],
        [InlineKeyboardButton("Delete Cookies 🗑️", callback_data="del_cookies")]
    ]
    await m.reply(settings_text, reply_markup=InlineKeyboardMarkup(buttons))

# --- CALLBACK HANDLER ---
@app.on_callback_query()
async def cb_handler(c, query):
    user_id = query.from_user.id
    
    # --- AUTO-LEECH: Quality selection callback removed as requested ---

    if query.data == "settings_menu":
        mode = await db.get_upload_mode(user_id) or "Media"
        thumb = await db.get_thumb(user_id)
        cook = await db.get_cookies(user_id)
        thumb_status = "✅ Set" if thumb else "❌ Not Set"
        cook_status = "✅ Set" if cook else "❌ Not Set"
        
        settings_text = (
            f"<b>⚙️ Bot Configuration</b>\n\n"
            f"<b>Upload Mode:</b> <code>{mode}</code>\n"
            f"<b>Custom Thumb:</b> <code>{thumb_status}</code>\n"
            f"<b>Cookies Status:</b> <code>{cook_status}</code>\n\n"
            "• /set_thumb : Reply to photo\n"
            "• Send .txt file for cookies"
        )
        try:
            await query.message.edit_caption(caption=settings_text, reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Toggle Mode 📂", callback_data="toggle_mode")],
                [InlineKeyboardButton("Upload Cookies 🍪", callback_data="ask_cookies")],
                [InlineKeyboardButton("Back 🔙", callback_data="back_start")]
            ]))
        except:
             await query.message.edit_text(text=settings_text, reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Toggle Mode 📂", callback_data="toggle_mode")],
                [InlineKeyboardButton("Upload Cookies 🍪", callback_data="ask_cookies")],
                [InlineKeyboardButton("Back 🔙", callback_data="back_start")]
            ]))

    elif query.data == "toggle_mode":
        curr = await db.get_upload_mode(user_id) or "Media"
        new = "Document" if curr == "Media" else "Media"
        await db.set_upload_mode(user_id, new)
        await query.answer(f"✅ Mode: {new}", show_alert=True)
        query.data = "settings_menu"
        await cb_handler(c, query)

    elif query.data == "ask_cookies":
        await query.message.reply("📂 **Please send your `cookies.txt` file (Netscape format) now.**")
        await query.answer()

    elif query.data == "del_cookies":
        await db.set_cookies(user_id, None)
        await query.answer("🗑️ Cookies Deleted!", show_alert=True)
        query.data = "settings_menu"
        await cb_handler(c, query)

    elif query.data == "back_start":
        welcome_text = (
            f"<b>👋 Hi {query.from_user.mention}!</b>\n\n"
            "I am a powerful **Pro Leech Bot**.\n\n"
            "🚀 **Commands:**\n"
            "• `/yt URL -n Name` : Social Media\n"
            "• `/l URL -n Name` : Direct Link"
        )
        try:
            await query.message.edit_caption(caption=welcome_text, reply_markup=get_start_buttons())
        except:
            await query.message.edit_text(text=welcome_text, reply_markup=get_start_buttons())

    elif query.data == "help":
        help_text = "<b>🛠 Help Menu</b>\n\nUse `/yt` or `/l` with `-n` for custom name.\nUse `-e` with `/l` or `/yt` to skip merging (Episode-wise).\n\nSend `cookies.txt` file to use premium accounts."
        try:
            await query.message.edit_caption(caption=help_text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Back 🔙", callback_data="back_start")]]))
        except:
            await query.message.edit_text(text=help_text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Back 🔙", callback_data="back_start")]]))

# --- COOKIE FILE HANDLER ---
@app.on_message(filters.document & filters.private)
async def handle_docs(c, m):
    if m.document.file_name.endswith(".txt"):
        status = await m.reply("⏳ **Validating Cookies...**")
        file_path = await m.download()
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            
            if "Netscape" in content or "# HTTP Cookie File" in content:
                await db.set_cookies(m.from_user.id, content)
                await status.edit("✅ **Cookies.txt saved successfully!** It will be used for your next `/yt` leech.")
            else:
                await status.edit("❌ **Invalid Format!** Please send a valid Netscape format `cookies.txt`.")
        except Exception as e:
            await status.edit(f"❌ **Error:** `{e}`")
        finally:
            if os.path.exists(file_path): os.remove(file_path)

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
            await m.reply_to_message.copy(user['_id'])
            count += 1
        except: pass
    await m.reply(f"✅ Broadcast Done! Sent to `{count}` users.")

# --- HELPERS: PARSE COMMANDS ---
def parse_args(text):
    is_extract = " -e" in text
    text = text.replace(" -e", "").strip()
    
    name = "default"
    if "-n " in text:
        parts = text.split("-n ")
        url = parts[0].strip()
        name = parts[1].strip()
    else:
        url = text.strip()
    return url, name, is_extract

# --- LEECH COMMANDS (Auto-Start Download) ---
@app.on_message(filters.command(["yt", "ytdl"]))
async def yt_cmd(c, m):
    if not await can_start_task(c, m): return
    if len(m.command) < 2: return await m.reply("❌ **Provide URL**")
    
    url, name, is_extract = parse_args(m.text.split(None, 1)[1])
    tid = str(int(time.time()))
    
    await send_log(c, f"🎬 **YT Leech (Best Qual) Started**\n👤 {m.from_user.first_name}\n🔗 {url}")
    
    # Ye ab buttons nahi dikhayega, seedha leech_logic start karega
    asyncio.create_task(leech_logic(c, m, tid, url, name, is_extract))

@app.on_message(filters.command("l"))
async def direct_cmd(c, m):
    if not await can_start_task(c, m): return
    if len(m.command) < 2: return await m.reply("❌ **Provide URL**")
    
    url, name, is_extract = parse_args(m.text.split(None, 1)[1])
    tid = str(int(time.time()))
    
    log_msg = f"🚀 **Direct/GDrive Started**\n👤 {m.from_user.first_name}\n🔗 {url}\nMode: {'Extract (-e)' if is_extract else 'Default (Merge)'}"
    await send_log(c, log_msg)
    
    asyncio.create_task(direct_download_logic(c, m, tid, url, name, is_extract))

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
    print("Bot Started!")
    await idle()

if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(run())
