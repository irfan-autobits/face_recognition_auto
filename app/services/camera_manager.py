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
from app.utils.time_utils import now_utc, to_utc_iso, parse_iso, to_utc, now_local
from itertools import groupby

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

    def _start_stream(self, name, source, attempts=7):
        """Test and start a VideoStream for a camera."""
        vs = VideoStream(src=source)
        vs.start()
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
            timestamp=now_utc()
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

    def start_camera(self, name, silent=False):
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
        # — before we log this new START, close out any lingering START w/o STOP
        if not silent:
            self._close_open_period(cam, event_type='camera')        
            self._log_event(cam, 'camera', 'start')
            cam_stat_logger.info(f"Camera {name} started")

        return {'message': f"Camera {name} started"}, 200

    def _close_open_period(self, cam: Camera, event_type: str):
        """
        If the last CameraEvent for this cam/event_type is a START with no STOP,
        write a STOP at now_utc().
        """
        last = (
            CameraEvent.query
            .filter_by(camera_id=cam.id, event_type=event_type)
            .order_by(CameraEvent.timestamp.desc())
            .first()
        )
        if last and last.action == 'start':
            stop_evt = CameraEvent(
                camera_id=cam.id,
                event_type=event_type,
                action='stop',
                timestamp=now_utc()
            )
            db.session.add(stop_evt)
            db.session.commit()
            cam_stat_logger.info(f"Camera {cam.camera_name} found open ended ,so its closed before start event")

    def _core_stop_operations(self, name):
        """Shared stop logic for both methods"""
        vs = None
        with self.vs_lock:
            vs = self._vs_list.pop(name, None)
        if vs:
            vs.stop()
        return Camera.query.filter_by(camera_name=name).first()

    def stop_camera(self, name, silent=False):
        cam = self._core_stop_operations(name)
        if not cam:
            cam_stat_logger.error(f"Camera {name} not found")
            return {'error': f"Camera {name} not found"}, 404
        
        if not silent:
            self._log_event(cam, 'camera', 'stop')
            cam_stat_logger.info(f"Stopped camera {name}")
        
        # Cleanup feed if it was using this camera
        if self.active_feed == name:
            self.stop_feed()
            
        return {'message': f"Camera {name} stopped"}, 200

    def handle_unexpected_stop(self, name):
        cam = self._core_stop_operations(name)
        if cam:
            self._log_event(cam, 'camera', 'stop')
            # Critical feed cleanup added
            if self.active_feed == name:
                self.stop_feed()
        cam_stat_logger.warning(f"Camera {name} auto-stopped after missed frames")

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

    def edit_camera(self, old_name, new_name=None, new_tag=None):
        """Edit camera record from DB"""
        cam = Camera.query.filter_by(camera_name=old_name).first()
        if not cam:
            cam_stat_logger.error(f"old Camera {old_name} not found in DB while editing")
            return {'error': f"old Camera {old_name} not found in DB while editing"}, 404
        # If a new name/tag is provided, update the existin camera record
        updated = False
        if new_name and new_name != old_name:
            existing = Camera.query.filter_by(camera_name=new_name).first()
            if existing:
                return {'error': f"Camera name '{new_name}' already exists"}, 409
            was_running = old_name in self._vs_list
            if was_running:
                self.stop_camera(old_name, silent=True)
            # updating ...
            cam.camera_name = new_name
            if was_running:
                self.start_camera(new_name, silent=True) 
            updated = True                
        if new_tag and new_tag != cam.tag:
            cam.tag = new_tag
            updated = True

        if updated:
            db.session.commit()            
            cam_stat_logger.info(f"edited camera {old_name} with new name {new_name} and tag {new_tag}")
        else:
            resp, status = {'error': f"edit Camera {old_name} new name or tag not provided"}, 404 
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

        # — before we log this new START, close out any lingering START w/o STOP
        self._close_open_period(cam, event_type='feed')     
        self._log_event(cam, 'feed', 'start')
        cam_stat_logger.info(f"Feed started for camera '{name}'")
        return {'message': f"Feed started for '{name}'"}, 200

    def stop_feed(self):
        with self.feed_lock:
            name = self.active_feed
            self.active_feed = None

        if not name:
            cam_stat_logger.error("No feed was active")
            return {'error': 'No feed was active'}, 400

        cam = Camera.query.filter_by(camera_name=name).first()
        self._log_event(cam, 'feed', 'stop')
        cam_stat_logger.info(f"Feed stopped for camera '{name}'")
        return {'message': f"Feed stopped for '{name}'"}, 200

    def get_active_feed(self):
        with self.feed_lock:
            return self.active_feed
        
    def count_running_streams(self) -> int:
        with self.vs_lock:
            return len(self._vs_list)
    
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


    def camera_timeline_status(self, start_str=None, end_str=None):
        """
        Returns JSON:
        {
          camData: [
            { camera, activePeriods:[{start,end}], feeds:[{start,end}] }, …
          ],
          range: { min, max }    # UTC ISO-Z strings
        }
        """
        # 1️⃣ Build UTC window from params or default last-30-days
        now   = now_utc()
        if start_str and end_str:
            try:
                sd = parse_iso(start_str)
                ed = parse_iso(end_str)

                start_utc = to_utc(sd)
                end_utc   = to_utc(ed)
                if start_utc > end_utc:
                    cam_stat_logger.info(f"camera timeline provided are: {start_utc} to {end_utc}")
                elif start_utc == end_utc:
                    cam_stat_logger.info(f"camera timeline provided are same: {start_utc} to {end_utc}")
                    end_utc   = now
                else:
                    local_midnight = now_local().replace(hour=0, minute=0, second=0, microsecond=0)
                    start_utc = to_utc(local_midnight)
                    end_utc   = now
                    cam_stat_logger.error("Invialid date range provided, defaulting to today")                    
            except Exception:
                # fallback to last 30d
                local_midnight = now_local().replace(hour=0, minute=0, second=0, microsecond=0)
                start_utc = to_utc(local_midnight)
                end_utc   = now
                cam_stat_logger.error("Invialid date range provided, defaulting to today")
        else:
            cam_stat_logger.info("No start/end dates provided, defaulting to today")
            # Calculate today’s local midnight in UTC
            # 1) take now in LOCAL_TZ, floor to midnight, then convert to UTC
            local_midnight = now_local().replace(hour=0, minute=0, second=0, microsecond=0)
            start_utc = to_utc(local_midnight)
            end_utc   = now

        # 2️⃣ Query CameraEvent between those UTC bounds
        events = (
            CameraEvent.query
            .filter(and_(
                CameraEvent.timestamp >= start_utc,
                CameraEvent.timestamp <= end_utc
            ))
            .order_by(CameraEvent.camera_id, CameraEvent.timestamp)
            .all()
        )

        # 3️⃣ Initialize per-camera structure
        cam_map = {
            str(cam.id): {"camera": cam.camera_name, "activePeriods": [], "feeds": []}
            for cam in Camera.query.all()
        }

        # 4️⃣ Helper to turn start/stop into periods, serializing as Z-strings
        def build_periods(evts):
            periods, current = [], None
            for e in evts:
                if e.action == 'start':
                    current = e.timestamp
                elif e.action == 'stop' and current:
                    periods.append({
                        "start": to_utc_iso(current),
                        "end":   to_utc_iso(e.timestamp)
                    })
                    current = None
            # open-ended?
            if current:
                periods.append({"start": to_utc_iso(current), "end": to_utc_iso(end_utc)})
            return periods

        # 5️⃣ Group events by camera_id
        from collections import defaultdict
        by_cam = defaultdict(list)
        for e in events:
            by_cam[str(e.camera_id)].append(e)

        overall_min, overall_max = None, None

        # 6️⃣ For each camera, split into “camera” vs “feed” events
        for cam_id, evts in by_cam.items():
            cam_events = [e for e in evts if e.event_type == 'camera']
            feed_events= [e for e in evts if e.event_type == 'feed']

            ap = build_periods(cam_events)
            fd = build_periods(feed_events)

            cam_map[cam_id]["activePeriods"] = ap
            cam_map[cam_id]["feeds"]         = fd

            # compute global min/max
            for seg in ap + fd:
                s = parse_iso(seg["start"])
                x = parse_iso(seg["end"])
                overall_min = s if overall_min is None or s < overall_min else overall_min
                overall_max = x if overall_max is None or x > overall_max else overall_max

        # 7️⃣ Return full payload
        return {
            "camData": list(cam_map.values()),
            "range": {
                "min": to_utc_iso(overall_min or start_utc),
                "max": to_utc_iso(overall_max or end_utc)
            }
        }, 200


# Module‑level instance
camera_service = CameraService(frame_lock, vs_lock, feed_lock)
