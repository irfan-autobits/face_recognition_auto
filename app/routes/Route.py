# app/routes/Route.py
from flask import Blueprint, jsonify, render_template, request
from flask import current_app 
from app.services.user_management import sign_up_user, log_in_user
from app.services.camera_manager import Add_camera, Remove_camera, Start_camera, Stop_camera, List_cameras, Recognition_table
from app.services.person_journey import List_knownperson, get_movement_history, update_movement_history
from flask_socketio import SocketIO
from flask import send_from_directory, abort
import os
from config.Paths import FACE_DIR, active_camera, active_camera_lock
import config.Paths as paths  # Ensure you're updating the module variable
from config.logger_config import cam_stat_logger , console_logger, exec_time_logger

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
    responce, status = Recognition_table()
    return responce, status

@bp.route('/faces/<path:subpath>')
def serve_face(subpath):
    """Serve face imgs"""
    file_path = os.path.join(FACE_DIR, subpath)
    if os.path.isfile(file_path):
        return send_from_directory(FACE_DIR, subpath)
    else:
        abort(404)

@bp.route('/api/movement/<person_name>', methods=['GET'])
def movement_history(person_name):
    history = update_movement_history(person_name)
    return jsonify(history)

@bp.route('/api/known_people', methods=['GET'])
def get_known_people():
    responce, status = List_knownperson()
    return responce, status
