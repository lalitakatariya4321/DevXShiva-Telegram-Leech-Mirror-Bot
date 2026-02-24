import os, subprocess

def generate_thumbnail(video_path, thumb_path):
    try:
        subprocess.call(['ffmpeg', '-i', video_path, '-ss', '00:00:02.000', '-vframes', '1', '-update', '1', thumb_path, '-y'])
        return thumb_path if os.path.exists(thumb_path) else None
    except:
        return None