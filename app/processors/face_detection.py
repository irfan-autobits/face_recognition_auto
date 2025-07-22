# app/processors/face_detection.py
import cv2
import pytz
import time
from collections import defaultdict
from flask import current_app
from integrations.custom_service import cutm_integ
from app.processors.frame_draw import drawing_on_frame
from app.processors.save_face import save_image
from app.models.model import db, Detection, Subject, Camera, Detection
from config.paths import FACE_REC_TH, FACE_DET_TH
from config.logger_config import cam_stat_logger, console_logger, exec_time_logger, det_logger
from datetime import datetime
import timeit
import psutil
import ctypes
from config.paths import IS_GEN_REPORT, SKIP_FRAME_CYCLE, AI_PROCESS_FRAMES, DETECTION_OVERLAY_OPTION

class FaceDetectionProcessor:
    def __init__(self, db_session, app):
        self.db_session = db_session
        self.app = app
        self.max_call_counter = 1000
        self.call_counter = 0
        
        # Load libc for malloc_trim
        self.libc = ctypes.CDLL("libc.so.6")
        
        # NEW: Frame skipping configuration
        self.frame_cycle = SKIP_FRAME_CYCLE            # Total frames in cycle 10
        self.process_frames = AI_PROCESS_FRAMES        # Process AI on first N frames of each cycle 2
        self.overlay_option = DETECTION_OVERLAY_OPTION # 1 = show last drawings, 2 = clean frames
        
        # Per-camera frame counting and caching
        self.frame_counts = defaultdict(int)
        self.last_ai_results = defaultdict(lambda: None)
        self.last_ai_timestamp = defaultdict(float)
        
        # FPS calculation (for AI processing only)
        self.fps_data = defaultdict(lambda: {
            'ai_processed_count': 0,
            'ai_start_time': time.time(),
            'last_fps_calc': time.time(),
            'current_fps': 0.0
        })
        
        exec_time_logger.info(
            f"FaceDetectionProcessor initialized with frame skipping: "
            f"{self.process_frames}/{self.frame_cycle} frames"
        )

    def process_frame(self, frame, cam_name):
        """Main processing method with built-in frame skipping"""
        
        # Increment frame counter
        self.frame_counts[cam_name] += 1
        
        # Decide if we should do AI processing (your original style)
        should_process_ai = self.frame_counts[cam_name] % self.frame_cycle < self.process_frames
        
        if should_process_ai:
            # Do AI processing
            return self._process_with_ai(frame, cam_name)
        else:
            # Skip AI, handle according to overlay option
            return self._process_without_ai(frame, cam_name)
    
    def _process_with_ai(self, frame, cam_name):
        """Process frame with AI detection (expensive)"""
        
        # AI processing with timing
        ai_start = time.time()
        results = cutm_integ(frame)
        ai_time = time.time() - ai_start
        
        # Update FPS calculation
        self._update_fps_stats(cam_name, ai_time)
        
        # Memory cleanup (your existing logic) not doing it right now
        # self.call_counter += 1
        # if self.call_counter % self.max_call_counter == 0:
        #     process = psutil.Process()  # Get current process
        #     mem_before = process.memory_info().rss  # Resident Set Size (RSS) in bytes
        #     self.libc.malloc_trim(0)  # Force memory release
        #     mem_after = process.memory_info().rss  # Check memory after cleanup
        #     freed_memory = mem_before - mem_after  # Calculate freed memory
        #     print(f"Memory cleanup done. Freed: {freed_memory / (1024 * 1024):.2f} MB")
        #     self.call_counter = 0
        
        # Cache AI results for non-processed frames
        if results:
            self.last_ai_results[cam_name] = results
            self.last_ai_timestamp[cam_name] = time.time()
        
        # Process and draw results
        processed_frame = self._apply_results_to_frame(frame, results, cam_name)
        
        # Periodic logging with FPS info
        if self.frame_counts[cam_name] % 50 == 0:
            fps_info = self.fps_data[cam_name]
            exec_time_logger.info(
                f"[{cam_name}] Frame {self.frame_counts[cam_name]} | "
                f"AI FPS: {fps_info['current_fps']:.1f} | "
                f"AI Time: {ai_time:.3f}s"
            )
        
        return processed_frame
    
    def _process_without_ai(self, frame, cam_name):
        """Process frame without AI (use cached results or clean frame)"""
        
        if self.overlay_option == 2:
            # Option 2: Return clean frame (no drawings)
            return frame
        
        # Option 1: Use last AI results if available and recent
        last_results = self.last_ai_results[cam_name]
        
        if (last_results and 
            (time.time() - self.last_ai_timestamp[cam_name]) < 2.0):
            # Apply last AI results to current frame
            return self._apply_results_to_frame(frame, last_results, cam_name, is_cached=True)
        else:
            # No recent AI results, return clean frame
            return frame
    
    def _apply_results_to_frame(self, frame, results, cam_name, is_cached=False):
        """Apply AI results to frame using existing drawing logic"""
        
        if not results:
            return frame
        
        processed_frame = frame.copy()
        
        # Your existing processing logic (unchanged)
        for result in results:
            box = result.get('box')
            landmarks = result.get('landmarks')
            landmark_3d_68 = result.get("landmark_3d_68")
            spoof_res = result.get("spoof_res")

            probability = box['probability']
            if probability <= float(FACE_DET_TH): 
                continue
                
            subject = result.get('subjects')[0]['subject']
            distance = result.get('subjects')[0]['similarity']
            
            is_unknown = False
            if distance <= float(FACE_REC_TH):
                color = (0, 255, 0)  # Green
            else:
                color = (0, 0, 255)  # Red
                is_unknown = True

            # Use your existing drawing function
            processed_frame = drawing_on_frame(
                processed_frame, box, landmarks, landmark_3d_68, 
                subject, color, probability, spoof_res, distance, is_unknown, draw_lan=False
            )
            
            # Save image and database operations (only for fresh AI results, not cached)
            if IS_GEN_REPORT and not is_cached:
                face_path = save_image(processed_frame, cam_name, box, subject, distance, is_unknown)
                face_url = f"{current_app.config['SERV_HOST']}:{current_app.config['PORT']}/faces/{face_path}"
                
                with self.app.app_context():
                    if not is_unknown:
                        subj = Subject.query.filter_by(subject_name=subject).first()
                    else:
                        subj = None  # This will store NULL in the subject foreign key column in Postgres
                    cam = Camera.query.filter_by(camera_name=cam_name).first()
                    det = Detection(
                        subject=subj,
                        camera=cam,
                        det_score=probability * 100,
                        distance=distance,
                        det_face=face_url
                    )
                    self.db_session.add(det)
                    self.db_session.commit()
                           
                    # # Commit every 10 detections
                    # if len(self.db_session.new) % 10 == 0:
                    #     self.db_session.commit()
        return processed_frame
    
    def _update_fps_stats(self, cam_name, processing_time):
        """Update FPS calculation for AI processing"""
        fps_info = self.fps_data[cam_name]
        fps_info['ai_processed_count'] += 1
        
        current_time = time.time()
        
        # Calculate FPS every 5 seconds
        if current_time - fps_info['last_fps_calc'] >= 5.0:
            elapsed = current_time - fps_info['ai_start_time']
            if elapsed > 0:
                fps_info['current_fps'] = fps_info['ai_processed_count'] / elapsed
            fps_info['last_fps_calc'] = current_time
    
    def get_ai_fps_stats(self):
        """Get AI processing FPS for all cameras"""
        stats = {}
        for cam_name, fps_info in self.fps_data.items():
            total_frames = self.frame_counts[cam_name]
            ai_processed = fps_info['ai_processed_count']
            
            stats[cam_name] = {
                'total_frames': total_frames,
                'ai_processed_frames': ai_processed,
                'ai_fps': fps_info['current_fps'],
                'processing_ratio': f"{ai_processed}/{total_frames} ({(ai_processed/total_frames*100):.1f}%)" if total_frames > 0 else "0%",
                'skip_config': f"{self.process_frames}/{self.frame_cycle}"
            }
        
        return stats
    
    def set_overlay_option(self, option):
        """Change overlay option: 1 = last_drawings, 2 = clean_frames"""
        self.overlay_option = option
        mode = 'last_drawings' if option == 1 else 'clean_frames'
        exec_time_logger.info(f"Overlay option changed to: {mode}")
    
    def set_frame_skip_config(self, frame_cycle, process_frames):
        """Change frame skipping configuration"""
        self.frame_cycle = frame_cycle
        self.process_frames = process_frames
        exec_time_logger.info(f"Frame skip config updated: {process_frames}/{frame_cycle}")
