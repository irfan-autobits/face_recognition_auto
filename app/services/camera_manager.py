# app/services/camera_manager.py
from datetime import datetime 
import json
import time
from app.models.model import Detection, Camera_list, Embedding, db
from flask import current_app
from app.processors.VideoCapture import VideoStream  
from config.Paths import frame_lock, vs_list, cam_sources
from config.logger_config import cam_stat_logger 

def Default_cameras():
    """Add and start default cameras, but only if they pass a responsiveness test."""
    try:
        global cam_sources
        valid_cameras = {}  # to hold cameras that passed the test
        
        with current_app.app_context():
            # Test each camera first
            for cam_name, source in cam_sources.items():
                cam_stat_logger.info(f"Testing camera {cam_name} at {source}")
                test_stream = VideoStream(src=source)
                test_stream.start()
                test_attempts = 7
                frame = None
                for attempt in range(test_attempts):
                    frame = test_stream.read()
                    if frame is not None:
                        cam_stat_logger.info(f"Camera {cam_name} responded on attempt {attempt+1}.")
                        break
                    time.sleep(0.5)  # wait half a second between attempts

                if frame is None:
                    cam_stat_logger.warning(f"Camera {cam_name} did not respond after {test_attempts} attempts. Skipping.")
                    test_stream.stop()
                else:
                    # Camera is responsive, so add it
                    new_camera = Camera_list(camera_name=cam_name, camera_url=source)
                    db.session.add(new_camera)
                    valid_cameras[cam_name] = source
                    # Stop the test stream; we'll create a new one for normal operation.
                    test_stream.stop()
                    cam_stat_logger.info(f"Default camera {cam_name} passed the test and is added.")

            db.session.commit()  # Commit only the valid cameras

            # Now initialize the video streams for the valid cameras
            with frame_lock:
                for cam_name, source in valid_cameras.items():
                    vs = VideoStream(src=source)
                    vs.start()
                    vs_list[cam_name] = vs
                    cam_stat_logger.info(f"Started VideoStream for camera {cam_name}.")

        return {'message': 'Default cameras added successfully', 'valid_cameras': list(valid_cameras.keys())}, 200

    except Exception as e:
        db.session.rollback()
        cam_stat_logger.error(f"Error in Default_cameras: {str(e)}")
        return {'error': str(e)}, 500


def Add_camera(camera_name,camera_url):
    """API endpoint to add a camera"""
    new_camera = Camera_list(camera_name=camera_name, camera_url=camera_url)
    global vs_list, cam_sources
    try:
        global cam_sources
        with current_app.app_context():
            db.session.add(new_camera)
            db.session.commit()
            with frame_lock:
                cam_sources[camera_name] = camera_url
                responce, status = Start_camera(camera_name)
                cam_stat_logger.info(f"{camera_name} Camera added successfully")
                # responce, status = {'message' : f"Camera {camera_name} added successfully"}, 200
            return responce, status
    except Exception as e:
        db.session.rollback()
        cam_stat_logger.error(f"Failed to add {camera_name} camera: {str(e)}")
        return {'error' : str(e)}, 500
    
def Remove_camera(camera_name):
    """API endpoint to remove a camera"""
    global vs_list, cam_sources
    try:
        with current_app.app_context():
            camera = Camera_list.query.filter_by(camera_name=camera_name).first()
            if camera:
                db.session.delete(camera)
                db.session.commit()
                with frame_lock:
                    responce, status = Stop_camera(camera_name)
                    cam_stat_logger.info(f"{camera_name} Camera removed successfully")
                    # responce, status = {'message' : f"Camera {camera_name} removed successfully"}, 200
                    if camera_name in cam_sources:
                        del cam_sources[camera_name]
                return responce, status
            else:
                return {'error' : f'{camera_name} Camera not found'}, 404
    except Exception as e:
        db.session.rollback()
        cam_stat_logger.error(f"Failed to Remove {camera_name} camera: {str(e)}")
        return {'error' : str(e)}, 500

def Start_camera(camera_name):
    """API endpoint to start a camera feed after testing its responsiveness."""
    global vs_list, cam_sources
    if camera_name in cam_sources:
        if camera_name in vs_list:
            cam_stat_logger.info(f'Recognition for {camera_name} Camera Already started')
            return {'message': f'Recognition for {camera_name} Camera Already started'}, 200
        else:
            # Initialize the video stream
            vs = VideoStream(src=cam_sources[camera_name])
            vs.start()
            # Test if the camera is responsive by trying to read a frame.
            test_attempts = 7
            frame = None
            for attempt in range(test_attempts):
                frame = vs.read()
                if frame is not None:
                    break
                time.sleep(0.5)  # wait half a second between attempts
            if frame is None:
                # If no frame is received after testing, stop the stream and return an error.
                vs.stop() 
                cam_stat_logger.error(f'[Test failed], Camera {camera_name} is not responding.')
                return {'error': f'[Test failed], Camera {camera_name} is not responding.'}, 400

            # If testing passed, add the camera to vs_list.
            vs_list[camera_name] = vs
            cam_stat_logger.info(f'[Test passed], Recognition started for {camera_name}')
            return {'message': f'[Test passed], Recognition started for {camera_name}'}, 200
    else:
        cam_stat_logger.error(f'{camera_name} Camera not found')
        return {'error': f'{camera_name} Camera not found'}, 404

def Stop_camera(camera_name):
    """API endpoint to stop a camera feed"""
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
        
def List_cameras():
    """API endpoint to list all the cameras with their status"""
    try:
        with current_app.app_context():
            cameras = Camera_list.query.all()
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
 
     
def Recognition_table(page,limit):
    """API endpoint to list all Recognition"""
    try:
        with current_app.app_context():
            # Get pagination parameters from query string
            offset = (page - 1) * limit
            # Query detections in descending order (adjust order as needed)
            detection = (Detection.query
                      .order_by(Detection.timestamp.desc())
                      .limit(limit)
                      .offset(offset)
                      .all())
            detection_list = [{"id":det.id, "person":det.person, "camera_name":det.camera_name, "det_score":det.det_score, "distance":det.distance, "timestamp":det.timestamp.isoformat(), "det_face":det.det_face} for det in detection]
            return {'detections': detection_list}, 200
    except Exception as e:
        db.session.rollback()
        cam_stat_logger.error(f"Failed to list cameras: {str(e)}")
        return {'error' : str(e)}, 500
