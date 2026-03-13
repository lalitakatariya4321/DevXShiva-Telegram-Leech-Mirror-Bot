FROM python:3.10-slim

# Aria2, FFmpeg, aur P7Zip install kiye gaye hain fastest speed ke liye
RUN apt-get update && apt-get install -y \
    ffmpeg \
    aria2 \
    p7zip-full \
    p7zip-rar \
    curl \
    --no-install-recommends && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Sabse pehle requirements copy karein taaki build fast ho (Caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Baaki saara code copy karein
COPY . .

# Bot run karne ke liye
CMD ["python", "main.py"]
