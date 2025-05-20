import cv2
import time
import requests
import psutil
from flask import Flask, Response, render_template, jsonify
import threading

# Konfigurasi RTSP dan server tujuan upload video
RTSP_URL = "rtsp://admin:Rizki2025%40%40@192.168.0.110:554/Stream/Channels/101"
SERVER_URL = "http://192.168.0.106:5000/upload"

# Durasi rekaman dan jeda antar rekaman
RECORD_DURATION = 10  # detik
SLEEP_DURATION = 5    # detik

app = Flask(__name__)
camera_lock = threading.Lock()
cap = cv2.VideoCapture(RTSP_URL)

# Fungsi untuk upload video ke server
def upload_video(video_path):
    with open(video_path, "rb") as f:
        files = {'video': f}
        try:
            response = requests.post(SERVER_URL, files=files)
            print("[SERVER RESP]", response.text)
        except Exception as e:
            print("[ERROR] Gagal upload video:", str(e))

# Fungsi untuk streaming ke browser
def gen_frames():
    while True:
        with camera_lock:
            ret, frame = cap.read()
        if not ret:
            print("[WARNING] Gagal membaca frame.")
            break
        ret, buffer = cv2.imencode('.jpg', frame)
        if ret:
            frame = buffer.tobytes()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

# Route untuk halaman utama
@app.route('/')
def index():
    return render_template('index.html')

# Route untuk video streaming
@app.route('/video_feed')
def video_feed():
    return Response(gen_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

# Mendapatkan status sistem
def get_system_status():
    cpu_percent = psutil.cpu_percent(interval=1)
    memory = psutil.virtual_memory()
    memory_used = memory.used / (1024 * 1024)
    memory_total = memory.total / (1024 * 1024)
    processes = []
    for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_info']):
        try:
            processes.append({
                'pid': proc.info['pid'],
                'name': proc.info['name'],
                'cpu_percent': proc.info['cpu_percent'],
                'memory_used': proc.info['memory_info'].rss / (1024 * 1024)
            })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return {
        'cpu_percent': cpu_percent,
        'memory_used': memory_used,
        'memory_total': memory_total,
        'processes': sorted(processes, key=lambda p: p['cpu_percent'], reverse=True)
    }

# Route untuk mengambil status sistem
@app.route('/system_status')
def system_status():
    try:
        status = get_system_status()
        return jsonify(status)
    except Exception as e:
        print("[ERROR] Gagal mengambil status sistem:", str(e))
        return jsonify({"error": str(e)}), 500

# Fungsi merekam video dan upload
def start_recording():
    while True:
        print("[INFO] Mulai merekam video...")
        fourcc = cv2.VideoWriter_fourcc(*'XVID')
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        out = cv2.VideoWriter("record.avi", fourcc, 20, (width, height))

        start = time.time()
        while time.time() - start < RECORD_DURATION:
            with camera_lock:
                ret, frame = cap.read()
            if not ret:
                print("[WARNING] Gagal membaca frame.")
                break
            out.write(frame)

        out.release()
        print("[INFO] Rekaman selesai, mengirim ke server...")
        upload_video("record.avi")
        print(f"[INFO] Jeda selama {SLEEP_DURATION} detik...\n")
        time.sleep(SLEEP_DURATION)

# Jalankan recording di background
def start_recording_in_background():
    recording_thread = threading.Thread(target=start_recording)
    recording_thread.daemon = True
    recording_thread.start()

start_recording_in_background()

# Jalankan Flask
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
