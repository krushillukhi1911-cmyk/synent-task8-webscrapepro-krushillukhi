import os
from flask import Blueprint, jsonify, request, send_file, current_app, flash, redirect, url_for
from flask_login import login_required, current_user
from app.extensions import db
from app.models import ScraperTask, DataRecord, ExportRecord, AuditLog, Project
from app.services.exporter import Exporter

exports_bp = Blueprint('exports', __name__, url_prefix='/exports')

@exports_bp.route('/create/<int:task_id>', methods=['POST'])
@login_required
def create_export(task_id):
    """Triggers file generation (JSON, CSV, EXCEL, PDF, ZIP) for scraped task data."""
    task = ScraperTask.query.get_or_404(task_id)
    # Ensure task belongs to current user
    if task.project.user_id != current_user.id:
        return jsonify({"error": "Unauthorized"}), 403
        
    if task.status != 'COMPLETED':
        return jsonify({"error": f"Cannot export data from a task with status: {task.status}"}), 400

    # Get records
    records = DataRecord.query.filter_by(task_id=task_id).all()
    if not records:
        return jsonify({"error": "No scraped records found to export."}), 404

    # Determine format
    file_format = request.args.get('format', 'csv').lower()
    if file_format not in ['csv', 'json', 'excel', 'pdf', 'zip']:
        return jsonify({"error": f"Invalid format '{file_format}'. Supported: csv, json, excel, pdf, zip"}), 400

    # Setup directories
    base_dir = current_app.config['EXPORT_DIR']
    task_export_dir = os.path.join(base_dir, f"task_{task_id}")
    os.makedirs(task_export_dir, exist_ok=True)
    
    # Filename schema
    safe_filename = f"scraped_data_task_{task_id}_{file_format}"
    if file_format == 'excel':
        filename = f"{safe_filename}.xlsx"
    else:
        filename = f"{safe_filename}.{file_format}"
        
    file_path = os.path.join(task_export_dir, filename)
    
    # Generate file
    try:
        if file_format == 'json':
            Exporter.export_to_json(records, file_path)
        elif file_format == 'csv':
            Exporter.export_to_csv(records, file_path)
        elif file_format == 'excel':
            Exporter.export_to_excel(records, file_path)
        elif file_format == 'pdf':
            Exporter.export_to_pdf(records, file_path, task)
        elif file_format == 'zip':
            Exporter.export_to_zip(records, file_path)
    except Exception as e:
        return jsonify({"error": f"Generation failed: {str(e)}"}), 500

    # Compute size
    file_size = os.path.getsize(file_path)
    
    # Log export in DB
    export_rec = ExportRecord.query.filter_by(task_id=task_id, file_format=file_format.upper()).first()
    if not export_rec:
        export_rec = ExportRecord(
            project_id=task.project_id,
            task_id=task_id,
            file_name=filename,
            file_path=file_path,
            file_format=file_format.upper(),
            file_size=file_size
        )
        db.session.add(export_rec)
    else:
        # Overwrite size / timestamp
        export_rec.file_size = file_size
        export_rec.created_at = db.session.utcnow() if hasattr(db.session, 'utcnow') else None # defaulting default datetimes
        
    db.session.commit()
    
    # Audit log
    log = AuditLog(
        user_id=current_user.id,
        action=f"Generated {file_format.upper()} export for Task {task_id}",
        ip_address=request.remote_addr
    )
    db.session.add(log)
    db.session.commit()
    
    return jsonify({
        "message": f"Export file generated successfully.",
        "download_url": url_for('exports.download_file', record_id=export_rec.id),
        "record": {
            "id": export_rec.id,
            "filename": export_rec.file_name,
            "format": export_rec.file_format,
            "size_bytes": export_rec.file_size
        }
    }), 201


@exports_bp.route('/download/<int:record_id>', methods=['GET'])
@login_required
def download_file(record_id):
    """Fetches export document and returns download stream."""
    export_rec = ExportRecord.query.get_or_404(record_id)
    # Ensure task/project belongs to user
    project = Project.query.get(export_rec.project_id)
    if not project or project.user_id != current_user.id:
        flash("You are not authorized to download this file.", "danger")
        return redirect(url_for('main.dashboard'))
        
    if not os.path.exists(export_rec.file_path):
        flash("Export file not found on disk. It may have been cleared.", "danger")
        return redirect(url_for('main.dashboard'))
        
    # Return file stream
    return send_file(
        export_rec.file_path,
        as_attachment=True,
        download_name=export_rec.file_name
    )


@exports_bp.route('/list/<int:project_id>', methods=['GET'])
@login_required
def list_exports(project_id):
    """Retrieve history of files exported for a given project."""
    project = Project.query.filter_by(id=project_id, user_id=current_user.id).first_or_404()
    exports = ExportRecord.query.filter_by(project_id=project_id).order_by(ExportRecord.created_at.desc()).all()
    
    export_list = [{
        "id": exp.id,
        "task_id": exp.task_id,
        "filename": exp.file_name,
        "format": exp.file_format,
        "size_bytes": exp.file_size,
        "created_at": exp.created_at.isoformat()
    } for exp in exports]
    
    return jsonify(export_list), 200
