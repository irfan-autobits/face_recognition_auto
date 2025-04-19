import os
import json
from pathlib import Path
from dotenv import load_dotenv
from config.pyutil import get_env_bool
# Load environment variables
CLEAN_VARS = [
    'IS_RECOGNIZE','IS_RM_REPORT','IS_GEN_REPORT',
    'model_pack_name','CAMERA_SOURCES','HOST','PORT','API_KEY',
    'FACE_DET_LM','FACE_DET_TH','FACE_REC_TH','SECRET_KEY'
]
for v in CLEAN_VARS:
    os.environ.pop(v, None)
load_dotenv(override=True)

# Base directories
BASE_DIR = Path(__file__).resolve().parent.parent
INSIGHTFACE_ROOT = Path(os.getenv("INSIGHTFACE_ROOT", "~/.insightface")).expanduser()
INSIGHT_MODELS = INSIGHTFACE_ROOT / "models"
# model_zoo = ['buffalo_l', 'buffalo_m', 'buffalo_s']
# model_pack_name = model_zoo[1]
# Model pack name (e.g. "buffalo_l", "buffalo_m", ...)
MODEL_PACK_NAME = os.getenv("MODEL_PACK_NAME", "buffalo_l")

# Application storage
DATABASE_DIR    = BASE_DIR / "AppData"
MODELS_DIR    = BASE_DIR / ".models"
SUBJECT_IMG_DIR = DATABASE_DIR / "subjects_imgs"
REPORTS_DIR     = DATABASE_DIR / "Reports"
FACE_DIR        = REPORTS_DIR / "saved_face"

# Ensure directories exist
for d in (DATABASE_DIR, SUBJECT_IMG_DIR, REPORTS_DIR, FACE_DIR):
    d.mkdir(parents=True, exist_ok=True)

# Log file paths
DET_LOG_FILE_PATH        = REPORTS_DIR / "detection_logs.txt"
CAM_STAT_LOG_FILE_PATH   = REPORTS_DIR / "cam_stat_logs.txt"
EXEC_TIME_LOG_FILE_PATH  = REPORTS_DIR / "exec_time_logs.txt"
FACE_PROC_LOG_FILE_PATH  = REPORTS_DIR / "face_proc_logs.txt"

# Feature flags
IS_RM_REPORT    = get_env_bool("IS_RM_REPORT")
IS_GEN_REPORT   = get_env_bool("IS_GEN_REPORT")
IS_RECOGNIZE    = get_env_bool("IS_RECOGNIZE")

# Optionally purge old reports on startup
if IS_RM_REPORT:
    import shutil
    shutil.rmtree(REPORTS_DIR, ignore_errors=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    FACE_DIR.mkdir(parents=True, exist_ok=True)

# Camera sources from environment (JSON string)
CAMERA_SOURCES = os.getenv("CAMERA_SOURCES", "{}")
cam_sources    = json.loads(CAMERA_SOURCES)

# Network & API settings
HOST    = os.getenv("HOST", "http://localhost")
PORT    = os.getenv("PORT", "8000")
API_KEY = os.getenv("API_KEY","00000000-0000-0000-0000-000000000002")

# Face detection/recognition thresholds
FACE_DET_TH = float(os.getenv("FACE_DET_TH", 0.8))
FACE_REC_TH = float(os.getenv("FACE_REC_TH", 0.8))
FACE_DET_LM = int(os.getenv("FACE_DET_LM", 0))

# Flask secret key
SECRET_KEY = os.getenv('SECRET_KEY', 'default_fallback_key')