from app.models.model import Detection, Camera_list, Embedding, Subject, db
from flask import current_app
from config.logger_config import cam_stat_logger, face_proc_logger
from datetime import datetime
import pytz

def format_duration(seconds):
    seconds = int(seconds)
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    parts = []
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0:
        parts.append(f"{minutes}m")
    if secs > 0 or not parts:
        parts.append(f"{secs}s")
    return " ".join(parts)

def get_person_journey(detections):
    """
    Process ordered detections for a person and merge consecutive detections 
    from the same camera into segments.
    Each segment contains:
      - 'camera_name': name of the camera
      - 'entry_time': the time of the first detection (formatted without microseconds)
      - 'start_time_raw': the raw datetime of the first detection (with microseconds zeroed)
      - 'duration': time difference in seconds between the first and last detection in that segment
    """
    if not detections:
        return []

    journey = []
    # Remove microseconds for consistency while retaining timezone awareness
    first_time = detections[0].timestamp.replace(microsecond=0)
    current_segment = {
        'camera_name': detections[0].camera_name,
        'entry_time': first_time.strftime('%Y-%m-%d %H:%M:%S'),
        'start_time_raw': first_time,
        'end_time': first_time
    }
    
    face_proc_logger.debug(f"[START] New journey. First detection: {first_time.isoformat()}")

    for det in detections[1:]:
        dt = det.timestamp.replace(microsecond=0)
        face_proc_logger.debug(f"[DETECTION] {det.camera_name} @ {dt.isoformat()}")
        
        # Skip duplicate timestamp for the same segment
        if det.camera_name == current_segment['camera_name'] and dt == current_segment['start_time_raw']:
            face_proc_logger.debug(f"[SKIP] Duplicate timestamp for same camera segment. Skipping.")
            continue
        
        if det.camera_name == current_segment['camera_name']:
            current_segment['end_time'] = dt
            face_proc_logger.debug(f"[UPDATE] Extended segment end_time to {dt.isoformat()}")
        else:
            duration = (current_segment['end_time'] - current_segment['start_time_raw']).total_seconds()
            duration = format_duration(duration)
            face_proc_logger.debug(f"[SEGMENT DONE] {current_segment['camera_name']} from {current_segment['start_time_raw']} to {current_segment['end_time']} duration: {duration}s")
            journey.append({
                'camera_name': current_segment['camera_name'],
                'entry_time': current_segment['entry_time'],
                'duration': duration,
                'start_time_raw': current_segment['start_time_raw'].isoformat()
            })
            # Start a new segment
            current_segment = {
                'camera_name': det.camera_name,
                'entry_time': dt.strftime('%Y-%m-%d %H:%M:%S'),
                'start_time_raw': dt,
                'end_time': dt
            }
            face_proc_logger.debug(f"[NEW SEGMENT] New segment started at {dt.isoformat()} on camera {det.camera_name}")

    # Append the final segment
    duration = (current_segment['end_time'] - current_segment['start_time_raw']).total_seconds()
    duration = format_duration(duration)
    face_proc_logger.debug(f"[FINAL SEGMENT] {current_segment['camera_name']} from {current_segment['start_time_raw']} to {current_segment['end_time']} duration: {duration}s")
    journey.append({
        'camera_name': current_segment['camera_name'],
        'entry_time': current_segment['entry_time'],
        'duration': duration,
        'start_time_raw': current_segment['start_time_raw'].isoformat()
    })
    
    face_proc_logger.debug(f"[DONE] Final journey: {journey}")
    return journey

def get_movement_history(person_name):
    """
    Recalculate the entire journey for the given person from scratch.
    This function always queries the database and processes all detections,
    ensuring the most updated data is returned.
    """
    with current_app.app_context():
        detections = Detection.query.filter_by(person=person_name).order_by(Detection.timestamp).all()
        face_proc_logger.debug(f"[HISTORY] Found {len(detections)} detections for {person_name}.")
        journey = get_person_journey(detections)
        face_proc_logger.debug(f"[HISTORY] Calculated journey: {journey}")
        return journey
