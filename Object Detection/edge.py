# kode python streaming, record, dan upload ke gcs dengan real-time people counter MobilenetSSD
from flask import Flask, Response, render_template, jsonify
from flask_cors import CORS
import cv2
import threading
import time
import requests
import os
import psutil
import platform
import subprocess
import socket
import firebase_admin
from firebase_admin import credentials, firestore
import hmac
import hashlib
import numpy as np

app = Flask(__name__)
CORS(app)

camera_lock = threading.Lock()
cap = cv2.VideoCapture(0)

if not cap.isOpened():
    print("[ERROR] Kamera tidak bisa dibuka.")
    exit()

# Konfigurasi
RECORD_DURATION = 10
ONLINE_SLEEP_DURATION = 15
OFFLINE_SLEEP_DURATION = 15
PENDING_FOLDER = "./videos_pending"
os.makedirs(PENDING_FOLDER, exist_ok=True)

SERVER_UPLOAD_URL = "https://pillbox-server-263713026348.asia-southeast2.run.app/videos"

# Secret key HMAC (harus sama dengan yang di server)
SECRET_KEY = b"pillboxpnj234"  # byte string

# Firebase setup
cred = credentials.Certificate("firebase.json")
firebase_admin.initialize_app(cred)
db = firestore.client()

# Load MobileNetSSD model (pastikan path sesuai)
prototxt_path = "models/MobileNetSSD_deploy.prototxt"
model_path = "models/MobileNetSSD_deploy.caffemodel"
net = cv2.dnn.readNetFromCaffe(prototxt_path, model_path)

# COCO classes MobileNetSSD (harus sama dengan model)
CLASSES = ["background", "aeroplane", "bicycle", "bird", "boat",
           "bottle", "bus", "car", "cat", "chair", "cow", "diningtable",
           "dog", "horse", "motorbike", "person", "pottedplant", "sheep",
           "sofa", "train", "tvmonitor"]

def process_frame_with_mobilenetssd(frame):
    """
    Proses satu frame dengan MobileNetSSD untuk deteksi 'person'.
    Mengembalikan frame dengan bounding box yang digambar.
    """
    h, w = frame.shape[:2]
    blob = cv2.dnn.blobFromImage(cv2.resize(frame, (300, 300)), 0.007843, (300, 300), 127.5)
    net.setInput(blob)
    detections = net.forward()

    for i in range(detections.shape[2]):
        confidence = detections[0, 0, i, 2]
        idx = int(detections[0, 0, i, 1])
        if confidence > 0.5 and CLASSES[idx] == "person":
            box = detections[0, 0, i, 3:7] * np.array([w, h, w, h])
            (startX, startY, endX, endY) = box.astype("int")
            label = f"Person: {confidence:.2f}"
            cv2.rectangle(frame, (startX, startY), (endX, endY), (0, 255, 0), 2)
            cv2.putText(frame, label, (startX, startY - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
    return frame

def gen_frames():
    while True:
        with camera_lock:
            success, frame = cap.read()
        if not success:
            print("[WARNING] Gagal membaca frame streaming.")
            break
        else:
            # Proses frame dengan MobileNetSSD untuk deteksi 'person'
            frame = process_frame_with_mobilenetssd(frame)

            ret, buffer = cv2.imencode('.jpg', frame)
            frame_bytes = buffer.tobytes()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

def is_connected(host="8.8.8.8", port=53, timeout=3):
    try:
        socket.setdefaulttimeout(timeout)
        socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect((host, port))
        return True
    except socket.error:
        return False

def generate_hmac(filename):
    """
    Generate HMAC SHA256 dari isi file video.
    """
    h = hmac.new(SECRET_KEY, digestmod=hashlib.sha256)
    with open(filename, 'rb') as f:
        while True:
            chunk = f.read(4096)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()

def upload_video(filename):
    try:
        if not is_connected():
            raise ConnectionError("Tidak ada koneksi sebelum mulai upload.")

        # HMAC v1 setup
        key_id = "v1"
        timestamp = str(int(time.time()))
        message = f"{key_id}:{timestamp}".encode()

        # HMAC-SHA256 signature dari pesan "v1:timestamp"
        signature = hmac.new(SECRET_KEY, message, hashlib.sha256).hexdigest()

        # Header HMAC
        headers = {
            'X-Key-Id': key_id,
            'X-Timestamp': timestamp,
            'X-Signature': signature
        }

        # Kirim file video dengan headers HMAC
        with open(filename, 'rb') as f:
            files = {'video': f}
            response = requests.post(SERVER_UPLOAD_URL, files=files, headers=headers, timeout=120)

        if response.status_code == 200:
            print("[UPLOAD SUCCESS]", response.text)
            return True
        else:
            print("[UPLOAD FAILED] Status code:", response.status_code)
            print("Response:", response.text)
            return False

    except (requests.exceptions.RequestException, ConnectionError) as e:
        print("[UPLOAD ERROR] Koneksi gagal selama upload:", str(e))
        return False

    except Exception as e:
        print("[UPLOAD ERROR] Error lain:", str(e))
        return False


def upload_pending_files():
    print("[INFO] Mengecek file offline untuk diupload...")
    while True:
        files = sorted(os.listdir(PENDING_FOLDER))
        if not files:
            print("[INFO] Folder pending sudah kosong, semua file berhasil diupload.")
            break

        for f in files:
            file_path = os.path.join(PENDING_FOLDER, f)
            if os.path.isfile(file_path):
                print(f"[UPLOAD PENDING] Mencoba upload {f}...")
                if upload_video(file_path):
                    os.remove(file_path)
                    print(f"[UPLOAD PENDING] Berhasil upload dan hapus {f}")
                else:
                    print(f"[UPLOAD PENDING] Gagal upload {f}, retry setelah delay...")
                    time.sleep(10)  # delay sebelum retry dari awal
                    break  # keluar dari for untuk ulang loop while lagi
        else:
            # Jika for selesai tanpa break berarti semua file berhasil diupload
            continue

def record_video(duration, filepath):
    fourcc = cv2.VideoWriter_fourcc(*'XVID')
    with camera_lock:
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    out = cv2.VideoWriter(filepath, fourcc, 20.0, (width, height))

    start_time = time.time()
    while time.time() - start_time < duration:
        with camera_lock:
            ret, frame = cap.read()
        if not ret:
            print("[WARNING] Gagal membaca frame saat rekaman.")
            break
        out.write(frame)
    out.release()

def record_video_loop():
    retry_interval = 120  # 2 menit
    last_retry_time = 0
    prev_connected = None

    while True:
        connected = is_connected()

        if prev_connected is None:
            prev_connected = connected
        elif prev_connected != connected:
            if connected:
                print("[FAILOVER] Koneksi PULIH (offline ? online)")
                upload_pending_files()
            else:
                print("[FAILOVER] Koneksi HILANG (online ? offline)")
            prev_connected = connected

        print(f"[INFO] Koneksi internet: {'TERHUBUNG' if connected else 'TIDAK TERHUBUNG'}")

        current_time = time.time()

        if connected:
            # Tambahkan cek upload file offline rutin setiap retry_interval saat online
            if current_time - last_retry_time >= retry_interval:
                print("[INFO] Waktu retry upload file offline (online mode)...")
                last_retry_time = current_time
                upload_pending_files()

            try:
                doc_ref = db.collection('pillbox').document('camera')
                doc = doc_ref.get()
                if doc.exists:
                    config = doc.to_dict()
                    record_duration = int(config.get('record', RECORD_DURATION))
                    pause_duration = int(config.get('pause', ONLINE_SLEEP_DURATION))
                else:
                    print("[WARNING] Dokumen Firestore tidak ditemukan. Gunakan default.")
                    record_duration = RECORD_DURATION
                    pause_duration = ONLINE_SLEEP_DURATION
            except Exception as e:
                print("[FIRESTORE ERROR]", str(e))
                record_duration = RECORD_DURATION
                pause_duration = ONLINE_SLEEP_DURATION

            filename = "output.avi"
            print(f"[INFO] Rekam {record_duration} detik (ONLINE)...")
            record_video(record_duration, filename)

            print("[INFO] Coba upload ke server...")
            success = upload_video(filename)

            if not success:
                timestamp = int(time.time())
                offline_filename = os.path.join(PENDING_FOLDER, f"offline_{timestamp}.avi")
                os.rename(filename, offline_filename)
                print(f"[FAILOVER] Upload gagal, file dipindahkan ke {offline_filename}")
            else:
                if os.path.exists(filename):
                    os.remove(filename)

            print(f"[INFO] Jeda {pause_duration} detik (ONLINE)...")
            time.sleep(pause_duration)

        else:
            record_duration = RECORD_DURATION
            pause_duration = OFFLINE_SLEEP_DURATION
            timestamp = int(time.time())
            filepath = os.path.join(PENDING_FOLDER, f"offline_{timestamp}.avi")

            print(f"[INFO] Rekam {record_duration} detik (OFFLINE)...")
            record_video(record_duration, filepath)

            if current_time - last_retry_time >= retry_interval:
                print("[INFO] Waktu retry upload file offline (offline mode)...")
                last_retry_time = current_time

                if is_connected():
                    print("[INFO] Koneksi ditemukan, mulai upload file offline...")
                    upload_pending_files()
                else:
                    print("[INFO] Koneksi belum ada, tunggu retry berikutnya.")

            print(f"[INFO] Jeda {pause_duration} detik (OFFLINE)...\n")
            time.sleep(pause_duration)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/videos/list')
def videos_list():
    try:
        if is_connected():
            response = requests.get("https://pillbox-server-263713026348.asia-southeast2.run.app/videos/list")
            return jsonify(response.json())
        else:
            files = [f for f in os.listdir(PENDING_FOLDER) if f.endswith('.avi')]
            return jsonify({"video_files": files})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
@app.route('/video_gallery', methods=['GET'])
def video_gallery():
    return render_template('gallery.html')

@app.route('/videos/list/<date>')
def videos_list_by_date(date):
    try:
        cloud_url = f"https://pillbox-server-263713026348.asia-southeast2.run.app/videos/list/{date}"
        response = requests.get(cloud_url, timeout=10)
        response.raise_for_status()
        return jsonify(response.json())
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/system_status')
def system_status():
    try:
        # CPU Load & Frequency
        cpu_load = psutil.cpu_percent(interval=1)
        cpu_freq = psutil.cpu_freq().current

        # Memory
        mem = psutil.virtual_memory()
        memory_used = mem.used / (1024 ** 2)
        memory_total = mem.total / (1024 ** 2)
        memory_percent = mem.percent

        # Temperature (Linux)
        cpu_temp = None
        try:
            if platform.system() == 'Linux':
                with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
                    cpu_temp = int(f.read()) / 1000.0
        except Exception:
            cpu_temp = None

        # Load average
        load_avg = os.getloadavg() if hasattr(os, 'getloadavg') else (0, 0, 0)

        # Uptime
        uptime_seconds = time.time() - psutil.boot_time()
        uptime = time.strftime("%H:%M:%S", time.gmtime(uptime_seconds))

        # Latency (ping Google)
        try:
            ping = subprocess.check_output(["ping", "-c", "1", "8.8.8.8"], universal_newlines=True)
            latency_line = [line for line in ping.split("\n") if "time=" in line][0]
            latency = latency_line.split("time=")[-1].split()[0]
        except Exception:
            latency = "N/A"

        return jsonify({
            "cpu_load": cpu_load,
            "cpu_freq": cpu_freq,
            "memory_used": round(memory_used, 2),
            "memory_total": round(memory_total, 2),
            "memory_percent": memory_percent,
            "cpu_temp": cpu_temp,
            "load_avg": load_avg,
            "uptime": uptime,
            "latency": latency
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/video_feed')
def video_feed():
    return Response(gen_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

def start_recording_thread():
    thread = threading.Thread(target=record_video_loop)
    thread.daemon = True
    thread.start()

start_recording_thread()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
