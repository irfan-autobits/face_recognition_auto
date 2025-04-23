# final-compre/app/models/model.py
import uuid
from datetime import datetime
import pytz
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy import Sequence, event
import uuid
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import Column, String, DateTime, ForeignKey
db = SQLAlchemy()

# Helper function to get current UTC time with timezone
def get_current_time_in_timezone():
    return datetime.now(pytz.utc)

class FaceRecogUser(db.Model):
    __tablename__ = 'face_recog_user'
    id       = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email    = db.Column(db.String(50), nullable=False)
    password = db.Column(db.String(50), nullable=False)

    def __repr__(self):
        return f"<User {self.email}>"

class Camera(db.Model):
    __tablename__ = 'camera'
    id           = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    camera_name  = db.Column(db.String(50), nullable=False, unique=True, index=True)
    camera_url   = db.Column(db.Text, nullable=False)
    tag          = db.Column(db.String(50), nullable=False)

    detections   = db.relationship(
        'Detection', back_populates='camera', lazy='dynamic', passive_deletes=True
    )
    camera_event = db.relationship(
        'CameraEvent', backref='camera', lazy='dynamic', cascade='all, delete-orphan'
    )
    def __repr__(self):
        return f"<Camera {self.camera_name} ({self.tag})>"

class CameraEvent(db.Model):
    __tablename__ = 'camera_event'
    id         = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # — Camera link; on delete, set FK null —
    camera_id  = db.Column(UUID(as_uuid=True), db.ForeignKey('camera.id'), nullable=True)

    event_type = db.Column(db.String(10), nullable=False)  # 'camera' or 'feed'
    action     = db.Column(db.String(10), nullable=False)  # 'start' or 'stop'
    timestamp  = db.Column(
        db.DateTime(timezone=True), default=get_current_time_in_timezone, index=True
    )
    def __repr__(self):
        return f"<CameraEvent {self.event_type} {self.action} ({self.timestamp})"

class Subject(db.Model):
    __tablename__ = 'subject'
    id           = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    subject_name = db.Column(db.String(100), nullable=False, unique=True)
    added_date   = db.Column(db.DateTime(timezone=True), nullable=False,
                             default=get_current_time_in_timezone)
    age          = db.Column(db.Integer)
    gender       = db.Column(db.String(10))
    email        = db.Column(db.String(100))
    phone        = db.Column(db.String(15))
    aadhar       = db.Column(db.String(20))

    # one-to-many without cascade; passive_deletes ensures SET NULL works
    detections   = db.relationship(
        'Detection', back_populates='subject', lazy='dynamic', passive_deletes=True
    )

    images       = db.relationship(
        'Img', backref='subject', lazy='dynamic', cascade='all, delete-orphan'
    )
    embeddings   = db.relationship(
        'Embedding', backref='subject', lazy='dynamic', cascade='all, delete-orphan'
    )

    def __repr__(self):
        return f"<Subject {self.subject_name} ({self.id})>"

class Img(db.Model):
    __tablename__ = 'img'
    id         = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    image_url  = db.Column(db.String(255), nullable=False)
    subject_id = db.Column(UUID(as_uuid=True), db.ForeignKey('subject.id'), nullable=False)

    embeddings = db.relationship(
        'Embedding', backref='image', lazy='dynamic', cascade='all, delete-orphan'
    )

    def __repr__(self):
        return f"<Img {self.id}>"

class Embedding(db.Model):
    __tablename__ = 'embedding'
    id         = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    embedding  = db.Column(ARRAY(db.Float), nullable=False)
    calculator = db.Column(db.String(255), nullable=False)
    subject_id = db.Column(UUID(as_uuid=True), db.ForeignKey('subject.id'), nullable=False)
    img_id     = db.Column(UUID(as_uuid=True), db.ForeignKey('img.id'), nullable=False)

    def __repr__(self):
        return f"<Embedding {self.id}>"

class Detection(db.Model):
    __tablename__ = 'detection'
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # auto-increment rec_no
    rec_no_seq = Sequence('detection_rec_no_seq', metadata=db.metadata)
    rec_no     = db.Column(
        db.Integer, rec_no_seq, server_default=rec_no_seq.next_value(),
        unique=True, nullable=False
    )

    # — Subject link; on delete, set FK null —
    subject_id = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey('subject.id', ondelete='SET NULL'),
        nullable=True
    )
    subject    = db.relationship('Subject', back_populates='detections', passive_deletes=True)

    # — Camera link; on delete, set FK null —
    camera_id  = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey('camera.id', ondelete='SET NULL'),
        nullable=True
    )
    camera     = db.relationship('Camera', back_populates='detections', passive_deletes=True)

    # snapshot columns
    legacy_subject_name = db.Column(db.String(100), nullable=False)
    legacy_camera_name  = db.Column(db.String(50), nullable=False)
    legacy_camera_tag   = db.Column(db.String(50), nullable=False)

    det_score = db.Column(db.Float, nullable=False)
    distance  = db.Column(db.Float, nullable=False)
    timestamp = db.Column(
        db.DateTime(timezone=True), default=get_current_time_in_timezone, index=True
    )
    det_face  = db.Column(db.Text, nullable=False)

    def __init__(self, *, subject=None, camera, **kwargs):
        # snapshot into legacy_* before FKs applied
        kwargs.setdefault('legacy_subject_name', subject.subject_name if subject else 'Unknown')
        kwargs.setdefault('legacy_camera_name',  camera.camera_name)
        kwargs.setdefault('legacy_camera_tag',   camera.tag)
        kwargs.setdefault('subject_id',          subject.id if subject else None)
        kwargs.setdefault('camera_id',           camera.id)
        super().__init__(**kwargs)

    @property
    def subject_name(self):
        if self.subject:
            return self.subject.subject_name
        if self.legacy_subject_name == "Unknown":
            return "Unknown"
        return f"unlink_{self.legacy_subject_name}"

    @property
    def camera_name(self):
        return self.camera.camera_name if self.camera else f"unlink_{self.legacy_camera_name}"

    @property
    def camera_tag(self):
        return self.camera.tag if self.camera else f"unlink_{self.legacy_camera_tag}"

    def __repr__(self):
        return f"<Detection {self.rec_no}: {self.subject_name} @ {self.camera_name}>"

# Event listeners to snapshot before deletes
@event.listens_for(Subject, 'before_delete')
def _snapshot_subject(mapper, connection, target):
    connection.execute(
        Detection.__table__.update()
        .where(Detection.subject_id == target.id)
        .values(
            legacy_subject_name=target.subject_name,
            subject_id=None
        )
    )

@event.listens_for(Camera, 'before_delete')
def _snapshot_camera(mapper, connection, target):
    connection.execute(
        Detection.__table__.update()
        .where(Detection.camera_id == target.id)
        .values(
            legacy_camera_name=target.camera_name,
            legacy_camera_tag=target.tag,
            camera_id=None
        )
    )

# class Location(db.Model):
#     __tablename__ = 'location'
#     id = db.Column(db.Integer, primary_key=True)
#     name = db.Column(db.String(100), nullable=False)   # e.g., "Building A", "Floor 1", "Room 101"
#     type = db.Column(db.String(50), nullable=False)      # e.g., "building", "floor", "room", "hall", etc.
    
#     # Self-referential foreign key; if this location is a child (e.g., a room), parent_id points to its parent.
#     parent_id = db.Column(db.Integer, db.ForeignKey('location.id'), nullable=True)
    
#     # Relationship to represent the hierarchical structure. "children" will be a list of Location objects.
#     children = db.relationship('Location',
#                                backref=db.backref('parent', remote_side=[id]),
#                                lazy=True)
    
#     def __repr__(self):
#         return f"<Location {self.name} ({self.type})>"