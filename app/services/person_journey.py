# app/services/person_journey.py
from datetime import datetime, timedelta
import pytz
from flask import current_app
from app.models.model import Detection, Subject
from config.logger_config import face_proc_logger
from app.utils.time_utils import parse_iso, to_local

def format_duration(seconds):
    seconds = int(seconds)
    hours   = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs    = seconds % 60
    parts   = []
    if hours:   parts.append(f"{hours}h")
    if minutes: parts.append(f"{minutes}m")
    if secs or not parts:
        parts.append(f"{secs}s")
    return " ".join(parts)

def get_person_journey_update(detections):
    """
    Build journey segments by merging consecutive detections with the same tag
    only if they occur within MAX_GAP (5 seconds).
    """
    if not detections:
        return []

    MAX_GAP = timedelta(seconds=5)  # Break segment if gap exceeds 5 seconds
    journey = []
    
    # Initialize first segment with null-safe tag access
    first_utc = detections[0].timestamp.replace(microsecond=0)
    current_segment = {
        'camera_tag': detections[0].m,  # Use legacy tag directly
        'start_utc': first_utc,
        'last_utc': first_utc
    }

    for det in detections[1:]:
        ts_utc = det.timestamp.replace(microsecond=0)
        # Always use legacy_camera_tag to avoid null issues
        tag = det.legacy_camera_tag
        
        # Calculate time gap from last detection
        gap = ts_utc - current_segment['last_utc']
        
        # Merge only if same tag AND within time gap threshold
        if tag == current_segment['camera_tag'] and gap <= MAX_GAP:
            current_segment['last_utc'] = ts_utc  # Extend segment
        else:
            # Finalize current segment
            dur = (current_segment['last_utc'] - current_segment['start_utc']).total_seconds()
            entry_time_local = to_local(current_segment['start_utc'])
            journey.append({
                'camera_tag': current_segment['camera_tag'],
                'entry_time': current_segment['start_utc'].strftime("%Y-%m-%dT%H:%M:%SZ"),
                'duration': format_duration(dur),
                'start_time_raw': entry_time_local.isoformat()
            })
            
            # Start new segment
            current_segment = {
                'camera_tag': tag,
                'start_utc': ts_utc,
                'last_utc': ts_utc
            }

    # Final segment
    dur = (current_segment['last_utc'] - current_segment['start_utc']).total_seconds()
    entry_time_local = to_local(current_segment['start_utc'])
    tm = current_segment['start_utc'].strftime("%Y-%m-%dT%H:%M:%SZ")
    face_proc_logger.info(f"camera_tag:{current_segment['camera_tag']},\n entry_time:{tm},\n duration:{format_duration(dur)}")
    journey.append({
        'camera_tag': current_segment['camera_tag'],
        'entry_time': current_segment['start_utc'].strftime("%Y-%m-%dT%H:%M:%SZ"),
        'duration': format_duration(dur),
        'start_time_raw': entry_time_local.isoformat()
    })
    return journey

def get_person_journey(detections):
    """
    Build a list of { camera_tag, entry_time, duration, start_time_raw }
    by merging consecutive detections with the same tag.
    """
    if not detections:
        return []

    journey = []
    # Use the first detection’s timestamp, with microseconds stripped, and its tag.
    first_time = detections[0].timestamp.replace(microsecond=0)
    entry_time_local = to_local(first_time)
    current_segment = {
        'camera_tag':     detections[0].camera.tag,
        # call astimezone on the datetime, not .timestamp()
        'entry_time':     entry_time_local.astimezone(pytz.UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        'start_time_raw': entry_time_local,
        'end_time':       entry_time_local
    }
    face_proc_logger.debug(f"[START] {entry_time_local.isoformat()} tag={current_segment['camera_tag']}")

    for det in detections[1:]:
        ts = det.timestamp.replace(microsecond=0)
        tag = det.camera.tag

        if tag == current_segment['camera_tag']:
            # extend same‑tag segment
            current_segment['end_time'] = ts
        else:
            # close out old segment
            dur = (current_segment['end_time'] - current_segment['start_time_raw']).total_seconds()
            journey.append({
                'camera_tag': current_segment['camera_tag'],
                'entry_time': current_segment['entry_time'],
                'duration':   format_duration(dur),
                'start_time_raw': current_segment['start_time_raw'].isoformat()
            })
            face_proc_logger.debug(f"[SEGMENT] {current_segment['camera_tag']} → {format_duration(dur)}")

            # start new one
            current_segment = {
                'camera_tag':     tag,
                # use the datetime itself, then convert to UTC ISO
                'entry_time':     ts.astimezone(pytz.UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
                'start_time_raw': ts,
                'end_time':       ts
            }
            face_proc_logger.debug(f"[NEW] {ts.isoformat()} tag={tag}")

    # final segment
    dur = (current_segment['end_time'] - current_segment['start_time_raw']).total_seconds()
    journey.append({
        'camera_tag': current_segment['camera_tag'],
        'entry_time': current_segment['entry_time'],
        'duration':   format_duration(dur),
        'start_time_raw': current_segment['start_time_raw'].isoformat()
    })
    face_proc_logger.debug(f"[FINAL] {current_segment['camera_tag']} → {format_duration(dur)}")

    return journey

def get_movement_history(subject_name, start_time, end_time):
    """
    Return the ‘journey’ for one subject between two ISO timestamps.
    entring format : 2025-06-09 13:09:00+00:00

    working
    raw : 2025-06-09T13:31:00.000Z to : 2025-06-09 13:31:00+00:00
    faulty
    raw:  2025-09-05T18:30:00.000Z to:  2025-09-05 18:30:00+00:00
    """
    # parse ISO strings

    now_utc   = datetime.now(pytz.UTC)
    # Parse incoming ISO strings into aware UTC datetimes
    start_dt  = parse_iso(start_time)
    end_dt    = parse_iso(end_time)

    with current_app.app_context():
        # find the subject record
        subject = Subject.query.filter_by(subject_name=subject_name).first()
        if not subject:
            face_proc_logger.error(f"No such Subject: {subject_name}")
            return []

        # fetch detections in range
        dets = (
            Detection.query
            .filter(Detection.subject_id == subject.id)
            .filter(Detection.timestamp >= start_dt,
                    Detection.timestamp <  end_dt)
            .order_by(Detection.timestamp.asc())
            .all()
        )
        face_proc_logger.debug(f"[HISTORY] {len(dets)} detections for “{subject_name}” "
                               f"between {start_dt.isoformat()} and {end_dt.isoformat()} raw : {start_time} to : {start_dt}")
        # return get_person_journey(dets)
        return get_person_journey_update(dets)
