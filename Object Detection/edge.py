from flask import Flask, render_template, Response, jsonify
import cv2
import torch
from ultralytics import YOLO
import threading
import os
import time
import psutil
import platform
import subprocess

app = Flask(__name__)

# Load YOLOv8n model (people detection only)
model = YOLO("yolov8n.pt")
model.fuse()

# Setup camera
cap = cv2.VideoCapture(0)
if not cap.isOpened():
    raise RuntimeError("[ERROR] Kamera tidak bisa dibuka.")

# Folder video
VIDEO_FOLDER = "./videos"
os.makedirs(VIDEO_FOLDER, exist_ok=True)

# Shared variable for people count
people_count = 0
frame_lock = threading.Lock()

def gen_frames():
    global people_count
    while True:
        success, frame = cap.read()
        if not success:
            break

        results = model(frame, verbose=False)[0]

        # Ambil hanya bbox dengan class == 0 (person)
        person_indices = (results.boxes.cls == 0)
        results.boxes = results.boxes[person_indices]

        # Hitung orang
        count = len(results.boxes)

        with frame_lock:
            people_count = count

        # Gambar hasil hanya untuk person
        annotated = results.plot()

        ret, buffer = cv2.imencode('.jpg', annotated)
        frame_bytes = buffer.tobytes()

        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/video_feed')
def video_feed():
    return Response(gen_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/people_count')
def get_people_count():
    with frame_lock:
        count = people_count
    return jsonify({"people_count": count})

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

@app.route('/video_gallery')
def video_gallery():
    return render_template('gallery.html')

@app.route('/videos/list')
def list_videos():
    try:
        files = [f for f in os.listdir(VIDEO_FOLDER) if f.endswith(('.mp4', '.avi'))]
        return jsonify({"video_files": files})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/videos/list/<date>')
def list_videos_by_date(date):
    folder = os.path.join(VIDEO_FOLDER, date)
    try:
        if not os.path.exists(folder):
            return jsonify({"video_files": []})
        files = [f for f in os.listdir(folder) if f.endswith(('.mp4', '.avi'))]
        return jsonify({"video_files": files})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
