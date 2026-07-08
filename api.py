from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
from app.extensions import db
from app.models import Project, ScraperTask, DataRecord, ExportRecord, AuditLog
from sqlalchemy import func

api_bp = Blueprint('api', __name__, url_prefix='/api')

# ==========================================
# PROJECT ENDPOINTS
# ==========================================

@api_bp.route('/projects', methods=['GET'])
@login_required
def get_projects():
    """Retrieve all projects belonging to the current user."""
    projects = Project.query.filter_by(user_id=current_user.id).order_by(Project.created_at.desc()).all()
    project_list = [{
        "id": p.id,
        "name": p.name,
        "description": p.description,
        "created_at": p.created_at.isoformat(),
        "task_count": len(p.tasks)
    } for p in projects]
    return jsonify(project_list), 200


@api_bp.route('/projects', methods=['POST'])
@login_required
def create_project():
    """Create a new project."""
    data = request.get_json() or {}
    name = data.get('name')
    description = data.get('description', '')
    
    if not name:
        return jsonify({"error": "Project name is required"}), 400
        
    project = Project(
        name=name,
        description=description,
        user_id=current_user.id
    )
    db.session.add(project)
    db.session.commit()
    
    # Audit log
    log = AuditLog(
        user_id=current_user.id,
        action=f"Created Project: {name} (ID: {project.id})",
        ip_address=request.remote_addr
    )
    db.session.add(log)
    db.session.commit()
    
    return jsonify({
        "message": "Project created successfully",
        "project": {
            "id": project.id,
            "name": project.name,
            "description": project.description,
            "created_at": project.created_at.isoformat()
        }
    }), 201


@api_bp.route('/projects/<int:project_id>', methods=['GET'])
@login_required
def get_project(project_id):
    """Retrieve details of a specific project."""
    project = Project.query.filter_by(id=project_id, user_id=current_user.id).first_or_404()
    
    tasks = [{
        "id": t.id,
        "url": t.url,
        "status": t.status,
        "total_extracted": t.total_extracted,
        "started_at": t.started_at.isoformat() if t.started_at else None,
        "completed_at": t.completed_at.isoformat() if t.completed_at else None
    } for t in project.tasks]
    
    return jsonify({
        "id": project.id,
        "name": project.name,
        "description": project.description,
        "created_at": project.created_at.isoformat(),
        "tasks": tasks
    }), 200


@api_bp.route('/projects/<int:project_id>', methods=['PUT'])
@login_required
def update_project(project_id):
    """Update name and description of a project."""
    project = Project.query.filter_by(id=project_id, user_id=current_user.id).first_or_404()
    data = request.get_json() or {}
    
    name = data.get('name')
    description = data.get('description')
    
    if name is not None:
        if not name.strip():
            return jsonify({"error": "Project name cannot be empty"}), 400
        project.name = name.strip()
    if description is not None:
        project.description = description.strip()
        
    db.session.commit()
    
    # Audit log
    log = AuditLog(
        user_id=current_user.id,
        action=f"Updated Project ID: {project_id}",
        ip_address=request.remote_addr
    )
    db.session.add(log)
    db.session.commit()
    
    return jsonify({
        "message": "Project updated successfully",
        "project": {
            "id": project.id,
            "name": project.name,
            "description": project.description
        }
    }), 200


@api_bp.route('/projects/<int:project_id>', methods=['DELETE'])
@login_required
def delete_project(project_id):
    """Delete a project and all associated tasks/records."""
    project = Project.query.filter_by(id=project_id, user_id=current_user.id).first_or_404()
    
    # Audit log before deletion
    log = AuditLog(
        user_id=current_user.id,
        action=f"Deleted Project: {project.name} (ID: {project_id})",
        ip_address=request.remote_addr
    )
    db.session.add(log)
    
    # SQLAlchemy cascade will delete associated tasks and records automatically
    db.session.delete(project)
    db.session.commit()
    
    return jsonify({"message": "Project and all associated scrapers/results deleted successfully."}), 200


# ==========================================
# TASK & DATA RECORD ENDPOINTS
# ==========================================

@api_bp.route('/tasks', methods=['GET'])
@login_required
def get_tasks():
    """Retrieve scraper tasks. Can filter by project_id in query params."""
    project_id = request.args.get('project_id')
    
    query = ScraperTask.query.join(Project).filter(Project.user_id == current_user.id)
    if project_id:
        query = query.filter(ScraperTask.project_id == project_id)
        
    tasks = query.order_by(ScraperTask.id.desc()).all()
    task_list = [{
        "id": t.id,
        "project_id": t.project_id,
        "project_name": t.project.name,
        "url": t.url,
        "status": t.status,
        "started_at": t.started_at.isoformat() if t.started_at else None,
        "completed_at": t.completed_at.isoformat() if t.completed_at else None,
        "total_extracted": t.total_extracted
    } for t in tasks]
    
    return jsonify(task_list), 200


@api_bp.route('/tasks/<int:task_id>/data', methods=['GET'])
@login_required
def get_task_data(task_id):
    """Retrieve data records collected by a specific task."""
    task = ScraperTask.query.get_or_404(task_id)
    if task.project.user_id != current_user.id:
        return jsonify({"error": "Unauthorized"}), 403
        
    records = DataRecord.query.filter_by(task_id=task_id).all()
    results = [r.data_content for r in records]
    
    return jsonify({
        "task_id": task_id,
        "url": task.url,
        "records_count": len(results),
        "data": results
    }), 200


# ==========================================
# ANALYTICS ENDPOINTS
# ==========================================

@api_bp.route('/analytics', methods=['GET'])
@login_required
def get_analytics():
    """Aggregate statistics for user dashboard."""
    # Count of user's projects
    proj_count = Project.query.filter_by(user_id=current_user.id).count()
    
    # Sub-query filtering tasks belonging to the current user
    user_tasks = ScraperTask.query.join(Project).filter(Project.user_id == current_user.id)
    
    task_count = user_tasks.count()
    completed_count = user_tasks.filter(ScraperTask.status == 'COMPLETED').count()
    failed_count = user_tasks.filter(ScraperTask.status == 'FAILED').count()
    active_count = user_tasks.filter(ScraperTask.status == 'RUNNING').count()
    
    success_rate = (completed_count / task_count * 100) if task_count > 0 else 100.0
    
    # Total data rows extracted
    total_data_rows = db.session.query(func.sum(ScraperTask.total_extracted))\
        .join(Project).filter(Project.user_id == current_user.id).scalar() or 0
        
    # Get active downloads count
    downloads_count = ExportRecord.query.join(Project).filter(Project.user_id == current_user.id).count()
    
    # Calculate average time (for successfully completed tasks)
    completed_tasks = user_tasks.filter(ScraperTask.status == 'COMPLETED').all()
    durations = []
    for t in completed_tasks:
        if t.started_at and t.completed_at:
            durations.append((t.completed_at - t.started_at).total_seconds())
    avg_duration = sum(durations) / len(durations) if durations else 0.0
    
    # Return structured analytics payload
    return jsonify({
        "projects_count": proj_count,
        "tasks_summary": {
            "total": task_count,
            "completed": completed_count,
            "failed": failed_count,
            "active": active_count,
            "success_rate": round(success_rate, 2)
        },
        "records_extracted": total_data_rows,
        "exports_count": downloads_count,
        "avg_scraping_duration_seconds": round(avg_duration, 2)
    }), 200
