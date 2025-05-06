# app/services/settings_manage.py
from config.paths import IS_RECOGNIZE, IS_GEN_REPORT, IS_RM_REPORT
from app.models.model import AppConfig, db
from config.logger_config import face_proc_logger

class SettingsService:
    def __init__(self):
        self._cache = {}

    def init_app(self, app):
        """Call this once, after your Flask app is created, to load from DB."""
        with app.app_context():
            self.reload()

    def reload(self):
        self._cache = {
          row.key: (row.value.lower() == "true")
          for row in AppConfig.query.all()
        }

    def get(self, key: str) -> bool:
        return self._cache.get(key, False)

    def set(self, key: str, value: bool):
        row = AppConfig.query.get(key)
        if row:
            row.value = "true" if value else "false"
        else:
            row = AppConfig(key=key, value="true" if value else "false")
            db.session.add(row)
        db.session.commit()
        self._cache[key] = value

settings = SettingsService()

def seed_feature_flags():
    defaults = {
        "RECOGNIZE":  IS_RECOGNIZE,
        "GEN_REPORT": IS_GEN_REPORT,
        "RM_REPORT":  IS_RM_REPORT,
    }
    for key, val in defaults.items():
        row = AppConfig.query.get(key)
        if row is None:
            # first‐time insert
            row = AppConfig(key=key, value="true" if val else "false")
            db.session.add(row)
        else:
            # keep whatever is in the database (so user toggles survive restarts)
            continue
    db.session.commit()
    face_proc_logger.info(f"settings populated as :{defaults}")