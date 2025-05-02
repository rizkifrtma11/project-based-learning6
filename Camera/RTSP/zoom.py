import cv2

# Fungsi untuk zoom gambar
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
