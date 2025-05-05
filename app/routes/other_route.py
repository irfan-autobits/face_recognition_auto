# app/routes/other_route.py
from flask import jsonify, render_template, request
from app.services.user_management import sign_up_user, log_in_user
from app.services.person_journey import get_movement_history
from app.services.table_stats import giving_system_stats, giving_detection_stats, recognition_table
# from app.services.infrastructure_layout import add_infra_location, remove_location, list_infra_locations
from flask import send_from_directory, abort
import os
from config.paths import FACE_DIR, SUBJECT_IMG_DIR
from config.logger_config import cam_stat_logger , console_logger, exec_time_logger
from app.services.settings_manage import settings
from app.routes import bp 

# Blueprint for routes

@bp.route('/')
def index():
    """Render the video feed page"""
    return {"nessage" : "accessed root page of flask."}, 200
    # return render_template('index_check.html')

@bp.route('/api/sign', methods=['POST'])
def sign():
    """API endpoint to save user data"""
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')

    if email and password:
        response, status = sign_up_user(email, password)
        return jsonify(response), status
    else:
        return {"error": "Email and password are required"}, 400
    
@bp.route('/api/login', methods=['POST'])
def login():
    """API endpoint to save user data"""
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')

    if not email or not password:
        return jsonify({'error': 'Email and password are required'}), 400
    return log_in_user(email, password)

# ─── serving table  ─────────────────────────────────────────────────
@bp.route('/api/reco_table', methods=['GET'])
def List_det():
    """List all the Recognitions"""
    page = request.args.get('page', 1, type=int)
    limit = request.args.get('limit', 500, type=int)
    search = request.args.get('search', '', type=str)
    sort_field = request.args.get('sort_field', 'timestamp', type=str)
    sort_order = request.args.get('sort_order', 'desc', type=str)
    offset = (page - 1) * limit
    responce, status = recognition_table(page,limit, search, sort_field, sort_order, offset)
    return responce, status

# ─── serving img routes  ─────────────────────────────────────────────────
@bp.route('/faces/<path:subpath>')
def serve_face(subpath):
    """Serve face imgs"""
    file_path = os.path.join(FACE_DIR, subpath)
    if os.path.isfile(file_path):
        return send_from_directory(FACE_DIR, subpath)
    else:
        abort(404)

@bp.route('/subserv/<path:subpath>')
def serve_sub(subpath):
    """Serve face imgs"""
    file_path = os.path.join(SUBJECT_IMG_DIR, subpath)
    if os.path.isfile(file_path):
        return send_from_directory(SUBJECT_IMG_DIR, subpath)
    else:
        abort(404)

# ─── person movement ─────────────────────────────────────────────────
@bp.route('/api/movement/<person_name>', methods=['GET'])
def get_movement(person_name):
    start_time = request.args.get('start')
    end_time   = request.args.get('end')

    history = get_movement_history(person_name, start_time, end_time)
    return jsonify(history)

# ─── system stats ─────────────────────────────────────────────────
@bp.route("/api/system_stats", methods=["GET"])
def get_system_stats():
    response, status = giving_system_stats()
    return response, status      

@bp.route('/api/detections_stats', methods=['GET'])
def detection_stats():
    start_str = request.args.get('start')  # default to today-29?
    end_str   = request.args.get('end')   
    response, status = giving_detection_stats(start_str, end_str)
    return response, status     
 
# ─── settings page ─────────────────────────────────────────────────

@bp.route("/settings", methods=["GET"])
def list_settings():
    return jsonify(settings._cache), 200

@bp.route("/settings", methods=["POST"])
def update_setting():
    data = request.get_json()
    key   = data.get("key")
    value = data.get("value")
    if key is None or not isinstance(value, bool):
        return jsonify({"error": "Must provide key (str) and value (bool)"}), 400
    settings.set(key, value)
    return jsonify({key: settings.get(key)}), 200

# @bp.route('/api/location', methods=['POST'])
# def add_location():
#     """
#     Add a new location.
#     Expects form data or JSON with:
#       - name: the location's name (e.g., "Floor 1", "Room 101")
#       - type: the type (e.g., "building", "floor", "room", etc.)
#       - parent_id (optional): the id of the parent location, if any
#     """
#     # Use request.form for form-data or request.get_json() for JSON payload
#     data = request.get_json() if request.is_json else request.form
#     name = data.get('name')
#     loc_type = data.get('type')
#     parent_id = data.get('parent_id')
    
#     if not name or not loc_type:
#         return jsonify({'error': 'Name and type are required.'}), 400
#     response, status = add_infra_location(name, loc_type, parent_id)
#     return response, status  

# @bp.route('/api/location/<int:location_id>', methods=['DELETE'])
# def delete_location(location_id):
#     """
#     Delete a location by ID.
#     Cascade rules in your model will handle deletion of child locations if configured.
#     """
#     response, status = remove_location(location_id)
#     return response, status 

# @bp.route('/api/location', methods=['GET'])
# def list_locations():
#     """
#     Get all locations in a simple list.
#     You can further structure this to output a tree if needed.
#     """
#     response, status = list_infra_locations()
#     return response, status 

