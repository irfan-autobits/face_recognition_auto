from pathlib import Path
import shutil
import cv2
from flask import Flask
from insightface.app import FaceAnalysis
from flask_sqlalchemy import SQLAlchemy
import numpy as np
from sqlalchemy.dialects.postgresql import UUID, ARRAY
import uuid
import itertools
# ----------------- Flask & Database Setup -----------------
app = Flask(__name__)
BASE_DIR = Path(__file__).resolve().parent

# Define directories
# SUBJECT_DIR = BASE_DIR / "subjects_img" / "train"
SUBJECT_DIR1 = BASE_DIR / "subjects_img" / "Autobits_emp"
SUBJECT_DIR2 = BASE_DIR / "subjects_img" / "Hathi_pic" 
TEST_DIR = BASE_DIR / "subjects_img" / "test"
MODELS_DIR = BASE_DIR / ".models"
TEST_RES_DIR = BASE_DIR / "Vis_res" / "Test" # Folder for saving visualization images
TRAIN_RES_DIR = BASE_DIR / "Vis_res" / "Train" # Folder for saving visualization images

# Clear and recreate the visualization directory
shutil.rmtree(TEST_RES_DIR, ignore_errors=True)
TEST_RES_DIR.mkdir(parents=True, exist_ok=True)
shutil.rmtree(TRAIN_RES_DIR, ignore_errors=True)
TRAIN_RES_DIR.mkdir(parents=True, exist_ok=True)

# Database Configuration (only raw embeddings will be stored in the DB)
app.config['SQLALCHEMY_DATABASE_URI'] = "postgresql+psycopg2://postgres:postgres@localhost:6432/frs"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

class Raw_Embedding(db.Model):
    __tablename__ = 'raw_embedding'
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)
    subject_name = db.Column(db.String(100), nullable=False)
    embedding = db.Column(ARRAY(db.Float), nullable=False)
    calculator = db.Column(db.String(255), nullable=False)

    def __repr__(self):
        return f"<Embedding {self.id}, Subject: {self.subject_name}>"

# Create the table if it doesn't exist
with app.app_context():
    db.drop_all()
    db.create_all()
    print("Table created: raw_embedding")

# ----------------- Initialize InsightFace -----------------
# Initialize the InsightFace app with detection and recognition modules.
model_zoo = ['buffalo_l', 'buffalo_m', 'buffalo_s']
model_pack_name = model_zoo[0]
analy_app = FaceAnalysis(name=model_pack_name ,allowed_modules=['detection', 'landmark_3d_68','recognition'])
# analy_app = FaceAnalysis(allowed_modules=['detection', 'recognition'])
analy_app.prepare(ctx_id=0, det_size=(640, 640))

# ----------------- Helper Functions -----------------
def store_embedding(subject_name, embedding_vector):
    """Store the face embedding in the Raw_Embedding table."""
    # add default camera
    with app.app_context():
        embedding_entry = Raw_Embedding(
            subject_name=subject_name,
            embedding=embedding_vector,
            calculator="insightface_R_100"
        )
        db.session.add(embedding_entry)
        db.session.commit()
        return embedding_entry.id

def draw_faces(image, faces, subject):
    """
    Draw bounding boxes and landmarks on the image.
    Each detected face is expected to have attributes:
      - face.bbox (bounding box)
      - face.landmark (landmarks, typically in shape (10,) or (5,2))
    """
    for face in faces:
        # Draw bounding box
        bbox = face.bbox
        kps = face.kps
        # Draw bounding box
        cv2.rectangle(image, (int(bbox[0]), int(bbox[1])), (int(bbox[2]), int(bbox[3])), (0, 255, 0), 2)
        cx = int(bbox[0])
        cy = int(bbox[1])+ 12
        cv2.putText(image, subject, (cx, cy),
                    cv2.FONT_HERSHEY_DUPLEX, 0.5, (0, 255, 0))        
        # Draw landmarks (check if they exist first)
        if hasattr(face, 'kps') and face.kps is not None:
            for (x, y) in kps:
                cv2.circle(image, (int(x), int(y)), 2, (0, 0, 255), -1)
    return image

def add_subjects():
    """Process all images in the subject directory:
       - Detect faces and extract embeddings (store in DB)
       - Draw visualizations and save them for validation.
    """
    valid_extensions = (".jpg", ".jpeg", ".png")
    
    # for image_path in SUBJECT_DIR.glob("*"):
    for image_path in itertools.chain(SUBJECT_DIR1.glob("*"), SUBJECT_DIR2.glob("*")):
    # for image_path in SUBJECT_DIR1.glob("*"):
        if image_path.suffix.lower() in valid_extensions:
            # Derive subject name from file name
            subject_name = image_path.stem.replace("_", " ").title()
            img_raw = cv2.imread(str(image_path))
            if img_raw is None:
                print(f"Failed to read {image_path}")
                continue

            # Run face detection and recognition
            faces = analy_app.get(img_raw)

            # For each detected face, store the embedding in the DB
            for face in faces:
                embedding = face.embedding  # Expected to be a numpy array
                if embedding is None:
                    continue
                embedding_list = embedding.tolist()
                emb_id = store_embedding(subject_name, embedding_list)
                print(f"Stored embedding for {subject_name} (ID: {emb_id})")
            
            # Create visualization: draw bounding boxes and landmarks on a copy of the image
            vis_img = img_raw.copy()
            vis_img = draw_faces(vis_img, faces, "Unknown")
            vis_image_path = TRAIN_RES_DIR / image_path.name
            cv2.imwrite(str(vis_image_path), vis_img)

    print("\nadding complete.")

# ----------- Verify ----------------------
from scipy.spatial.distance import euclidean

# Function to normalize an embedding (L2 normalization)
def normalize(embedding):
    norm = np.linalg.norm(embedding)
    if norm == 0:
        return embedding
    return embedding / norm

# Function to calculate the Euclidean distance
def euclidean_distance(embedding1, embedding2):
    return euclidean(embedding1, embedding2)

# Function to verify the top N closest matches
def verify_identity(input_embedding, known_embeddings, top_n=1, threshold=0.6):
    # Normalize the input embedding
    input_embedding = normalize(input_embedding)
    
    distances = []
    
    # Calculate the distance for each known embedding
    for emb in known_embeddings:
        known_embedding = normalize(emb['embedding'])
        distance = euclidean_distance(input_embedding, known_embedding)
        
        # Store the distance with the corresponding subject name
        distances.append({
            'subject_name': emb['subject_name'],
            'distance': distance
        })
    
    # Sort the distances by ascending order (smallest distance first)
    distances.sort(key=lambda x: x['distance'])
    
    # Get the top N matches (or as many as possible based on the threshold)
    matches = []
    for i in range(min(top_n, len(distances))):
        # if distances[i]['distance'] < threshold:
            matches.append(distances[i])  # Add the match if it's below the threshold
        # else:
            # break  # Stop if the distance exceeds the threshold
    
    return matches

def verification(input_embedding):
    # Example usage with known embeddings from the database (Raw_Embedding.query.all())
    with app.app_context():
        embeddings = Raw_Embedding.query.all()
        
        # List of known embeddings from the database (you need to format this appropriately)
        known_embeddings = [{'subject_name': emb.subject_name, 'embedding': np.array(emb.embedding)} for emb in embeddings]
                
        # Get the top 3 closest matches
        matches = verify_identity(input_embedding, known_embeddings, top_n=1, threshold=0.6)
        return matches
        
# ----------------------------------------------------------------------------
def test_subjects():
    """Process all images in the test directory:
       - Detect faces and extract embeddings (compare with db)
       - Draw visualizations and save them for validation.
    """
    valid_extensions = (".jpg", ".jpeg", ".png")
    
    for image_path in TEST_DIR.glob("*"):
        if image_path.suffix.lower() in valid_extensions:
            # Derive subject name from file name
            
            img_raw = cv2.imread(str(image_path))
            if img_raw is None:
                print(f"Failed to read {image_path}")
                continue

            # Run face detection and recognition
            faces = analy_app.get(img_raw)

            # For each detected face, store the embedding in the DB
            for face in faces:
                embedding = face.embedding  # Expected to be a numpy array
                if embedding is None:
                    continue
            matches = verification(embedding)
            # Display the results
            if matches:
                for match in matches:
                    print(f"Match found: {match['subject_name']} with distance {match['distance']}")
            else:
                print("No matches found within the threshold.")            
            # Create visualization: draw bounding boxes and landmarks on a copy of the image
            vis_img = img_raw.copy()
            vis_img = draw_faces(vis_img, faces,match['subject_name'])
            vis_image_path = TEST_RES_DIR / image_path.name
            cv2.imwrite(str(vis_image_path), vis_img)
            print(f"Total Faces Detected: {len(faces)}")
            print("----------------------------------------------------")
            for face in faces:
                print(f"BBox: {face.bbox}")
                print(f"kps: {face.kps}")
                print(f"det_score: {face.det_score}")
                # print(f"landmark_3d_68: {face.landmark_3d_68[:5]}")  
                print(f"pose: {face.pose}")  
                # print(f"landmark_2d_106: {face.landmark_2d_106[:5]}")  
                print(f"gender: {face.gender}")  
                print(f"age: {face.age}")  
                print(f"Embedding: {face.embedding[:5]}")  # Print first 5 elements

    print("\nTesting complete.")

# ----------------- Run Processing and Flask App -----------------
if __name__ == "__main__":
    add_subjects()  # Process images, save vis images, and store embeddings in the DB
    # test_subjects()
    app.run(debug=False)

