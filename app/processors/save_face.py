# final-compre/app/processors/save_face.py
from pathlib import Path
import cv2
from datetime import datetime
from threading import Lock
from config.paths import FACE_DIR  # Assume FACE_DIR is a Path object
from config.logger_config import det_logger 

def save_image(frame, cam_id, box, subject, distance, is_unknown):
    """Save the detected face as an image file and return its relative path."""
    lock = Lock()
    face_dir = FACE_DIR  # FACE_DIR should be defined as your base folder for faces
    
    # Create a timestamp string
    timestamp = datetime.now().strftime('%y%m%d-%H:%M:%S-%f')[:-4]
    
    with lock:
        face_image = frame[box['y_min']:box['y_max'], box['x_min']:box['x_max']]
    
    if face_image is None or face_image.size == 0:
        print("Error: face_image is empty!")
        return "None_img"
    
    # Create a file name for the saved face image
    face_image_name = f"{distance}_{subject}_{cam_id}_{timestamp}_.jpg"
    
    # Determine the directory for the subject
    if is_unknown:
        subject_dir = face_dir / "Unknown"
    else:
        subject_dir = face_dir / subject
    subject_dir.mkdir(parents=True, exist_ok=True)
    
    # Save the image file
    face_image_path = subject_dir / face_image_name
    cv2.imwrite(str(face_image_path), face_image)
    
    # Return the relative path with respect to FACE_DIR.
    # This might look like "subject/filename.jpg" or "Unknown/filename.jpg"
    relative_path = face_image_path.relative_to(face_dir)
    # Log the full image path for debugging purposes
    # det_logger.info(str(relative_path))
    
    return str(relative_path)
