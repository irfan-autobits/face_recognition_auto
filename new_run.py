# run.py
from app.services.processing_service import ProcessingService
from app.services.camera_manager import camera_service
import json
import threading
import traceback
from flask import Flask
from flask_socketio import SocketIO, emit
import cv2
import base64
import torch
# import nvtx
from config.paths import cam_sources
from config.state import frame_lock, vs_lock
import config.state as state
from config.logger_config import cam_stat_logger , console_logger, exec_time_logger
from config.config import Config
from app.routes.route import bp as video_feed_bp
from app.models.model import db, Detection, Camera
from scripts.manage_db import manage_table
from app.processors.face_detection import FaceDetectionProcessor
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

CORS(app, resources={r"/*": {"origins": "*"}})
socketio = SocketIO(app, cors_allowed_origins="*")
db.init_app(app)

with app.app_context():
    manage_table(drop=True)
    # read your env‑provided dict exactly once, then forget cam_sources
    camera_service.bootstrap_from_env(cam_sources)

face_processor = FaceDetectionProcessor(db.session, app)
processing     = ProcessingService(app, face_processor, max_workers=4)

def send_frame():
    FPS = 1/25
    log_interval = float('inf')
    frame_count = defaultdict(int)

    while True:
        with frame_lock:
            # get a thread‑safe snapshot
            for cam_name, vs in camera_service.streams.items():
                raw = vs.read()
                frame_count[cam_name] += 1
                if raw is None:
                    continue

                # only process 50% of frames:
                # if frame_count[cam_name] % 6 < 3:
                processing.submit(cam_name, raw, emit_frame)

        socketio.sleep(FPS)

def emit_frame(cam_name, frame):
    """Called in worker callback; must re-enter SocketIO context."""
    socketio.start_background_task(_emit, cam_name, frame)

def _emit(cam_name, frame):
    with state.active_camera_lock:
        if state.active_camera != cam_name: return
    _, buf = cv2.imencode('.jpg', frame)
    b64   = base64.b64encode(buf).decode('utf-8')
    socketio.emit('frame', {'camera_name': cam_name, 'image': b64})

if __name__ == '__main__':
    socketio.start_background_task(send_frame)
    socketio.run(app, host='0.0.0.0', port=5757)
