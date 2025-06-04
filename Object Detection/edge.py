from flask import Flask, Response, render_template, jsonify
from flask_cors import CORS
import cv2
import threading
import time
import os
import psutil
import platform
import subprocess
from datetime import datetime
from collections import defaultdict

import firebase_admin
from firebase_admin import credentials, firestore

from deep_sort_realtime.deepsort_tracker import DeepSort

# ===== Firebase Setup =====
cred = credentials.Certificate("firebase.json")
firebase_admin.initialize_app(cred)
db = firestore.client()

def get_record_settings():
    try:
        doc_ref = db.collection("pillboox").document("camera")
        doc = doc_ref.get()
        if doc.exists:
            data = doc.to_dict()
            record_duration = int(data.get("record", 10))
            record_cooldown = int(data.get("pause", 15))
            return record_duration, record_cooldown
    except Exception as e:
        print(f"[ERROR] Gagal mengambil setting Firestore: {e}")
    return 10, 15

# ===== Flask App =====
app = Flask(__name__)
CORS(app)

camera_lock = threading.Lock()
cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)

if not cap.isOpened():
    print("[ERROR] Kamera tidak bisa dibuka.")
    exit()

PROTO_PATH = "mobilenet_ssd/MobileNetSSD_deploy.prototxt"
MODEL_PATH = "mobilenet_ssd/MobileNetSSD_deploy.caffemodel"
net = cv2.dnn.readNetFromCaffe(PROTO_PATH, MODEL_PATH)
CLASSES = ["background", "aeroplane", "bicycle", "bird", "boat",
           "bottle", "bus", "car", "cat", "chair", "cow", "diningtable",
           "dog", "horse", "motorbike", "person", "pottedplant", "sheep",
           "sofa", "train", "tvmonitor"]

tracker = DeepSort(max_age=40)
people_log = defaultdict(int)
last_log_time = None

recording = False
last_record_time = 0

def record_video(frames, width, height, filename):
    fourcc = cv2.VideoWriter_fourcc(*'XVID')
    out = cv2.VideoWriter(filename, fourcc, 20.0, (width, height))
    for frame in frames:
        out.write(frame)
    out.release()

def gen_frames():
    global people_log, last_log_time, recording, last_record_time

    unique_ids_in_interval = set()
    record_frames = []
    recording_active = False
    frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    record_duration, record_cooldown = get_record_settings()
    last_settings_check = time.time()

    while True:
        with camera_lock:
            success, frame = cap.read()
        if not success:
            print("[WARNING] Gagal membaca frame streaming.")
            break

        if time.time() - last_settings_check > 10:
            record_duration, record_cooldown = get_record_settings()
            last_settings_check = time.time()

        h_ori, w_ori = frame.shape[:2]
        frame_resized = cv2.resize(frame, (640, 360))

        blob = cv2.dnn.blobFromImage(frame_resized, 0.007843, (300, 300), 127.5)
        net.setInput(blob)
        detections = net.forward()

        det_list = []
        for i in range(detections.shape[2]):
            confidence = detections[0, 0, i, 2]
            if confidence > 0.5:
                idx = int(detections[0, 0, i, 1])
                if CLASSES[idx] == "person":
                    box = detections[0, 0, i, 3:7] * [640, 360, 640, 360]
                    (x1, y1, x2, y2) = box.astype("int")
                    det_list.append(([x1, y1, x2, y2], confidence, 'person'))

        tracks = tracker.update_tracks(det_list, frame=frame_resized)

        people_count = 0
        for track in tracks:
            if not track.is_confirmed():
                continue
            track_id = track.track_id
            unique_ids_in_interval.add(track_id)

            ltrb = track.to_ltrb()
            x1, y1, x2, y2 = map(int, ltrb)
            x1 = int(x1 * w_ori / 640)
            y1 = int(y1 * h_ori / 360)
            x2 = int(x2 * w_ori / 640)
            y2 = int(y2 * h_ori / 360)

            people_count += 1
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.putText(frame, f'ID {track_id}', (x1, y1 - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)

        cv2.putText(frame, f'People Count: {people_count}', (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)

        now = datetime.now()
        current_time = int(now.timestamp())

        if last_log_time is None or datetime.now().hour != datetime.fromtimestamp(last_log_time).hour:
            hour_str = now.strftime('%Y-%m-%d %H:00')
            people_log[hour_str] += len(unique_ids_in_interval)
            unique_ids_in_interval.clear()
            last_log_time = current_time

        # Rekam video jika ada orang
        if people_count > 0 and not recording:
            if current_time - last_record_time > record_cooldown:
                recording = True
                recording_active = True
                record_frames = []
                print("[INFO] Mulai rekam video...")

        if recording:
            record_frames.append(frame.copy())
            if len(record_frames) >= record_duration * 20:
                recording = False
                last_record_time = current_time
                recording_active = False
                folder = now.strftime("%Y-%m-%d")
                os.makedirs(f"videos/{folder}", exist_ok=True)
                filename = f"videos/{folder}/record_{now.strftime('%H%M%S')}.avi"
                threading.Thread(target=record_video, args=(record_frames, w_ori, h_ori, filename)).start()
                print(f"[INFO] Rekaman selesai dan disimpan: {filename}")

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
        if platform.system() == 'Linux':
            with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
                cpu_temp = int(f.read()) / 1000.0
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
