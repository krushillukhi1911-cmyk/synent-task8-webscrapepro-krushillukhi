from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_required, current_user
from app.extensions import db
from app.models import Project, ScraperTask, AuditLog, DataRecord, ExportRecord

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def index():
    """Landing index page for unauthenticated visitors."""
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    return render_template('main/index.html')


@main_bp.route('/dashboard')
@login_required
def dashboard():
    """User dashboard aggregating metrics, charts, and project items."""
    projects = Project.query.filter_by(user_id=current_user.id).order_by(Project.created_at.desc()).all()
    
    # Fetch recent tasks
    recent_tasks = ScraperTask.query.join(Project).filter(Project.user_id == current_user.id)\
        .order_by(ScraperTask.started_at.desc()).limit(5).all()
        
    # Aggregate Stats
    total_projects = len(projects)
    total_tasks = ScraperTask.query.join(Project).filter(Project.user_id == current_user.id).count()
    completed_tasks = ScraperTask.query.join(Project).filter(Project.user_id == current_user.id)\
        .filter(ScraperTask.status == 'COMPLETED').count()
    
    total_records = db.session.query(db.func.sum(ScraperTask.total_extracted))\
        .join(Project).filter(Project.user_id == current_user.id).scalar() or 0
        
    success_rate = round((completed_tasks / total_tasks * 100), 1) if total_tasks > 0 else 100.0
    
    # Fetch Audit Logs for activity logs
    activities = AuditLog.query.filter_by(user_id=current_user.id)\
        .order_by(AuditLog.created_at.desc()).limit(8).all()
        
    return render_template(
        'main/dashboard.html',
        projects=projects,
        recent_tasks=recent_tasks,
        total_projects=total_projects,
        total_tasks=total_tasks,
        success_rate=success_rate,
        total_records=total_records,
        activities=activities
    )


@main_bp.route('/saved-projects')
@login_required
def saved_projects():
    """Saved projects grid directory view."""
    projects = Project.query.filter_by(user_id=current_user.id).order_by(Project.created_at.desc()).all()
    return render_template('main/saved_projects.html', projects=projects)


@main_bp.route('/history')
@login_required
def history():
    """Detailed history list view of all executed scraper runs."""
    tasks = ScraperTask.query.join(Project).filter(Project.user_id == current_user.id)\
        .order_by(ScraperTask.id.desc()).all()
    return render_template('main/history.html', tasks=tasks)


@main_bp.route('/exports-center')
@login_required
def exports_center():
    """Center to review and download generated CSV, JSON, Excel, and PDF files."""
    exports = ExportRecord.query.join(Project).filter(Project.user_id == current_user.id)\
        .order_by(ExportRecord.created_at.desc()).all()
    return render_template('main/exports_center.html', exports=exports)


@main_bp.route('/analytics')
@login_required
def analytics():
    """Dedicated analytics dashboard displaying advanced chart visualizations."""
    projects = Project.query.filter_by(user_id=current_user.id).all()
    total_tasks = ScraperTask.query.join(Project).filter(Project.user_id == current_user.id).count()
    completed_tasks = ScraperTask.query.join(Project).filter(Project.user_id == current_user.id)\
        .filter(ScraperTask.status == 'COMPLETED').count()
        
    success_rate = round((completed_tasks / total_tasks * 100), 1) if total_tasks > 0 else 100.0
    
    total_records = db.session.query(db.func.sum(ScraperTask.total_extracted))\
        .join(Project).filter(Project.user_id == current_user.id).scalar() or 0
        
    return render_template(
        'main/analytics.html', 
        projects=projects,
        total_tasks=total_tasks, 
        success_rate=success_rate, 
        total_records=total_records
    )


@main_bp.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    """General application settings panel."""
    if request.method == 'POST':
        # Mock settings save logic
        flash("Application settings saved successfully.", "success")
        return redirect(url_for('main.settings'))
    return render_template('main/settings.html')


@main_bp.route('/about')
def about():
    """Information page explaining the WebScrape Pro platform."""
    return render_template('main/about.html')


@main_bp.route('/help-center')
def help_center():
    """Help center and FAQ hub."""
    return render_template('main/help.html')


@main_bp.route('/contact', methods=['GET', 'POST'])
def contact():
    """Contact form endpoint."""
    if request.method == 'POST':
        flash("Your message has been sent. Thank you!", "success")
        return redirect(url_for('main.contact'))
    return render_template('main/contact.html')
