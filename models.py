from datetime import datetime
from flask_login import UserMixin
from app.extensions import db, bcrypt

class Role(db.Model):
    """Role model for Role-Based Access Control (RBAC)."""
    __tablename__ = 'roles'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    description = db.Column(db.String(255), nullable=True)
    
    # Relationships
    users = db.relationship('User', backref='role', lazy=True)
    
    def __repr__(self):
        return f"<Role {self.name}>"


class User(db.Model, UserMixin):
    """User account model."""
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    role_id = db.Column(db.Integer, db.ForeignKey('roles.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    
    # Relationships
    projects = db.relationship('Project', backref='user', lazy=True, cascade='all, delete-orphan')
    audit_logs = db.relationship('AuditLog', backref='user', lazy=True, cascade='all, delete-orphan')

    def set_password(self, password):
        """Hashes password and saves to database field."""
        self.password_hash = bcrypt.generate_password_hash(password).decode('utf-8')

    def check_password(self, password):
        """Verifies given password matches the hashed one."""
        return bcrypt.check_password_hash(self.password_hash, password)

    def is_admin(self):
        """Check if user has Administrator role."""
        return self.role.name == 'Administrator'

    def __repr__(self):
        return f"<User {self.username}>"


class Project(db.Model):
    """Scraping project container (holds multiple tasks and results)."""
    __tablename__ = 'projects'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    tasks = db.relationship('ScraperTask', backref='project', lazy=True, cascade='all, delete-orphan')
    data_records = db.relationship('DataRecord', backref='project', lazy=True, cascade='all, delete-orphan')
    export_records = db.relationship('ExportRecord', backref='project', lazy=True, cascade='all, delete-orphan')

    def __repr__(self):
        return f"<Project {self.name}>"


class ScraperTask(db.Model):
    """Represents a single execution run of the scraping engine."""
    __tablename__ = 'scraper_tasks'
    
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=False)
    url = db.Column(db.String(2083), nullable=False)
    status = db.Column(db.String(20), default='PENDING')  # PENDING, RUNNING, COMPLETED, FAILED, PAUSED, CANCELLED
    
    # Scraper config fields serialized as JSON (depth, dynamic rendering, selector list, headers, limit)
    configuration = db.Column(db.JSON, nullable=False)
    
    started_at = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    
    total_extracted = db.Column(db.Integer, default=0)
    error_message = db.Column(db.Text, nullable=True)
    log_file_path = db.Column(db.String(512), nullable=True)
    
    # Relationships
    data_records = db.relationship('DataRecord', backref='task', lazy=True, cascade='all, delete-orphan')
    export_records = db.relationship('ExportRecord', backref='task', lazy=True, cascade='all, delete-orphan')

    def __repr__(self):
        return f"<ScraperTask {self.id} Status: {self.status}>"


class DataRecord(db.Model):
    """Stores a single item extracted by the scraper (e.g., product, article, table row)."""
    __tablename__ = 'data_records'
    
    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, db.ForeignKey('scraper_tasks.id'), nullable=False)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=False)
    url = db.Column(db.String(2083), nullable=False)
    
    # Store dynamic fields as a JSON dictionary
    data_content = db.Column(db.JSON, nullable=False)
    
    scraped_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<DataRecord {self.id} for Task {self.task_id}>"


class ExportRecord(db.Model):
    """Metadata tracking generated export files."""
    __tablename__ = 'export_records'
    
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=False)
    task_id = db.Column(db.Integer, db.ForeignKey('scraper_tasks.id'), nullable=True)
    
    file_name = db.Column(db.String(255), nullable=False)
    file_path = db.Column(db.String(512), nullable=False)
    file_format = db.Column(db.String(10), nullable=False)  # CSV, JSON, EXCEL, PDF, ZIP
    file_size = db.Column(db.Integer, nullable=False)  # in bytes
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<ExportRecord {self.file_name}>"


class AuditLog(db.Model):
    """System log monitoring user activities."""
    __tablename__ = 'audit_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    action = db.Column(db.String(255), nullable=False)
    ip_address = db.Column(db.String(45), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<AuditLog User {self.user_id} - {self.action}>"
