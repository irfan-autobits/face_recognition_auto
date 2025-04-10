# custom_service/insightface_bundle/real_time_buffalo.py
import time
from insightface.app import FaceAnalysis
import numpy as np
from custom_service.insightface_bundle.verify_euclidean_dis import verify_identity
from app.models.model import Embedding, db
from flask import current_app      
from config.logger_config import cam_stat_logger , console_logger, exec_time_logger

from custom_service.insightface_bundle.recog_split import recognize_faces
from custom_service.silent_antispoof.real_time_antispoof import test
from config.Paths import MODELS_DIR, model_pack_name
spoof_dir = MODELS_DIR / "anti_spoof_models"
# Initialize the InsightFace app with detection and recognition modules.
# analy_app = FaceAnalysis(allowed_modules=['detection', 'recognition'])
print(f"using model pack {model_pack_name}")
analy_app = FaceAnalysis(name=model_pack_name ,allowed_modules=['detection', 'landmark_3d_68'])
analy_app.prepare(ctx_id=0, det_size=(640, 640))

def verification(input_embedding):
    # Example usage with known embeddings from the database
    with current_app.app_context():
        embeddings = Embedding.query.all()
        
        # Now access the subject name through the relationship: emb.subject.subject_name
        known_embeddings = [{
            'subject_name': emb.subject.subject_name,
            'embedding': np.array(emb.embedding)
        } for emb in embeddings]
                
        # Get the top 1 closest match
        matches = verify_identity(input_embedding, known_embeddings, top_n=1)
        return matches

def formatter(face, sub_nam, distance, spoof_res, elapsed_time=0):
    
    bbox = face.bbox
    landms = face.kps
    confidence = face.det_score
    age = face.age if hasattr(face, "age") else None
    gender = face.gender if hasattr(face, "gender") else None
    embedding = face.embedding.tolist() if getattr(face, "embedding", None) is not None else []
    landmark_3d_68 = face.landmark_3d_68 if getattr(face, "landmark_3d_68", None) is not None else []
    is_spoof = True if spoof_res[0] else False
    spoof_score = float(spoof_res[1]) if spoof_res[1] else 0.0
    spoof_dura = spoof_res[2] if spoof_res[2] else 0.0


    # Ensure bbox values are floats for precision
    x1, y1, x2, y2 = map(float, bbox[:4])  

    # Ensure landmarks exist before accessing
    if landms is not None and len(landms) >= 5:
        landmarks = {
            "left_eye": [float(landms[0][0]), float(landms[0][1])],
            "right_eye": [float(landms[1][0]), float(landms[1][1])],
            "nose": [float(landms[2][0]), float(landms[2][1])],
            "right_mouth": [float(landms[3][0]), float(landms[3][1])],
            "left_mouth": [float(landms[4][0]), float(landms[4][1])],
        }
    else:
        landmarks = {}

    # Format output in CompreFace format
    compreface_result = {
        "age": {
            "probability": None,  
            "high": None,
            "low": None,
            "value": age
        },
        "gender": {
            "probability": None,  
            "value": gender
        },
        "mask": {
            "probability": None,  
            "value": None
        },
        "embedding": embedding,  
        "box": {
            "probability": float(confidence),  
            "x_min": int(x1),
            "y_min": int(y1),
            "x_max": int(x2),
            "y_max": int(y2)
        },
        "landmarks": [
            landmarks.get("left_eye", []),
            landmarks.get("right_eye", []),
            landmarks.get("nose", []),
            landmarks.get("right_mouth", []),
            landmarks.get("left_mouth", [])
        ],
        "landmark_3d_68" : landmark_3d_68,
        "spoof_res": {
            "is_spoof" :is_spoof,
            "spoof_score":spoof_score,
            "spoof_dura":spoof_dura
        },
        "subjects": [
            { "subject": sub_nam, "similarity": distance }
        ],  
        "execution_time": {
            "age": None,
            "gender": None,
            "detector": elapsed_time,
            "calculator": None,
            "mask": None
        }
    }

    return compreface_result

def detect_faces(img):
    """
    Runs face detection only (without recognition).
    Returns a list of detected face objects.
    """
    faces = analy_app.get(img, max_num=0)  # Runs both detection and recognition by default
    return faces

def run_buffalo(frame):
    # Run face detection and recognition

    # Step 1: Detect faces
    start_time = time.time()  # Start timing before reading the frame
    detected_faces = detect_faces(frame)
    frame_time = time.time() - start_time 
    # exec_time_logger.debug(f"det {frame_time:.4f} seconds")    
    # print(f"Detected {len(detected_faces)} faces.")

    # Step 2: Recognize faces
    # Step 1: Detect faces
    start_time = time.time()  # Start timing before reading the frame
    recognized_faces = recognize_faces(frame, detected_faces, mode='local') # remote
    frame_time = time.time() - start_time 
    # exec_time_logger.debug(f"rec {frame_time:.4f} seconds")      
    # print(f"rec {recognized_faces}")
    compreface_results = []
    # For each detected face, store the embedding in the DB
    if recognized_faces is not None:
        for face in recognized_faces:
            # spoof_res = test(frame, face.bbox, str(spoof_dir), 0)
            spoof_res = [False, 0.0, 0.0]

            embedding = face.embedding  # Expected to be a numpy array
            if embedding is None:
                print("no embedding generated")
                continue
            matches = verification(embedding)

            # Ensure matches exist before accessing
            if not matches:
                print("No match found")
                continue  # Skip to the next face
            # print(f"faces {face}")
            compreface_result = formatter(face, matches[0]["subject_name"], matches[0]["distance"], spoof_res, elapsed_time=0)
            compreface_results.append(compreface_result)

    return compreface_results
