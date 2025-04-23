from sqlalchemy.orm import joinedload
from flask import jsonify, current_app
from config.logger_config import cam_stat_logger, face_proc_logger
from config.paths import MODEL_PACK_NAME
from sqlalchemy import func, distinct, literal
from app.models.model import db, Detection, Subject, Camera, Img, Embedding
from datetime import datetime, timedelta
from collections import defaultdict

def giving_system_stats():
    try:
        model_used = MODEL_PACK_NAME

        total_detections = db.session.query(func.count(Detection.id)).scalar()
        total_subjects   = db.session.query(func.count(Subject.id)).scalar()

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
            "total_subjects":   total_subjects,
            "subjects":         subjects
        }), 200

    except Exception as e:
        db.session.rollback()
        face_proc_logger.error(f"Error gathering system stats: {e}")
        return jsonify({ "error": str(e) }), 500

def giving_detection_stats():
    try:
        # Step 1: Date range: last 30 days
        end_date = datetime.today().date()
        start_date = end_date - timedelta(days=29)
        date_window = [start_date + timedelta(days=i) for i in range(30)]

        # Step 2: Get actual counts from DB
        results = (
            db.session.query(
                func.date(Detection.timestamp).label("date"),
                func.count(Detection.id).label("count")
            )
            .filter(func.date(Detection.timestamp) >= start_date)
            .group_by("date")
            .order_by("date")
            .all()
        )

        # Step 3: Convert query results into a dict
        counts_by_date = {row.date: row.count for row in results}

        # Step 4: Merge
        day_stats = []
        for d in date_window:
            day_stats.append({
                "date": d.isoformat(),
                "count": counts_by_date.get(d, 0)
            })
            # face_proc_logger.info(f"day_stats: {row} - {counts_by_cam.get(row,0)}")

        # 2) Camera‑wise totals
        cams = Camera.query.all()
        cam_window = [cam.camera_name for cam in cams]

        cam_rows = (
            db.session
            .query(
                Camera.camera_name.label("camera"),
                func.count(Detection.id).label("count")
            )
            .join(Detection, Detection.camera_id == Camera.id)
            .group_by(Camera.camera_name)
            .all()
        )
        counts_by_cam = {row.camera: row.count for row in cam_rows}

        cam_stats = []
        for row in cam_window:
            cam_stats.append({"camera": row, "count": counts_by_cam.get(row,0)})
            # face_proc_logger.info(f"cam_stats: {row} - {counts_by_cam.get(row,0)}")

        # 3) Subject-wise totals, including “Unknown” bucket
        sub_rows = (
            db.session
            .query(
                func.coalesce(Subject.subject_name, literal('Unknown')).label('subject'),
                func.count(Detection.id).label('count')
            )
            .select_from(Detection)                       # ← start from detections
            .outerjoin(Subject, Detection.subject_id == Subject.id)
            .group_by('subject')                          # ← group by the alias  
            .all()
        )

        # Turn it into a simple list/dict for your UI:
        sub_stats = [
            {'subject': row.subject, 'count': row.count}
            for row in sub_rows
        ]
            
        return jsonify({
            "day_stats": day_stats,
            "camera_stats": cam_stats,
            "subject_stats": sub_stats
        }), 200

    except Exception as e:
        db.session.rollback()
        face_proc_logger.error(f"Failed to gather stats: {e}")
        return jsonify({"error": str(e)}), 500
        
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
                body.append({
                    "id":          str(d.rec_no),
                    "subject":     d.subject_name or "Unknown",
                    "camera_name": d.camera_name or "Unknown",
                    "camera_tag":  d.camera_tag or "Unknown",
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