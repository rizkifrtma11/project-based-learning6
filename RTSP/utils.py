import cv2
import base64
import numpy as np

# Fungsi untuk encode frame ke format base64
def encode_frame(frame):
    _, buffer = cv2.imencode('.jpg', frame)
    jpg_as_text = base64.b64encode(buffer).decode('utf-8')
    return jpg_as_text

# Fungsi untuk decode frame dari base64
def decode_frame(encoded_str):
    img_data = base64.b64decode(encoded_str)
    np_arr = np.frombuffer(img_data, np.uint8)
    frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
    return frame
