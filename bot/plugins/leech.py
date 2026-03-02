import os, asyncio, yt_dlp, time, shutil, aiohttp, subprocess, re
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

# --- STATUS UPDATER ---
async def status_updater(msg, tid):
    while tid in ACTIVE_TASKS:
        if tid in STOP_TASKS: break
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

# --- CANCEL COMMAND HANDLER ---
@Client.on_message(filters.command("cancel"))
async def cancel_cmd(client, message):
    if len(message.command) < 2:
        return await message.reply("❌ **Usage:** `/cancel TaskID`")
    tid = message.command[1]
    if tid in ACTIVE_TASKS:
        STOP_TASKS.append(tid)
        await message.reply(f"🛑 **Task** `{tid}` **will be stopped shortly.**")
    else:
        await message.reply("❌ **Invalid Task ID or Task not found.**")

# --- FILE PROCESSORS (SPLIT/MERGE/EXTRACT) ---
async def split_file(file_path, tid):
    ACTIVE_TASKS[tid]['status'] = "Splitting..."
    base_name = os.path.basename(file_path)
    dir_name = os.path.dirname(file_path)
    split_size = f"{int(MAX_SIZE)}b"
    output_7z = f"{file_path}.7z"
    cmd = ["7z", "a", f"-v{split_size}", "-mx0", output_7z, file_path]
    process = await asyncio.create_subprocess_exec(*cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    await process.communicate()
    if os.path.exists(file_path): os.remove(file_path)
    return sorted([os.path.join(dir_name, f) for f in os.listdir(dir_name) if f.startswith(base_name + ".7z")])

async def extract_zip_only(d_path, tid):
    """Episode-wise Extraction: Jab user -e use kare."""
    ACTIVE_TASKS[tid]['status'] = "Unzipping Episodes..."
    zip_extensions = ('.zip', '.7z', '.rar', '.001')
    zip_files = [f for f in os.listdir(d_path) if f.lower().endswith(zip_extensions)]
    if not zip_files: return False
    for f in zip_files:
        file_path = os.path.join(d_path, f)
        cmd = ["7z", "x", file_path, f"-o{d_path}", "-y"]
        process = await asyncio.create_subprocess_exec(*cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        await process.communicate()
        if os.path.exists(file_path): os.remove(file_path)
    return True

async def extract_and_merge(d_path, tid, user_id):
    """Smart Merge: Agar Media mode hai toh extract karke merge karega."""
    upload_mode = await db.get_upload_mode(user_id) or "Media"
    
    # Check for zip/split files
    zip_files = sorted([f for f in os.listdir(d_path) if f.lower().endswith(('.zip', '.7z', '.rar', '.001'))])
    if not zip_files: return False

    # Agar mode Document hai, toh sirf split parts ko merge karo, unzip mat karo
    if upload_mode == "Document":
        split_parts = [f for f in zip_files if re.search(r'\.\d{3}$', f)]
        if not split_parts: return False
        ACTIVE_TASKS[tid]['status'] = "Merging Parts..."
        cmd = ["7z", "e", os.path.join(d_path, split_parts[0]), f"-o{d_path}", "-y"]
        await (await asyncio.create_subprocess_exec(*cmd)).communicate()
        for f in split_parts: os.remove(os.path.join(d_path, f))
        return True

    # AGAR MODE MEDIA HAI: Videos merge karke single file banayega
    ACTIVE_TASKS[tid]['status'] = "Extracting Videos..."
    for f in zip_files:
        cmd = ["7z", "x", os.path.join(d_path, f), f"-o{d_path}", "-y"]
        await (await asyncio.create_subprocess_exec(*cmd)).communicate()
        os.remove(os.path.join(d_path, f))

    video_files = []
    for root, dirs, files in os.walk(d_path):
        for file in files:
            if file.lower().endswith((".mp4", ".mkv", ".mov", ".webm")):
                video_files.append(os.path.join(root, file))
    video_files.sort()

    if len(video_files) > 1:
        ACTIVE_TASKS[tid]['status'] = "Merging into One..."
        list_file = os.path.join(d_path, "list.txt")
        output_name = "Merged_Video.mkv"
        with open(list_file, "w") as f:
            for v in video_files: f.write(f"file '{os.path.abspath(v)}'\n")
        
        m_cmd = ["ffmpeg", "-f", "concat", "-safe", "0", "-i", list_file, "-c", "copy", os.path.join(d_path, output_name), "-y"]
        await (await asyncio.create_subprocess_exec(*m_cmd)).communicate()
        
        for v in video_files: os.remove(v)
        os.remove(list_file)
    return True

# --- UPLOAD LOGIC ---
async def common_upload_logic(client, message, tid, file_path, name, is_video, status_msg):
    user_id = message.from_user.id
    d_path = os.path.dirname(file_path)
    if os.path.getsize(file_path) > MAX_SIZE:
        files_to_upload = await split_file(file_path, tid)
    else:
        files_to_upload = [file_path]
    
    total_parts = len(files_to_upload)
    upload_mode = await db.get_upload_mode(user_id) or "Media"
    custom_thumb = await db.get_thumb(user_id)

    for i, path in enumerate(files_to_upload):
        if tid in STOP_TASKS: break
        clean_name = os.path.basename(path).replace(".7z", "")
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
        
        caption = f"✅ **Leeched:** `{clean_name}`{part_info}\n\n👤 **Requested by:** {message.from_user.mention}"
        try:
            if upload_mode == "Media" and is_video:
                sent = await client.send_video(chat_id=user_id, video=path, thumb=ph_path, caption=caption, supports_streaming=True, progress=up_prog)
            else:
                sent = await client.send_document(chat_id=user_id, document=path, thumb=ph_path, caption=caption, file_name=clean_name, progress=up_prog)
            try: await sent.copy(Config.DUMP_CHAT_ID)
            except: pass
        except Exception: pass
        finally:
            if ph_path and os.path.exists(ph_path): os.remove(ph_path)
            if os.path.exists(path): os.remove(path)

# --- ENGINE 1: YT-DLP ---
async def leech_logic(client, message, tid, url, name, is_extract=False):
    async with semaphore:
        d_path = f"downloads/{tid}/"
        os.makedirs(d_path, exist_ok=True)
        user_id = message.from_user.id
        ACTIVE_TASKS[tid] = {'name': name, 'curr': 0, 'total': 1, 'status': 'Downloading', 'speed': '0B/s', 'eta': 'N/A', 'start_time': time.time(), 'user_name': message.from_user.first_name, 'user_id': user_id}
        await db.add_task(tid, user_id, name)
        status_msg = await client.send_message(message.chat.id, "⏳ Initializing YT Leech...")
        updater_task = asyncio.create_task(status_updater(status_msg, tid))

        def ytdl_hook(d):
            if tid in STOP_TASKS: raise Exception("Cancelled")
            if d['status'] == 'downloading':
                ACTIVE_TASKS[tid].update({'curr': d.get('downloaded_bytes', 0), 'total': d.get('total_bytes') or d.get('total_bytes_estimate', 1), 'speed': d.get('_speed_str', '0B/s'), 'eta': d.get('_eta_str', 'N/A')})

        try:
            ydl_opts = {'format': 'best', 'outtmpl': f'{d_path}%(title)s.%(ext)s', 'progress_hooks': [ytdl_hook], 'quiet': True}
            with yt_dlp.YoutubeDL(ydl_opts) as ydl: ydl.extract_info(url, download=True)
            
            if is_extract: await extract_zip_only(d_path, tid)
            else: await extract_and_merge(d_path, tid, user_id)
            
            all_files = []
            for root, dirs, files in os.walk(d_path):
                for file in files:
                    if not file.startswith("."): all_files.append(os.path.join(root, file))

            for path in sorted(all_files):
                if tid in STOP_TASKS: break
                is_vid = path.lower().endswith((".mp4", ".mkv", ".mov", ".webm"))
                await common_upload_logic(client, message, tid, path, os.path.basename(path), is_vid, status_msg)
            
            await db.increment_task_stat(user_id)
            await status_msg.edit_text(f"✅ {message.from_user.mention}, **Leech Done!**")
        except Exception as e: await status_msg.edit_text(f"❌ **Error:** `{str(e)}`")
        finally:
            updater_task.cancel()
            ACTIVE_TASKS.pop(tid, None)
            if tid in STOP_TASKS: STOP_TASKS.remove(tid)
            shutil.rmtree(d_path, ignore_errors=True); await db.rm_task(tid)

# --- ENGINE 2: DIRECT & G-DRIVE ---
async def direct_download_logic(client, message, tid, url, name, is_extract):
    async with semaphore:
        d_path = f"downloads/{tid}/"
        os.makedirs(d_path, exist_ok=True)
        user_id = message.from_user.id
        ACTIVE_TASKS[tid] = {'name': name if name != "default" else "Initializing...", 'curr': 0, 'total': 1, 'status': 'Downloading...', 'speed': '0B/s', 'eta': 'N/A', 'start_time': time.time(), 'user_name': message.from_user.first_name, 'user_id': user_id}
        await db.add_task(tid, user_id, name)
        status_msg = await client.send_message(message.chat.id, "⏳ Initializing...")
        updater_task = asyncio.create_task(status_updater(status_msg, tid))

        try:
            if "drive.google.com" in url:
                ACTIVE_TASKS[tid]['status'] = "G-Drive Syncing..."
                cmd = ["gdown", "--cookie", "cookies.txt", "-O", d_path, "--folder", url] if "folders" in url else ["gdown", "--cookie", "cookies.txt", "-O", d_path, url]
                await (await asyncio.create_subprocess_exec(*cmd)).communicate()
            else:
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, timeout=None) as response:
                        if response.status != 200: raise Exception(f"HTTP {response.status}")
                        total_size = int(response.headers.get('content-length', 0))
                        ACTIVE_TASKS[tid]['total'] = total_size
                        if name == "default":
                            cd = response.headers.get("Content-Disposition")
                            name = cd.split("filename=")[1].strip('"') if cd and "filename=" in cd else url.split("/")[-1].split("?")[0] or "file"
                        
                        file_path = os.path.join(d_path, name)
                        with open(file_path, 'wb') as f:
                            dl = 0; start = time.time()
                            async for chunk in response.content.iter_chunked(1024*1024):
                                if tid in STOP_TASKS: raise Exception("Cancelled")
                                f.write(chunk); dl += len(chunk)
                                elapsed = time.time() - start
                                speed = dl / elapsed if elapsed > 0 else 0
                                ACTIVE_TASKS[tid].update({'curr': dl, 'speed': f"{speed/1024/1024:.2f} MB/s", 'eta': get_readable_time((total_size-dl)/speed) if speed > 0 else "N/A"})

            if is_extract: await extract_zip_only(d_path, tid)
            else: await extract_and_merge(d_path, tid, user_id)

            all_files = []
            for root, dirs, files in os.walk(d_path):
                for file in files:
                    if not file.startswith("."): all_files.append(os.path.join(root, file))

            for path in sorted(all_files):
                if tid in STOP_TASKS: break
                is_vid = os.path.basename(path).lower().endswith((".mp4", ".mkv", ".mov", ".webm"))
                await common_upload_logic(client, message, tid, path, os.path.basename(path), is_vid, status_msg)

            await db.increment_task_stat(user_id)
            await status_msg.edit_text(f"✅ {message.from_user.mention}, **Leech Done!**")
        except Exception as e: await status_msg.edit_text(f"❌ **Error:** `{str(e)}`")
        finally:
            updater_task.cancel()
            ACTIVE_TASKS.pop(tid, None)
            if tid in STOP_TASKS: STOP_TASKS.remove(tid)
            shutil.rmtree(d_path, ignore_errors=True); await db.rm_task(tid)

# --- STATUS COMMAND ---
@Client.on_message(filters.command("status"))
async def status_cmd(client, message):
    if not ACTIVE_TASKS: return await message.reply_text("❌ **No active tasks!**")
    status_text = await get_status_msg(ACTIVE_TASKS)
    await message.reply_text(status_text)
