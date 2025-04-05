# app/services/subject_manager.py
import cv2
from app.models.model import Subject, Embedding, db
from flask import current_app
from config.Paths import model_pack_name, BASE_DIR
from insightface.app import FaceAnalysis
from config.logger_config import face_proc_logger 
from app.models.model import Subject, Img, db

analy_app = FaceAnalysis(name=model_pack_name ,allowed_modules=['detection', 'landmark_3d_68','recognition'])
# analy_app = FaceAnalysis(allowed_modules=['detection', 'recognition'])
analy_app.prepare(ctx_id=0, det_size=(640, 640))
SUBJECT_DIR1 = BASE_DIR / "subjects_img" / "Autobits_emp"

def store_embedding(subject, embedding_vector):
    """Store the face embedding in the Embedding table, linking it to the subject."""
    try:
        with current_app.app_context():
            embedding_entry = Embedding(
                embedding=embedding_vector,
                calculator=f"{model_pack_name}",
                subject_id=subject.id  # Link via subject ID
            )
            db.session.add(embedding_entry)
            db.session.commit()
            return embedding_entry.id
    except Exception as e:
        db.session.rollback()  
        face_proc_logger.error(f"Can't store embeddings for {subject.subject_name}: {str(e)}")

def gen_embedding(subject, img_paths):
    """Generate and store embeddings for a given subject from one or more image paths."""
    valid_extensions = (".jpg", ".jpeg", ".png")
    
    # Ensure we have a list to iterate over
    if not isinstance(img_paths, list):
        img_paths = [img_paths]
    
    for path in img_paths:
        from pathlib import Path
        image_path = Path(path)
        
        if image_path.suffix.lower() not in valid_extensions:
            face_proc_logger.debug(f"Skipped unsupported file type: {image_path}")
            continue

        print(f"Processing image: {image_path}")
        face_proc_logger.debug(f"Processing image: {image_path}")
        
        img_raw = cv2.imread(str(image_path))
        if img_raw is None:
            print(f"Failed to read {image_path}")
            face_proc_logger.debug(f"Failed to read {image_path}")
            continue

        faces = analy_app.get(img_raw)
        for face in faces:
            embedding = face.embedding
            if embedding is None:
                continue
            embedding_list = embedding.tolist()
            emb_id = store_embedding(subject, embedding_list)
            print(f"Stored embedding for {subject.subject_name} (ID: {emb_id})")
            face_proc_logger.debug(f"Stored embedding for {subject.subject_name} (ID: {emb_id})")
    
    print("\nEmbedding generation complete.")
    face_proc_logger.debug("Embedding generation complete.")
    return {'message': 'Embeddings generated and stored successfully.'}, 200


def list_subject():
    """API endpoint to list all the subjects with their images"""
    try:
        with current_app.app_context():
            subjects = Subject.query.all()
            subject_list = []
            for sub in subjects:
                # Get image URLs from the images relationship
                images = [img.image_url for img in sub.images]
                subject_list.append({
                    'subject_name': sub.subject_name,
                    'added_date': sub.added_date.isoformat(),  # Optional: include added date
                    'images': images
                })
            return {'subjects': subject_list}, 200
    except Exception as e:
        db.session.rollback()
        face_proc_logger.error(f"Failed to list subjects: {str(e)}")
        return {'error': str(e)}, 500

def add_subject(filename, subject_name, img_path):
    # Construct the serving URL (assume /faces/ serves images from SUBJECT_IMG_DIR)
    image_url = f"http://localhost:5757/subserv/{filename}"
    # face_url = f"http://localhost:5757/faces/{face_path}"
    # Create new subject in DB
    new_subject = Subject(subject_name=subject_name)
    db.session.add(new_subject)
    db.session.commit()

    # Create an Img entry for this subject
    new_img = Img(image_url=image_url, subject_id=new_subject.id)
    db.session.add(new_img)
    db.session.commit()

    # Pass the subject object along with the image path(s) to generate embeddings.
    response, status = gen_embedding(new_subject, img_path)
    return response, status
