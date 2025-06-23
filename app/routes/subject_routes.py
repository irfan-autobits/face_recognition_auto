# app/routes/subject_routes.py
import pandas as pd
from flask import Blueprint, jsonify, render_template, request
from app.services.subject_manager import subject_service
from config.logger_config import cam_stat_logger , console_logger, exec_time_logger, sub_proc_logger

# now we are importing bp
from app.routes import bp 
import traceback

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
    mode = request.form.get("mode")
    print(f"moda while adding is {mode}")
    if mode == "bulk":
        return _handle_csv_upload()
    elif mode == "single":
        return _handle_single_upload()
    else:
        return jsonify({"error": f"{mode} (must be 'bulk' or 'single')"}), 400


def _handle_csv_upload():
    try:
        print("bulk add sub")
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
        file_objs = request.files.getlist('file')
        if not file_objs:
            sub_proc_logger.error("No files provided in single upload")
            return jsonify({"error": "At least one file is required"}), 400
        name = request.form.get('subject_name')
        
        if not file_objs or not name:
            sub_proc_logger.error("File(s) or subject name missing in single upload")
            return jsonify({"error": "File and subject name required"}), 400

        meta = {k.lower(): v for k,v in request.form.items() if k not in ['subject_name', "mode"]}
        sub_proc_logger.info(f"Adding subject '{name}' with meta {meta} and {len(file_objs)} file(s)")
        resp, status = subject_service.add_subject(
            subject_name=name,
            files=file_objs,
            **meta
        )
        sub_proc_logger.info(f"Add subject response: {resp}, status: {status}")
        return jsonify(resp), status

    except Exception as e:
        tb = traceback.format_exc()
        sub_proc_logger.error(f"Exception during single upload: {e}\n{tb}")
        return jsonify({'error': str(e), 'traceback': tb}), 500

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

@bp.route('/api/edit_sub/<subject_id>', methods=['POST'])
def edit_sub(subject_id):
    """
    Edit subject details
    """
    try:
        name = request.form.get('subject_name')
        if not name:
            return jsonify({"error": "Subject name required"}), 400

        # updated_data = {k.lower(): v for k,v in request.form.items() if k != 'subject_name'}
        updated_data = {k.lower(): v for k,v in request.form.items()}
        print(f"editing {subject_id} with name {name} with data {updated_data}")
        resp, status = subject_service.edit_subject(subject_id, **updated_data)

        return jsonify(resp), status

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/api/regen_embeddings/<subject_id>', methods=['POST'])
def regen_embeddings(subject_id):
    model = request.json.get('model')  # optional override
    resp, status = subject_service.regenerate_embeddings(subject_id, model_name=model)
    return jsonify(resp), status