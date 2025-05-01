# app/app_setup.py
import cv2
from flask import Flask
from config.config import Config
from app.routes import bp as route_blueprint 
from app.models.model import db
import threading
from collections import defaultdict
import time
from config.state import frame_lock
from app.services.camera_manager import camera_service
from app.extensions import socketio

def create_app():
    app = Flask(__name__, template_folder='app/templates')  # Specify template folder
    app.config.from_object(Config)

    # Register blueprint
    app.register_blueprint(route_blueprint, url_prefix='/')

    return app

def send_frame(processing):
    FPS = 1/25
    log_interval   = float('inf')
    frame_count    = defaultdict(int)
    failure_counts = defaultdict(int)
    MAX_FAILURES   = 10

    while True:
        with frame_lock:
            for cam_name, vs in camera_service.streams.items():
                raw = vs.read()
                if raw is None:
                    # Increment a “miss” counter
                    failure_counts[cam_name] += 1

                    # If too many misses, assume dead → tear down
                    if failure_counts[cam_name] >= MAX_FAILURES:
                        camera_service.handle_unexpected_stop(cam_name)
                        failure_counts[cam_name] = 0
                    continue

                # Got a frame → reset failure counter
                failure_counts[cam_name] = 0

                # 2️⃣ Still run your face‐detection in background
                processing.submit(cam_name, raw, emit_frame)
        socketio.sleep(FPS)

def emit_frame(cam_name, frame):
    # debug: call _emit synchronously instead of via start_background_task
    socketio.start_background_task(_emit, cam_name, frame)

def _emit(cam_name, frame):
    active_feed = camera_service.get_active_feed()
    # print(f"[_emit] cam_name={cam_name}, active_feed={active_feed}", flush=True)
    if active_feed != cam_name:
        # print("[_emit] skipping, mismatch", flush=True)
        return

    success, buf = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
    if not success:
        return

    # Send a single payload dict; bytes get sent as true binary attachment.
    socketio.emit(
        'frame-bin',
        {
          'camera_name': cam_name,
          'image': buf.tobytes()
        }
    )
    # print("[_emit] frame-bin emitted for", cam_name, flush=True)