# app/routes/camera_routes.py
from flask import Blueprint, jsonify, render_template, request
from app.services.camera_manager import camera_service
from config.logger_config import cam_stat_logger , console_logger, exec_time_logger

# now we are importing bp
from app.routes import bp 
# ─── camera management  ─────────────────────────────────────────────────
@bp.route('/api/add_camera', methods=['POST'])
def add_camera_route():
    data = request.get_json()
    print(f"adding camera data: {data}")
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

@bp.route('/api/start_feed', methods=['POST'])
def start_feed():
    data = request.get_json()
    name = data.get('camera_name')

    # DEBUG: what streams do we know about?
    # print("▶️ streams before start_feed:", list(camera_service.streams.keys()), flush=True)
    # print("▶️ active_feed before start_feed:", camera_service.get_active_feed(), flush=True)

    resp, status = camera_service.start_feed(name)

    # DEBUG: did start_feed actually flip the switch?
    # print("👈 start_feed response:", resp, status, flush=True)
    # print("▶️ active_feed after start_feed:", camera_service.get_active_feed(), flush=True)
    
    return jsonify(resp), status

@bp.route('/api/stop_feed', methods=['POST'])
def stop_feed():
    data = request.get_json()
    # grab the camera that was active before you clear it
    old = camera_service.get_active_feed()
    resp, status = camera_service.stop_feed()

    return jsonify(resp), status

@bp.route('/api/camera_list', methods=['GET'])
def List_cam():
    """List all the camera"""
    response, status = camera_service.list_cameras()
    return response, status

@bp.route('/camera_timeline', methods=['GET'])
def camera_timeline():
    """Get camera timeline data"""
    response, status = camera_service.camera_timeline_status()
    return jsonify(response), status    

@bp.route('/api/active_feed', methods=['GET'])
def active_feed():
    """Returns the currently active camera feed (or null)."""
    state_out = camera_service.get_active_feed()
    return jsonify({'active_camera': state_out if state_out else None}), 200