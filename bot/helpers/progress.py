import time, psutil

def humanbytes(size):
    if not size: return "0 B"
    try:
        size = float(size)
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024: return f"{size:.2f} {unit}"
            size /= 1024
    except:
        return "0 B"

def get_progress_bar(percent):
    try:
        percent = float(percent)
        done = int(percent / 10)
        # Ensuring bar doesn't exceed 10 or go below 0
        done = max(0, min(10, done))
        return f"{'✦' * done}{'✧' * (10 - done)}"
    except:
        return "✧✧✧✧✧✧✧✧✧✧"

async def get_status_msg(ACTIVE_TASKS):
    if not ACTIVE_TASKS:
        return "✨ **No active tasks currently!**"
    
    msg = ""
    for tid, t in ACTIVE_TASKS.items():
        try:
            # Safe calculation for aria2c/m3u8 fragments
            curr = t.get('curr', 0)
            total = t.get('total', 1) # Avoid division by zero
            
            if total > 0:
                percent = (curr * 100 / total)
            else:
                percent = 0
                
            # Formatting ETA and Speed safely
            speed = t.get('speed', '0B/s')
            eta = t.get('eta', 'N/A')
            status = t.get('status', 'Downloading')
            
            elapsed_time = time.time() - t.get('start_time', time.time())
            elapsed_str = time.strftime('%M:%S', time.gmtime(elapsed_time))
            
            msg += f"📦 `{t.get('name', 'Initializing...')}`\n"
            msg += f"┃ 〖{get_progress_bar(percent)}〗 {percent:.2f}%\n"
            msg += f"┠ Processed: {humanbytes(curr)} of {humanbytes(total)}\n"
            msg += f"┠ Status: {status}\n"
            msg += f"┠ Speed: {speed} | ETA: {eta}\n"
            msg += f"┠ Elapsed: {elapsed_str} | Engine: yt-dlp Pro\n"
            msg += f"┠ User: {t.get('user_name', 'User')} | ID: `{t.get('user_id', '0')}`\n"
            msg += f"┖ /cancel_{tid}\n\n"
        except Exception as e:
            msg += f"⚠️ **Task Error:** `{tid}`\n\n"
            continue

    return msg
