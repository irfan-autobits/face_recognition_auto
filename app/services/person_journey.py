from app.models.model import Detection, Embedding, Subject, db
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
    from cameras, grouping by camera tag rather than by camera name.
    Each segment includes:
      - 'camera_tag': tag of the camera (e.g., "Meeting Room")
      - 'entry_time': formatted time of the first detection (without microseconds)
      - 'start_time_raw': the raw datetime (with microseconds zeroed)
      - 'duration': time difference in seconds between the first and last detection in that segment
    """
    if not detections:
        return []

    journey = []
    # Use the first detection’s timestamp, with microseconds stripped, and its tag.
    first_time = detections[0].timestamp.replace(microsecond=0)
    cam_tag = detections[0].camera_tag  # Correctly take the first detection's tag.
    current_segment = {
        'camera_tag': cam_tag,
        'entry_time': first_time.strftime('%Y-%m-%d %H:%M:%S'),
        'start_time_raw': first_time,
        'end_time': first_time
    }
    
    face_proc_logger.debug(f"[START] New journey. First detection: {first_time.isoformat()} on tag: {cam_tag}")

    for det in detections[1:]:
        dt = det.timestamp.replace(microsecond=0)
        # Use each detection's own tag instead of detections[0]'s tag.
        det_tag = det.camera_tag  
        face_proc_logger.debug(f"[DETECTION] {det.camera_name} (tag: {det_tag}) @ {dt.isoformat()}")

        # Skip duplicate timestamps for the same segment.
        if det_tag == current_segment['camera_tag'] and dt == current_segment['start_time_raw']:
            face_proc_logger.debug("[SKIP] Duplicate timestamp for same tag. Skipping.")
            continue

        if det_tag == current_segment['camera_tag']:
            current_segment['end_time'] = dt
            face_proc_logger.debug(f"[UPDATE] Extended segment end_time to {dt.isoformat()} for tag {det_tag}")
        else:
            duration = (current_segment['end_time'] - current_segment['start_time_raw']).total_seconds()
            face_proc_logger.debug(f"[SEGMENT DONE] {current_segment['camera_tag']} from {current_segment['start_time_raw']} to {current_segment['end_time']} duration: {duration}s")
            journey.append({
                'camera_tag': current_segment['camera_tag'],
                'entry_time': current_segment['entry_time'],
                'duration': format_duration(duration),
                'start_time_raw': current_segment['start_time_raw'].isoformat()
            })
            # Start a new segment for the new tag.
            current_segment = {
                'camera_tag': det_tag,
                'entry_time': dt.strftime('%Y-%m-%d %H:%M:%S'),
                'start_time_raw': dt,
                'end_time': dt
            }
            face_proc_logger.debug(f"[NEW SEGMENT] New segment started at {dt.isoformat()} on tag {det_tag}")

    # Append the final segment.
    duration = (current_segment['end_time'] - current_segment['start_time_raw']).total_seconds()
    face_proc_logger.debug(f"[FINAL SEGMENT] {current_segment['camera_tag']} from {current_segment['start_time_raw']} to {current_segment['end_time']} duration: {duration}s")
    journey.append({
        'camera_tag': current_segment['camera_tag'],
        'entry_time': current_segment['entry_time'],
        'duration': format_duration(duration),
        'start_time_raw': current_segment['start_time_raw'].isoformat()
    })
    
    face_proc_logger.debug(f"[DONE] Final journey: {journey}")
    return journey

def get_movement_history(person_name, start_time, end_time):
    """
    Recalculate the entire journey for the given person from scratch.
    This function always queries the database and processes all detections,
    ensuring the most updated data is returned.
    """
    utc = pytz.UTC
    # Convert string to datetime if needed
    start_dt = datetime.fromisoformat(start_time)
    end_dt = datetime.fromisoformat(end_time)
    end_dt = end_dt.replace(second=59, microsecond=999999)

    # Localize if naive
    if start_dt.tzinfo is None:
        start_dt = utc.localize(start_dt)
    if end_dt.tzinfo is None:
        end_dt = utc.localize(end_dt)
    # Query filtered by person and time
    with current_app.app_context():
        detections = Detection.query.filter(Detection.person == person_name,Detection.timestamp >= start_dt,Detection.timestamp <= end_dt).order_by(Detection.timestamp.asc()).all()
        # test_detections = Detection.query.all()
        # for det in test_detections:
        #     print(f"Start: {start_dt.isoformat()}")
        #     print(f"TS:    {det.timestamp.isoformat()}")
        #     print(f"End:   {end_dt.isoformat()}")
        #     print(f"result :{start_dt <= det.timestamp <= end_dt}")
        journey = get_person_journey(detections)
        face_proc_logger.debug(f"[HISTORY] Calculated journey: {journey}")
        return journey
