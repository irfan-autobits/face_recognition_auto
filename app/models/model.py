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
    camera_tag = db.Column(db.String(50), nullable=False)
    det_score = db.Column(db.Float, nullable=False)    
    distance = db.Column(db.Float, nullable=False)
    timestamp = db.Column(db.DateTime(timezone=True), default=get_current_time_in_timezone)
    det_face = db.Column(db.Text, nullable=False)

    def __repr__(self):
        return f"<Detection {self.camera_name}, {self.det_face}>"
    
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

    # 🆕 New identity fields
    age = db.Column(db.Integer)
    gender = db.Column(db.String(10))
    email = db.Column(db.String(100))
    phone = db.Column(db.String(15))
    aadhar = db.Column(db.String(20))
        
    # A subject can have many images and embeddings.
    images = db.relationship('Img', backref='subject', lazy=True, cascade="all, delete-orphan")
    embeddings = db.relationship('Embedding', backref='subject', lazy=True, cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Subject {self.id}, Name: {self.subject_name}>"

class Img(db.Model):
    __tablename__ = 'img'
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)
    image_url = db.Column(db.String(255), nullable=False)  # This could be a serving URL or file path.
    subject_id = db.Column(UUID(as_uuid=True), db.ForeignKey('subject.id'), nullable=False)
    # Cascade delete: if an image is removed, its embeddings are also removed.
    embeddings = db.relationship('Embedding', backref='image', lazy=True, cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Image {self.id}, URL: {self.image_url}>"

class Embedding(db.Model):
    __tablename__ = 'embedding'
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)
    embedding = db.Column(ARRAY(db.Float), nullable=False)
    calculator = db.Column(db.String(255), nullable=False)
    subject_id = db.Column(UUID(as_uuid=True), db.ForeignKey('subject.id'), nullable=False)
    # This optional field links the embedding to the image it was generated from.
    img_id = db.Column(UUID(as_uuid=True), db.ForeignKey('img.id'), nullable=True)

    def __repr__(self):
        return f"<Embedding {self.id}, Subject ID: {self.subject_id}>"

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

class Camera(db.Model):
    __tablename__ = 'camera'
    id = db.Column(db.Integer, primary_key=True)
    camera_name = db.Column(db.String(50), nullable=False)
    camera_url = db.Column(db.Text, nullable=False)
    tag = db.Column(db.String(50), nullable=False)
    
    # Each camera is installed in one location.
    # location_id = db.Column(db.Integer, db.ForeignKey('location.id'), nullable=True)
    # location = db.relationship('Location', backref=db.backref('cameras', lazy=True))
    def __repr__(self):
        # This will show the camera's name and the location it is installed in.
        return f"<Camera {self.camera_name} in {self.location}>"
