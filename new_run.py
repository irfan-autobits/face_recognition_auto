# run.py
import atexit
import signal
import sys

from flask_cors import CORS
from config.paths import cam_sources
from scripts.manage_db import manage_table
from app.services.settings_manage import settings
from app.services.camera_manager import camera_service
from app.services.processing_service import ProcessingService
from app.processors.face_detection import FaceDetectionProcessor
from app.app_setup import create_app, socketio, db, send_frame
from app.services.settings_manage import seed_feature_flags

app = create_app()
CORS(app, resources={r"/*": {"origins": "*"}})
socketio.init_app(app)
db.init_app(app)

face_processor = FaceDetectionProcessor(db.session, app)
processing     = ProcessingService(app, face_processor, max_workers=4)

def graceful_shutdown(*args):
    """Stop all streams and log stops inside app context, then exit on signal."""
    with app.app_context():
        camera_service.stop_all()
    sys.exit(0)  # only here, in the signal handler

# Register teardown handlers
atexit.register(lambda: camera_service.stop_all())
signal.signal(signal.SIGINT, graceful_shutdown)
signal.signal(signal.SIGTERM, graceful_shutdown)

if __name__ == "__main__":
    with app.app_context():
        # Rebuild or migrate your tables
        manage_table(spec=True)
        # Bootstrap cameras from config
        camera_service.bootstrap_from_env(cam_sources)
        seed_feature_flags()
        # now load settings from the database:
        settings.init_app(app)

    # Kick off the frame‐pumping loop
    socketio.start_background_task(send_frame, processing)
    # Start the server
    socketio.run(
      app,
      host="0.0.0.0",
      port=5757,
      use_reloader=False,
      debug=True
    )
