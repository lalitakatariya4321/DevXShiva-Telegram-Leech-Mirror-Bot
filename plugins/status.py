from pyrogram import Client, filters
from bot.helpers.progress import get_status_msg

# Import ACTIVE_TASKS from main to show real-time data
async def status_handler(client, message, ACTIVE_TASKS):
    status_text = await get_status_msg(ACTIVE_TASKS)
    await message.reply(status_text)