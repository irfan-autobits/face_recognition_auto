# app/routes/route.py
import pandas as pd
from flask import Blueprint, jsonify, render_template, request
from flask import current_app 
from app.services.user_management import sign_up_user, log_in_user
from app.services.camera_manager import camera_service, recognition_table
from app.services.person_journey import get_movement_history
from app.services.subject_manager import add_subject, list_subject, delete_subject, add_image_to_subject, delete_subject_img
# from app.services.infrastructure_layout import add_infra_location, remove_location, list_infra_locations
from flask_socketio import SocketIO
from flask import send_from_directory, abort
import os
from config.paths import FACE_DIR, active_camera, active_camera_lock, SUBJECT_IMG_DIR
import config.paths as paths  # Ensure you're updating the module variable
from config.logger_config import cam_stat_logger , console_logger, exec_time_logger
from flask import request, jsonify, current_app
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
    with paths.active_camera_lock:
        paths.active_camera = camera_name
        print(f"activa camera is : {paths.active_camera}")
        cam_stat_logger.debug(f"activa camera is : {paths.active_camera}")
    return {'message': f'Now emitting fDetectionrames for {camera_name}'}, 200

@bp.route('/api/stop_feed', methods=['POST'])
def stop_feed():
    with paths.active_camera_lock:
        paths.active_camera = None
        print(f"activa camera is : {paths.active_camera}")
        cam_stat_logger.debug(f"activa camera is : {paths.active_camera}")
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
    print("on list sub")
    response, status = list_subject()
    return response, status

@bp.route('/api/add_sub', methods=['POST'])
def add_sub():
    """
    API endpoint to add subjects with metadata from form or CSV.
    for single mode it can take multiple img for single subject 
    for csv mode it can take multiple subjects , but one img per subject extra img can be addded separately
    """

    # Bulk CSV mode
    if 'csv' in request.files:
        csv_file = request.files['csv']
        df = pd.read_csv(csv_file)
        uploaded_files = {f.filename: f for f in request.files.getlist('file')}

        added_subjects = []

        for _, row in df.iterrows():
            subject_name = row.get('subject_name')
            file_name = row.get('file_name')
            age = row.get('Age')
            gender = row.get('Gender')
            email = row.get('Email')
            phone = row.get('Phone')
            aadhar = row.get('Aadhar')

            file = uploaded_files.get(file_name)
            if not file:
                continue  # Skip if no matching image was uploaded

            filename = secure_filename(file.filename)
            img_path = str(SUBJECT_IMG_DIR / filename)
            os.makedirs(os.path.dirname(img_path), exist_ok=True)
            file.save(img_path)

            response, status = add_subject(subject_name, img_path, age, gender, email, phone, aadhar)
            if status == 200:
                added_subjects.append(response.get('message', subject_name))

        return jsonify({'message': 'Subjects added via CSV', 'subjects': added_subjects}), 200

    # Single subject form mode
    if 'file' not in request.files:
        return jsonify({'error': 'No image file provided'}), 400

    files = request.files.getlist('file')
    subject_name = request.form.get('subject_name')
    age = request.form.get('Age')
    gender = request.form.get('Gender')
    email = request.form.get('Email')
    phone = request.form.get('Phone')
    aadhar = request.form.get('Aadhar')

    if not subject_name:
        return jsonify({'error': 'Subject name is required'}), 400

    added_subjects = []

    for file in files:
        filename = secure_filename(file.filename)
        img_path = str(SUBJECT_IMG_DIR / filename)
        os.makedirs(os.path.dirname(img_path), exist_ok=True)
        file.save(img_path)

        response, status = add_subject(subject_name, img_path, age, gender, email, phone, aadhar)
        if status == 200:
            added_subjects.append(response.get('message', subject_name))

    return jsonify({'message': 'Subjects added', 'subjects': added_subjects}), 200

@bp.route('/api/remove_sub/<subject_id>', methods=['DELETE'])
def remove_sub(subject_id):
    response, status = delete_subject(subject_id)
    return response, status    

@bp.route('/api/add_subject_img/<subject_id>', methods=['POST'])
def add_subject_img(subject_id):
    """
    API endpoint to add a new image to an existing subject.
    Expects one file in request.files with key 'file'.
    """
    # Check if the file is provided in the request
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400

    file = request.files['file']
    if not file.filename:
        return jsonify({'error': 'No file selected'}), 400

    # Call the service function to add the image
    response, status = add_image_to_subject(subject_id, file)
    return jsonify(response), status

@bp.route('/api/remove_subject_img/<img_id>', methods=['DELETE'])
def remove_subject_img(img_id):
    response, status = delete_subject_img(img_id)
    return response, status  


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
