# final-compre/integrations/custom_service.py
# from custom_service.main_run import yunet_detect, find_faces_post, init_model, RetinaFace_detect
from custom_service.main_run import insightface_buffalo
# from custom_service.main_run import tensorrt_buffalo
from config.paths import IS_RECOGNIZE
from config.state import model_lock

def cutm_integ(frame):
    with model_lock:
        if IS_RECOGNIZE:
            # results = yunet_detect(frame)
            # results = RetinaFace_detect(frame)
            # results = find_faces_post(frame)
            results = insightface_buffalo(frame)
            # results = tensorrt_buffalo(frame)
        else:
            results = None
        return results