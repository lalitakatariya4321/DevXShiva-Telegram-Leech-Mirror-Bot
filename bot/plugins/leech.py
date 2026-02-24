import os, asyncio, yt_dlp, time, shutil, aiohttp
from pyrogram import Client, filters
from bot.config import Config
from bot.helpers.ffmpeg import generate_thumbnail
from bot.helpers.database import db
from bot.helpers.progress import get_status_msg 

# Global Tasks Tracking
ACTIVE_TASKS = {}
STOP_TASKS = []
semaphore = asyncio.Semaphore(5)

async def status_updater(msg, tid):
    """Background task jo message ko har 4-5 second mein edit karega."""
    while tid in ACTIVE_TASKS:
        try:
            status_text = await get_status_msg({tid: ACTIVE_TASKS[tid]})
            await msg.edit_text(status_text)
            await asyncio.sleep(4) 
        except Exception:
            await asyncio.sleep(4)
            continue

# --- Helpers for Progress ---
def get_readable_time(seconds):
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    if h > 0: return f"{h}h {m}m {s}s"
    return f"{m}m {s}s"

# --- ENGINE 1: yt-dlp (For Social Media / YT Links) ---
async def leech_logic(client, message, tid, url, name):
    async with semaphore:
        d_path = f"downloads/{tid}/"
        os.makedirs(d_path, exist_ok=True)
        user_id = message.from_user.id
        group_id = message.chat.id
        
        ACTIVE_TASKS[tid] = {
            'name': name, 'curr': 0, 'total': 1, 'status': 'Downloading', 
            'speed': '0B/s', 'eta': 'N/A', 'start_time': time.time(),
            'user_name': message.from_user.first_name, 'user_id': user_id
        }
        await db.add_task(tid, user_id, name)
        status_msg = await client.send_message(group_id, "⏳ Initializing yt-dlp...")
        updater_task = asyncio.create_task(status_updater(status_msg, tid))

        def check_cancel(d):
            if tid in STOP_TASKS: raise Exception("Task Cancelled")

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
            ydl_opts = {'format': 'best', 'outtmpl': f'{d_path}%(title)s.%(ext)s', 'progress_hooks': [ytdl_hook], 'quiet': True}
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                file_path = ydl.prepare_filename(info)
                if name != "default":
                    ext = os.path.splitext(file_path)[1]
                    new_path = os.path.join(d_path, f"{name}{ext}")
                    os.rename(file_path, new_path); file_path = new_path

            # Upload Phase
            ACTIVE_TASKS[tid]['status'] = "Uploading to PM"
            thumb = generate_thumbnail(file_path, f"{d_path}thumb.jpg")
            async def up_prog(c, t):
                if tid in STOP_TASKS: client.stop_transmission()
                ACTIVE_TASKS[tid].update({'curr': c, 'total': t})

            sent = await client.send_video(chat_id=user_id, video=file_path, thumb=thumb,
                                          caption=f"✅ **Leeched:** `{os.path.basename(file_path)}`", progress=up_prog)
            try: await sent.copy(Config.DUMP_CHAT_ID, caption=f"👤 {message.from_user.mention}\n🔗 {url}")
            except: pass
            await db.increment_task_stat(user_id)
            await status_msg.edit_text(f"✅ {message.from_user.mention}, **Leech Done!** Check PM.")

        except Exception as e:
            await status_msg.edit_text(f"❌ **Error:** `{str(e)}`")
        finally:
            updater_task.cancel()
            await asyncio.sleep(10); await status_msg.delete()
            ACTIVE_TASKS.pop(tid, None)
            if tid in STOP_TASKS: STOP_TASKS.remove(tid)
            shutil.rmtree(d_path, ignore_errors=True); await db.rm_task(tid)

# --- ENGINE 2: Direct Leech (For Direct Download Links) ---
async def direct_download_logic(client, message, tid, url, name):
    async with semaphore:
        d_path = f"downloads/{tid}/"
        os.makedirs(d_path, exist_ok=True)
        user_id = message.from_user.id
        group_id = message.chat.id

        ACTIVE_TASKS[tid] = {
            'name': name if name != "default" else "Direct File",
            'curr': 0, 'total': 1, 'status': 'Downloading (Direct)',
            'speed': '0B/s', 'eta': 'N/A', 'start_time': time.time(),
            'user_name': message.from_user.first_name, 'user_id': user_id
        }
        await db.add_task(tid, user_id, name)
        status_msg = await client.send_message(group_id, "⏳ Initializing Direct Download...")
        updater_task = asyncio.create_task(status_updater(status_msg, tid))

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=None) as response:
                    if response.status != 200: raise Exception(f"HTTP Status {response.status}")
                    
                    if name == "default":
                        cd = response.headers.get("Content-Disposition")
                        name = cd.split("filename=")[1].strip('"') if cd and "filename=" in cd else url.split("/")[-1].split("?")[0] or "file"
                    
                    file_path = os.path.join(d_path, name)
                    total_size = int(response.headers.get('content-length', 0))
                    ACTIVE_TASKS[tid]['total'] = total_size

                    with open(file_path, 'wb') as f:
                        dl = 0; start = time.time()
                        async for chunk in response.content.iter_chunked(1024*1024):
                            if tid in STOP_TASKS: raise Exception("Task Cancelled")
                            f.write(chunk); dl += len(chunk)
                            elapsed = time.time() - start
                            speed = dl / elapsed if elapsed > 0 else 0
                            ACTIVE_TASKS[tid].update({
                                'curr': dl, 'speed': f"{speed/1024/1024:.2f} MB/s",
                                'eta': get_readable_time((total_size-dl)/speed) if speed > 0 else "N/A"
                            })

            # Upload Direct File
            ACTIVE_TASKS[tid]['status'] = "Uploading to PM"
            async def up_prog(c, t):
                if tid in STOP_TASKS: client.stop_transmission()
                ACTIVE_TASKS[tid].update({'curr': c, 'total': t})

            # Check if video or document
            is_video = name.lower().endswith((".mp4", ".mkv", ".mov", ".webm"))
            if is_video:
                thumb = generate_thumbnail(file_path, f"{d_path}thumb.jpg")
                sent = await client.send_video(chat_id=user_id, video=file_path, thumb=thumb, caption=f"✅ **Leeched:** `{name}`", progress=up_prog)
            else:
                sent = await client.send_document(chat_id=user_id, document=file_path, caption=f"✅ **Leeched:** `{name}`", progress=up_prog)
            
            try: await sent.copy(Config.DUMP_CHAT_ID)
            except: pass
            await db.increment_task_stat(user_id)
            await status_msg.edit_text(f"✅ {message.from_user.mention}, **Direct Leech Done!**")

        except Exception as e:
            await status_msg.edit_text(f"❌ **Error:** `{str(e)}`")
        finally:
            updater_task.cancel()
            await asyncio.sleep(10); await status_msg.delete()
            ACTIVE_TASKS.pop(tid, None)
            if tid in STOP_TASKS: STOP_TASKS.remove(tid)
            shutil.rmtree(d_path, ignore_errors=True); await db.rm_task(tid)
