# app/routes/other_route.py
from flask import jsonify, render_template, request
from app.services.user_management import sign_up_user, log_in_user
from app.services.person_journey import get_movement_history
from app.services.table_stats import giving_system_stats, giving_detection_stats, recognition_table, heatmap_by_range
# from app.services.infrastructure_layout import add_infra_location, remove_location, list_infra_locations
from flask import send_from_directory, abort
import os
from config.paths import FACE_DIR, SUBJECT_IMG_DIR, DOWNLOAD_DIR
from config.logger_config import cam_stat_logger , console_logger, exec_time_logger, face_proc_logger
from app.services.settings_manage import settings
from app.routes import bp 
from app.services.reco_table_helper import parse_params

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
@bp.route('/api/reco_table', methods=['POST'])
def List_det():
    data = request.get_json()
    params = parse_params(data)
    responce, status = recognition_table(params)
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

@bp.route('/download/<path:csvpath>', methods=['GET'])
def download_csv(csvpath):
    """Serve file for download with content-disposition header"""
    file_path = os.path.join(DOWNLOAD_DIR, csvpath)
    print(f"file path is {file_path} \n should be {DOWNLOAD_DIR}/sample_add.csv")
    if os.path.isfile(file_path):
        return send_from_directory(
            DOWNLOAD_DIR,
            csvpath,
            as_attachment=True,
            download_name=csvpath
        )
    else:
        abort(404)

# ─── person movement ─────────────────────────────────────────────────
@bp.route('/api/movement/<person_name>', methods=['GET'])
def get_movement(person_name):
    start_time = request.args.get('start')
    end_time   = request.args.get('end')

    history = get_movement_history(person_name, start_time, end_time)
    # print(f"movement for {person_name} from {start_time} end{end_time}:{history}")
    # face_proc_logger.info(f"movement for {person_name} :{history}")
    return jsonify(history)

# ─── system stats ─────────────────────────────────────────────────
@bp.route("/api/system_stats", methods=["GET"])
def get_system_stats():
    response, status = giving_system_stats()
    return response, status      

@bp.route('/api/detections_stats', methods=['GET'])
def detection_stats():
    """ /api/detections_stats?start=2025-06-18&end=2025-06-18 """
    start_str = request.args.get('start') # 2025-06-18T06:36:43Z
    end_str   = request.args.get('end')
    interval   = request.args.get('interval') # 'daily', 'hourly'
    response, status = giving_detection_stats(time_window_start=start_str, time_window_end=end_str, interval=interval)
    return response, status     
 
@bp.route('/api/detection_heatmap_range', methods=['GET'])
def detection_heatmap_range():
    """ 
    REQ:- GET /api/detection_heatmap_range?start=YYYY-MM-DD&end=YYYY-MM-DD
    returns:- 
        {
        "start": "2025-02-21",
        "end": "2025-06-20",
        "data": [
            { "date": "2025-02-21", "count": 5 },
            { "date": "2025-02-22", "count": 0 },
            ...
        ]
        }
    """
    start = request.args.get("start")
    end = request.args.get("end")

    if not start or not end:
        return jsonify({"error": "start and end dates required"}), 400

    response, status = heatmap_by_range(start, end)
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
