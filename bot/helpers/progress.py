import time, psutil

def humanbytes(size):
    if not size: return "0 B"
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size < 1024: return f"{size:.2f}{unit}"
        size /= 1024

def get_progress_bar(percent):
    done = int(percent / 10)
    return f"{'✦' * done}{'✧' * (10 - done)}"

async def get_status_msg(ACTIVE_TASKS):
    if not ACTIVE_TASKS:
        return "✨ **No active tasks currently!**"
    
    msg = ""
    for tid, t in ACTIVE_TASKS.items():
        percent = (t['curr'] * 100 / t['total']) if t['total'] > 0 else 0
        elapsed = time.time() - t['start_time']
        
        msg += f"📦 `{t['name']}`\n"
        msg += f"┃ 〖{get_progress_bar(percent)}〗 {percent:.2f}%\n"
        msg += f"┠ Processed: {humanbytes(t['curr'])} of {humanbytes(t['total'])}\n"
        msg += f"┠ Status: {t['status']}\n"
        msg += f"┠ Speed: {t['speed']} | Elapsed: {time.strftime('%M:%S', time.gmtime(elapsed))}\n"
        msg += f"┠ Engine: yt-dlp Pro\n"
        msg += f"┠ User: {t['user_name']} | ID: {t['user_id']}\n"
        msg += f"┖ /cancel_{tid}\n\n"

    return msg

