from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from bot.config import Config
from bot.helpers.database import db
from bot.helpers.fsub import check_fsub

@Client.on_message(filters.command("start"))
async def start_handler(client, message):
    # Database mein user add karna
    await db.add_user(message.from_user.id, message.from_user.first_name)
    
    # FSub Check
    if not await check_fsub(client, message):
        return

    welcome_text = (
        f"👋 **Hello {message.from_user.first_name}!**\n\n"
        "I am a **Professional Mirror-Leech Bot**.\n"
        "I can download files from links and upload them to Telegram.\n\n"
        "✨ **Features:**\n"
        "┠ Real-time Progress Bar\n"
        "┠ Custom Renaming Support\n"
        "┠ Queue System (Max 5 Tasks)\n"
        "┖ Dump Channel Backup"
    )
    
    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("Help & Commands", callback_data="help_cmd")],
        [InlineKeyboardButton("Developer", url=f"tg://user?id={Config.OWNER_ID}")]
    ])
    
    await message.reply_text(welcome_text, reply_markup=buttons)

@Client.on_message(filters.command("help"))
async def help_handler(client, message):
    help_text = (
        "📖 **How to Use Me:**\n\n"
        "1️⃣ **Simple Leech:**\n"
        "`/yt https://link.com` - Direct link download.\n\n"
        "2️⃣ **Rename Leech:**\n"
        "`/yt -n My_Video https://link.com` - Download with custom name.\n\n"
        "3️⃣ **Status:**\n"
        "`/status` - Check all active tasks & server load.\n\n"
        "4️⃣ **Cancel:**\n"
        "Use the `/cancel_taskid` link generated in the status message."
    )
    await message.reply_text(help_text)