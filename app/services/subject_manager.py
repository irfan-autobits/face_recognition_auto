# app/services/subject_manager.py
import os
from sqlite3 import IntegrityError
import uuid
import cv2
from flask import current_app
from werkzeug.utils import secure_filename
from sqlalchemy.exc import SQLAlchemyError

from app.models.model import db, Subject, Img, Embedding
from insightface.app import FaceAnalysis
from config.paths import MODEL_PACK_NAME, SUBJECT_IMG_DIR
from config.logger_config import sub_proc_logger

# initialize the face‐analysis engine once
analy_app = FaceAnalysis(
    name=MODEL_PACK_NAME,
    allowed_modules=['detection', 'landmark_3d_68', 'recognition']
)
analy_app.prepare(ctx_id=0, det_size=(640, 640))

class SubjectService:
    def list_subjects(self):
        subjects = Subject.query.all()
        out = []
        for s in subjects:
            images = [{"id": str(i.id), "url": i.image_url} for i in s.images]
            out.append({
                "id":           str(s.id),
                "subject_name": s.subject_name,
                "age":          s.age,
                "gender":       s.gender,
                "email":        s.email,
                "phone":        s.phone,
                "aadhar":       s.aadhar,
                "added_date":   s.added_date.isoformat(),
                "images":       images
            })
        return {"subjects": out}, 200

    def _process_uploaded_image(self, file_obj):
        """Centralized image processing with face validation"""
        filename = secure_filename(file_obj.filename)
        disk_path = SUBJECT_IMG_DIR / filename
        
        # Ensure directory exists
        SUBJECT_IMG_DIR.mkdir(parents=True, exist_ok=True)
        
        # Save file
        file_obj.save(disk_path)
        sub_proc_logger.info(f"Saved file to {disk_path}")

        # Validate image and faces
        img = cv2.imread(str(disk_path))
        if img is None:
            sub_proc_logger.error(f"img not read while processing for {file_obj.filename} at processing")
            raise ValueError("Invalid image file")
            
        faces = analy_app.get(img)
        if not faces:
            sub_proc_logger.error(f"No faces detected for {file_obj.filename} at processing")
            raise ValueError("No faces detected")
        if len(faces) > 1:
            sub_proc_logger.error(f"Multiple faces detected for {file_obj.filename} at processing")
            raise ValueError("Multiple faces detected")
            
        # Draw bounding box
        face = faces[0]
        x1, y1, x2, y2 = face.bbox.astype(int)
        cv2.rectangle(img, (x1, y1), (x2, y2), (0, 255, 0), 2)
        cv2.imwrite(str(disk_path), img)
        
        return disk_path, face

    def _create_image_record(self, disk_path, subject_id):
        """Centralized image record creation"""
        filename = disk_path.name
        public_url = f"{current_app.config['SERV_HOST']}:{current_app.config['PORT']}/subserv/{filename}"
        img = Img(image_url=public_url, subject_id=subject_id)
        sub_proc_logger.info(f"Image record commited for {filename}")
        db.session.add(img)
        db.session.flush()  # Get ID without commit
        return img    

    def _create_embedding_record(self, face, subject_id, img_id, model=MODEL_PACK_NAME):
        """Centralized embedding creation"""
        if face.embedding is None:
            sub_proc_logger.error(f"no embedding found")
            raise ValueError("No face embedding found")
            
        emb = Embedding(
            embedding=face.embedding.tolist(),
            calculator=model,
            subject_id=subject_id,
            img_id=img_id
        )
        db.session.add(emb)
        return emb

    def _handle_upload_error(self, disk_path, error):
        """Consistent error handling for upload operations"""
        db.session.rollback()
        if disk_path.exists():
            try:
                disk_path.unlink()
                sub_proc_logger.info(f"Removed file {disk_path.name} due to error")
            except Exception as e:
                sub_proc_logger.error(f"Error deleting {disk_path}: {e}")
        sub_proc_logger.error(f"Upload error: {error}")
        return {"error": str(error)}, 400

    def add_subject(self, subject_name, files, **meta):
        if not isinstance(files, list):
            files = [files]

        disk_paths = []
        processed_images = []

        try:
            # Pre-validate all images
            image_data = []
            for file_obj in files:
                filename = secure_filename(file_obj.filename)
                public_url = f"{current_app.config['SERV_HOST']}:{current_app.config['PORT']}/subserv/{filename}"
                existing = Img.query.filter_by(image_url=public_url).first()
                if existing:
                    continue  # skip duplicates

                disk_path, face = self._process_uploaded_image(file_obj)
                image_data.append((file_obj, disk_path, face))
                disk_paths.append(disk_path)

            # If nothing valid, raise
            if not image_data:
                raise ValueError("No valid images were processed")

            # Now create the subject — only if image(s) are valid
            subject = Subject(subject_name=subject_name, **meta)
            db.session.add(subject)
            db.session.flush()

            # Save images + embeddings
            for file_obj, disk_path, face in image_data:
                img = self._create_image_record(disk_path, subject.id)
                self._create_embedding_record(face, subject.id, img.id)

                processed_images.append({
                    "filename": disk_path.name,
                    "url": img.image_url,
                    "img_id": str(img.id)
                })

            db.session.commit()
            sub_proc_logger.info(f"add_Subject successful for {subject_name} with {len(processed_images)} images")

            return {
                "subject": subject_name,
                "images": processed_images
            }, 200

        except Exception as e:
            sub_proc_logger.error(f"error while add_sub :{e}")
            db.session.rollback()
            # Clean up all saved files
            for disk_path in disk_paths:
                if disk_path.exists():
                    try:
                        disk_path.unlink()
                        sub_proc_logger.info(f"Cleaned up {disk_path}")
                    except Exception as cleanup_err:
                        sub_proc_logger.error(f"Cleanup failed for {disk_path}: {cleanup_err}")

            return {"error": str(e)}, 400

    def add_image(self, subject_id, file_obj):
        """Simplified using shared methods"""
        disk_path = None
        try:
            filename = file_obj.filename
            public_url = f"{current_app.config['SERV_HOST']}:{current_app.config['PORT']}/subserv/{filename}"            
            existing = Img.query.filter_by(image_url=public_url).first()
            if existing:
                return {"error": "Image already exists"}, 409            
            subject = Subject.query.get_or_404(subject_id)
            disk_path, face = self._process_uploaded_image(file_obj)
            img = self._create_image_record(disk_path, subject.id)

            self._create_embedding_record(face, subject.id, img.id)
            
            db.session.commit()
            sub_proc_logger.info(f"add_img successful for {subject.subject_name} with img:{file_obj.filename}")
            return {"message": "Image added", "img_id": str(img.id)}, 200
            
        except Exception as e:
            sub_proc_logger.error(f"Error while adding image for {disk_path.name}: {e}")
            return self._handle_upload_error(disk_path, e)
        
    def delete_subject(self, subject_id):
        """
        Remove subject + all its images & embeddings.  Files are unlinked first.
        """
        sub = Subject.query.get(subject_id)
        if not sub:
            sub_proc_logger.error(f"Subject record {subject_id} while delete_sub not found")
            return {"error": "Subject not found"}, 404

        # delete image files
        for img in sub.images:
            fn = os.path.basename(img.image_url)
            fp = SUBJECT_IMG_DIR / fn
            if fp.exists():
                try:
                    fp.unlink()
                    sub_proc_logger.info(f"removed img:{fn} for delete_sub")
                except Exception:
                    pass

        db.session.delete(sub)
        db.session.commit()
        sub_proc_logger.info(f"sub_id:{subject_id} removed from DB for delete_sub")
        return {"message": f"Subject {sub.subject_name} removed"}, 200

    def delete_subject_img(self, img_id):
        """
        Remove single Img + its embeddings + unlink file.
        """
        img = Img.query.get(img_id)
        if not img:
            sub_proc_logger.error(f"Img record {img_id} while delete_img not found")
            return {"error": "Image not found"}, 404

        # don’t allow removal if this is the only image for its subject
        subject = img.subject
        # if using lazy='dynamic', .images is a query
        total_images = subject.images.count() if hasattr(subject.images, 'count') else len(subject.images)
        # if total_images <= 1:
        #     sub_proc_logger.warning(f"Attempt to remove last image of subject {subject.subject_name}")
        #     return {"error": "Cannot remove the only image for a subject"}, 400

        fn = os.path.basename(img.image_url)
        fp = SUBJECT_IMG_DIR / fn
        if fp.exists():
            try:
                fp.unlink()
                sub_proc_logger.info(f"removed img:{fn} while delete_img")
            except Exception:
                pass

        db.session.delete(img)
        db.session.commit()
        sub_proc_logger.info(f"img_id:{img_id} removed from DB for delete_img")
        return {"message": "Image removed"}, 200

    def edit_subject(self, subject_id, **updated_data):
        """
        Edit subject details.
        """
        sub_proc_logger.info(f"Subject record {subject_id} processing")
        sub = Subject.query.get(subject_id)
        if not sub:
            sub_proc_logger.error(f"Subject record {subject_id} while delete_sub not found")
            return {"error": "Subject not found"}, 404
        
        for key, value in updated_data.items():
            if hasattr(sub, key):
                setattr(sub, key, value)
            else:
                sub_proc_logger.warning(f"Invalid field {key} for subject edit")
        try:
            db.session.commit()
            sub_proc_logger.info(f"Subject {sub.subject_name} updated successfully")
            return {"message": "Subject updated"}, 200
        except SQLAlchemyError as e:
            db.session.rollback()
            sub_proc_logger.error(f"Error updating subject {sub.subject_name}: {e}")
            return {"error": "Failed to update subject"}, 500

    def regenerate_embeddings(self, subject_id, model_name=None):
        """
        (Re)generate embeddings for _all_ images of a subject under a new model.
        If model_name is None, uses current CONFIG model.
        """
        sub = Subject.query.get(subject_id)
        if not sub:
            return {"error": "Subject not found"}, 404

        name = model_name or current_app.config["MODEL_PACK_NAME"]
        # load a fresh FaceAnalysis under this name:
        engine = FaceAnalysis(name=name, allowed_modules=['detection','recognition'])
        engine.prepare(ctx_id=0, det_size=(640,640))

        for img in sub.images:
            path = SUBJECT_IMG_DIR / os.path.basename(img.image_url)
            frame = cv2.imread(str(path))
            if frame is None: 
                continue
            faces = engine.get(frame)
            for face in faces:
                emb = face.embedding
                if emb is None: 
                    continue
                e = Embedding(
                    embedding=emb.tolist(),
                    calculator=name,
                    subject_id=sub.id,
                    img_id=img.id
                )
                db.session.add(e)
        db.session.commit()
        return {"message": f"Regenerated embeddings under model {name}"}, 200

# module‑level singleton used by your routes:
subject_service = SubjectService()
