# app/services/processing_service.py
from concurrent.futures import ThreadPoolExecutor
import os
import time
from functools import partial
from config.logger_config import exec_time_logger

class ProcessingService:
    def __init__(self, app, face_processor, max_workers=4):
        self.app = app
        self.face_processor = face_processor
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.futures = {}
        self.last_processed = {}  # Tracks last processing time per camera
        self.MIN_PROCESS_INTERVAL = 0.1  # 100ms between frames per camera

    def submit(self, cam_name, frame, callback):
        now = time.monotonic()
        last_ts = self.last_processed.get(cam_name, 0)
        
        # Skip if: within interval OR existing pending future
        if (now - last_ts < self.MIN_PROCESS_INTERVAL) or \
           (self.futures.get(cam_name) and not self.futures[cam_name].done()):
            return
        
        fut = self.executor.submit(self._do_processing, cam_name, frame)
        self.futures[cam_name] = fut
        self.last_processed[cam_name] = now
        fut.add_done_callback(partial(self._done, cam_name, callback=callback))

    def _do_processing(self, cam_name, frame):
        with self.app.app_context():
            start = time.time()
            out = self.face_processor.process_frame(frame, cam_name)
            exec_time_logger.debug(f"Processed {cam_name} in {time.time()-start:.3f}s")
            return out

    def _done(self, cam_name, future, callback):
        if future.cancelled():
            return
        exc = future.exception()
        if exc:
            exec_time_logger.error(f"Error in {cam_name} processing: {exc}")
            return
        processed = future.result()
        callback(cam_name, processed)