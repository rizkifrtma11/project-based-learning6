from flask import Flask, Response, render_template
import subprocess
import numpy as np
import cv2
from ultralytics import YOLO

WIDTH, HEIGHT = 640, 480
model = YOLO("yolov8n.pt")

app = Flask(__name__)

def generate_frames():
    libcamera_cmd = [
        "libcamera-vid",
        "--nopreview",                      # ? Nonaktifkan window preview
        "-t", "0",                          # Durasi tak terbatas
        "--width", str(WIDTH),
        "--height", str(HEIGHT),
        "--codec", "yuv420",
        "--inline",
        "-o", "-"
    ]

    ffmpeg_cmd = [
        "ffmpeg",
        "-f", "rawvideo",
        "-pix_fmt", "yuv420p",
        "-s", f"{WIDTH}x{HEIGHT}",
        "-i", "-",
        "-f", "image2pipe",
        "-pix_fmt", "bgr24",
        "-vcodec", "rawvideo",
        "-"
    ]

    libcamera_proc = subprocess.Popen(libcamera_cmd, stdout=subprocess.PIPE)
    ffmpeg_proc = subprocess.Popen(ffmpeg_cmd, stdin=libcamera_proc.stdout, stdout=subprocess.PIPE)

    try:
        while True:
            frame_bytes = ffmpeg_proc.stdout.read(WIDTH * HEIGHT * 3)
            if not frame_bytes:
                break

            frame = np.frombuffer(frame_bytes, np.uint8).reshape((HEIGHT, WIDTH, 3))
            frame = frame.copy()  # make writable

            # Deteksi orang
            results = model(frame)
            count_person = 0
            for r in results:
                for box in r.boxes:
                    if int(box.cls) == 0:
                        count_person += 1
                        x1, y1, x2, y2 = map(int, box.xyxy[0])
                        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)

            cv2.putText(frame, f"People: {count_person}", (20, 50),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)

            # Encode sebagai JPEG
            ret, buffer = cv2.imencode('.jpg', frame)
            if not ret:
                continue
            frame = buffer.tobytes()

            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
    finally:
        libcamera_proc.terminate()
        ffmpeg_proc.terminate()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
