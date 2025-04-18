# app/services/camera_manager.py
from datetime import datetime
import time
from flask import current_app
from app.models.model import Camera, db
from app.processors.videocapture import VideoStream
from config.paths import cam_sources, vs_list, vs_lock
from config.logger_config import cam_stat_logger

class CameraService:
    def __init__(self, vs_lock, cam_sources, vs_list):
        self.vs_lock = vs_lock
        self.cam_sources = cam_sources
        self.vs_list = vs_list

    def _start_stream(self, name, source):
        """Test and start a VideoStream for a camera."""
        vs = VideoStream(src=source)
        vs.start()
        attempts = 7
        for i in range(attempts):
            frame = vs.read()
            if frame is not None:
                cam_stat_logger.info(f"Camera {name} responded on attempt {i+1}.")
                with self.vs_lock:
                    self.vs_list[name] = vs
                return True
            time.sleep(0.5)
        vs.stop()
        cam_stat_logger.error(f"Camera {name} failed to respond after {attempts} attempts.")
        return False

    def add_camera(self, name, url, tag):
        """
        Add a new camera record and start its stream if responsive.
        Returns (response_dict, status_code).
        """
        # Persist camera record
        new_cam = Camera(camera_name=name, camera_url=url, tag=tag)
        db.session.add(new_cam)
        # Update source config
        self.cam_sources[name] = {"url": url, "tag": tag}

        # Test & start
        if self._start_stream(name, url):
            db.session.commit()
            cam_stat_logger.info(f"Added and started camera {name}")
            return {'message': f"Camera {name} added and started"}, 200
        else:
            db.session.rollback()
            # rollback cam_sources entry
            self.cam_sources.pop(name, None)
            return {'error': f"Camera {name} not responding"}, 400

    def start_camera(self, name):
        """Start an existing camera if not already running."""
        details = self.cam_sources.get(name)
        if not details:
            return {'error': f"Camera {name} not found in sources"}, 404
        if name in self.vs_list:
            return {'message': f"Camera {name} already started"}, 200
        if self._start_stream(name, details['url']):
            return {'message': f"Camera {name} started"}, 200
        else:
            return {'error': f"Camera {name} not responding"}, 400

    def stop_camera(self, name):
        """Stop a running camera stream."""
        if name not in self.vs_list:
            return {'error': f"Camera {name} is not running"}, 404
        with self.vs_lock:
            self.vs_list[name].stop()
            del self.vs_list[name]
        cam_stat_logger.info(f"Stopped camera {name}")
        return {'message': f"Camera {name} stopped"}, 200

    def remove_camera(self, name):
        """Remove camera record from DB and stop its stream."""
        cam = Camera.query.filter_by(camera_name=name).first()
        if not cam:
            return {'error': f"Camera {name} not found in DB"}, 404
        db.session.delete(cam)
        db.session.commit()
        resp, status = self.stop_camera(name)
        # Remove from source config
        self.cam_sources.pop(name, None)
        cam_stat_logger.info(f"Removed camera {name}")
        return resp, status

    def start_all(self):
        """Start all configured cameras."""
        results = {}
        for name in list(self.cam_sources.keys()):
            resp, status = self.start_camera(name)
            results[name] = {'response': resp, 'status': status}
        return results, 200

    def stop_all(self):
        """Stop all running cameras."""
        results = {}
        for name in list(self.vs_list.keys()):
            resp, status = self.stop_camera(name)
            results[name] = {'response': resp, 'status': status}
        return results, 200

    def default_cameras(self):
        """
        Loop over all entries in cam_sources and call add_camera for each.
        """
        results = {}
        for name, details in self.cam_sources.items():
            resp, status = self.add_camera(name, details['url'], details['tag'])
            results[name] = {'status': status, 'response': resp}
        return results, 200
    
    def list_cameras(self):
        """List all cameras in DB with their running status."""
        cams = Camera.query.all()
        camera_list = []
        for cam in cams:
            camera_list.append({
                'camera_name': cam.camera_name,
                'camera_url': cam.camera_url,
                'tag': cam.tag,
                'status': cam.camera_name in self.vs_list
            })
        return {'cameras': camera_list}, 200


# Module‑level instance to import in your routes
camera_service = CameraService(vs_lock, cam_sources, vs_list)

from sqlalchemy.orm import joinedload
from app.models.model import Detection, Subject, Camera

def recognition_table(page,limit, search, sort_field, sort_order, offset):
    """API endpoint to list all Recognition"""
    try:
        with current_app.app_context():        
            # ─── build base query (outerjoin so subj can be None) ─────────────
            query = (
                Detection
                .query
                .outerjoin(Subject)
                .outerjoin(Camera)
            )

            # ─── full‐text search over person|camera|tag ───────────────────────
            if search:
                like_val = f"%{search}%"
                query = query.filter(
                    Subject.subject_name.ilike(like_val) |
                    Camera.camera_name .ilike(like_val) |
                    Camera.tag         .ilike(like_val)
                )

            # ─── apply sorting ─────────────────────────────────────────────────
            sort_col = getattr(Detection, sort_field, Detection.timestamp)
            sort_col = sort_col.asc() if sort_order == 'asc' else sort_col.desc()

            # ─── fetch with joined‑load to avoid N+1 ──────────────────────────
            detections = (
                query
                .options(
                    joinedload(Detection.subject),
                    joinedload(Detection.camera),
                )
                .order_by(sort_col)
                .offset(offset)
                .limit(limit)
                .all()
            )

            # ─── serialize, defaulting to "Unknown" ────────────────────────────
            body = []
            for d in detections:
                # if you created a dummy subject_name="__UNKNOWN__", hide it here:
                name = (
                    d.subject.subject_name
                    if d.subject and d.subject.subject_name != None
                    else "Unknown"
                )
                body.append({
                    "id":          str(d.rec_no),
                    "subject":     name,
                    "camera_name": d.camera.camera_name,
                    "camera_tag":  d.camera.tag,
                    "det_score":   d.det_score,
                    "distance":    d.distance,
                    "timestamp":   d.timestamp.isoformat(),
                    "det_face":    d.det_face,
                })

            return {
                'detections': body,
                'page':       page,
                'limit':      limit
            }, 200

    except Exception as e:
        db.session.rollback()
        cam_stat_logger.error(f"Failed to list detections: {str(e)}")
        return {'error': str(e)}, 500