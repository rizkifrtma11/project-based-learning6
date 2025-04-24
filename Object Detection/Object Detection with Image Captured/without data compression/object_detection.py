from flask import Flask, Response, render_template
import cv2
import torch
import os
import time
from ultralytics import YOLO

app = Flask(__name__)

# Load model YOLOv8
model = YOLO("yolov8n.pt")

# Buka kamera
cap = cv2.VideoCapture(0)

# Buat folder image jika belum ada
if not os.path.exists('image'):
    os.makedirs('image')

# Variabel waktu terakhir capture
last_capture_time = 0
capture_interval = 10  # dalam detik

def generate_frames():
    global last_capture_time

    while True:
        success, frame = cap.read()
        if not success:
            break

        # Deteksi objek dengan YOLOv8
        results = model(frame)
        count_person = 0
        person_detected = False

        for r in results:
            for box in r.boxes:
                if int(box.cls) == 0:  # Kelas 'person'
                    person_detected = True
                    count_person += 1
                    x1, y1, x2, y2 = map(int, box.xyxy[0])
                    cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)

        # Capture gambar jika orang terdeteksi dan cukup waktu telah berlalu
        current_time = time.time()
        if person_detected and (current_time - last_capture_time > capture_interval):
            filename = f'image/non_compression_{int(current_time)}.jpg'
            cv2.imwrite(filename, frame)
            last_capture_time = current_time

        # Tampilkan jumlah orang
        cv2.putText(frame, f"People: {count_person}", (20, 50),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)

        # Encode frame ke format JPEG
        _, buffer = cv2.imencode('.jpg', frame)
        frame_bytes = buffer.tobytes()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

@app.route('/')
def index():
    return render_template('index1.html')

@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
