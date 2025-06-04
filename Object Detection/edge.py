from flask import Flask, Response, render_template, jsonify
from flask_cors import CORS
import cv2
import threading
import time
import os
import psutil
import platform
import subprocess
from ultralytics import YOLO
from datetime import datetime
from collections import defaultdict

from deep_sort_realtime.deepsort_tracker import DeepSort

app = Flask(__name__)
CORS(app)

camera_lock = threading.Lock()
cap = cv2.VideoCapture(0)
model = YOLO("yolov8n.pt")  # YOLOv8 nano

if not cap.isOpened():
    print("[ERROR] Kamera tidak bisa dibuka.")
    exit()

# Inisialisasi DeepSORT tracker
tracker = DeepSort(max_age=10)  # max_age untuk berapa lama object tetap di-track tanpa update

people_log = defaultdict(int)
last_log_minute = None

def gen_frames():
    global people_log, last_log_time
    last_log_time = None  # inisialisasi waktu log terakhir

    while True:
        with camera_lock:
            success, frame = cap.read()
        if not success:
            print("[WARNING] Gagal membaca frame streaming.")
            break

        # Ukuran asli frame
        h_ori, w_ori = frame.shape[:2]

        # Resize frame untuk proses deteksi/tracking
        frame_resized = cv2.resize(frame, (640, 360))
        rgb_frame = cv2.cvtColor(frame_resized, cv2.COLOR_BGR2RGB)

        results = model(rgb_frame, verbose=False)[0]

        detections = []
        for box in results.boxes:
            cls = int(box.cls[0])
            if cls == 0:  # class person
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                conf = box.conf[0].item()
                detections.append(([x1, y1, x2, y2], conf, 'person'))

        # Update tracker dengan frame yang di-resize
        tracks = tracker.update_tracks(detections, frame=frame_resized)

        people_count = 0
        for track in tracks:
            if not track.is_confirmed():
                continue
            track_id = track.track_id
            ltrb = track.to_ltrb()  # left, top, right, bottom di frame kecil
            x1, y1, x2, y2 = ltrb

            # Scale bounding box ke frame asli
            x1 = int(x1 * w_ori / 640)
            y1 = int(y1 * h_ori / 360)
            x2 = int(x2 * w_ori / 640)
            y2 = int(y2 * h_ori / 360)

            people_count += 1
            # Draw box dan label di frame asli
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.putText(frame, f'ID {track_id}', (x1, y1 - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)

        cv2.putText(frame, f'People Count: {people_count}', (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)

        # Logging setiap 20 detik berdasarkan people_count yang ter-track
        now = datetime.now()
        current_time = int(now.timestamp())

        if last_log_time is None or (current_time - last_log_time) >= 20:
            hour_str = now.strftime('%Y-%m-%d %H:00')
            people_log[hour_str] += people_count
            last_log_time = current_time

        ret, buffer = cv2.imencode('.jpg', frame)
        frame_jpg = buffer.tobytes()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_jpg + b'\r\n')

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/video_feed')
def video_feed():
    return Response(gen_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')


@app.route('/system_status')
def system_status():
    try:
        cpu_load = psutil.cpu_percent(interval=1)
        cpu_freq = psutil.cpu_freq().current

        mem = psutil.virtual_memory()
        memory_used = mem.used / (1024 ** 2)
        memory_total = mem.total / (1024 ** 2)
        memory_percent = mem.percent

        cpu_temp = None
        try:
            if platform.system() == 'Linux':
                with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
                    cpu_temp = int(f.read()) / 1000.0
        except Exception:
            cpu_temp = None

        load_avg = os.getloadavg() if hasattr(os, 'getloadavg') else (0, 0, 0)

        uptime_seconds = time.time() - psutil.boot_time()
        uptime = time.strftime("%H:%M:%S", time.gmtime(uptime_seconds))

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


@app.route('/people_log')
def get_people_log():
    return jsonify(dict(people_log))


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
