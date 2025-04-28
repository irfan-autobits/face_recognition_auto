# app/services/camera_manager.py
import time
import pytz
from sqlalchemy import and_
from datetime import datetime, timedelta
from app.models.model import Camera, CameraEvent, db
from app.services.videocapture import VideoStream
from config.state import vs_lock, frame_lock, feed_lock
from config.logger_config import cam_stat_logger
from sqlalchemy.exc import IntegrityError

# Removed duplicate _start_stream function, please use the method defined in CameraService.
class CameraService:
    def __init__(self, frame_lock, vs_lock, feed_lock):
        # we no longer carry cam_sources or vs_list around in module globals
        self.frame_lock = frame_lock
        self.feed_lock  = feed_lock
        self.vs_lock    = vs_lock
        self._vs_list   = {}     # name → VideoStream
        self.active_feed = None        
        # the DB is the canonical source of truth for camera configs

    @property
    def streams(self):
        """Thread‑safe snapshot of all VideoStream instances."""
        with self.vs_lock:
            return dict(self._vs_list)

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
                    self._vs_list[name] = vs
                return True
            time.sleep(0.5)
        vs.stop()
        cam_stat_logger.error(f"Camera {name} failed to respond after {attempts} attempts.")
        return False

    def _log_event(self, cam: Camera, event_type: str, action: str):
        """Single place to INSERT into camera_event."""
        evt = CameraEvent(
            camera_id=cam.id,
            event_type=event_type,
            action=action,
            timestamp=datetime.now(pytz.UTC)
        )
        db.session.add(evt)
        db.session.commit()

    def add_camera(self, name, url, tag):
        """Try to insert a new Camera row, then start it.   
        DB enforces uniqueness, we just catch any dup‐key error."""
        if not name or not url or not tag:
            return {'error': 'name, url, and tag are required'}, 400        
        new_cam = Camera(camera_name=name, camera_url=url, tag=tag)
        db.session.add(new_cam)
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            # we know the only duplicate‐key here is camera_name, so:
            return {'error': f"Camera '{name}' already exists"}, 409

        # if we got here, the row is in the DB—now start the stream & log the event
        resp, status = self.start_camera(name)
        # if start_camera fails you might even want to delete the row … up to you
        return resp, status

    def start_camera(self, name):
        """Start an existing camera if not already running."""
        cam = Camera.query.filter_by(camera_name=name).first()
        if not cam:
            cam_stat_logger.error(f"Camera {name} not found on camera service")
            return {'error': f"Camera {name} not found on camera service"}, 404        
        if name in self._vs_list:
            cam_stat_logger.info(f"Camera {name} already started")
            return {'message': f"Camera {name} already started"}, 200
        if not self._start_stream(name, cam.camera_url):
            cam_stat_logger.error(f"Camera {name} not responding")
            return {'error': f"Camera {name} not responding"}, 400

        # only one lookup, then reuse `cam`
        self._log_event(cam, 'camera', 'start')
        cam_stat_logger.info(f"Camera {name} started")
        return {'message': f"Camera {name} started"}, 200

    def stop_camera(self, name):
        """Stop a running camera stream."""
        cam = Camera.query.filter_by(camera_name=name).first()
        if not cam:
            cam_stat_logger.error(f"Camera {name} not found")
            return {'error': f"Camera {name} not found"}, 404          
        if name not in self._vs_list:
            return {'error': f"Camera {name} is not running"}, 404

        # tear down stream…
        with self.vs_lock:
            self._vs_list[name].stop()
            del self._vs_list[name]

        self._log_event(cam, 'camera', 'stop')
        cam_stat_logger.info(f"Stopped camera {name}")
        #  ── auto‐tear‐down any live feed on that camera ──
        if self.active_feed == name:
            self.stop_feed()        
        return {'message': f"Camera {name} stopped"}, 200

    def remove_camera(self, name):
        """Remove camera record from DB and stop its stream."""
        cam = Camera.query.filter_by(camera_name=name).first()
        if not cam:
            cam_stat_logger.error(f"Camera {name} not found in DB")
            return {'error': f"Camera {name} not found in DB"}, 404
        resp, status = self.stop_camera(name)
        db.session.delete(cam)
        db.session.commit()
        cam_stat_logger.info(f"Removed camera {name}")
        return resp, status

    def start_feed(self, name):
        cam = Camera.query.filter_by(camera_name=name).first()
        if not cam:
            cam_stat_logger.error(f"Camera {name} not found in DB")
            return {'error': f"Camera {name} not found in DB"}, 404 
               
        if name not in self._vs_list:
            cam_stat_logger.error(f"Cannot start feed: camera '{name}' is not running")
            return {'error': f"Camera '{name}' is not running"}, 400

        old = self.active_feed
        with self.feed_lock:
            # if switching feeds, auto-stop the old one
            if old and old != name:
                old_cam = Camera.query.filter_by(camera_name=old).first()
                self._log_event(old_cam, 'feed', 'stop')
            self.active_feed = name

        self._log_event(cam, 'feed', 'start')
        cam_stat_logger.info(f"Feed started for camera '{name}'")
        return {'message': f"Feed started for '{name}'"}, 200

    def stop_feed(self):
        with self.feed_lock:
            name = self.active_feed
            self.active_feed = None

        if not name:
            return {'error': 'No feed was active'}, 400

        cam = Camera.query.filter_by(camera_name=name).first()
        self._log_event(cam, 'feed', 'stop')
        cam_stat_logger.info(f"Feed stopped for camera '{name}'")
        return {'message': f"Feed stopped for '{name}'"}, 200

    def get_active_feed(self):
        with self.feed_lock:
            return self.active_feed

    def start_all(self):
        """Start all configured cameras."""
        results = {}
        for cam in Camera.query:
            resp, st = self.start_camera(cam.camera_name)
            results[cam.camera_name] = {'response': resp, 'status': st}
        return results, 200

    def stop_all(self):
        """Stop all running cameras."""
        results = {}
        for name in list(self._vs_list.keys()):
            resp, status = self.stop_camera(name)
            results[name] = {'response': resp, 'status': status}
        return results, 200

    def bootstrap_from_env(self, env_sources):
        """
        On app‑startup only: read your env‑dict, add each to DB & spin up its stream.
        """
        results = {}
        for name, details in env_sources.items():
            resp, st = self.add_camera(name, details['url'], details['tag'])
            results[name] = {'status': st, 'response': resp}
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
                'status': cam.camera_name in self._vs_list
            })
        return {'cameras': camera_list}, 200
    
    def camera_timeline_status(self):
        """
        Returns JSON:
        {
        "camData": [
            { camera, activePeriods: [{start,end}], feeds: [{start,end}] },
            …
        ],
        "range": { min, max }
        }
        """
        now = datetime.now(pytz.utc)
        window_start = now - timedelta(days=30)

        # fetch all events in window
        events = (
            CameraEvent.query
            .filter(and_(CameraEvent.timestamp >= window_start,
                        CameraEvent.timestamp <= now))
            .order_by(CameraEvent.camera_id, CameraEvent.timestamp)
            .all()
        )

        # gather an entry per camera
        cam_map = {}
        for cam in Camera.query.all():
            cam_map[str(cam.id)] = {
                "camera": cam.camera_name,
                "activePeriods": [], 
                "feeds": []
            }

        # helper to consume paired start→stop into periods
        def build_periods(evts, etype):
            periods, current = [], None
            for e in evts:
                if e.action == 'start':
                    current = e.timestamp
                elif e.action == 'stop' and current:
                    periods.append({"start": current.isoformat(),
                                    "end":   e.timestamp.isoformat()})
                    current = None
            # if still open-ended
            if current:
                periods.append({"start": current.isoformat(),
                                "end":   now.isoformat()})
            return periods

        # group events by camera
        by_cam = {}
        for e in events:
            cid = str(e.camera_id)
            by_cam.setdefault(cid, []).append(e)

        overall_min, overall_max = None, None

        for cid, evts in by_cam.items():
            # split camera-type vs feed-type
            cam_evts  = [e for e in evts if e.event_type == 'camera']
            feed_evts = [e for e in evts if e.event_type == 'feed']

            ap = build_periods(cam_evts, 'camera')
            fd = build_periods(feed_evts, 'feed')

            cam_map[cid]["activePeriods"] = ap
            cam_map[cid]["feeds"]         = fd

            # update overall range
            for seg in ap + fd:
                s = datetime.fromisoformat(seg["start"])
                e = datetime.fromisoformat(seg["end"])                  
                overall_min = s if overall_min is None or s < overall_min else overall_min
                overall_max = e if overall_max is None or e > overall_max else overall_max

        return {
            "camData": list(cam_map.values()),
            "range": {
                "min": overall_min.isoformat() if overall_min else window_start.isoformat(),
                "max": overall_max.isoformat() if overall_max else now.isoformat()
            }
        }, 200
        
# Module‑level instance
camera_service = CameraService(frame_lock, vs_lock, feed_lock)
