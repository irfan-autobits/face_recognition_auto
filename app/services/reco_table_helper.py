# app/services/reco_table_helper.py
from sqlalchemy.orm import joinedload
from sqlalchemy import func
from app.models.model import Detection, Subject, Camera
from app.utils.time_utils import parse_iso, to_utc_iso

# ─── HELPER 1 ───
def parse_params(args):
    """Extract and validate all query params from request.args."""
    return {
        'page':       int(args.get('page',  1)),
        'limit':      int(args.get('offset', 100)),
        'search':     args.get('search', '',),
        'subject':    args.get('subject', ''),
        'camera':     args.get('camera',  ''),
        'tag':        args.get('tag',     ''),
        'sort_field': args.get('sort_field', 'timestamp'),
        'sort_order': args.get('sort_order', 'desc' ),
        'start_time': args.get('start'),
        'end_time':   args.get('end'),
    }

# ─── HELPER 2 ───
def build_base_query(start_iso, end_iso):
    """Return a Query on Detection with Subject/Camera joined and date filters applied."""
    if start_iso and end_iso is not None :
        start_dt = parse_iso(start_iso)
        end_dt   = parse_iso(end_iso)
        print(f"final check start raw: {start_iso} to: {start_dt}")
        print(f"final check end raw: {end_iso} to: {end_dt}")
        return (
            Detection.query
            .outerjoin(Subject)
            .outerjoin(Camera)
            .filter(Detection.timestamp >= start_dt,
                    Detection.timestamp <  end_dt)
        )
    else:
        return(
            Detection.query.outerjoin(Subject).outerjoin(Camera)
        )
# ─── HELPER 3 ───
def apply_text_filters(query, search, subject, camera, tag):
    """Chain on any full-text filters for search, subject, camera, tag."""
    if search:
        like = f"%{search}%"
        query = query.filter(
            Subject.subject_name.ilike(like) |
            Camera.camera_name .ilike(like) |
            Camera.tag         .ilike(like)
        )
    if subject:
        query = query.filter(Subject.subject_name.ilike(f"%{subject}%"))
    if camera:
        query = query.filter(Camera.camera_name.ilike(f"%{camera}%"))
    if tag:
        query = query.filter(Camera.tag.ilike(f"%{tag}%"))
    return query

# ─── HELPER 4 ───
def apply_sorting(query, sort_field, sort_order):
    """Turn sort_field + sort_order into an ORDER BY clause."""
    if sort_field == 'id':
        col = Detection.rec_no
    elif sort_field == 'subject':
        col = Subject.subject_name
    elif sort_field == 'camera_name':
        col = Camera.camera_name
    elif sort_field == 'camera_tag':
        col = Camera.tag
    elif sort_field in ('det_score','distance','timestamp'):
        col = getattr(Detection, sort_field)
    else:
        col = Detection.timestamp

    col = col.asc() if sort_order == 'asc' else col.desc()
    return query.order_by(col)

# ─── HELPER 5 ───
def fetch_page(query, page, limit):
    """Apply eager‐load, offset, limit, then execute .all()."""
    # offset = (page - 1) * limit
    offset = max(0, (page - 1) * limit)
    print(f"in helper offset:{offset}, page:{page}, limit:{limit}")
    return (
        query
        .options(
            joinedload(Detection.subject),
            joinedload(Detection.camera),
        )
        .offset(offset)
        .limit(limit)
        .all()
    )

# ─── HELPER 6 ───
def serialize_detections(detections):
    """Convert ORM Detection objects into JSON-serializable dicts."""
    body = []
    for d in detections:
        body.append({
            "id":          d.rec_no,
            "subject":     d.subject_name or "Unknown",
            "camera_name": d.camera_name, 
            "camera_tag":  d.camera_tag,
            "det_score":   f"{d.det_score:.2f}%",
            "distance":    f"{d.distance:.2f}",
            "timestamp":   to_utc_iso(d.timestamp),
            "det_face":    d.det_face,
        })
    return body

# ─── HELPER 7 ───
def count_total(query):
    """Return the total count of rows in 'query' (before pagination)."""
    return query.with_entities(func.count(Detection.id)).scalar()