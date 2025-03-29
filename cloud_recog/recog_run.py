import os
import jwt
from flask import Flask, request, jsonify, abort
from functools import wraps
import cv2
import numpy as np
import base64
from insightface.model_zoo import get_model
from dotenv import load_dotenv
from pathlib import Path

# Load environment variables
load_dotenv()
SECRET_KEY = os.getenv("SECRET_KEY", "top_secret")
model_pack_name = os.getenv("model_pack_name", "buffalo_l")
print(f"using {model_pack_name} pack")

# Set up InsightFace models
INSIGHTFACE_ROOT = Path('~/.insightface').expanduser()
INSIGHT_MODELS = INSIGHTFACE_ROOT / "models"
rec_model = INSIGHT_MODELS / model_pack_name / "w600k_r50.onnx"
rec_handler = get_model(str(rec_model))
rec_handler.prepare(ctx_id=0)

app = Flask(__name__)

def decode_jwt(token):
    """Decodes the JWT token using the SECRET_KEY."""
    try:
        print(f"decoding header with {SECRET_KEY}")
        return jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        abort(401, description="Token expired")
    except jwt.InvalidTokenError:
        abort(401, description="Invalid token")

def requires_auth(f):
    """Decorator to protect endpoints with JWT authentication."""
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        if not auth_header:
            abort(401, description="Missing Authorization header")
        # If needed, you can strip a 'Bearer ' prefix here.
        decode_jwt(auth_header)
        return f(*args, **kwargs)
    return decorated     

@app.route('/recognize', methods=['POST'])
@requires_auth  # Protect this endpoint with JWT auth
def recognize():
    try:
        data = request.json
        images_data = data.get("images", None)
        if not images_data:
            return jsonify({"error": "No images provided"}), 400
        
        aligned_images = []
        for img_str in images_data:
            img_bytes = base64.b64decode(img_str)
            img_np = np.frombuffer(img_bytes, dtype=np.uint8)
            img = cv2.imdecode(img_np, cv2.IMREAD_COLOR)
            aligned_images.append(img)
        
        embeddings = rec_handler.get_feat(aligned_images)
        embeddings_list = [emb.flatten().tolist() for emb in embeddings]
        return jsonify({"embeddings": embeddings_list})
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=False)
