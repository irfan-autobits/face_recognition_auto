# final-compre/app/processors/face_detection.py
# from integrations.Compre_Api import compreface_api
import cv2
import pytz
from integrations.custom_service import cutm_integ
from app.processors.frame_draw import drawing_on_frame
from app.processors.save_face import save_image
# from app.processors.emb_viz import visulize
from app.models.model import db, Detection, Subject, Camera, Detection
from config.paths import FACE_REC_TH, FACE_DET_TH
from config.logger_config import cam_stat_logger , console_logger, exec_time_logger, det_logger
from datetime import datetime
import timeit
import time
import psutil
import ctypes
from config.paths import IS_GEN_REPORT

class FaceDetectionProcessor:
    def __init__(self, db_session, app):
        # self.camera_sources = camera_sources
        self.db_session = db_session
        self.app = app  # Store the Flask app instance
        self.max_call_counter = 1000
        self.call_counter = 0        

        # Load libc for malloc_trim
        self.libc = ctypes.CDLL("libc.so.6")    

    def process_frame(self, frame, cam_name):
        # results = compreface_api(frame)
        results = cutm_integ(frame)
        # details = self.camera_sources.get(cam_name)
        # cam_tag = details.get("tag")
        self.call_counter += 1  # Increment call counter
        cv2.putText(frame, "sample_text", (20, 20),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        # Memory cleanup
        if self.call_counter % self.max_call_counter == 0:
            process = psutil.Process()  # Get current process
            mem_before = process.memory_info().rss  # Resident Set Size (RSS) in bytes
            # self.libc.malloc_trim(0)  # Force memory release
            mem_after = process.memory_info().rss  # Check memory after cleanup
            freed_memory = mem_before - mem_after  # Calculate freed memory
            print(f"Memory cleanup done. Freed: {freed_memory / (1024 * 1024):.2f} MB")
            self.call_counter = 0  # Reset counter  

        # time_taken = timeit.timeit(lambda: compreface_api(frame), number=1)  # Execute 10 times
        # exec_time_logger.debug(f"compreface api Execution time: {time_taken / 10:.5f} seconds per run")
        if results:            
            # print("got res")
            for result in results:
                box = result.get('box')
                landmarks = result.get('landmarks')
                landmark_3d_68 = result.get("landmark_3d_68")
                spoof_res = result.get("spoof_res")
                # print(f"spoof res : {spoof_res}")

                probability = box['probability']
                if probability <= float(FACE_DET_TH): 
                    continue
                subject = result.get('subjects')[0]['subject']
                distance = result.get('subjects')[0]['similarity']
                # execution_time = result.get('execution_time')
                # detector_time = execution_time['detector']
                # calc_time = execution_time['calculator']
                # embedding = result.get('embedding')
                is_unknown = False
                # if similarity >= float(FACE_REC_TH):
                # if distance <= 1.17:
                if distance <= float(FACE_REC_TH):
                    color = (0, 255, 0)  # Green color for text                        
                else:
                    color = (0, 0, 255)
                    subject = f"Un_{subject}"
                    is_unknown = True

                # exec_time_logger.debug(f"detection - {detector_time/1000},calc - {calc_time/1000} camera :{cam_name} for {len(results)} result")

                # visulize(embedding)
                frame = drawing_on_frame(frame, box, landmarks, landmark_3d_68, subject, color, probability, spoof_res, distance, draw_lan=False)  
                if IS_GEN_REPORT:
                    face_path = save_image(frame, cam_name, box, subject, distance, is_unknown)
                    face_url = f"http://localhost:5757/faces/{face_path}"
                    # Use the app context explicitly
                    with self.app.app_context():
                        subj = Subject.query.filter_by(subject_name=subject).first()
                        cam  = Camera.query.filter_by(camera_name=cam_name).first()
                        if not cam:
                                det_logger.error(f"Couldn't find Camera({cam_name})")
                        else :
                            det = Detection(
                                subject_id=subj.id if subj else None,
                                camera_id=cam.id,
                                det_score=probability * 100,
                                distance=distance,
                                timestamp=datetime.now(pytz.utc),
                                det_face=face_url
                            )
                            self.db_session.add(det)
                            self.db_session.commit()                            
                        # # Commit every 10 detections
                        # if len(self.db_session.new) % 10 == 0:
                        #     self.db_session.commit()
        else:
            # print("no results")
            pass

        return frame
