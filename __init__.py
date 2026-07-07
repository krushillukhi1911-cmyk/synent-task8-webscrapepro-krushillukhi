import os
from flask import Flask, render_template
from app.config import config_by_name
from app.extensions import db, bcrypt, login_manager

def create_app(config_name='default'):
    """Application factory for Flask app instantiation."""
    app = Flask(__name__)
    
    # Load configuration
    app.config.from_object(config_by_name[config_name])
    
    # Initialize Extensions
    db.init_app(app)
    bcrypt.init_app(app)
    login_manager.init_app(app)
    
    # Configure user loader
    from app.models import User, Role
    
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))
        
    # Register blueprints (Blueprints will be created in Part 2 and beyond)
    # We will import and register them here as we build them.
    from app.routes.auth import auth_bp
    from app.routes.main import main_bp
    from app.routes.scraper import scraper_bp
    from app.routes.api import api_bp
    from app.routes.exports import exports_bp
    
    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(scraper_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(exports_bp)
    
    # Context processor to make active user role check easier in templates
    @app.context_processor
    def inject_user_role():
        return dict(Role=Role)

    # Register custom error views page templates
    @app.errorhandler(404)
    def page_not_found(e):
        return render_template('errors/404.html'), 404

    @app.errorhandler(500)
    def internal_server_error(e):
        return render_template('errors/500.html'), 500

    # Initialize Database & seed default records
    with app.app_context():
        db.create_all()
        seed_database()
        
    return app


def seed_database():
    """Seeds default Roles and a Default Administrator if not present."""
    from app.models import Role, User
    
    # Seed Roles
    roles = {
        'Administrator': 'System Administrator with full access to manage all projects, scraping configurations, and users.',
        'Member': 'Standard user who can create projects, run scrapers, and export data.'
    }
    
    for r_name, r_desc in roles.items():
        role = Role.query.filter_by(name=r_name).first()
        if not role:
            role = Role(name=r_name, description=r_desc)
            db.session.add(role)
    db.session.commit()
    
    # Seed default administrator if no users exist
    admin_role = Role.query.filter_by(name='Administrator').first()
    if admin_role and not User.query.first():
        admin = User(
            username='admin',
            email='admin@webscrapepro.com',
            role_id=admin_role.id
        )
        admin.set_password('AdminPass123!')
        db.session.add(admin)
        db.session.commit()
        print("Database seeded: Default roles and 'admin' user created.")
