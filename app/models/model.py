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
        return f"<Detection {self.camera_name}, {self.detected_face}>"
    
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

class Raw_Embedding(db.Model):
    __tablename__ = 'raw_embedding'
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)
    subject_name = db.Column(db.String(100), nullable=False)
    embedding = db.Column(ARRAY(db.Float), nullable=False)
    calculator = db.Column(db.String(255), nullable=False)

    def __repr__(self):
        return f"<Embedding {self.id}, Subject: {self.subject_name}>"
    
# from sqlalchemy.dialects.postgresql import UUID, ARRAY
# import uuid

# class Subject(db.Model):
#     id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)
#     subject_name = db.Column(db.String(100), nullable=False)
#     api_key = db.Column(db.String(255), unique=True, nullable=False)

# class Img(db.Model):
#     id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)
#     image_data = db.Column(db.LargeBinary, nullable=True)  # Adjust as per your requirement

# class Raw_Embedding(db.Model):
#     id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)

#     subject_name = db.Column(db.String(100), nullable=False)
    
#     embedding = db.Column(ARRAY(db.Float), nullable=False)
#     calculator = db.Column(db.String(255), nullable=False)

#     subject_id = db.Column(UUID(as_uuid=True), db.ForeignKey('subject.id'), nullable=False)
#     subject = db.relationship('Subject', backref=db.backref('embeddings', lazy=True))    
#     img_id = db.Column(UUID(as_uuid=True), db.ForeignKey('img.id'), nullable=True)
#     img = db.relationship('Img', backref=db.backref('embeddings', lazy=True))

#     def __repr__(self):
#         return f"<Embedding {self.id}, Subject: {self.subject_name}>"
