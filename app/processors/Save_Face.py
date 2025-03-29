# final-compre/app/processors/Save_Face.py
from pathlib import Path
import cv2
from datetime import datetime
from threading import Lock
from config.Paths import FACE_DIR
from config.logger_config import det_logger 

def save_image(frame, cam_id, box, subject, similarity, is_unknown):
    """ Save the detected face as an image file """
    lock = Lock()
    face_dir = FACE_DIR  # Assuming FACE_DIR is already a Path object

    timestamp = datetime.now().strftime('%y%m%d-%H:%M:%S-%f')[:-4]
    with lock:
        face_image = frame[box['y_min']:box['y_max'], box['x_min']:box['x_max']]

    if face_image is None or face_image.size == 0:
        print("Error: face_image is empty!")
        return "None_img"
    face_image_name = f"{similarity}_{subject}_{cam_id}_{timestamp}_.jpg"

    # Create a directory for the subject if it doesn't exist
    if is_unknown:
        subject_dir = face_dir / "Unknown"
    else:
        subject_dir = face_dir / subject
    subject_dir.mkdir(parents=True, exist_ok=True)

    # Save the face image
    face_image_path = subject_dir / face_image_name
    cv2.imwrite(str(face_image_path), face_image)

    # Log the saved face image path
    det_logger.info(str(face_image_path))

    return str(face_image_path)
