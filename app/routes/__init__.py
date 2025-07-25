# app/routes/__init__.py
from flask import Blueprint

bp = Blueprint('api', __name__)

from app.routes.camera_routes import *
from app.routes.other_route   import *
from app.routes.subject_routes import *
# … repeat for each file that declares routes on `bp` …
