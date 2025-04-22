# app/routes/route.py
import pandas as pd
from flask import Blueprint, jsonify, render_template, request, current_app
from app.services.user_management import sign_up_user, log_in_user
from app.services.camera_manager import camera_service
from app.services.subject_manager import subject_service
from app.services.person_journey import get_movement_history
from app.services.table_stats import giving_system_stats, giving_detection_stats, recognition_table
# from app.services.infrastructure_layout import add_infra_location, remove_location, list_infra_locations
from flask_socketio import SocketIO
from flask import send_from_directory, abort
import os
from config.paths import FACE_DIR, SUBJECT_IMG_DIR
import config.state as state  # Ensure you're updating the module variable
from config.logger_config import cam_stat_logger , console_logger, exec_time_logger
from werkzeug.utils import secure_filename

# Blueprint for routes
bp = Blueprint('video_feed', __name__)

# Flag to control the camera feed
active_cameras = []

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

# ─── camera management  ─────────────────────────────────────────────────
@bp.route('/api/add_camera', methods=['POST'])
def add_camera_route():
    data = request.get_json()
    resp, status = camera_service.add_camera(
        data['camera_name'], data['camera_url'], data['tag']
    )
    return jsonify(resp), status

@bp.route('/api/remove_camera', methods=['POST'])
def remove_camera_route():
    """API endpoint to remove a camera"""
    data = request.get_json()
    response, status = camera_service.remove_camera(data.get('camera_name'))
    return jsonify(response), status

@bp.route('/api/start_proc', methods=['POST'])
def start_proc():
    """Start the camera"""
    data = request.get_json()
    camera_name = data.get('camera_name')
    if camera_name:
        response, status = camera_service.start_camera(camera_name)
        return response, status
    else:
        return {'error' : 'Camera name not provided for starting processing'}, 400

@bp.route('/api/stop_proc', methods=['POST'])
def stop_proc():
    """Stop the camera"""
    data = request.get_json()
    camera_name = data.get('camera_name')
    if camera_name:
        response, status = camera_service.stop_camera(camera_name)
        return response, status
    else:
        return {'error' : 'Camera name not provided for stopping processing'}, 400

@bp.route('/api/start_all_proc', methods=['GET'])
def start_all_proc():
    """Start all cameras."""
    response, status = camera_service.start_all()
    return jsonify(response), status

@bp.route('/api/stop_all_proc', methods=['GET'])
def stop_all_proc():
    """Stop all cameras."""
    response, status = camera_service.stop_all()
    return jsonify(response), status

@bp.route('/api/restart_all_proc', methods=['GET'])
def restart_all_proc():
    """Restart all cameras: stop then start."""
    stop_response, stop_status = camera_service.start_all()
    # Optionally, can check stop_status before proceeding.
    start_response, start_status = camera_service.start_all()
    # want to return both responses, for example:
    combined_response = {
        "stop": stop_response,
        "start": start_response
    }
    # In this example, we return the start status, but can be adjusted as needed.
    return jsonify(combined_response), start_status

@bp.route('/api/camera_list', methods=['GET'])
def List_cam():
    """List all the camera"""
    response, status = camera_service.list_cameras()
    return response, status

@bp.route('/api/start_feed', methods=['POST'])
def start_feed():
    data = request.get_json()
    camera_name = data.get('camera_name')    
    with state.active_camera_lock:
        state.active_camera = camera_name
        print(f"activa camera is : {state.active_camera}")
        cam_stat_logger.debug(f"activa camera is : {state.active_camera}")
    return {'message': f'Now emitting fDetectionrames for {camera_name}'}, 200

@bp.route('/api/stop_feed', methods=['POST'])
def stop_feed():
    with state.active_camera_lock:
        state.active_camera = None
        print(f"activa camera is : {state.active_camera}")
        cam_stat_logger.debug(f"activa camera is : {state.active_camera}")
    return {'message': f'Now emitting frames for None'}, 200

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
def movement_history(person_name):
    history = get_movement_history(person_name)
    return jsonify(history)

@bp.route('/api/movement/<person_name>', methods=['POST'])
def get_movement(person_name):
    data = request.get_json()
    start_time = data.get('start_time')
    end_time = data.get('end_time')

    history = get_movement_history(person_name, start_time, end_time)
    return jsonify(history)

# ─── subject management ─────────────────────────────────────────────────
@bp.route('/api/subject_list', methods=['GET'])
def subject_list():
    resp, status = subject_service.list_subjects()
    return jsonify(resp), status

@bp.route('/api/add_sub', methods=['POST'])
def add_sub():
    """
    Add subjects via CSV or single form, using standardized processing
    """
    if 'csv' in request.files:
        return _handle_csv_upload()
    return _handle_single_upload()

def _handle_csv_upload():
    try:
        csv_file = request.files['csv']
        df = pd.read_csv(csv_file)
        uploaded_files = {f.filename: f for f in request.files.getlist('file')}
        results = []

        for _, row in df.iterrows():
            result = _process_subject_row(row, uploaded_files)
            results.append(result)

        return jsonify({'results': results}), 207

    except Exception as e:
        return jsonify({'error': str(e)}), 500

def _handle_single_upload():
    try:
        file_obj = request.files.get('file')
        name = request.form.get('subject_name')
        
        if not file_obj or not name:
            return jsonify({"error": "File and subject name required"}), 400

        meta = {k.lower(): v for k,v in request.form.items() if k != 'subject_name'}
        resp, status = subject_service.add_subject(
            subject_name=name,
            file_obj=file_obj,
            **meta
        )
        return jsonify(resp), status

    except Exception as e:
        return jsonify({'error': str(e)}), 500

def _process_subject_row(row, uploaded_files):
    name = row.get('subject_name')
    fname = row.get('file_name')
    file = uploaded_files.get(fname)
    
    if not file:
        return {
            'subject': name,
            'status': 'error',
            'message': f"Missing file '{fname}'"
        }

    try:
        meta = {k.lower(): row.get(k) for k in ['Age', 'Gender', 'Email', 'Phone', 'Aadhar']}
        resp, status = subject_service.add_subject(name, file, **meta)
        return {
            'subject': name,
            'status': 'success' if status == 200 else 'error',
            'response': resp
        }
    except Exception as e:
        return {
            'subject': name,
            'status': 'error',
            'message': str(e)
        }

@bp.route('/api/add_subject_img/<subject_id>', methods=['POST'])
def add_subject_img(subject_id):
    f = request.files.get('file')
    if not f:
        return jsonify({"error": "No image file provided"}), 400
    resp, status = subject_service.add_image(subject_id, f)
    return jsonify(resp), status

@bp.route('/api/remove_sub/<subject_id>', methods=['DELETE'])
def remove_sub(subject_id):
    resp, status = subject_service.delete_subject(subject_id)
    return jsonify(resp), status

@bp.route('/api/remove_subject_img/<img_id>', methods=['DELETE'])
def remove_subject_img(img_id):
    resp, status = subject_service.delete_subject_img(img_id)
    return jsonify(resp), status

@bp.route('/api/regen_embeddings/<subject_id>', methods=['POST'])
def regen_embeddings(subject_id):
    model = request.json.get('model')  # optional override
    resp, status = subject_service.regenerate_embeddings(subject_id, model_name=model)
    return jsonify(resp), status

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

# 
@bp.route("/api/system_stats", methods=["GET"])
def get_system_stats():
    response, status = giving_system_stats()
    return response, status      

@bp.route('/api/detections_stats', methods=['GET'])
def detection_stats():
    response, status = giving_detection_stats()
    return response, status      
