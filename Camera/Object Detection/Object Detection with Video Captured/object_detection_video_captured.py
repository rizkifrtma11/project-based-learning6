import cv2
import os
import time
from datetime import datetime
from flask import Flask, Response, render_template, jsonify
from PIL import Image
import imagehash
import threading

app = Flask(__name__)

proto_file = "deploy.prototxt"
model_file = "mobilenet_iter_73000.caffemodel"

net = cv2.dnn.readNetFromCaffe(proto_file, model_file)

face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')

output_folder = "captured_videos"
os.makedirs(output_folder, exist_ok=True)

cap = cv2.VideoCapture(0)
capture_interval = 10
last_capture_time = time.time()
last_image_filename = ""
is_capturing = True
last_image_hash = None

# Buffer dan variabel perekaman
video_buffer = []
recording = False
record_start_time = 0
record_duration = 3  # default durasi

def generate_image_hash(image):
    """Menghasilkan hash dari gambar untuk perbandingan"""
    img = Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
    return imagehash.average_hash(img)

def save_video_from_buffer(frames, filename):
    if not frames:
        return
    height, width = frames[0].shape[:2]
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    fps = 20.0
    video_path = os.path.join(output_folder, filename)

    out = cv2.VideoWriter(video_path, fourcc, fps, (width, height))
    for frame in frames:
        out.write(frame)
    out.release()

    print(f"✅ Video disimpan: {filename}")

def generate_frames():
    global last_capture_time, last_image_hash
    global video_buffer, recording, record_start_time, record_duration

    while True:
        success, frame = cap.read()
        if not success:
            break

        if not is_capturing:
            continue

        h, w = frame.shape[:2]
        blob = cv2.dnn.blobFromImage(frame, scalefactor=0.007843, size=(300, 300), mean=127.5)
        net.setInput(blob)
        detections = net.forward()

        humans = []
        for i in range(detections.shape[2]):
            confidence = detections[0, 0, i, 2]
            if confidence > 0.5:
                class_id = int(detections[0, 0, i, 1])
                if class_id == 15:
                    box = detections[0, 0, i, 3:7] * [w, h, w, h]
                    (x, y, x2, y2) = box.astype("int")
                    humans.append((x, y, x2 - x, y2 - y))
                    cv2.rectangle(frame, (x, y), (x2, y2), (255, 0, 0), 2)

        cv2.putText(frame, f"{len(humans)} orang terdeteksi", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 2)

        current_time = time.time()

        if len(humans) > 0:
            current_hash = generate_image_hash(frame)

            if not recording and (last_image_hash is None or abs(current_hash - last_image_hash) > 5):
                # Mulai rekaman baru
                recording = True
                video_buffer = []
                record_start_time = current_time
                record_duration = 15 if len(humans) <= 2 else 30
                last_image_hash = current_hash
                last_capture_time = current_time
                print(f"🎥 Mulai merekam video dari buffer selama {record_duration} detik...")

            if recording:
                video_buffer.append(frame.copy())

                if current_time - record_start_time >= record_duration:
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    video_filename = f"video_{timestamp}.mp4"
                    # Simpan video dalam thread terpisah
                    threading.Thread(target=save_video_from_buffer, args=(video_buffer.copy(), video_filename)).start()
                    recording = False
                    video_buffer = []

        # Kirim frame ke halaman web
        ret, buffer = cv2.imencode('.jpg', frame)
        frame_bytes = buffer.tobytes()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/last_capture')
def last_capture():
    return jsonify({"filename": last_image_filename})

@app.route('/check_new_capture')
def check_new_capture():
    return jsonify({"filename": last_image_filename})

@app.route('/start_capture', methods=['POST'])
def start_capture():
    global is_capturing
    is_capturing = True
    return jsonify({"status": "Capturing started"})

@app.route('/stop_capture', methods=['POST'])
def stop_capture():
    global is_capturing
    is_capturing = False
    return jsonify({"status": "Capturing stopped"})

if __name__ == '__main__':
    app.run(debug=True)
