import cv2
import paho.mqtt.client as mqtt
from utils import decode_frame
import tkinter as tk
from tkinter import Button
from zoom import zoom

# Setup untuk topik MQTT
topic_frame = "kamera/frame"
topic_deteksi = "kamera/deteksi"

# Global flag untuk mengaktifkan/menonaktifkan live view
live_view = False
zoom_factor = 1  # Faktor zoom, mulai dengan nilai normal

# Fungsi untuk mengaktifkan atau menonaktifkan live streaming
def toggle_live_view():
    global live_view
    live_view = not live_view
    if live_view:
        print("Live View Activated")
    else:
        print("Live View Deactivated")

# Fungsi untuk zoom in
def zoom_in():
    global zoom_factor
    zoom_factor *= 1.1  # Zoom in 10%
    print(f"Zoom in: Faktor zoom = {zoom_factor}")

# Fungsi untuk zoom out
def zoom_out():
    global zoom_factor
    zoom_factor /= 1.1  # Zoom out 10%
    print(f"Zoom out: Faktor zoom = {zoom_factor}")

# Fungsi callback untuk koneksi MQTT
def on_connect(client, userdata, flags, rc):
    print("Subscriber terhubung ke broker")
    client.subscribe(topic_frame)
    client.subscribe(topic_deteksi)

# Fungsi callback untuk menerima pesan MQTT
def on_message(client, userdata, msg):
    global live_view
    if msg.topic == topic_frame and live_view:
        # Decode dan tampilkan gambar jika live view diaktifkan
        frame = decode_frame(msg.payload.decode())

        # Terapkan zoom ke frame jika perlu
        zoomed_frame = zoom(frame, zoom_factor)

        # Tampilkan frame yang sudah di-zoom
        cv2.imshow("SUB - Live Kamera", zoomed_frame)
        cv2.waitKey(1)
    elif msg.topic == topic_deteksi:
        print(f"[DETEKSI]: {msg.payload.decode()}")

# Fungsi untuk membuat GUI dengan tombol kontrol
def create_gui():
    window = tk.Tk()
    window.title("Kamera Kontrol")

    # Membuat tombol untuk mengaktifkan atau menonaktifkan live view
    toggle_button = Button(window, text="Toggle Live View", command=toggle_live_view)
    toggle_button.pack()

    # Membuat tombol zoom in
    zoom_in_button = Button(window, text="Zoom In (+)", command=zoom_in)
    zoom_in_button.pack()

    # Membuat tombol zoom out
    zoom_out_button = Button(window, text="Zoom Out (-)", command=zoom_out)
    zoom_out_button.pack()

    # Menjalankan GUI
    window.mainloop()

# Menghubungkan ke broker MQTT dan menjalankan loop
def start_mqtt():
    broker_address = "localhost"
    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message

    client.connect(broker_address)
    client.loop_start()  # Non-blocking loop

# Main function untuk menjalankan aplikasi
if __name__ == "__main__":
    start_mqtt()
    create_gui()
