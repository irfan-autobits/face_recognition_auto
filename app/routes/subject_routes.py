# app/routes/subject_routes.py
import pandas as pd
from flask import Blueprint, jsonify, render_template, request
from app.services.subject_manager import subject_service
from config.logger_config import cam_stat_logger , console_logger, exec_time_logger

# now we are importing bp
from app.routes import bp 

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