import time
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, Response, current_app
from flask_login import login_required, current_user
from app.extensions import db
from app.models import Project, ScraperTask, DataRecord, AuditLog
from app.services.task_manager import task_manager

scraper_bp = Blueprint('scraper', __name__, url_prefix='/scraper')

@scraper_bp.route('/console', methods=['GET', 'POST'])
@login_required
def console():
    """Form to initiate new scraping tasks."""
    # List user's projects to populate select dropdown
    projects = Project.query.filter_by(user_id=current_user.id).order_by(Project.created_at.desc()).all()
    
    if request.method == 'POST':
        project_id = request.form.get('project_id')
        url = request.form.get('url')
        depth = int(request.form.get('depth', 1))
        dynamic = True if request.form.get('dynamic') == 'on' else False
        timeout = int(request.form.get('timeout', 15))
        rate_limit = float(request.form.get('rate_limit', 1.0))
        ignore_robots = True if request.form.get('ignore_robots') == 'on' else False
        
        # Verify project belongs to current user
        project = Project.query.filter_by(id=project_id, user_id=current_user.id).first()
        if not project:
            flash("Invalid project selection.", "danger")
            return redirect(url_for('scraper.console'))
            
        if not url:
            flash("Target URL is required.", "danger")
            return redirect(url_for('scraper.console'))

        # Prepare JSON config
        configuration = {
            "depth": depth,
            "dynamic": dynamic,
            "timeout": timeout,
            "rate_limit": rate_limit,
            "ignore_robots_txt": ignore_robots,
            "selectors": {}  # Add custom selectors support in future edit
        }
        
        # Create Scraper Task
        new_task = ScraperTask(
            project_id=project.id,
            url=url,
            configuration=configuration,
            status='PENDING'
        )
        db.session.add(new_task)
        db.session.commit()
        
        # Create Audit Log
        log = AuditLog(
            user_id=current_user.id,
            action=f"Created Scraper Task {new_task.id} for URL {url}",
            ip_address=request.remote_addr
        )
        db.session.add(log)
        db.session.commit()
        
        # Launch Task in Background
        # We pass flask current_app context to execute DB statements inside threads
        task_manager.start_task(current_app._get_current_object(), new_task.id)
        
        flash("Scraping task initiated successfully!", "success")
        return redirect(url_for('scraper.progress', task_id=new_task.id))
        
    return render_template('scraper/console.html', projects=projects)


@scraper_bp.route('/task/<int:task_id>/progress')
@login_required
def progress(task_id):
    """Visual page displaying live log stream and progress."""
    task = ScraperTask.query.get_or_404(task_id)
    # Ensure task belongs to user's project
    if task.project.user_id != current_user.id:
        return "Unauthorized", 403
        
    return render_template('scraper/progress.html', task=task)


@scraper_bp.route('/task/<int:task_id>/cancel', methods=['POST'])
@login_required
def cancel(task_id):
    """API endpoint to cancel a running task."""
    task = ScraperTask.query.get_or_404(task_id)
    if task.project.user_id != current_user.id:
        return jsonify({"error": "Unauthorized"}), 403
        
    success = task_manager.cancel_task(task_id)
    if success:
        # Force update db status in case worker is idle
        task.status = "CANCELLED"
        db.session.commit()
        
        log = AuditLog(
            user_id=current_user.id,
            action=f"Scraper Task {task_id} cancellation requested.",
            ip_address=request.remote_addr
        )
        db.session.add(log)
        db.session.commit()
        
        return jsonify({"message": "Task cancellation signaled successfully."}), 200
        
    return jsonify({"error": "Task is not active or could not be cancelled."}), 400


@scraper_bp.route('/task/<int:task_id>/status')
@login_required
def status(task_id):
    """API endpoint checking status of task."""
    task = ScraperTask.query.get_or_404(task_id)
    if task.project.user_id != current_user.id:
        return jsonify({"error": "Unauthorized"}), 403
        
    return jsonify({
        "task_id": task.id,
        "status": task.status,
        "total_extracted": task.total_extracted,
        "started_at": task.started_at.isoformat() if task.started_at else None,
        "completed_at": task.completed_at.isoformat() if task.completed_at else None,
        "error_message": task.error_message
    })


@scraper_bp.route('/task/<int:task_id>/results')
@login_required
def results(task_id):
    """View details of scraped results (Overview & Data Preview)."""
    task = ScraperTask.query.get_or_404(task_id)
    if task.project.user_id != current_user.id:
        return "Unauthorized", 403
        
    records = DataRecord.query.filter_by(task_id=task_id).all()
    return render_template('scraper/results.html', task=task, records=records)


@scraper_bp.route('/task/<int:task_id>/stream')
@login_required
def stream(task_id):
    """Server-Sent Events stream yielding scraping log lines in real-time."""
    task_check = ScraperTask.query.get_or_404(task_id)
    if task_check.project.user_id != current_user.id:
        return "Unauthorized", 403

    app = current_app._get_current_object()

    def generate_logs():
        with app.app_context():
            task = ScraperTask.query.get(task_id)
            if not task:
                return
                
            last_log_index = 0
            
            while True:
                # Get in-memory logs
                logs = task_manager.get_task_logs(task_id)
                
                # If the task finished and memory log cache cleared, read from file
                if logs is None:
                    # Read final file lines if they exist
                    if task.log_file_path and os.path.exists(task.log_file_path):
                        try:
                            with open(task.log_file_path, 'r') as f:
                                lines = f.readlines()
                            if len(lines) > last_log_index:
                                for line in lines[last_log_index:]:
                                    yield f"data: {line.strip()}\n\n"
                        except Exception:
                            pass
                    yield "data: [Task Terminated]\n\n"
                    break
                    
                if len(logs) > last_log_index:
                    for log in logs[last_log_index:]:
                        yield f"data: {log}\n\n"
                    last_log_index = len(logs)
                    
                # Force close read transaction to pull updated task status from SQLite
                try:
                    db.session.commit()
                except Exception:
                    db.session.rollback()
                    
                db.session.refresh(task)
                if task.status in ['COMPLETED', 'FAILED', 'CANCELLED'] and len(logs) == last_log_index:
                    yield "data: [Task Terminated]\n\n"
                    break
                    
                time.sleep(0.5)

    return Response(generate_logs(), mimetype='text/event-stream')
