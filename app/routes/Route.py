# app/routes/Route.py
from flask import Blueprint, jsonify, render_template, request
from flask import current_app 
from app.services.user_management import sign_up_user, log_in_user
from app.services.camera_manager import Add_camera, Remove_camera, Start_camera, Stop_camera, List_cameras, Recognition_table
from app.services.person_journey import get_movement_history
from app.services.subject_manager import add_subject, list_subject, delete_subject
from flask_socketio import SocketIO
from flask import send_from_directory, abort
import os
from config.Paths import FACE_DIR, active_camera, active_camera_lock, SUBJECT_IMG_DIR
import config.Paths as paths  # Ensure you're updating the module variable
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
        responce, status = sign_up_user(email, password)
        return jsonify(responce), status
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

@bp.route('/api/add_camera', methods=['POST'])
def add_camera():
    """API endpoint to add a camera"""
    data = request.get_json()
    camera_name = data.get('camera_name')
    camera_url = data.get('camera_url')
    if camera_name and camera_url:
        responce, status = Add_camera(camera_name,camera_url)
        return jsonify(responce), status
    else:
        return {'error' : 'Camera name or url not provided'}, 400

@bp.route('/api/remove_camera', methods=['POST'])
def remove_camera():
    """API endpoint to remove a camera"""
    data = request.get_json()
    camera_name = data.get('camera_name')
    if camera_name :
        responce, status = Remove_camera(camera_name)
        return jsonify(responce), status
    else:
        return {'error' : 'Camera name or url not provided'}, 400

@bp.route('/api/start_proc', methods=['POST'])
def start_proc():
    """Start the video feed"""
    data = request.get_json()
    camera_name = data.get('camera_name')
    if camera_name:
        responce, status = Start_camera(camera_name)
        return responce, status
    else:
        return {'error' : 'Camera name not provided for starting processing'}, 400

@bp.route('/api/stop_proc', methods=['POST'])
def stop_proc():
    """Stop the video feed"""
    data = request.get_json()
    camera_name = data.get('camera_name')
    if camera_name:
        responce, status = Stop_camera(camera_name)
        return responce, status
    else:
        return {'error' : 'Camera name not provided for stopping processing'}, 400

@bp.route('/api/start_feed', methods=['POST'])
def start_feed():
    data = request.get_json()
    camera_name = data.get('camera_name')    
    with paths.active_camera_lock:
        paths.active_camera = camera_name
        print(f"activa camera is : {paths.active_camera}")
        cam_stat_logger.debug(f"activa camera is : {paths.active_camera}")
    return {'message': f'Now emitting frames for {camera_name}'}, 200

@bp.route('/api/stop_feed', methods=['POST'])
def stop_feed():
    with paths.active_camera_lock:
        paths.active_camera = None
        print(f"activa camera is : {paths.active_camera}")
        cam_stat_logger.debug(f"activa camera is : {paths.active_camera}")
    return {'message': f'Now emitting frames for None'}, 200

@bp.route('/api/camera_list', methods=['GET'])
def List_cam():
    """List all the camera"""
    responce, status = List_cameras()
    return responce, status
    
@bp.route('/api/reco_table', methods=['GET'])
def List_det():
    """List all the Recognitions"""
    page = request.args.get('page', 1, type=int)
    limit = request.args.get('limit', 100, type=int)
    responce, status = Recognition_table(page,limit)
    return responce, status

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

@bp.route('/api/movement/<person_name>', methods=['GET'])
def movement_history(person_name):
    history = get_movement_history(person_name)
    return jsonify(history)

@bp.route('/api/subject_list', methods=['GET'])
def subject_list():
    print("on list sub")
    response, status = list_subject()
    return response, status

@bp.route('/api/add_sub', methods=['POST'])
def add_sub():
    """API endpoint to add multiple subjects, one per image."""
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400

    files = request.files.getlist('file')
    # Optionally, if you want a default subject name, you can get one field,
    # but typically each file will get its own subject name based on its filename.
    added_subjects = []
    
    for file in files:
        filename = secure_filename(file.filename)
        # Derive subject name from file name (without extension)
        subject_name = os.path.splitext(filename)[0].replace('_', ' ').title()
        
        # Save file locally
        img_path = SUBJECT_IMG_DIR / filename
        img_path = str(img_path)
        os.makedirs(os.path.dirname(img_path), exist_ok=True)
        file.save(img_path)

        # Call service function to add subject for this file/image
        response, status = add_subject(subject_name, img_path)
        if status == 200:
            added_subjects.append(response.get('message', subject_name))
    
    return jsonify({'message': 'Subjects added', 'subjects': added_subjects}), 200


@bp.route('/api/remove_sub/<subject_id>', methods=['DELETE'])
def remove_sub(subject_id):
    response, status = delete_subject(subject_id)
    return response, status    