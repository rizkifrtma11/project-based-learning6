from flask import Flask, render_template, Response, request, jsonify
import cv2
import threading
import paho.mqtt.client as mqtt
from utils import decode_frame
from zoom import zoom

app = Flask(__name__)

topic_frame = "kamera/frame"
topic_deteksi = "kamera/deteksi"

live_view = False
zoom_factor = 1.0
current_frame = None
lock = threading.Lock()

def on_connect(client, userdata, flags, rc):
    print("Subscriber terhubung ke broker")
    client.subscribe(topic_frame)
    client.subscribe(topic_deteksi)

def on_message(client, userdata, msg):
    global current_frame, live_view, zoom_factor

    if msg.topic == topic_frame and live_view:
        frame = decode_frame(msg.payload.decode())
        frame = zoom(frame, zoom_factor)
        with lock:
            current_frame = frame
    elif msg.topic == topic_deteksi:
        print(f"[DETEKSI]: {msg.payload.decode()}")

def mqtt_thread():
    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect("localhost")
    client.loop_forever()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/toggle', methods=['POST'])
def toggle():
    global live_view
    live_view = not live_view
    return jsonify({'status': live_view})

@app.route('/zoom', methods=['POST'])
def zoom_control():
    global zoom_factor
    direction = request.json.get('direction')
    if direction == 'in':
        zoom_factor *= 1.1
    elif direction == 'out':
        zoom_factor /= 1.1
    return jsonify({'zoom_factor': zoom_factor})

def generate_frames():
    global current_frame
    while True:
        with lock:
            if current_frame is not None:
                ret, buffer = cv2.imencode('.jpg', current_frame)
                frame = buffer.tobytes()
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

if __name__ == "__main__":
    threading.Thread(target=mqtt_thread, daemon=True).start()
    app.run(debug=True)
