import subprocess
from flask import Flask, request, jsonify
import os
import cv2
from ultralytics import YOLO
from datetime import datetime
from tempfile import NamedTemporaryFile
from google.cloud import storage
from werkzeug.utils import secure_filename
import json
import firebase_admin
from firebase_admin import credentials, firestore
import hmac
import hashlib

# Inisialisasi aplikasi Flask
app = Flask(__name__)

# -------- Setup YOLO & Google Cloud Storage (GCS) --------
model = YOLO('yolov8n.pt')
with open("pillbox_bucket.json") as f:
    service_account_info = json.load(f)
storage_client = storage.Client.from_service_account_info(service_account_info)

BUCKET_NAME = 'pillboxid'
UPLOAD_FOLDER = 'uploads'
OUTPUT_FOLDER = f'{UPLOAD_FOLDER}/output'

# -------- Setup Firebase Firestore --------
cred = credentials.Certificate('firebase.json')
firebase_admin.initialize_app(cred)
db = firestore.client()

# -------- Setup HMAC --------
SECRET_KEYS = {
    "v1": b"pillboxpnj234",
    "v2": b"pillboxpnj123"
}

def verify_signature_internal(key_id, timestamp, signature):
    secret_key = SECRET_KEYS.get(key_id)
    if not secret_key:
        print(f"Unknown key_id: {key_id}")
        return False

    try:
        message = f"{key_id}:{timestamp}".encode()
        expected_signature = hmac.new(secret_key, message, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected_signature, signature):
            print("Signature mismatch")
            print(f"Expected: {expected_signature}")
            print(f"Got     : {signature}")
            return False
        return True
    except Exception as e:
        print(f"Exception during HMAC verification: {e}")
        return False

def verify_request():
    key_id = request.headers.get("X-Key-Id")
    timestamp = request.headers.get("X-Timestamp")
    signature = request.headers.get("X-Signature")
    if not all([key_id, timestamp, signature]):
        return False, jsonify({"error": "Missing signature headers"}), 403
    if not verify_signature_internal(key_id, timestamp, signature):
        return False, jsonify({"error": "Invalid signature"}), 403
    return True, None, None

def upload_to_gcs(local_path, gcs_path):
    bucket = storage_client.bucket(BUCKET_NAME)
    blob = bucket.blob(gcs_path)
    blob.upload_from_filename(local_path)
    return blob.public_url

def list_gcs_files(prefix):
    bucket = storage_client.bucket(BUCKET_NAME)
    blobs = bucket.list_blobs(prefix=prefix)
    return [blob.name for blob in blobs if not blob.name.endswith('/')]

def delete_gcs_file(path):
    bucket = storage_client.bucket(BUCKET_NAME)
    blob = bucket.blob(path)
    if blob.exists():
        blob.delete()
        return True
    return False

# Fungsi IOU sederhana
def iou(box1, box2):
    xA = max(box1[0], box2[0])
    yA = max(box1[1], box2[1])
    xB = min(box1[2], box2[2])
    yB = min(box1[3], box2[3])

    interArea = max(0, xB - xA + 1) * max(0, yB - yA + 1)
    box1Area = (box1[2] - box1[0] + 1) * (box1[3] - box1[1] + 1)
    box2Area = (box2[2] - box2[0] + 1) * (box2[3] - box2[1] + 1)

    iou = interArea / float(box1Area + box2Area - interArea)
    return iou

@app.route('/', methods=['GET'])
def index():
    return jsonify({
        "message": "Selamat datang di API Deteksi Video YOLOv8 untuk Pillbox",
        "endpoint": {
            "POST /videos": "...",
            "GET /videos/list": "...",
            "GET /videos/list/<tanggal>": "...",
            "GET /videos/dates": "...",
            "DELETE /videos/<tanggal>/<nama_file>": "...",
            "POST /videos/camera": "...",
            "GET /videos/camera": "..."
        }
    }), 200

@app.route('/videos', methods=['POST'])
def upload_video():
    valid, resp, code = verify_request()
    if not valid:
        return resp, code

    if 'video' not in request.files:
        return jsonify({"error": "No video file provided"}), 400

    video_file = request.files['video']
    if video_file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    try:
        filename = secure_filename(video_file.filename)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        raw_output_filename = f"output_raw_{timestamp}.avi"
        compressed_filename = f"output_{timestamp}.mp4"
        today = datetime.now().strftime('%Y-%m-%d')
        gcs_output_path = f"{OUTPUT_FOLDER}/{today}/{compressed_filename}"

        with NamedTemporaryFile(delete=False, suffix=".avi") as temp_input:
            video_file.save(temp_input.name)
            input_path = temp_input.name

        with NamedTemporaryFile(delete=False, suffix=".avi") as temp_output:
            output_path = temp_output.name

        cap = cv2.VideoCapture(input_path)
        if not cap.isOpened():
            return jsonify({"error": "Failed to open video"}), 400

        fourcc = cv2.VideoWriter_fourcc(*'XVID')
        fps = cap.get(cv2.CAP_PROP_FPS)
        frame_size = (int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)))
        out = cv2.VideoWriter(output_path, fourcc, fps, frame_size)

        # --- Tracking Manual ---
        tracked_boxes = []
        iou_threshold = 0.5

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            results = model(frame)[0]
            current_boxes = []
            for box in results.boxes:
                cls_id = int(box.cls.item())
                label = model.names[cls_id]
                if label == 'person':
                    x1, y1, x2, y2 = map(int, box.xyxy[0])
                    current_boxes.append((x1, y1, x2, y2))

                    # Gambar kotak deteksi
                    cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                    cv2.putText(frame, label, (x1, y1 - 10),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

            for box in current_boxes:
                matched = False
                for tracked_box in tracked_boxes:
                    if iou(box, tracked_box) > iou_threshold:
                        matched = True
                        break
                if not matched:
                    tracked_boxes.append(box)

            out.write(frame)

        cap.release()
        out.release()

        compressed_path = output_path.replace(".avi", "_compressed.mp4")
        ffmpeg_cmd = [
            "ffmpeg", "-y",
            "-i", output_path,
            "-vcodec", "libx264", "-crf", "28", "-preset", "fast",
            compressed_path
        ]
        subprocess.run(ffmpeg_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)

        output_url = upload_to_gcs(compressed_path, gcs_output_path)

        # Hapus file lokal sementara
        os.remove(input_path)
        os.remove(output_path)
        os.remove(compressed_path)

        # Hitung jumlah orang unik
        unique_person_count = len(tracked_boxes)

        # Simpan hasil ke Firestore
        # Simpan hasil ke Firestore dalam bentuk map: tanggal -> {nama_file: jumlah_orang}
        video_name = os.path.splitext(compressed_filename)[0]
        today = datetime.now().strftime("%Y-%m-%d")
        detections_ref = db.collection("pillbox").document("detections")

        # Update field sesuai tanggal
        detections_ref.set({
            today: {
                video_name: unique_person_count
            }
        }, merge=True)

        return jsonify({
            "message": "Video processed and compressed successfully",
            "output_url": output_url,
            "unique_person_count": unique_person_count
        }), 200

    except subprocess.CalledProcessError as ffmpeg_error:
        return jsonify({"error": "FFmpeg compression failed", "details": str(ffmpeg_error)}), 500
    except Exception as e:
        return jsonify({"error": f"Processing failed: {str(e)}"}), 500

@app.route('/videos/list', methods=['GET'])
def get_videos_grouped_by_date():
    try:
        files = list_gcs_files(OUTPUT_FOLDER)
        result = {}
        for file in files:
            parts = file.split('/')
            if len(parts) >= 4:
                date = parts[3]
                url = f"https://storage.googleapis.com/{BUCKET_NAME}/{file}"
                result.setdefault(date, []).append(url)
        return jsonify({"videos_by_date": result}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/videos/list/<date>', methods=['GET'])
def list_videos_by_date(date):
    try:
        safe_date = secure_filename(date)
        prefix = f"{OUTPUT_FOLDER}/{safe_date}/"
        files = list_gcs_files(prefix)
        urls = [f"https://storage.googleapis.com/{BUCKET_NAME}/{file}" for file in files]
        return jsonify({
            "date": safe_date,
            "count": len(urls),
            "videos": urls
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/videos/<date>/<filename>', methods=['DELETE'])
def delete_video(date, filename):
    valid, resp, code = verify_request()
    if not valid:
        return resp, code

    gcs_path = f"{OUTPUT_FOLDER}/{secure_filename(date)}/{secure_filename(filename)}"
    try:
        if delete_gcs_file(gcs_path):
            return jsonify({"message": f"{filename} deleted from GCS"}), 200
        else:
            return jsonify({"error": f"{filename} not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/videos/dates', methods=['GET'])
def list_available_dates():
    try:
        files = list_gcs_files(OUTPUT_FOLDER)
        dates = set()
        for file in files:
            parts = file.split('/')
            if len(parts) >= 4:
                dates.add(parts[3])
        return jsonify(sorted(dates)), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/videos/camera', methods=['POST'])
def update_duration():
    valid, resp, code = verify_request()
    if not valid:
        return resp, code

    data = request.get_json()
    if not data:
        return jsonify({"error": "JSON body required"}), 400

    pause = data.get('pause')
    record = data.get('record')
    if pause is None or record is None:
        return jsonify({"error": "'pause' and 'record' fields required"}), 400

    try:
        doc_ref = db.collection('pillbox').document('camera')
        doc_ref.update({'pause': pause, 'record': record})
        return jsonify({"message": "Fields updated successfully"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/videos/camera', methods=['GET'])
def get_camera_status():
    try:
        doc_ref = db.collection('pillbox').document('camera')
        doc = doc_ref.get()
        if doc.exists:
            return jsonify(doc.to_dict()), 200
        else:
            return jsonify({"error": "Camera document not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(debug=True, host='0.0.0.0', port=port)
