from pyrogram.errors import UserNotParticipant
from bot.config import Config

async def check_fsub(client, message):
    if not Config.FSUB_CHANNEL:
        return True
    try:
        user = await client.get_chat_member(Config.FSUB_CHANNEL, message.from_user.id)
        if user.status == "kicked":
            await message.reply("You are banned from using this bot.")
            return False
        return True
    except UserNotParticipant:
        await message.reply(f"❌ **Access Denied!**\nJoin @{Config.FSUB_CHANNEL} to use this bot.")
        return False
    except Exception:

        return True
