import datetime
import cv2
import requests
import base64
from insightface.model_zoo import get_model
from config.Paths import INSIGHT_MODELS, model_pack_name, SECRET_KEY
import numpy as np
from insightface.utils import face_align
import jwt

# Load model for local processing
rec_model = INSIGHT_MODELS / model_pack_name / "w600k_r50.onnx"
rec_handler = get_model(str(rec_model))
rec_handler.prepare(ctx_id=0)

def recognize_faces_local(img, faces):
    """Runs face recognition locally."""
    for face in faces:
        rec_handler.get(img, face)  # Apply recognition model
    return faces

# Generate a valid JWT token for authentication
def generate_token():
    payload = {
        "user_id": 1,
        "exp": datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1)
    }
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")

token = generate_token()  # Use this token in the header

def recognize_faces_remote(img, faces):
    """Sends cropped face images to the remote API with JWT authentication."""
    encoded_images = []

    for face in faces:
        # Crop and encode each face
        aimg, _ = face_align.norm_crop2(img, face.kps, 112)
        _, img_encoded = cv2.imencode('.jpg', aimg)
        img_base64 = base64.b64encode(img_encoded.tobytes()).decode("utf-8")
        encoded_images.append(img_base64)

    # Prepare the payload
    data = {"images": encoded_images}
    
    # Add the generated JWT token to headers
    headers = {
        "Authorization": token,
        "Content-Type": "application/json"
    }
    print(f"headers {headers}")
    
    # Send the request with authentication
    response = requests.post("http://localhost:5001/recognize", json=data, headers=headers)

    if response.status_code == 200:
        # Extract embeddings
        embeddings = response.json()["embeddings"]
        for face, emb in zip(faces, embeddings):
            face.embedding = np.array(emb)
    else:
        print("Remote recognition error:", response.status_code, response.text)
    
    return faces

def recognize_faces(img, faces, mode="local"):
    """
    Recognizes faces using either local or remote processing.
    :param img: Image array
    :param faces: Detected face objects (only for local)
    :param mode: "local" or "remote"
    :return: Recognized face data
    """
    if mode == "local":
        return recognize_faces_local(img, faces)
    elif mode == "remote":
        return recognize_faces_remote(img, faces)
    else:
        raise ValueError("Invalid mode. Use 'local' or 'remote'.")
