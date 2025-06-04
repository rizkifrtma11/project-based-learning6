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

app = Flask(__name__)
CORS(app)

camera_lock = threading.Lock()
cap = cv2.VideoCapture(0)
model = YOLO("yolov8n.pt")  # Gunakan YOLOv8n

if not cap.isOpened():
    print("[ERROR] Kamera tidak bisa dibuka.")
    exit()

# Log jumlah orang per jam
people_log = defaultdict(int)

def gen_frames():
    global people_log
    while True:
        with camera_lock:
            success, frame = cap.read()
        if not success:
            print("[WARNING] Gagal membaca frame streaming.")
            break

        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = model(rgb_frame, verbose=False)[0]

        count = 0
        for box in results.boxes:
            cls = int(box.cls[0])
            if cls == 0:  # class 'person'
                count += 1
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                cv2.putText(frame, 'Person', (x1, y1 - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

        # Update log jumlah orang
        now = datetime.now()
        hour_str = now.strftime('%Y-%m-%d %H:00')  # Format jam
        people_log[hour_str] += count

        # Tampilkan jumlah orang di frame
        cv2.putText(frame, f'People Count: {count}', (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)

        ret, buffer = cv2.imencode('.jpg', frame)
        frame = buffer.tobytes()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

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
