# app/services/table_stats.py
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

def giving_system_stats():
    try:
        model_used = MODEL_PACK_NAME

        total_detections = db.session.query(func.count(Detection.id)).scalar()
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
            "subjects":         subjects
        }), 200

    except Exception as e:
        db.session.rollback()
        face_proc_logger.error(f"Error gathering system stats: {e}")
        return jsonify({ "error": str(e) }), 500

def giving_detection_stats(start_str, end_str):
    try:
        # 1️⃣ Parse inputs and build UTC range
        if start_str and end_str:
            # user-supplied window
            start_dt = parse_iso(start_str)
            end_dt   = parse_iso(end_str)
            # bump to end of day if they only provided a date
            if end_dt.hour == 0 and end_dt.minute == 0 and end_dt.second == 0:
                end_dt = end_dt.replace(hour=23, minute=59, second=59, microsecond=999999)
            start_utc = to_utc(start_dt)
            end_utc   = to_utc(end_dt)
            face_proc_logger.info(f"Detection stats window: {start_utc} to {end_utc}")
        else:
            # default to “today from midnight until now”
            face_proc_logger.info("No start/end, defaulting to today")
            local_mid = now_local().replace(hour=0, minute=0, second=0, microsecond=0)
            start_utc = to_utc(local_mid)
            end_utc   = to_utc(now_local())

        # 2️⃣ Day-wise counts
        results = (
            db.session.query(
                func.date(Detection.timestamp).label("date"),
                func.count(Detection.id).label("count")
            )
            .filter(and_(
                Detection.timestamp >= start_utc,
                Detection.timestamp <= end_utc
            ))
            .group_by("date")
            .order_by("date")
            .all()
        )

        # Build a list of dates between start and end (inclusive)
        local_start = start_utc.date()
        local_end   = end_utc.date()
        face_proc_logger.info(f"start {local_start} and {local_end} provided for detection stats")
        
        days = (local_end - local_start).days + 1
        date_window = [local_start + timedelta(days=i) for i in range(days)]

        counts_by_date = {r.date: r.count for r in results}
        day_stats = [
            {"date": d.isoformat(), "count": counts_by_date.get(d, 0)}
            for d in date_window
        ]

        # 3️⃣ Camera-wise totals (ignoring date)
        cam_rows = (
            db.session.query(
                Camera.camera_name.label("camera"),
                func.count(Detection.id).label("count")
            )
            .join(Detection, Detection.camera_id == Camera.id)
            .group_by(Camera.camera_name)
            .all()
        )
        cam_stats = [{"camera": r.camera, "count": r.count} for r in cam_rows]

        # 4️⃣ Subject-wise totals (ignoring date)
        sub_rows = (
            db.session.query(
                func.coalesce(Subject.subject_name, literal('Unknown')).label('subject'),
                func.count(Detection.id).label('count')
            )
            .select_from(Detection)
            .outerjoin(Subject, Detection.subject_id == Subject.id)
            .group_by('subject')
            .all()
        )
        sub_stats = [{"subject": r.subject, "count": r.count} for r in sub_rows]
        face_proc_logger.info(f"stats returned are {day_stats}")
        return jsonify({
            "day_stats":     day_stats,
            "camera_stats":  cam_stats,
            "subject_stats": sub_stats
        }), 200

    except Exception as e:
        db.session.rollback()
        face_proc_logger.error(f"Failed to gather detection stats: {e}")
        return jsonify({"error": str(e)}), getattr(e, 'code', 500)

# app/services/table_stats.py
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
            if sort_field == 'id':
                sort_col = Detection.rec_no
            elif sort_field == 'subject':
                sort_col = Subject.subject_name
            elif sort_field == 'camera_name':
                sort_col = Camera.camera_name
            elif sort_field == 'camera_tag':
                sort_col = Camera.tag
            elif sort_field in ('det_score','distance','timestamp'):
                sort_col = getattr(Detection, sort_field)
            else:
                sort_col = Detection.timestamp

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
            from app.utils.time_utils import to_utc_iso
            body = []
            for d in detections:
                body.append({
                    "id":          d.rec_no,             # keep it numeric
                    "subject":     d.subject_name or "Unknown",
                    "camera_name": d.camera_name or "Unknown",
                    "camera_tag":  d.camera_tag or "Unknown",
                    "det_score":   d.det_score,
                    "distance":    d.distance,
                    "timestamp":   to_utc_iso(d.timestamp),
                    "det_face":    d.det_face,
                })

            # → compute total *after* filtering, before pagination
            total = query.with_entities(func.count(Detection.id)).scalar()

            return {
                'detections': body,
                'page':       page,
                'limit':      limit,
                'total':      total,
            }, 200

    except Exception as e:
        db.session.rollback()
        cam_stat_logger.error(f"Failed to list detections: {str(e)}")
        return {'error': str(e)}, 500