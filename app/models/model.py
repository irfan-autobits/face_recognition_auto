# final-compre/app/models/model.py
from datetime import datetime
import pytz
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.dialects.postgresql import UUID, ARRAY
import uuid
from sqlalchemy import Sequence, Integer

db = SQLAlchemy()

# Helper function to get current UTC time with timezone
def get_current_time_in_timezone():
    return datetime.now(pytz.utc)
    
class Face_recog_User(db.Model):
    id        = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email     = db.Column(db.String(50), nullable=False)
    password  = db.Column(db.String(50), nullable=False)

    def __repr__(self):
        return f"<User {self.email}>"
class Subject(db.Model):
    __tablename__ = 'subject'
    id            = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    subject_name  = db.Column(db.String(100), nullable=False, unique=True)
    added_date    = db.Column(db.DateTime(timezone=True), nullable=False,
                              default=get_current_time_in_timezone)
    age           = db.Column(db.Integer)
    gender        = db.Column(db.String(10))
    email         = db.Column(db.String(100))
    phone         = db.Column(db.String(15))
    aadhar        = db.Column(db.String(20))

    images        = db.relationship('Img',       backref='subject',
                                    lazy='dynamic', cascade='all, delete-orphan')
    embeddings    = db.relationship('Embedding', backref='subject',
                                    lazy='dynamic', cascade='all, delete-orphan')
    detections    = db.relationship('Detection', back_populates='subject',
                                    lazy='dynamic', cascade='all, delete-orphan')

    def __repr__(self):
        return f"<Subject {self.subject_name} ({self.id})>"

class Img(db.Model):
    __tablename__ = 'img'
    id         = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    image_url  = db.Column(db.String(255), nullable=False)
    subject_id = db.Column(UUID(as_uuid=True), db.ForeignKey('subject.id'),
                           nullable=False)

    embeddings = db.relationship('Embedding', backref='image',
                                 lazy='dynamic', cascade='all, delete-orphan')

    def __repr__(self):
        return f"<Img {self.id}>"

class Camera(db.Model):
    __tablename__ = 'camera'
    id           = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    camera_name  = db.Column(db.String(50), nullable=False, unique=True)
    camera_url   = db.Column(db.Text,       nullable=False)
    tag          = db.Column(db.String(50), nullable=False)

    detections   = db.relationship('Detection', back_populates='camera',
                                   lazy='dynamic', cascade='all, delete-orphan')

    def __repr__(self):
        return f"<Camera {self.camera_name} ({self.tag})>"

class Embedding(db.Model):
    __tablename__ = 'embedding'
    id          = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    embedding   = db.Column(ARRAY(db.Float), nullable=False)
    calculator  = db.Column(db.String(255), nullable=False)
    subject_id  = db.Column(UUID(as_uuid=True), db.ForeignKey('subject.id'),
                            nullable=False)
    img_id      = db.Column(UUID(as_uuid=True), db.ForeignKey('img.id'),
                            nullable=False)

    def __repr__(self):
        return f"<Embedding {self.id}>"

class Detection(db.Model):
    __tablename__ = 'detection'
    id          = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # rec_no will get its value from a Postgres sequence:
    rec_no_seq = Sequence('detection_rec_no_seq', metadata=db.metadata)
    rec_no = db.Column(Integer,
                       rec_no_seq,
                       server_default=rec_no_seq.next_value(),
                       unique=True,
                       nullable=False)    
    subject_id  = db.Column(UUID(as_uuid=True), db.ForeignKey('subject.id'),
                            nullable=True)
    subject     = db.relationship('Subject', back_populates='detections')

    camera_id   = db.Column(UUID(as_uuid=True), db.ForeignKey('camera.id'),
                            nullable=False)
    camera      = db.relationship('Camera', back_populates='detections')

    det_score   = db.Column(db.Float, nullable=False)
    distance    = db.Column(db.Float, nullable=False)
    timestamp   = db.Column(db.DateTime(timezone=True),
                            default=get_current_time_in_timezone,
                            index=True)
    det_face    = db.Column(db.Text, nullable=False)

    @property
    def camera_tag(self):
        return self.camera.tag

    def __repr__(self):
        return (f"<Detection {self.id}: "
                f"{self.subject.subject_name} @ {self.camera.camera_name}>")

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