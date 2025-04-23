# # app/services/feed_service.py
# import threading
# from flask import current_app
# from app.models.model import Camera, CameraEvent, db
# from config.logger_config import cam_stat_logger
# from app.services.camera_manager import camera_service  # ← pull in camera state

# class FeedService:
#     def __init__(self):
#         self.feed_lock   = threading.Lock()
#         self.active_feed = None

#     def start_feed(self, camera_name):
#         # 1) ensure the camera is actually streaming
#         if camera_name not in camera_service.streams:
#             cam_stat_logger.error(f"Cannot start feed: camera '{camera_name}' is not running")
#             return {'error': f"Camera '{camera_name}' is not running"}, 400

#         with self.feed_lock:
#             self.active_feed = camera_name

#         cam = Camera.query.filter_by(camera_name=camera_name).first()
#         evt = CameraEvent(camera_id=cam.id, event_type='feed', action='start')
#         db.session.add(evt)
#         db.session.commit()

#         cam_stat_logger.info(f"Feed started for camera '{camera_name}'")
#         return {'message': f"Feed started for '{camera_name}'"}, 200

#     def stop_feed(self):
#         with self.feed_lock:
#             camera_name = self.active_feed
#             self.active_feed = None

#         if not camera_name:
#             return {'error': 'No feed is currently active'}, 400

#         cam = Camera.query.filter_by(camera_name=camera_name).first()
#         evt = CameraEvent(camera_id=cam.id, event_type='feed', action='stop')
#         db.session.add(evt)
#         db.session.commit()

#         cam_stat_logger.info(f"Feed stopped for camera '{camera_name}'")
#         return {'message': f"Feed stopped for '{camera_name}'"}, 200

#     def getactive_feed(self):
#         with self.feed_lock:
#             return self.active_feed

# # module‐level singleton
# feed_service = FeedService()