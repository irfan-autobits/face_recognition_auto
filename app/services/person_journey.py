# app/services/person_journey.py
from app.models.model import Detection, Camera_list, Raw_Embedding, db
from flask import current_app
from config.logger_config import cam_stat_logger 
from datetime import datetime

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


movement_cache = {}

def get_person_journey(detections):
    """
    Process ordered detections for a person and merge consecutive detections 
    from the same camera into segments.
    Each segment contains:
      - 'camera_name': name of the camera
      - 'entry_time': the time of the first detection (formatted as a string)
      - 'duration': time difference in seconds between the first and last detection in that segment
    """
    if not detections:
        return []

    journey = []
    # Start the first segment with the first detection
    current_segment = {
        'camera_name': detections[0].camera_name,
        'entry_time': detections[0].timestamp.strftime('%Y-%m-%d %H:%M:%S'),
        'start_time': detections[0].timestamp,  # Keep as datetime for calculation
        'end_time': detections[0].timestamp
    }
    
    for det in detections[1:]:
        if det.camera_name == current_segment['camera_name']:
            # Update end_time if still the same camera
            current_segment['end_time'] = det.timestamp
        else:
            # Compute duration for the current segment
            duration = (current_segment['end_time'] - current_segment['start_time']).total_seconds()
            journey.append({
                'camera_name': current_segment['camera_name'],
                'entry_time': current_segment['entry_time'],
                'duration': duration
            })
            # Start a new segment for the new camera
            current_segment = {
                'camera_name': det.camera_name,
                'entry_time': det.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                'start_time': det.timestamp,
                'end_time': det.timestamp
            }
    
    # Append the last segment
    duration = (current_segment['end_time'] - current_segment['start_time']).total_seconds()
    journey.append({
        'camera_name': current_segment['camera_name'],
        'entry_time': current_segment['entry_time'],
        'duration': format_duration(duration)
    })
    
    return journey


def get_movement_history(person_name):
    if person_name in movement_cache:
        print(f"Cache hit for {person_name}")
        return movement_cache[person_name]  # Return cached data

    print(f"Cache miss for {person_name}, processing...")
    detections = Detection.query.filter_by(person=person_name).order_by(Detection.timestamp).all()
    path = get_person_journey(detections)

    movement_cache[person_name] = path  # Store result in cache
    return path

def update_movement_history(person_name):
    # If no cached data, process from scratch
    if person_name not in movement_cache or not movement_cache[person_name]:
        return get_movement_history(person_name)

    # Convert the last cached entry_time to a datetime object
    last_entry_str = movement_cache[person_name][-1]["entry_time"]
    last_known_time = datetime.strptime(last_entry_str, '%Y-%m-%d %H:%M:%S')

    # Query new detections after the last known time
    new_detections = Detection.query.filter(
        Detection.person == person_name,
        Detection.timestamp > last_known_time
    ).order_by(Detection.timestamp).all()

    if not new_detections:
        # No new detections; return cached data
        return movement_cache[person_name]

    # Process new detections to create a new journey segment list
    new_journey = get_person_journey(new_detections)

    # Merge new journey with cached data if the last camera is the same as the first new segment
    cached_journey = movement_cache[person_name]
    if new_journey:
        if cached_journey[-1]["camera_name"] == new_journey[0]["camera_name"]:
            # Update the duration of the last segment: from its start to the new segment's entry_time
            last_segment_start = datetime.strptime(cached_journey[-1]["entry_time"], '%Y-%m-%d %H:%M:%S')
            new_entry_time = datetime.strptime(new_journey[0]["entry_time"], '%Y-%m-%d %H:%M:%S')
            cached_journey[-1]["duration"] = (new_entry_time - last_segment_start).total_seconds()
            # Append the rest of the new journey (skip the first segment which is merged)
            cached_journey.extend(new_journey[1:])
        else:
            # Cameras differ; just append new segments
            cached_journey.extend(new_journey)
    else:
        # No new journey segments (shouldn't happen, but just in case)
        pass
    print(f"returning journy is : {cached_journey}")
    return cached_journey

def List_knownperson():
    """API endpoint to list all known person"""
    try:
        with current_app.app_context():
            subjects = Raw_Embedding.query.all()
            person_list = []
            for sub in subjects:
                person_list.append({
                    'subject_name': sub.subject_name,
                })
            # print(f"returnning known people : {person_list}")
            return {'subjects': person_list}, 200
    except Exception as e:
        db.session.rollback()
        cam_stat_logger.error(f"Failed to list subjects: {str(e)}")
        return {'error': str(e)}, 500

