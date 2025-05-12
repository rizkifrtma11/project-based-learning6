import cv2
import paho.mqtt.client as mqtt
import time
from utils import encode_frame
import threading

# Fungsi zoom untuk gambar
def zoom(frame, zoom_factor):
    h, w = frame.shape[:2]
    center_x, center_y = w // 2, h // 2
    crop_w, crop_h = int(w / zoom_factor), int(h / zoom_factor)

    crop_x1 = max(center_x - crop_w // 2, 0)
    crop_x2 = min(center_x + crop_w // 2, w)
    crop_y1 = max(center_y - crop_h // 2, 0)
    crop_y2 = min(center_y + crop_h // 2, h)

    cropped_frame = frame[crop_y1:crop_y2, crop_x1:crop_x2]
    zoomed_frame = cv2.resize(cropped_frame, (w, h), interpolation=cv2.INTER_LINEAR)
    return zoomed_frame

# Topik MQTT
broker_address = "192.168.200.161"
topic_frame = "kamera/frame"
topic_deteksi = "kamera/deteksi"

# Inisialisasi MQTT client
client = mqtt.Client()
client.connect(broker_address)

cap = cv2.VideoCapture(0)
zoom_factor = 1  # Mulai dengan zoom normal

def publish_frame():
    while True:
        ret, frame = cap.read()
        if not ret:
            break

        # Apply zoom
        zoomed_frame = zoom(frame, zoom_factor)

        # Encode frame ke format base64
        encoded = encode_frame(zoomed_frame)

        # Publish gambar ke topik 'kamera/frame'
        client.publish(topic_frame, encoded)

        # Kirim hasil deteksi dummy ke topik 'kamera/deteksi'
        client.publish(topic_deteksi, "mobil_terdeteksi")

        # Beri delay
        time.sleep(1)

def check_zoom_key():
    global zoom_factor
    while True:
        key = cv2.waitKey(1) & 0xFF
        if key == ord('+'):  # Zoom in (menambah faktor zoom)
            zoom_factor *= 1.1
            print(f"Zoom in: Faktor zoom = {zoom_factor}")
        elif key == ord('-'):  # Zoom out (mengurangi faktor zoom)
            zoom_factor /= 1.1
            print(f"Zoom out: Faktor zoom = {zoom_factor}")

# Mulai thread untuk publish frame dan cek tombol zoom
threading.Thread(target=publish_frame).start()
threading.Thread(target=check_zoom_key).start()
