# run.py
import eventlet
eventlet.monkey_patch()

from app.app_setup import create_app, socketio, db, send_frame
from app.processors.face_detection import FaceDetectionProcessor

from app.services.processing_service import ProcessingService
from config.paths import cam_sources
from app.services.camera_manager import camera_service
from scripts.manage_db import manage_table

app = create_app()
face_processor = FaceDetectionProcessor(db.session, app)
processing     = ProcessingService(app, face_processor, max_workers=4)

if __name__ == '__main__':
    with app.app_context():
        manage_table(drop=True)
        # read your env‑provided dict exactly once, then forget cam_sources
        camera_service.bootstrap_from_env(cam_sources)
    # after app context & bootstrap...
    socketio.start_background_task(send_frame, processing)
    socketio.run(app, host='0.0.0.0', port=5757)
