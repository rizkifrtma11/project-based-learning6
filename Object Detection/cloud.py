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
# Memuat model YOLO dari file
model = YOLO('yolov8n.pt')

# Membaca informasi akun layanan untuk GCS
with open("pillbox_bucket.json") as f:
    service_account_info = json.load(f)
# Membuat klien GCS
storage_client = storage.Client.from_service_account_info(service_account_info)

# Nama bucket dan folder untuk upload dan output
BUCKET_NAME = 'pillboxid'
UPLOAD_FOLDER = 'uploads'
OUTPUT_FOLDER = f'{UPLOAD_FOLDER}/output'

# -------- Setup Firebase Firestore --------
# Menginisialisasi Firebase dengan kredensial
cred = credentials.Certificate('firebase.json')
firebase_admin.initialize_app(cred)
db = firestore.client()

# -------- Setup HMAC --------
# Kunci rahasia untuk verifikasi HMAC
SECRET_KEYS = {
    "v1": b"pillboxpnj234",
    "v2": b"pillboxpnj123"
}

# Fungsi untuk memverifikasi tanda tangan HMAC
def verify_signature_internal(key_id, timestamp, signature):
    secret_key = SECRET_KEYS.get(key_id)
    if not secret_key:
        print(f"Unknown key_id: {key_id}")
        return False

    try:
        # Membuat pesan untuk verifikasi
        message = f"{key_id}:{timestamp}".encode()
        expected_signature = hmac.new(secret_key, message, hashlib.sha256).hexdigest()

        # Membandingkan tanda tangan yang diharapkan dengan yang diterima
        if not hmac.compare_digest(expected_signature, signature):
            print("Signature mismatch")
            print(f"Expected: {expected_signature}")
            print(f"Got     : {signature}")
            return False

        return True
    except Exception as e:
        print(f"Exception during HMAC verification: {e}")
        return False

# Fungsi untuk memverifikasi permintaan HMAC
def verify_request():
    key_id = request.headers.get("X-Key-Id")
    timestamp = request.headers.get("X-Timestamp")
    signature = request.headers.get("X-Signature")

    # Memeriksa apakah semua header tanda tangan ada
    if not all([key_id, timestamp, signature]):
        return False, jsonify({"error": "Missing signature headers"}), 403

    # Memverifikasi tanda tangan
    if not verify_signature_internal(key_id, timestamp, signature):
        return False, jsonify({"error": "Invalid signature"}), 403

    return True, None, None

# -------- Fungsi Utilitas untuk GCS --------
# Fungsi untuk mengupload file ke GCS
def upload_to_gcs(local_path, gcs_path):
    bucket = storage_client.bucket(BUCKET_NAME)
    blob = bucket.blob(gcs_path)
    blob.upload_from_filename(local_path)
    return blob.public_url

# Fungsi untuk mendapatkan daftar file dari GCS
def list_gcs_files(prefix):
    bucket = storage_client.bucket(BUCKET_NAME)
    blobs = bucket.list_blobs(prefix=prefix)
    return [blob.name for blob in blobs if not blob.name.endswith('/')]

# Fungsi untuk menghapus file dari GCS
def delete_gcs_file(path):
    bucket = storage_client.bucket(BUCKET_NAME)
    blob = bucket.blob(path)
    if blob.exists():
        blob.delete()
        return True
    return False

# -------- Rute API --------

# Rute untuk halaman utama
@app.route('/', methods=['GET'])
def index():
    return jsonify({
        "message": "Selamat datang di API Deteksi Video YOLOv8 untuk Pillbox",
        "deskripsi": "API ini memungkinkan Anda untuk mengunggah video, memprosesnya dengan deteksi objek YOLOv8, mengelola file video di Google Cloud Storage, dan mengontrol status perekaman kamera.",
        "endpoint": {
            "POST /videos": {
                "deskripsi": "Unggah video untuk diproses dengan YOLOv8. Mengembalikan URL video hasil deteksi.",
                "header": {
                    "X-Key-Id": "Diperlukan untuk autentikasi HMAC",
                    "X-Timestamp": "Timestamp saat ini",
                    "X-Signature": "Tanda tangan HMAC-SHA256"
                },
                "body": {
                    "video": "File video (multipart/form-data)"
                }
            },
            "GET /videos/list": {
                "deskripsi": "Melihat daftar video yang telah diproses, dikelompokkan berdasarkan tanggal."
            },
            "GET /videos/list/<tanggal>": {
                "deskripsi": "Melihat daftar video record untuk tanggal tertentu memungkinkan fitur search by date (format: YYYY-MM-DD)."
            },
            "GET /videos/dates": {
                "deskripsi": "Melihat record dari semua tanggal yang memiliki video hasil proses."
            },
            "DELETE /videos/<tanggal>/<nama_file>": {
                "deskripsi": "Menghapus video berdasarkan tanggal dan nama file dari GCS.",
                "header": {
                    "X-Key-Id": "Diperlukan untuk autentikasi HMAC",
                    "X-Timestamp": "Timestamp saat ini",
                    "X-Signature": "Tanda tangan HMAC-SHA256"
                }
            },
            "POST /videos/camera": {
                "deskripsi": "Memperbarui nilai 'pause' dan 'record' untuk mengontrol status kamera di Firestore.",
                "header": {
                    "X-Key-Id": "Diperlukan untuk autentikasi HMAC",
                    "X-Timestamp": "Timestamp saat ini",
                    "X-Signature": "Tanda tangan HMAC-SHA256"
                },
                "body": {
                    "pause": "Int/number untuk durasinya",
                    "record": "Int/number untuk durasinya"
                }
            },
            "GET /videos/camera": {
                "deskripsi": "Melihat durasi 'pause' dan 'record' kamera saat ini dari Firestore."
            }
        }
    }), 200

# Rute untuk mengupload video
@app.route('/videos', methods=['POST'])
def upload_video():
    # Verifikasi HMAC
    valid, resp, code = verify_request()
    if not valid:
        return resp, code

    # Memeriksa apakah file video ada
    if 'video' not in request.files:
        return jsonify({"error": "No video file provided"}), 400

    video_file = request.files['video']
    if video_file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    try:
        # Menyimpan file video dengan nama aman
        filename = secure_filename(video_file.filename)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        raw_output_filename = f"output_raw_{timestamp}.avi"
        compressed_filename = f"output_{timestamp}.mp4"
        today = datetime.now().strftime('%Y-%m-%d')
        gcs_output_path = f"{OUTPUT_FOLDER}/{today}/{compressed_filename}"

        # Simpan input dan output sementara
        with NamedTemporaryFile(delete=False, suffix=".avi") as temp_input:
            video_file.save(temp_input.name)
            input_path = temp_input.name

        with NamedTemporaryFile(delete=False, suffix=".avi") as temp_output:
            output_path = temp_output.name

        # Deteksi video menggunakan YOLO
        cap = cv2.VideoCapture(input_path)
        if not cap.isOpened():
            return jsonify({"error": "Failed to open video"}), 400

        fourcc = cv2.VideoWriter_fourcc(*'XVID')
        fps = cap.get(cv2.CAP_PROP_FPS)
        frame_size = (
            int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
            int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        )
        out = cv2.VideoWriter(output_path, fourcc, fps, frame_size)

        # Proses setiap frame video
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            results = model(frame)[0]
            for box in results.boxes:
                cls_id = int(box.cls.item())
                label = model.names[cls_id]
                if label == 'person':
                    x1, y1, x2, y2 = map(int, box.xyxy[0])
                    cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                    cv2.putText(frame, label, (x1, y1 - 10),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            out.write(frame)

        cap.release()
        out.release()

        # Kompres ulang dengan ffmpeg (AVI → MP4 dengan H.264 codec)
        compressed_path = output_path.replace(".avi", "_compressed.mp4")
        ffmpeg_cmd = [
            "ffmpeg",
            "-y",  # overwrite output if exists
            "-i", output_path,
            "-vcodec", "libx264",
            "-crf", "28",
            "-preset", "fast",
            compressed_path
        ]
        subprocess.run(ffmpeg_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)

        # Upload hasil ke GCS
        output_url = upload_to_gcs(compressed_path, gcs_output_path)

        # Hapus file sementara
        os.remove(input_path)
        os.remove(output_path)
        os.remove(compressed_path)

        return jsonify({
            "message": "Video processed and compressed successfully",
            "output_url": output_url
        }), 200

    except subprocess.CalledProcessError as ffmpeg_error:
        return jsonify({"error": "FFmpeg compression failed", "details": str(ffmpeg_error)}), 500

    except Exception as e:
        return jsonify({"error": f"Processing failed: {str(e)}"}), 500

# Rute untuk mendapatkan daftar video yang diproses
@app.route('/videos/list', methods=['GET'])
def get_videos_grouped_by_date():
    try:
        files = list_gcs_files(OUTPUT_FOLDER)
        result = {}

        # Mengelompokkan video berdasarkan tanggal
        for file in files:
            parts = file.split('/')
            if len(parts) >= 4:
                date = parts[3]
                url = f"https://storage.googleapis.com/{BUCKET_NAME}/{file}"
                result.setdefault(date, []).append(url)

        return jsonify({"videos_by_date": result}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Rute untuk mendapatkan daftar video berdasarkan tanggal
@app.route('/videos/list/<date>', methods=['GET'])
def list_videos_by_date(date):
    try:
        safe_date = secure_filename(date)  # amankan nama folder dari input user
        prefix = f"{OUTPUT_FOLDER}/{safe_date}/"  # tambahkan slash di akhir agar benar-benar ke folder
        files = list_gcs_files(prefix)
        urls = [f"https://storage.googleapis.com/{BUCKET_NAME}/{file}" for file in files]
        return jsonify({
            "date": safe_date,
            "count": len(urls),
            "videos": urls
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# Rute untuk menghapus video berdasarkan tanggal dan nama file
@app.route('/videos/<date>/<filename>', methods=['DELETE'])
def delete_video(date, filename):
    # Verifikasi HMAC
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
                dates.add(parts[3])  # Ambil bagian tanggal

        return jsonify(sorted(dates)), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Rute untuk memperbarui status kamera
@app.route('/videos/camera', methods=['POST'])
def update_duration():
    # Verifikasi HMAC
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
        # Memperbarui status kamera di Firestore
        doc_ref = db.collection('pillbox').document('camera')
        doc_ref.update({
            'pause': pause,
            'record': record
        })
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

# Menjalankan aplikasi Flask
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(debug=True, host='0.0.0.0', port=port)
