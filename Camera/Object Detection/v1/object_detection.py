import cv2
import torch
from ultralytics import YOLO

# Load model YOLOv8
try:
    model = YOLO("yolov8n.pt")  # Pastikan model ada di folder yang benar
    print("Model YOLOv8 berhasil dimuat.")
except Exception as e:
    print(f"Error saat memuat model: {e}")
    exit()

# Buka video dari webcam
cap = cv2.VideoCapture(0)

if not cap.isOpened():
    print("Error: Kamera tidak dapat dibuka.")
    exit()

while cap.isOpened():
    ret, frame = cap.read()
    if not ret:
        print("Error: Tidak bisa menangkap frame.")
        break

    # Deteksi objek
    try:
        results = model(frame)
    except Exception as e:
        print(f"Error saat deteksi objek: {e}")
        break

    # Filter hanya objek 'person'
    count_person = 0
    for r in results:
        for box in r.boxes:
            if int(box.cls) == 0:  # Class 'person'
                count_person += 1
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)

    # Tampilkan jumlah orang
    cv2.putText(frame, f"People: {count_person}", (20, 50),
                cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)

    # Tampilkan hasil
    cv2.imshow("YOLOv8 Person Counter", frame)

    # Tekan 'q' untuk keluar
    if cv2.waitKey(100) & 0xFF == ord('q'):  # Coba jeda lebih lama
        break

cap.release()
cv2.destroyAllWindows()
