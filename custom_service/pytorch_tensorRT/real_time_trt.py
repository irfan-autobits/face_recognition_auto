# from insightface.app import FaceAnalysis    
# from app import FaceAnalysis    
import time
from model_zoo import get_model
import numpy as np
from custom_service.insightface_bundle.verify_euclidean_dis import verify_identity
from app.models.model import Raw_Embedding, db
from flask import current_app      
from config.logger_config import cam_stat_logger , console_logger, exec_time_logger

from custom_service.insightface_bundle.recog_split import recognize_faces
from custom_service.insightface_bundle.silent_antispoof.real_time_antispoof import test
from config.Paths import MODELS_DIR, model_pack_name, INSIGHT_MODELS
spoof_dir = MODELS_DIR / "anti_spoof_models"
# Initialize the InsightFace app with detection and recognition modules.
# analy_app = FaceAnalysis(allowed_modules=['detection', 'recognition'])
print(f"using model pack {model_pack_name}")
# Paths for TRT and ONNX files.
trt_file = INSIGHT_MODELS / model_pack_name / "det_10g.trt"
onnx_file = INSIGHT_MODELS / model_pack_name / "det_10g.onnx"

# Load the detection model using get_model.
analy_app = get_model(str(model_pack_name), trt_file=str(trt_file))
if analy_app is None:
    raise RuntimeError("Failed to load detection model.")

# Prepare the model.
analy_app.prepare(ctx_id=0, det_size=(640, 640))


# def verification(input_embedding):
#     # Example usage with known embeddings from the database
#     with current_app.app_context():
#         embeddings = Raw_Embedding.query.all()
        
#         # List of known embeddings from the database (you need to format this appropriately)
#         known_embeddings = [{'subject_name': emb.subject_name, 'embedding': np.array(emb.embedding)} for emb in embeddings]
                
#         # Get the top 3 closest matches
#         matches = verify_identity(input_embedding, known_embeddings, top_n=1)
#         return matches

def formatter_trt(detection, keypoints, sub_nam, distance, spoof_res, elapsed_time=0):
    """
    Convert a TRT detection result to CompreFace format.
    
    Args:
        detection (np.ndarray): A 1D array [x1, y1, x2, y2, score].
        keypoints (np.ndarray): A 2D array of shape (5,2) with facial landmarks.
        sub_nam (str): The subject name.
        distance (float): Similarity/distance value.
        spoof_res (tuple): A tuple (spoof_flag, spoof_score, spoof_duration).
        elapsed_time (float): Execution time for detection.
        
    Returns:
        dict: A dictionary formatted in CompreFace style.
    """
    # Unpack detection values and cast coordinates to float
    x1, y1, x2, y2, score = map(float, detection[:5])
    
    # Unpack keypoints; we expect exactly 5 keypoints: left_eye, right_eye, nose, right_mouth, left_mouth
    if keypoints is not None and keypoints.shape[0] >= 5:
        landmarks = {
            "left_eye": [float(keypoints[0][0]), float(keypoints[0][1])],
            "right_eye": [float(keypoints[1][0]), float(keypoints[1][1])],
            "nose": [float(keypoints[2][0]), float(keypoints[2][1])],
            "right_mouth": [float(keypoints[3][0]), float(keypoints[3][1])],
            "left_mouth": [float(keypoints[4][0]), float(keypoints[4][1])],
        }
    else:
        landmarks = {}

    # Process spoof result tuple: (spoof_flag, spoof_score, spoof_duration)
    is_spoof = bool(spoof_res[0])
    spoof_score = float(spoof_res[1]) if spoof_res[1] is not None else 0.0
    spoof_dura = spoof_res[2] if spoof_res[2] is not None else 0.0

    # Build the output dictionary in CompreFace format.
    compreface_result = {
        "age": {
            "probability": None,  
            "high": None,
            "low": None,
            "value": None  # No age estimation here.
        },
        "gender": {
            "probability": None,  
            "value": None  # No gender estimation here.
        },
        "mask": {
            "probability": None,  
            "value": None
        },
        "embedding": [],  # Not provided here.
        "box": {
            "probability": score,  
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
        "landmark_3d_68": [],
        "spoof_res": {
            "is_spoof": is_spoof,
            "spoof_score": spoof_score,
            "spoof_dura": spoof_dura
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
    dets, kps = analy_app.detect(img)
    return dets, kps 

def run_trt(frame):
    # Run face detection and recognition

    # Step 1: Detect faces
    start_time = time.time()  # Start timing before reading the frame
    dets, kps = detect_faces(frame)
    frame_time = time.time() - start_time 
    exec_time_logger.debug(f"det {frame_time:.4f} seconds")    
    # print(f"Detected {len(detected_faces)} faces.")

    # Step 2: Recognize faces
    # Step 1: Detect faces
    # start_time = time.time()  # Start timing before reading the frame
    # recognized_faces = recognize_faces(frame, detected_faces, mode='local') # remote
    # frame_time = time.time() - start_time 
    # exec_time_logger.debug(f"rec {frame_time:.4f} seconds")      
    # print(f"rec {recognized_faces}")
    compreface_results = []
    # For each detected face, store the embedding in the DB
    if dets is not None:
        for i in range(dets.shape[0]):
            # spoof_res = test(frame, face.bbox, str(spoof_dir), 0)
            spoof_res = [False, 0.0, 0.0]

            # embedding = face.embedding  # Expected to be a numpy array
            # if embedding is None:
            #     print("no embedding generated")
            #     continue
            # matches = verification(embedding)

            # # Ensure matches exist before accessing
            # if not matches:
            #     print("No match found")
            #     continue  # Skip to the next face
            # # print(f"faces {face}")
            
            compreface_result = formatter_trt(dets[i], kps[i], "Unknown", "100", spoof_res, elapsed_time=0)
            compreface_results.append(compreface_result)

    return compreface_results
