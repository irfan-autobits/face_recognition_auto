# config/Paths.py
import json
import os
from pathlib import Path
import shutil
import threading
from dotenv import load_dotenv
from threading import Lock

# Load environment variables from the .env file
load_dotenv(override=True)

# Define the base directory as the directory where the script is located
BASE_DIR = Path(__file__).resolve().parent.parent
INSIGHTFACE_ROOT = Path('~/.insightface').expanduser()
INSIGHT_MODELS = INSIGHTFACE_ROOT / "models"
# model_zoo = ['buffalo_l', 'buffalo_m', 'buffalo_s']
# model_pack_name = model_zoo[1]
model_pack_name = os.getenv("model_pack_name", "buffalo_l")

# Define other paths relative to the base directory
DATABASE_DIR = BASE_DIR / "Reports"
FACE_DIR = DATABASE_DIR / "saved_face"
SUBJECT_IMG_DIR = DATABASE_DIR / "subjects_imgs"
MODELS_DIR = BASE_DIR / ".models"
DET_LOG_FILE_PATH = DATABASE_DIR / "detection_logs.txt"
CAM_STAT_LOG_FILE_PATH = DATABASE_DIR / "cam_stat_logs.txt"
EXEC_TIME_LOG_FILE_PATH = DATABASE_DIR / "exec_time_logs.txt"
FACE_PROC_LOG_FILE_PATH = DATABASE_DIR / "face_proc_logs.txt"

# Retrieve CAMERA_SOURCES and parse it as JSON
CAMERA_SOURCES = os.getenv("CAMERA_SOURCES", "{}")
cam_sources = json.loads(CAMERA_SOURCES)

HOST = os.getenv("HOST", "http://localhost")
PORT = os.getenv("PORT", "8000")
API_KEY = os.getenv("API_KEY", "00000000-0000-0000-0000-000000000002")
FACE_DET_TH = os.getenv("FACE_DET_TH", 0.8)
FACE_REC_TH = os.getenv("FACE_REC_TH", 0.8)
FACE_DET_LM = os.getenv("FACE_DET_LM", 0)

# Simulating variables
database_dir = DATABASE_DIR
face_dir = FACE_DIR
sub_img_dir = SUBJECT_IMG_DIR

IS_RM_REPORT = os.getenv('IS_RM_REPORT', True)
IS_GEN_REPORT = os.getenv('IS_GEN_REPORT', True)
IS_RECOGNIZE = os.getenv('IS_RECOGNIZE', True)
# Remove the database directory and its contents
if IS_RM_REPORT:
    shutil.rmtree(database_dir, ignore_errors=True)

# Create the database directory
database_dir.mkdir(parents=True, exist_ok=True)
face_dir.mkdir(parents=True, exist_ok=True)
sub_img_dir.mkdir(parents=True, exist_ok=True)

SECRET_KEY = os.getenv('SECRET_KEY', 'default_fallback_key')

# Define a global lock
frame_lock = Lock()
vs_list = dict()
active_camera_lock = threading.Lock()
active_camera = None