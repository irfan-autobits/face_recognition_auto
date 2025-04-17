# app/services/camera_manager.py
from datetime import datetime 
import json
import time
from app.models.model import Detection, Camera, Embedding, db
from flask import current_app
from app.processors.videocapture import VideoStream  
from config.paths import frame_lock, vs_list, cam_sources
from config.logger_config import cam_stat_logger 
from sqlalchemy.orm import joinedload
from app.models.model import Detection, Subject, Camera

def default_cameras():
    """Add and start default cameras, testing each for responsiveness.
       If a camera passes the test, use the same VideoStream for live processing.
    """
    try:
        valid_cameras = {}  # dictionary to hold working streams keyed by camera name

        with current_app.app_context():
            # Iterate over your camera sources (each source is a dict with 'url' and 'tag')
            for cam_name, details in cam_sources.items():
                source = details.get("url")
                tag = details.get("tag")  # Use provided tag

                cam_stat_logger.info(f"Testing camera {cam_name} at {source}")
                # Create one VideoStream instance for testing that will also be used live if it passes
                vs = VideoStream(src=source)
                vs.start()
                test_attempts = 7
                frame = None
                for attempt in range(test_attempts):
                    frame = vs.read()
                    if frame is not None:
                        cam_stat_logger.info(f"Camera {cam_name} responded on attempt {attempt+1}.")
                        break
                    time.sleep(0.5)  # wait half a second between attempts

                if frame is None:
                    cam_stat_logger.warning(f"Camera {cam_name} did not respond after {test_attempts} attempts. Skipping.")
                    vs.stop()
                else:
                    # Camera is responsive, so add it to the DB and keep the stream
                    new_camera = Camera(camera_name=cam_name, camera_url=source, tag=tag)
                    db.session.add(new_camera)
                    # Save the working stream (vs) for live processing
                    valid_cameras[cam_name] = vs
                    cam_stat_logger.info(f"Default camera {cam_name} passed the test and is added with tag {tag}.")

            db.session.commit()  # Commit only the valid camera records

            # With a lock, update the global vs_list with our working streams from valid_cameras.
            with frame_lock:
                for cam_name, vs in valid_cameras.items():
                    vs_list[cam_name] = vs
                    cam_stat_logger.info(f"Started VideoStream for camera {cam_name}.")

        return {'message': 'Default cameras added successfully', 'valid_cameras': list(valid_cameras.keys())}, 200

    except Exception as e:
        db.session.rollback()
        cam_stat_logger.error(f"Error in Default_cameras: {str(e)}")
        return {'error': str(e)}, 500

# Example: Adding a camera to Room 101.

def add_new_camera(camera_name, camera_url, tag):
    """API endpoint to add a camera"""
    cam_stat_logger.info(f"[arg] at add cam {camera_name} url:{camera_url} tag:{tag} ")
    new_camera = Camera(camera_name=camera_name, camera_url=camera_url, tag=tag)
    global vs_list, cam_sources
    try:
        global cam_sources
        with current_app.app_context():
            with frame_lock:
                cam_sources[camera_name] = {"url": camera_url, "tag": tag }
                response, status = start_camera(camera_name)
                if status == 200:
                    db.session.add(new_camera)
                    db.session.commit()                
                    cam_stat_logger.info(f"new {camera_name} Camera added successfully")
            return response, status
        
    except Exception as e:
        db.session.rollback()
        cam_stat_logger.error(f"Failed to add {camera_name} camera: {str(e)}")
        return {'error' : str(e)}, 500

def start_camera(camera_name):
    """API endpoint to start a camera feed after testing its responsiveness."""
    cam_stat_logger.info(f"[arg] at start cam {camera_name}.")
    global vs_list, cam_sources
    details = cam_sources.get(camera_name)
    if not details:
        cam_stat_logger.error(f"{camera_name} Camera not found in sources")
        return {'error': f'{camera_name} Camera not found'}, 404
    
    source = details.get("url")
    if not source:
        cam_stat_logger.error(f"No URL defined for camera {camera_name}")
        return {'error': f'No URL defined for {camera_name}'}, 404

    if camera_name in vs_list:
        cam_stat_logger.info(f'Recognition for {camera_name} Camera Already started')
        return {'message': f'Recognition for {camera_name} Camera Already started'}, 200
    else:
        vs = VideoStream(src=source)
        cam_stat_logger.info(f'[Debug] Starting VideoStream for source: {source}')
        vs.start()
        test_attempts = 7
        frame = None
        for attempt in range(test_attempts):
            frame = vs.read()
            if frame is not None:
                break
            time.sleep(0.5)  # wait half a second between attempts
        if frame is None:
            vs.stop()
            cam_stat_logger.error(f'[Test failed], Camera {camera_name} is not responding.')
            return {'error': f'[Test failed], Camera {camera_name} is not responding.'}, 400

        vs_list[camera_name] = vs
        cam_stat_logger.info(f'[Test passed], Recognition started for {camera_name}')
        return {'message': f'[Test passed], Recognition started for {camera_name}'}, 200

def start_all_camera():
    """API endpoint to start all camera feeds and return a summary for each."""
    global vs_list, cam_sources
    results = {}
    # Iterate over a copy of keys in cam_sources (to avoid modification issues)
    for camera_name in list(cam_sources.keys()):
        response, status = start_camera(camera_name)
        results[camera_name] = {"response": response, "status": status}
    return results, 200
        
def rm_camera(camera_name):
    """API endpoint to remove a camera"""
    global vs_list, cam_sources
    try:
        with current_app.app_context():
            camera = Camera.query.filter_by(camera_name=camera_name).first()
            if camera:
                db.session.delete(camera)
                db.session.commit()
                with frame_lock:
                    response, status = stop_camera(camera_name)
                    cam_stat_logger.info(f"{camera_name} Camera removed successfully")
                    # response, status = {'message' : f"Camera {camera_name} removed successfully"}, 200
                    if camera_name in cam_sources:
                        del cam_sources[camera_name]
                return response, status
            else:
                return {'error' : f'{camera_name} Camera not found'}, 404
    except Exception as e:
        db.session.rollback()
        cam_stat_logger.error(f"Failed to Remove {camera_name} camera: {str(e)}")
        return {'error' : str(e)}, 500

def stop_camera(camera_name):
    """API endpoint to stop a camera process"""
    global vs_list, cam_sources
    if camera_name in cam_sources:
        if camera_name in vs_list:
            vs_list[camera_name].stop()
            del vs_list[camera_name]
            cam_stat_logger.info(f"Recognition for {camera_name} Camera stoped successfully.")
            return {'message' : f'Recognition stopped for {camera_name}'}, 200
        else:
            return {'error' : f'Recognition for {camera_name} Camera Already stopped'}, 404
    else:
        return {'error' : f'{camera_name} Camera not found'}, 404   

def stop_all_camera():
    """API endpoint to stop all camera processes and return a summary for each."""
    global vs_list, cam_sources
    results = {}
    # Iterate over a copy of the keys to avoid modification issues
    for camera_name in list(cam_sources.keys()):
        response, status = stop_camera(camera_name)
        results[camera_name] = {"response": response, "status": status}
    return results, 200

def list_cameras():
    """API endpoint to list all the cameras with their status"""
    try:
        with current_app.app_context():
            cameras = Camera.query.all()
            camera_list = []
            for cam in cameras:
                # Check if camera is active in vs_list
                status = cam.camera_name in vs_list
                camera_list.append({
                    'camera_name': cam.camera_name,
                    'camera_url': cam.camera_url,
                    'status': status  # True if active, False otherwise
                })
            return {'cameras': camera_list}, 200
    except Exception as e:
        db.session.rollback()
        cam_stat_logger.error(f"Failed to list cameras: {str(e)}")
        return {'error': str(e)}, 500

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
                    if d.subject and d.subject.subject_name != "__UNKNOWN__"
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