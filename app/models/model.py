# final-compre/app/models/model.py
from datetime import datetime
import pytz
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.dialects.postgresql import UUID, ARRAY
import uuid

db = SQLAlchemy()

# Helper function to get current UTC time with timezone
def get_current_time_in_timezone():
    return datetime.now(pytz.utc)

class Detection(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    person = db.Column(db.String(100), nullable=False)
    camera_name = db.Column(db.String(50), nullable=False)
    det_score = db.Column(db.Float, nullable=False)    
    distance = db.Column(db.Float, nullable=False)
    timestamp = db.Column(db.DateTime(timezone=True), default=get_current_time_in_timezone)
    det_face = db.Column(db.Text, nullable=False)

    def __repr__(self):
        return f"<Detection {self.camera_name}, {self.det_face}>"
    
class Camera_list(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    camera_name = db.Column(db.String(50), nullable=False)
    camera_url = db.Column(db.Text, nullable=False)

    def __repr__(self):
        return f"<Camera_list {self.camera_name}, {self.camera_url}>"
    
class Face_recog_User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(50), nullable=False)
    password = db.Column(db.String(50), nullable=False)

    def __repr__(self):
        return f"<User {self.email}>"

class Subject(db.Model):
    __tablename__ = 'subject'
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)
    subject_name = db.Column(db.String(100), nullable=False)
    added_date = db.Column(db.DateTime(timezone=True), nullable=False, default=get_current_time_in_timezone)
    # Relationships to images and embeddings
    images = db.relationship('Img', backref='subject', lazy=True, cascade="all, delete-orphan")
    embeddings = db.relationship('Embedding', backref='subject', lazy=True, cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Subject {self.id}, Name: {self.subject_name}>"

class Img(db.Model):
    __tablename__ = 'img'
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)
    # Store a serving URL or file path
    image_url = db.Column(db.String(255), nullable=False)
    subject_id = db.Column(UUID(as_uuid=True), db.ForeignKey('subject.id'), nullable=False)

    def __repr__(self):
        return f"<Image {self.id}, URL: {self.image_url}>"

class Embedding(db.Model):
    __tablename__ = 'embedding'
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)
    embedding = db.Column(ARRAY(db.Float), nullable=False)
    calculator = db.Column(db.String(255), nullable=False)
    subject_id = db.Column(UUID(as_uuid=True), db.ForeignKey('subject.id'), nullable=False)

    def __repr__(self):
        return f"<Embedding {self.id}, Subject ID: {self.subject_id}>"
