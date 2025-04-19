import cv2
from flask import current_app
from config.paths import MODEL_PACK_NAME, BASE_DIR, SUBJECT_IMG_DIR
from insightface.app import FaceAnalysis
from config.logger_config import face_proc_logger 
import os
from app.models.model import Subject, Img, Embedding, db
from werkzeug.utils import secure_filename

# Initialize the face analysis engine
analy_app = FaceAnalysis(name=MODEL_PACK_NAME, 
                         allowed_modules=['detection', 'landmark_3d_68','recognition'])
analy_app.prepare(ctx_id=0, det_size=(640, 640))
SUBJECT_DIR1 = BASE_DIR / "subjects_img" / "Autobits_emp"

def store_embedding(subject, embedding_vector, img_id=None):
    """
    Store the face embedding in the Embedding table, linking it to the subject
    and optionally to a specific image (via img_id).
    """
    try:
        with current_app.app_context():
            embedding_entry = Embedding(
                embedding=embedding_vector,
                calculator=f"{MODEL_PACK_NAME}",
                subject_id=subject.id,  # Link to the subject
                img_id=img_id            # Link to the image (optional)
            )
            db.session.add(embedding_entry)
            db.session.commit()
            return embedding_entry.id
    except Exception as e:
        db.session.rollback()  
        face_proc_logger.error(f"Can't store embeddings for {subject.subject_name}: {str(e)}")
        return None

def gen_embedding(subject, img_paths, img_id=None):
    """
    Generate and store embeddings for a given subject from one or more image paths.
    Each generated embedding will be optionally linked to the provided image ID.
    """
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
            emb_id = store_embedding(subject, embedding_list, img_id)
            if emb_id:
                face_proc_logger.debug(f"Stored embedding for {subject.subject_name} (Img ID: {img_id}, Embedding ID: {emb_id})")
    
    print("\nEmbedding generation complete.")
    face_proc_logger.debug("Embedding generation complete.")
    return {'message': 'Embeddings generated and stored successfully.'}, 200

def list_subject():
    """Return a list of subjects with their images."""
    try:
        with current_app.app_context():
            subjects = Subject.query.all()
            subject_list = []
            for sub in subjects:
                # Retrieve image URLs from the images relationship
                images = [{"id": str(img.id), "url": img.image_url} for img in sub.images]
                subject_list.append({
                    'id': str(sub.id),
                    'subject_name': sub.subject_name,
                    'age': sub.age,
                    'gender': sub.gender,
                    'email': sub.email,
                    'phone': sub.phone,
                    'aadhar': sub.aadhar,
                    'added_date': sub.added_date.isoformat(),
                    'images': images
                })
                
            return {'subjects': subject_list}, 200
    except Exception as e:
        db.session.rollback()
        face_proc_logger.error(f"Failed to list subjects: {str(e)}")
        return {'error': str(e)}, 500

def add_subject(subject_name, img_path, age=None, gender=None, email=None, phone=None, aadhar=None):
    """
    Create a new subject with a single image.
    This function:
      1. Creates the new Subject record.
      2. Saves the image as an Img record and associates it with the subject.
      3. Generates embeddings for that image and links them to the new image.
    """
    filename = os.path.basename(img_path)
    image_url = f"http://localhost:5757/subserv/{filename}"

    # 🆕 Include metadata when creating subject
    new_subject = Subject(
        subject_name=subject_name,
        age=age,
        gender=gender,
        email=email,
        phone=phone,
        aadhar=aadhar
    )
    db.session.add(new_subject)
    db.session.commit()

    # Create an Img record for this subject
    new_img = Img(image_url=image_url, subject_id=new_subject.id)
    db.session.add(new_img)
    db.session.commit()

    # Generate embeddings using the image and associate them with new_img.id
    response, status = gen_embedding(new_subject, img_path, img_id=new_img.id)
    return response, status

def delete_subject(subject_id):
    """
    Delete a subject along with all its associated Img and Embedding records.
    Also removes image files from the local storage.
    """
    try:
        with current_app.app_context():
            subject = Subject.query.get(subject_id)
            if subject is None:
                return {'error': 'Subject not found'}, 404

            # Remove associated image files from local storage
            for img in subject.images:
                file_path = os.path.join(str(SUBJECT_IMG_DIR), os.path.basename(img.image_url))
                if os.path.exists(file_path):
                    try:
                        os.remove(file_path)
                        face_proc_logger.info(f"Deleted image file: {file_path}")
                    except Exception as file_error:
                        face_proc_logger.error(f"Error deleting file {file_path}: {file_error}")
                else:
                    face_proc_logger.warning(f"File not found: {file_path}")

            # Delete the subject. Cascade deletes remove associated Img and Embedding records.
            db.session.delete(subject)
            db.session.commit()
            return {'message': 'Subject and associated images removed successfully.'}, 200
    except Exception as e:
        db.session.rollback()
        face_proc_logger.error(f"Failed to remove subject {subject_id}: {str(e)}")
        return {'error': str(e)}, 500

def add_image_to_subject(subject_id, file):
    """
    Adds a new image to an existing subject.
    Steps:
      1. Query the subject by subject_id.
      2. Save the new image file to disk.
      3. Create a new Img record for the subject.
      4. Generate an embedding from the new image and associate it with the new Img record.
    """
    subject = Subject.query.get(subject_id)
    if not subject:
        face_proc_logger.error(f"Subject not found: {subject_id}")
        return {'error': 'Subject not found'}, 404

    filename = secure_filename(file.filename)
    img_path = SUBJECT_IMG_DIR / filename
    img_path_str = str(img_path)

    try:
        file.save(img_path_str)
        face_proc_logger.debug(f"Saved new image to {img_path_str}")
    except Exception as e:
        face_proc_logger.error(f"Error saving file {img_path_str}: {e}")
        return {'error': f'Error saving file: {e}'}, 500

    image_url = f"http://localhost:5757/subserv/{filename}"
    new_img = Img(image_url=image_url, subject_id=subject.id)
    db.session.add(new_img)
    db.session.commit()
    face_proc_logger.debug(f"Created Img record for subject {subject.id} with image {image_url}")

    # Generate embedding for the new image and link it using new_img.id
    embed_response, embed_status = gen_embedding(subject, img_path_str, img_id=new_img.id)
    if embed_status != 200:
        face_proc_logger.error("Failed to generate embedding for the new image.")
        return {'error': 'Image saved but failed to generate embedding.'}, 500

    return {'message': 'New image added and embedding generated successfully.'}, 200

def delete_subject_img(img_id):
    """
    Delete an image associated with a subject.
    Steps:
      1. Query the Img record by img_id.
      2. Remove the image file from disk.
      3. Delete the Img record from the database.
    """
    try:
        with current_app.app_context():
            img = Img.query.get(img_id)
            if not img:
                return {'error': 'Image not found'}, 404

            # Remove the image file from disk
            file_path = os.path.join(str(SUBJECT_IMG_DIR), os.path.basename(img.image_url))
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                    face_proc_logger.info(f"Deleted image file: {file_path}")
                except Exception as file_error:
                    face_proc_logger.error(f"Error deleting file {file_path}: {file_error}")
            else:
                face_proc_logger.warning(f"File not found: {file_path}")

            # Delete the Img record
            db.session.delete(img)
            db.session.commit()
            return {'message': 'Image removed successfully.'}, 200
    except Exception as e:
        db.session.rollback()
        face_proc_logger.error(f"Failed to remove image {img_id}: {str(e)}")
        return {'error': str(e)}, 500