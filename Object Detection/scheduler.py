import os
import time
import hmac
import hashlib
import requests
from datetime import datetime

VIDEO_DIR = "videos"
UPLOAD_URL = "https://yourserver.com/upload"
HMAC_KEY = b"your_hmac_secret_key"

def generate_hmac_signature(filename, timestamp):
    message = f"{filename}{timestamp}".encode()
    return hmac.new(HMAC_KEY, message, hashlib.sha256).hexdigest()

def is_upload_time():
    now = datetime.now()
    return 23 <= now.hour or now.hour < 4  # 23:00 - 04:00

def upload_video(file_path):
    filename = os.path.basename(file_path)
    timestamp = str(int(time.time()))
    signature = generate_hmac_signature(filename, timestamp)

    files = {'file': open(file_path, 'rb')}
    data = {
        'timestamp': timestamp,
        'signature': signature,
        'filename': filename
    }

    try:
        response = requests.post(UPLOAD_URL, files=files, data=data)
        return response.status_code == 200
    except Exception as e:
        print(f"[ERROR] Upload failed: {e}")
        return False

def clean_empty_folders(root):
    for dirpath, dirnames, filenames in os.walk(root, topdown=False):
        if not filenames and not dirnames:
            os.rmdir(dirpath)

def scan_and_upload():
    for root, dirs, files in os.walk(VIDEO_DIR):
        for file in files:
            if file.endswith('.avi'):
                full_path = os.path.join(root, file)
                print(f"[INFO] Uploading {full_path}")
                if upload_video(full_path):
                    os.remove(full_path)
                    print(f"[INFO] Deleted {full_path}")
    clean_empty_folders(VIDEO_DIR)

if __name__ == "__main__":
    while True:
        if is_upload_time():
            print(f"[INFO] Uploading at {datetime.now()}")
            scan_and_upload()
        else:
            print(f"[INFO] Not in upload window: {datetime.now().strftime('%H:%M:%S')}")
        time.sleep(60)
