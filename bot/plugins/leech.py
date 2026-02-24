import os, asyncio, yt_dlp, time, shutil
from pyrogram import Client, filters
from bot.config import Config
from bot.helpers.ffmpeg import generate_thumbnail
from bot.helpers.database import db  # Database helper imported

# Global Tasks Tracking
ACTIVE_TASKS = {}
STOP_TASKS = []
semaphore = asyncio.Semaphore(5)

async def leech_logic(client, message, tid, url, name):
    async with semaphore:
        d_path = f"downloads/{tid}/"
        os.makedirs(d_path, exist_ok=True)
        user_id = message.from_user.id
        
        # 1. Task Initialization (Memory & Database)
        ACTIVE_TASKS[tid] = {
            'name': name, 'curr': 0, 'total': 1, 'status': 'Downloading', 
            'speed': '0B/s', 'eta': 'N/A', 'start_time': time.time(),
            'user_name': message.from_user.first_name, 'user_id': user_id
        }
        
        # Task Start: Add to MongoDB Active Tasks
        await db.add_task(tid, user_id, name)

        def check_cancel(d):
            if tid in STOP_TASKS:
                raise Exception("Task Cancelled by User")

        def ytdl_hook(d):
            check_cancel(d)
            if d['status'] == 'downloading':
                ACTIVE_TASKS[tid].update({
                    'curr': d.get('downloaded_bytes', 0),
                    'total': d.get('total_bytes') or d.get('total_bytes_estimate', 1),
                    'speed': d.get('_speed_str', '0B/s'),
                    'eta': d.get('_eta_str', 'N/A')
                })

        try:
            # 2. Downloading Phase
            ydl_opts = {
                'format': 'best', 
                'outtmpl': f'{d_path}%(title)s.%(ext)s', 
                'progress_hooks': [ytdl_hook], 
                'quiet': True
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                file_path = ydl.prepare_filename(info)
                
                if name != "default":
                    ext = os.path.splitext(file_path)[1]
                    new_path = os.path.join(d_path, f"{name}{ext}")
                    os.rename(file_path, new_path)
                    file_path = new_path

            # 3. Uploading Phase
            ACTIVE_TASKS[tid]['status'] = "Uploading"
            thumb = generate_thumbnail(file_path, f"{d_path}thumb.jpg")
            
            async def upload_progress(current, total):
                if tid in STOP_TASKS: 
                    client.stop_transmission()
                ACTIVE_TASKS[tid]['curr'], ACTIVE_TASKS[tid]['total'] = current, total

            # Send to PM
            sent = await client.send_video(
                chat_id=message.chat.id, 
                video=file_path, 
                thumb=thumb,
                caption=f"✅ **Leeched:** `{os.path.basename(file_path)}`",
                progress=upload_progress
            )
            
            # Send to Dump
            await sent.copy(Config.DUMP_CHAT_ID, caption=f"👤 {message.from_user.mention}\n🔗 {url}")

            # 4. Stats: Increment User Task Count on Success
            await db.increment_task_stat(user_id)

        except Exception as e:
            await message.reply(f"❌ **Task Error/Stopped:** `{str(e)}`")
            
        finally:
            # --- AUTO-CLEANUP LAYER (Memory, Disk, DB) ---
            
            # Remove from Global Dict
            ACTIVE_TASKS.pop(tid, None)
            
            # Clear Cancel list
            if tid in STOP_TASKS: 
                STOP_TASKS.remove(tid)
            
            # Delete Local Files
            if os.path.exists(d_path):
                shutil.rmtree(d_path, ignore_errors=True)
            
            # Task Finish/Cancel: Remove from MongoDB Active Tasks
            await db.rm_task(tid)