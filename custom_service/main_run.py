import traceback
from flask import jsonify
import numpy as np
from custom_service.yunet_detection import FaceDetectorYunet, convert_yunet_to_compreface
from config.paths import MODELS_DIR
from config.logger_config import cam_stat_logger , console_logger, exec_time_logger, det_logger

from custom_service.insightface_bundle.real_time_buffalo import run_buffalo 
# from custom_service.pytorch_tensorRT.real_time_trt import run_trt

def yunet_detect(frame):
    yunet_detect = MODELS_DIR / "face_detection_yunet_2023mar.onnx"

    face_detector = FaceDetectorYunet(model_path=str(yunet_detect), img_size=(300, 300), threshold=0.5)

    try:
        faces = face_detector.detect(frame)
        # frame = face_detector.draw_faces(frame, faces, draw_landmarks=False, show_confidence=True)
        compreface_results = convert_yunet_to_compreface(faces)
    except Exception as e:
        print(e)
        compreface_results = []

    return compreface_results
         
def insightface_buffalo(frame):
    try:
        compreface_results = run_buffalo(frame)
    except Exception as e:
        print(e)
        traceback.print_exc() 

        compreface_results = []   
    return compreface_results

# def tensorrt_buffalo(frame):
#     try:
#         compreface_results = run_trt(frame)
#     except Exception as e:
#         print(e)
#         traceback.print_exc() 

#         compreface_results = []   
#     return compreface_results    
    