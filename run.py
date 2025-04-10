# run.py
import json
import threading
import traceback
from flask import Flask
from flask_socketio import SocketIO, emit
import cv2
import base64
import torch
# import nvtx
from config.Paths import frame_lock, cam_sources, vs_list
import config.Paths as paths
from config.logger_config import cam_stat_logger , console_logger, exec_time_logger
from config.config import Config
from app.routes.Route import bp as video_feed_bp, active_cameras
from app.models.model import db, Detection, Camera_list
from scripts.manage_db import manage_table, import_tab
from app.processors.face_detection import FaceDetectionProcessor
from app.services.camera_manager import Default_cameras
from flask_cors import CORS
import time
from collections import defaultdict

def create_app():
    app = Flask(__name__, template_folder='app/templates')  # Specify template folder
    app.config.from_object(Config)
    
    # Register blueprint
    app.register_blueprint(video_feed_bp, url_prefix='/')
    return app

app = create_app()

# Enable CORS for all routes, including SocketIO
# CORS(app, origins=["http://localhost:3000"])
CORS(app, resources={r"/*": {"origins": "*"}})  # Adjust the wildcard "*" to specific origins for better security.

# Initialize Flask-SocketIO
socketio = SocketIO(app, cors_allowed_origins="*", ping_interval=10, ping_timeout=30)

# Initialize the database
db.init_app(app)

# add default camera
with app.app_context():
    manage_table(spec = True) # drop all tables
    db_url = app.config['SQLALCHEMY_DATABASE_URI']
    print(f"dburl: {db_url}")
    # import_tab(db_url)
    responce, status = Default_cameras()

face_processor = FaceDetectionProcessor(cam_sources, db.session, app)

def send_frame():
    FPS = 1 / 25  # 30 FPS
    log_interval = 25
    frame_count = defaultdict(int)
    last_frame_time = defaultdict(lambda: time.time())   
    start_time = defaultdict(lambda: time.time())   
    frame_time = defaultdict(lambda: time.time())   
    is_compre = True 
    """function to send frames to the client from all cameras"""
    try:
        with app.app_context():  # Explicitly create an app context
            while True:
                with frame_lock:  # Ensure thread-safe access
                    for cam_name, vs in list(vs_list.items()):  # Create a list to avoid runtime changes
                        frame = vs.read()                            
                        # frame cal
                        # if frame_count[cam_name] % log_interval == 0:
                        #     current_time = time.time()
                        #     time_diff = current_time - last_frame_time[cam_name]
                        #     fps = 1 / time_diff if time_diff > 0 else 0
                        #     last_frame_time[cam_name] = current_time 
                            
                            # exec_time_logger.debug(f"took {time_diff:.4f} seconds with compreface as :{is_compre} for camera {cam_name}")
                        frame_count[cam_name] += 1
                        if frame is not None:
                            if frame_count[cam_name] % log_interval == 0:
                                cam_stat_logger.debug(f"Processed {frame_count[cam_name]} frames from camera {cam_name}")
                            if frame_count[cam_name] % 6 < 3 and is_compre:
                                start_time[cam_name] = time.time()  # Start timing before reading the frame
                                
                                # with torch.profiler.profile(activities=[torch.profiler.ProfilerActivity.CUDA]) as prof:
                                    # torch.cuda.nvtx.range_push(f"Processing frame for {cam_name}")
                                frame = face_processor.process_frame(frame, cam_name)
                                    # torch.cuda.nvtx.range_pop()
                                    
                                # print(prof.key_averages().table(sort_by="cuda_time_total"))                                 
                                frame_time[cam_name] = time.time() - start_time[cam_name] 
                                exec_time_logger.debug(f"took {frame_time[cam_name]:.4f} seconds for camera {cam_name}")

                                # At the beginning of processing, read the active camera safely:
                                # At the beginning of processing, read the active camera safely:
                                with paths.active_camera_lock:
                                    current_active_camera = paths.active_camera
                                if cam_name == current_active_camera:
                                    print(f"emitting for {cam_name}")
                                    if frame_count[cam_name] % 3 == 0:
                                        cam_stat_logger.debug(f"emmitting frames for camera {cam_name}")
                                    # Now, only emit if this camera is active
                                    _, buffer = cv2.imencode('.jpg', frame)
                                    frame_data = base64.b64encode(buffer).decode('utf-8')
                                    socketio.emit('frame', {'camera_name': cam_name, 'image': frame_data})
                                    
                                else:
                                    # Optionally, you might emit a placeholder or simply skip
                                    pass                            
                        else:
                            if frame_count[cam_name] % log_interval == 0:
                                cam_stat_logger.warning(f"No frame read from camera {cam_name} after {frame_count[cam_name]} attempts ")
                            socketio.emit('frame', {'camera_name': cam_name})
                socketio.sleep(FPS)     
    except Exception as e:
        cam_stat_logger.error(f"Error in send_frame: {e}")
        socketio.emit('error', {'error': str(e)})
        print("An error occurred:")
        traceback.print_exc() 

if __name__ == '__main__':
    with app.app_context():
        # Ensure the table exists before starting the application
        socketio.start_background_task(send_frame)  # Start the thread within app context
    socketio.run(app, host='0.0.0.0', port=5757, debug=False)
