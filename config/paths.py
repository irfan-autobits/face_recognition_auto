# config/paths.py
import json
import os
from pathlib import Path
import shutil
import threading
from dotenv import load_dotenv
from threading import Lock
import os

# TEMP UNSET (only for this Python process and child processes)
# 👇 Step 1: Wipe all possible custom env vars
CLEAN_VARS = [
    'IS_RECOGNIZE', 'IS_RM_REPORT', 'IS_GEN_REPORT',
    'model_pack_name', 'CAMERA_SOURCES', 'HOST', 'PORT', 'API_KEY',
    'FACE_DET_LM', 'FACE_DET_TH', 'FACE_REC_TH', 'SECRET_KEY'
]

for var in CLEAN_VARS:
    if var in os.environ:
        print(f"🧹 Unsetting {var}")
        del os.environ[var]
        
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
DATABASE_DIR = BASE_DIR / "AppData"
MODELS_DIR = BASE_DIR / ".models"

SUBJECT_IMG_DIR = DATABASE_DIR / "subjects_imgs"
REPORTS_DIR = DATABASE_DIR / "Reports"

FACE_DIR = REPORTS_DIR / "saved_face"
DET_LOG_FILE_PATH = REPORTS_DIR / "detection_logs.txt"
CAM_STAT_LOG_FILE_PATH = REPORTS_DIR / "cam_stat_logs.txt"
EXEC_TIME_LOG_FILE_PATH = REPORTS_DIR / "exec_time_logs.txt"
FACE_PROC_LOG_FILE_PATH = REPORTS_DIR / "face_proc_logs.txt"

# Simulating variables
database_dir = DATABASE_DIR
reports_dir = REPORTS_DIR
sub_img_dir = SUBJECT_IMG_DIR
face_dir = FACE_DIR

IS_RM_REPORT = os.getenv('IS_RM_REPORT', "true").lower()
IS_GEN_REPORT = os.getenv('IS_GEN_REPORT', "true").lower()
IS_RECOGNIZE = os.getenv('IS_RECOGNIZE', "true").lower()
# Remove the database directory and its contents
if IS_RM_REPORT.lower() == "true":
    shutil.rmtree(reports_dir, ignore_errors=True)
# Create the database directory
database_dir.mkdir(parents=True, exist_ok=True)
reports_dir.mkdir(parents=True, exist_ok=True)
sub_img_dir.mkdir(parents=True, exist_ok=True)
face_dir.mkdir(parents=True, exist_ok=True)

# Retrieve CAMERA_SOURCES and parse it as JSON
CAMERA_SOURCES = os.getenv("CAMERA_SOURCES", "{}")
cam_sources = json.loads(CAMERA_SOURCES)

HOST = os.getenv("HOST", "http://localhost")
PORT = os.getenv("PORT", "8000")
API_KEY = os.getenv("API_KEY", "00000000-0000-0000-0000-000000000002")
FACE_DET_TH = os.getenv("FACE_DET_TH", 0.8)
FACE_REC_TH = os.getenv("FACE_REC_TH", 0.8)
FACE_DET_LM = os.getenv("FACE_DET_LM", 0)


SECRET_KEY = os.getenv('SECRET_KEY', 'default_fallback_key')

# Define a global lock
frame_lock = Lock()
vs_list = dict()
active_camera_lock = threading.Lock()
active_camera = None