# final-compre/app/processors/face_detection.py
# from integrations.Compre_Api import compreface_api
import cv2
from integrations.custom_service import cutm_integ
from app.processors.frame_draw import Drawing_on_frame
from app.processors.Save_Face import save_image
# from app.processors.emb_viz import visulize
from app.models.model import db, Detection
from config.Paths import FACE_REC_TH
from config.logger_config import cam_stat_logger , console_logger, exec_time_logger
from datetime import datetime
import timeit
import time
import psutil
import ctypes

class FaceDetectionProcessor:
    def __init__(self, camera_sources, db_session, app):
        self.camera_sources = camera_sources
        self.db_session = db_session
        self.app = app  # Store the Flask app instance
        self.max_call_counter = 1000
        self.call_counter = 0        

        # Load libc for malloc_trim
        self.libc = ctypes.CDLL("libc.so.6")    

    def process_frame(self, frame, cam_name):
        # results = compreface_api(frame)
        results = cutm_integ(frame)

        self.call_counter += 1  # Increment call counter

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
                if probability <= 0.57:
                    continue
                subject = result.get('subjects')[0]['subject']
                similarity = result.get('subjects')[0]['similarity']
                # execution_time = result.get('execution_time')
                # detector_time = execution_time['detector']
                # calc_time = execution_time['calculator']
                # embedding = result.get('embedding')
                is_unknown = False
                # if similarity >= float(FACE_REC_TH):
                # if probability > 0.57:
                if similarity <= 1.17:
                    color = (0, 255, 0)  # Green color for text                        
                else:
                    color = (0, 0, 255)
                    subject = f"Un_{subject}"
                    is_unknown = True

                # exec_time_logger.debug(f"detection - {detector_time/1000},calc - {calc_time/1000} camera :{cam_name} for {len(results)} result")

                # visulize(embedding)
                frame = Drawing_on_frame(frame, box, landmarks, landmark_3d_68, subject, color, probability, spoof_res, similarity, draw_lan=False)  
                # face_path = save_image(frame, cam_name, box, subject, similarity, is_unknown)
                # # Use the app context explicitly
                # with self.app.app_context():
                #     detection = Detection(
                #         camera_name=cam_name, 
                #         det_face=face_path,
                #         det_score=probability * 100,
                #         person = subject, 
                #         similarity=similarity,
                #         timestamp=datetime.now()
                #     )
                #     self.db_session.add(detection)
                #     self.db_session.commit()

                #     # Commit every 10 detections
                #     if len(self.db_session.new) % 10 == 0:
                #         self.db_session.commit()
        else:
            # print("no results")
            pass

        return frame
