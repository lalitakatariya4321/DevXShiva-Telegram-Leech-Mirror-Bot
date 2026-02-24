import os, asyncio, yt_dlp, time, shutil, aiohttp, subprocess
from pyrogram import Client, filters, enums
from bot.config import Config
from bot.helpers.ffmpeg import generate_thumbnail
from bot.helpers.database import db
from bot.helpers.progress import get_status_msg 

# Global Settings
MAX_SIZE = 1.9 * 1024 * 1024 * 1024 # 1.9GB
ACTIVE_TASKS = {}
STOP_TASKS = []
semaphore = asyncio.Semaphore(5)

async def status_updater(msg, tid):
    while tid in ACTIVE_TASKS:
        try:
            status_text = await get_status_msg({tid: ACTIVE_TASKS[tid]})
            await msg.edit_text(status_text)
            await asyncio.sleep(4) 
        except Exception:
            await asyncio.sleep(4)
            continue

def get_readable_time(seconds):
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    if h > 0: return f"{h}h {m}m {s}s"
    return f"{m}m {s}s"

async def split_file(file_path, tid):
    """Badi file ko 7z se split karna aur parts ki list return karna."""
    ACTIVE_TASKS[tid]['status'] = "Splitting File..."
    base_name = os.path.basename(file_path)
    dir_name = os.path.dirname(file_path)
    
    split_size = f"{int(MAX_SIZE)}b"
    output_7z = f"{file_path}.7z"
    cmd = ["7z", "a", f"-v{split_size}", "-mx0", output_7z, file_path]
    
    process = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    await process.communicate()
    
    if os.path.exists(file_path):
        os.remove(file_path)
    
    parts = sorted([
        os.path.join(dir_name, f) 
        for f in os.listdir(dir_name) 
        if f.startswith(base_name + ".7z")
    ])
    return parts

async def common_upload_logic(client, user_id, tid, file_path, name, url, is_video):
    """Media/File toggle, Auto-Thumb aur No 7z extension cleanup logic."""
    d_path = os.path.dirname(file_path)
    
    if os.path.getsize(file_path) > MAX_SIZE:
        files_to_upload = await split_file(file_path, tid)
    else:
        files_to_upload = [file_path]

    total_parts = len(files_to_upload)
    upload_mode = await db.get_upload_mode(user_id) or "Media"
    custom_thumb = await db.get_thumb(user_id)

    for i, path in enumerate(files_to_upload):
        original_name = os.path.basename(path)
        clean_name = original_name.replace(".7z", "")
        
        part_info = f" (Part {i+1}/{total_parts})" if total_parts > 1 else ""
        ACTIVE_TASKS[tid]['status'] = f"Uploading{part_info}"
        
        async def up_prog(c, t):
            if tid in STOP_TASKS: client.stop_transmission()
            ACTIVE_TASKS[tid].update({'curr': c, 'total': t})

        ph_path = None
        if custom_thumb:
            try: ph_path = await client.download_media(custom_thumb)
            except: ph_path = None
        
        if not ph_path and is_video:
            ph_path = generate_thumbnail(path, f"{d_path}/thumb_{i}.jpg")

        caption = f"✅ **Leeched:** `{clean_name}`{part_info}"
        
        try:
            if upload_mode == "Media" and is_video:
                sent = await client.send_video(
                    chat_id=user_id, video=path, thumb=ph_path, 
                    caption=caption, file_name=clean_name, 
                    supports_streaming=True, progress=up_prog
                )
            else:
                sent = await client.send_document(
                    chat_id=user_id, document=path, thumb=ph_path, 
                    caption=caption, file_name=clean_name, progress=up_prog
                )
            
            try: await sent.copy(Config.DUMP_CHAT_ID)
            except: pass
            
        except Exception as e:
            print(f"Upload Error: {e}")
        finally:
            if ph_path and os.path.exists(ph_path):
                os.remove(ph_path)

# --- ENGINE 1: yt-dlp ---
# FIX: Arguments updated to match main.py
async def leech_logic(client, message, tid, url, name):
    async with semaphore:
        d_path = f"downloads/{tid}/"
        os.makedirs(d_path, exist_ok=True)
        user_id = message.from_user.id
        
        ACTIVE_TASKS[tid] = {'name': name, 'curr': 0, 'total': 1, 'status': 'Downloading', 
                            'speed': '0B/s', 'eta': 'N/A', 'start_time': time.time(),
                            'user_name': message.from_user.first_name, 'user_id': user_id}
        
        await db.add_task(tid, user_id, name)
        status_msg = await client.send_message(message.chat.id, "⏳ Initializing yt-dlp...")
        updater_task = asyncio.create_task(status_updater(status_msg, tid))

        try:
            ydl_opts = {
                'format': 'best', 
                'outtmpl': f'{d_path}%(title)s.%(ext)s', 
                'progress_hooks': [lambda d: ACTIVE_TASKS[tid].update({
                    'curr': d.get('downloaded_bytes', 0),
                    'total': d.get('total_bytes') or d.get('total_bytes_estimate', 1),
                    'speed': d.get('_speed_str', '0B/s'), 'eta': d.get('_eta_str', 'N/A')
                }) if d['status'] == 'downloading' else None], 
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

            await common_upload_logic(client, user_id, tid, file_path, name, url, is_video=True)
            await db.increment_task_stat(user_id)
            await status_msg.edit_text(f"✅ {message.from_user.mention}, **Leech Done!**")

        except Exception as e:
            await status_msg.edit_text(f"❌ **Error:** `{str(e)}`")
        finally:
            updater_task.cancel()
            await asyncio.sleep(5); await status_msg.delete()
            ACTIVE_TASKS.pop(tid, None)
            shutil.rmtree(d_path, ignore_errors=True); await db.rm_task(tid)

# --- ENGINE 2: Direct Leech ---
# FIX: Arguments updated to match main.py
async def direct_download_logic(client, message, tid, url, name):
    async with semaphore:
        d_path = f"downloads/{tid}/"
        os.makedirs(d_path, exist_ok=True)
        user_id = message.from_user.id

        ACTIVE_TASKS[tid] = {'name': name if name != "default" else "Direct File",
                            'curr': 0, 'total': 1, 'status': 'Downloading (Direct)',
                            'speed': '0B/s', 'eta': 'N/A', 'start_time': time.time(),
                            'user_name': message.from_user.first_name, 'user_id': user_id}
        
        await db.add_task(tid, user_id, name)
        status_msg = await client.send_message(message.chat.id, "⏳ Initializing Direct Download...")
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
                                'curr': dl, 
                                'speed': f"{speed/1024/1024:.2f} MB/s",
                                'eta': get_readable_time((total_size-dl)/speed) if speed > 0 else "N/A"
                            })

            is_vid = name.lower().endswith((".mp4", ".mkv", ".mov", ".webm"))
            await common_upload_logic(client, user_id, tid, file_path, name, url, is_video=is_vid)
            await db.increment_task_stat(user_id)
            await status_msg.edit_text(f"✅ {message.from_user.mention}, **Direct Leech Done!**")

        except Exception as e:
            await status_msg.edit_text(f"❌ **Error:** `{str(e)}`")
        finally:
            updater_task.cancel()
            await asyncio.sleep(5); await status_msg.delete()
            ACTIVE_TASKS.pop(tid, None)
            shutil.rmtree(d_path, ignore_errors=True); await db.rm_task(tid)

# --- STATUS COMMAND ---
@Client.on_message(filters.command("status") & filters.private)
async def status_cmd(client, message):
    if not ACTIVE_TASKS:
        return await message.reply_text("❌ No active tasks!")
    status_text = await get_status_msg(ACTIVE_TASKS)
    await message.reply_text(status_text)
