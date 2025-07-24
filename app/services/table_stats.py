# app/services/table_stats.py
import math
from sqlalchemy.orm import joinedload
from sqlalchemy import and_
from flask import jsonify, current_app
from config.logger_config import cam_stat_logger, face_proc_logger
from config.paths import MODEL_PACK_NAME
from sqlalchemy import func, distinct, literal
from app.models.model import db, Detection, Subject, Camera, Img, Embedding
from datetime import datetime, timedelta
from collections import defaultdict
from app.utils.time_utils import now_local, to_utc, parse_iso
from app.services.camera_manager import camera_service
from app.services.reco_table_helper import *
import traceback

def giving_system_stats():
    try:
        model_used = MODEL_PACK_NAME

        total_detections = db.session.query(func.count(Detection.id)).scalar()
        total_cameras = db.session.query(func.count(Camera.id)).scalar()
        total_active_cameras = camera_service.count_running_streams()
        # count DISTINCT images & embeddings per subject
        subject_stats = (
            db.session.query(
                Subject.id.label("subject_id"),
                Subject.subject_name,
                func.count(distinct(Img.id)).label("image_count"),
                func.count(distinct(Embedding.id)).label("embedding_count")
            )
            .outerjoin(Img,        Img.subject_id == Subject.id)
            .outerjoin(Embedding,  Embedding.subject_id == Subject.id)
            .group_by(Subject.id, Subject.subject_name)
            .all()
        )

        subjects = []
        for row in subject_stats:
            subjects.append({
                "subject_id":       str(row.subject_id),
                "subject_name":     row.subject_name,
                "image_count":      row.image_count,
                "embedding_count":  row.embedding_count,
            })
        
        return jsonify({
            "model":            model_used,
            "total_detections": total_detections,
            "active_cameras":   total_active_cameras,
            "total_cameras": total_cameras,
            "subjects":         subjects
        }), 200

    except Exception as e:
        db.session.rollback()
        face_proc_logger.error(f"Error gathering system stats: {e}")
        return jsonify({ "error": str(e) }), 500

# def giving_detection_stats(start_str, end_str):
#     try:
#         # 1️⃣ Parse inputs and build UTC range
#         if start_str and end_str:
#             # user-supplied window
#             start_dt = parse_iso(start_str)
#             end_dt   = parse_iso(end_str)
#             # bump to end of day if they only provided a date
#             if end_dt.hour == 0 and end_dt.minute == 0 and end_dt.second == 0:
#                 end_dt = end_dt.replace(hour=23, minute=59, second=59, microsecond=999999)
#             start_utc = to_utc(start_dt)
#             end_utc   = to_utc(end_dt)
#             face_proc_logger.info(f"Detection stats window: {start_utc} to {end_utc}")
#         else:
#             # default to “today from midnight until now”
#             face_proc_logger.info("No start/end, defaulting to today")
#             local_mid = now_local().replace(hour=0, minute=0, second=0, microsecond=0)
#             start_utc = to_utc(local_mid)
#             end_utc   = to_utc(now_local())

#         # 2️⃣ Day-wise counts
#         results = (
#             db.session.query(
#                 func.date(Detection.timestamp).label("date"),
#                 func.count(Detection.id).label("count")
#             )
#             .filter(and_(
#                 Detection.timestamp >= start_utc,
#                 Detection.timestamp <= end_utc
#             ))
#             .group_by("date")
#             .order_by("date")
#             .all()
#         )

#         # Build a list of dates between start and end (inclusive)
#         local_start = start_utc.date()
#         local_end   = end_utc.date()
#         face_proc_logger.info(f"start {local_start} and {local_end} provided for detection stats")
        
#         days = (local_end - local_start).days + 1
#         date_window = [local_start + timedelta(days=i) for i in range(days)]

#         counts_by_date = {r.date: r.count for r in results}
#         day_stats = [
#             {"date": d.isoformat(), "count": counts_by_date.get(d, 0)}
#             for d in date_window
#         ]

#         # 3️⃣ Camera-wise totals (ignoring date)
#         cam_rows = (
#             db.session.query(
#                 Camera.camera_name.label("camera"),
#                 func.count(Detection.id).label("count")
#             )
#             .join(Detection, Detection.camera_id == Camera.id)
#             .group_by(Camera.camera_name)
#             .all()
#         )
#         cam_stats = [{"camera": r.camera, "count": r.count} for r in cam_rows]

#         # 4️⃣ Subject-wise totals (ignoring date)
#         sub_rows = (
#             db.session.query(
#                 func.coalesce(Subject.subject_name, literal('Unknown')).label('subject'),
#                 func.count(Detection.id).label('count')
#             )
#             .select_from(Detection)
#             .outerjoin(Subject, Detection.subject_id == Subject.id)
#             .group_by('subject')
#             .all()
#         )
#         sub_stats = [{"subject": r.subject, "count": r.count} for r in sub_rows]
#         face_proc_logger.info(f"stats returned are {day_stats}")
#         return jsonify({
#             "day_stats":     day_stats,
#             "camera_stats":  cam_stats,
#             "subject_stats": sub_stats
#         }), 200

#     except Exception as e:
#         db.session.rollback()
#         face_proc_logger.error(f"Failed to gather detection stats: {e}")
#         return jsonify({"error": str(e)}), getattr(e, 'code', 500)


def giving_detection_stats(time_window_start=None, time_window_end=None, interval='hourly'):
    try:
        # print(f"time_window_start",time_window_start)
        # print(f"time_window_end",time_window_end)
        cam_stat_logger.info(f"det_stat_start: {time_window_start}, end: {time_window_end}")
        # Default to last 24 hours if no window specified
        # Group by clause depends on interval
        if interval == 'hourly':
            if not time_window_start:
                # Default to today in local time
                today = now_local().replace(hour=0, minute=0, second=0, microsecond=0)
            else:
                today = parse_iso(time_window_start).replace(hour=0, minute=0, second=0, microsecond=0)
            
            start_utc = to_utc(today)
            end_utc = start_utc + timedelta(hours=23, minutes=59, seconds=59, microseconds=999999)
            group_by = func.date_trunc('hour', Detection.timestamp)
            delta = timedelta(hours=1)

        else:  # daily
            if not time_window_start or not time_window_end:
                end_dt = now_local()
                start_dt = end_dt - timedelta(days=7)  # or 1 day, or your default
            else:
                start_dt = parse_iso(time_window_start)
                end_dt = parse_iso(time_window_end)
                if end_dt.time() == datetime.min.time():
                    end_dt = end_dt.replace(hour=23, minute=59, second=59, microsecond=999999)

            start_utc = to_utc(start_dt)
            end_utc = to_utc(end_dt)
            group_by = func.date_trunc('day', Detection.timestamp)
            delta = timedelta(days=1)

        # Generate time intervals
        intervals = []
        current = start_utc
        while current <= end_utc:
            intervals.append(current)
            current += delta

        # Query for time-based stats
        time_results = (
            db.session.query(
                group_by.label("interval"),
                func.count(Detection.id).label("count")
            )
            .filter(and_(
                Detection.timestamp >= start_utc,
                Detection.timestamp <= end_utc
            ))
            .group_by("interval")
            .order_by("interval")
            .all()
        )

        # Build time stats with zero-filling
        counts_by_interval = {
            r.interval.replace(minute=0, second=0, microsecond=0): r.count
            for r in time_results
        }

        time_stats = [
            {"interval": i.isoformat(), "count": counts_by_interval.get(i, 0)}
            for i in intervals
        ]

        # Camera stats for the window
        camera_stats = (
            db.session.query(
                Camera.camera_name.label("camera"),
                func.count(Detection.id).label("count")
            )
            .select_from(Camera)  # Start from Camera table
            .outerjoin(Detection, and_(
                Detection.camera_id == Camera.id,  # Join condition
                Detection.timestamp >= start_utc,  # Time window conditions
                Detection.timestamp <= end_utc
            ))
            .group_by(Camera.camera_name)
            .all()
        )
        # Subject stats for the window
        # Option to include 'Unknown' subjects
        include_unknown = False  # Set to False if you don't want 'Unknown' in results

        subject_query = db.session.query(
            func.coalesce(Subject.subject_name, literal('Unknown')).label('subject'),
            func.count(Detection.id).label('count')
        ).select_from(Detection).outerjoin(
            Subject, Detection.subject_id == Subject.id
        ).filter(
            Detection.timestamp >= start_utc,
            Detection.timestamp <= end_utc
        ).group_by('subject')

        subject_stats = subject_query.all()

        if not include_unknown:
            subject_stats = [r for r in subject_stats if r.subject != 'Unknown']

        return jsonify({
            "interval_stats": time_stats,
            "camera_stats": [{"camera": r.camera, "count": r.count} for r in camera_stats],
            "subject_stats": [{"subject": r.subject, "count": r.count} for r in subject_stats],
            "window": {
                "start": start_utc.isoformat(),
                "end": end_utc.isoformat(),
                "interval": interval
            }
        }), 200

    except Exception as e:
        db.session.rollback()
        face_proc_logger.error(f"Failed to gather interval stats: {e}")
        return jsonify({"error": str(e)}), 500

def recognition_table(params):
    """List all the Recognitions (refactored)."""
    try:
        # 1) base query with date range
        # for key, value in params.items():
            # face_proc_logger.info(f"all params Key: {key}, Value: {value}",)
        base_q = build_base_query(params['start_time'], params['end_time'])
            
        # 2) apply text filters
        filt_q = apply_text_filters(
            base_q,
            params['search'],
            params['subject'],
            params['camera'],
            params['tag']
        )

        # 3) apply sorting
        sorted_q = apply_sorting(
            filt_q,
            params['sort_field'],
            params['sort_order']
        )

        # 4) total count
        total = count_total(filt_q)

        # 5) fetch current page
        detections = fetch_page(sorted_q, params['page'], params['limit'])

        return {
        'detections': serialize_detections(detections),
        'page':       params['page'],
        'offset':      params['limit'],
        'total':      total,
        'total_pages': math.ceil(total / params['limit']),
        }, 200        

    except Exception as e:
        traceback_str = traceback.format_exc()
        current_app.logger.error(f"Failed to list detections: {e} Traceback {traceback_str}")
        db.session.rollback()
        return {'error': str(e)}, 500
    




# app/services/table_stats.py
def heatmap_by_range(start_str: str, end_str: str):
    try:
        today = now_local().date()

        # Parse ISO dates
        start_date = datetime.fromisoformat(start_str).date()
        end_date = datetime.fromisoformat(end_str).date()

        # Validate bounds
        if end_date < start_date:
            return jsonify({"error": "end date must be after start date"}), 400
        if end_date > today:
            return jsonify({"error": "end date cannot be in the future"}), 400

        # Build UTC datetime bounds
        start_dt = to_utc(datetime.combine(start_date, datetime.min.time()))
        end_dt = to_utc(datetime.combine(end_date, datetime.max.time()))

        # Query counts
        results = (
            db.session.query(
                func.date(Detection.timestamp).label("date"),
                func.count(Detection.id).label("count")
            )
            .filter(Detection.timestamp >= start_dt, Detection.timestamp <= end_dt)
            .group_by("date")
            .order_by("date")
            .all()
        )

        date_counts = {r.date.isoformat(): r.count for r in results}
        total_days = (end_date - start_date).days + 1
        all_dates = [start_date + timedelta(days=i) for i in range(total_days)]

        heatmap_data = [
            {"date": d.isoformat(), "count": date_counts.get(d.isoformat(), 0)}
            for d in all_dates
        ]

        return jsonify({
            "data": heatmap_data,
            "start": start_date.isoformat(),
            "end": end_date.isoformat()
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"internal error: {str(e)}"}), 500
