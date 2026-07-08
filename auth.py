from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from app.extensions import db
from app.models import User, Role, AuditLog

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """Handles new user registration."""
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
        
    if request.method == 'POST':
        # Accept either JSON or Form data
        if request.is_json:
            data = request.get_json()
        else:
            data = request.form
            
        username = data.get('username')
        email = data.get('email')
        password = data.get('password')
        
        # Validation
        if not username or not email or not password:
            error_msg = "Username, email, and password are required."
            if request.is_json:
                return jsonify({"error": error_msg}), 400
            flash(error_msg, 'danger')
            return render_template('auth/register.html')
            
        # Check if username or email already exists
        if User.query.filter_by(username=username).first():
            error_msg = "Username already taken."
            if request.is_json:
                return jsonify({"error": error_msg}), 400
            flash(error_msg, 'danger')
            return render_template('auth/register.html')
            
        if User.query.filter_by(email=email).first():
            error_msg = "Email address already registered."
            if request.is_json:
                return jsonify({"error": error_msg}), 400
            flash(error_msg, 'danger')
            return render_template('auth/register.html')
            
        # Set user role to 'Member' by default
        member_role = Role.query.filter_by(name='Member').first()
        if not member_role:
            # Fallback if roles aren't seeded
            member_role = Role(name='Member', description='Standard user')
            db.session.add(member_role)
            db.session.commit()
            
        # Create user
        new_user = User(
            username=username,
            email=email,
            role_id=member_role.id
        )
        new_user.set_password(password)
        
        db.session.add(new_user)
        db.session.commit()
        
        # Log registration action
        log = AuditLog(
            user_id=new_user.id,
            action=f"User registration successful for {username}",
            ip_address=request.remote_addr
        )
        db.session.add(log)
        db.session.commit()
        
        success_msg = "Registration successful! Please log in."
        if request.is_json:
            return jsonify({"message": success_msg}), 201
            
        flash(success_msg, 'success')
        return redirect(url_for('auth.login'))
        
    return render_template('auth/register.html')


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Logs in an existing user."""
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
        
    if request.method == 'POST':
        if request.is_json:
            data = request.get_json()
        else:
            data = request.form
            
        username = data.get('username')
        password = data.get('password')
        remember = True if data.get('remember') in [True, 'on', 'true'] else False
        
        if not username or not password:
            error_msg = "Username and password are required."
            if request.is_json:
                return jsonify({"error": error_msg}), 400
            flash(error_msg, 'danger')
            return render_template('auth/login.html')
            
        user = User.query.filter_by(username=username).first()
        
        if user and user.check_password(password):
            if not user.is_active:
                error_msg = "Your account has been deactivated."
                if request.is_json:
                    return jsonify({"error": error_msg}), 403
                flash(error_msg, 'danger')
                return render_template('auth/login.html')
                
            login_user(user, remember=remember)
            
            # Log audit
            log = AuditLog(
                user_id=user.id,
                action="Login successful",
                ip_address=request.remote_addr
            )
            db.session.add(log)
            db.session.commit()
            
            # Redirect parameter support
            next_page = request.args.get('next')
            if request.is_json:
                return jsonify({
                    "message": "Login successful",
                    "user": {"username": user.username, "email": user.email, "role": user.role.name}
                }), 200
                
            return redirect(next_page or url_for('main.dashboard'))
            
        # Failed login audit
        if user:
            log = AuditLog(
                user_id=user.id,
                action="Failed login attempt: invalid password",
                ip_address=request.remote_addr
            )
            db.session.add(log)
            db.session.commit()
            
        error_msg = "Invalid username or password."
        if request.is_json:
            return jsonify({"error": error_msg}), 401
        flash(error_msg, 'danger')
        return render_template('auth/login.html')
        
    return render_template('auth/login.html')


@auth_bp.route('/logout')
@login_required
def logout():
    """Logs out the active user."""
    # Audit log before logout destroys context
    log = AuditLog(
        user_id=current_user.id,
        action="User logged out",
        ip_address=request.remote_addr
    )
    db.session.add(log)
    db.session.commit()
    
    logout_user()
    
    if request.args.get('format') == 'json':
        return jsonify({"message": "Logged out successfully"}), 200
        
    flash("You have been logged out.", 'info')
    return redirect(url_for('auth.login'))


@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    """ForgotPassword stub page."""
    if request.method == 'POST':
        if request.is_json:
            data = request.get_json()
        else:
            data = request.form
            
        email = data.get('email')
        # Simulate emailing reset link
        user = User.query.filter_by(email=email).first()
        if user:
            # Seed audit log
            log = AuditLog(
                user_id=user.id,
                action="Password reset link requested",
                ip_address=request.remote_addr
            )
            db.session.add(log)
            db.session.commit()
            
        msg = "If that email address is registered, a password reset link has been sent."
        if request.is_json:
            return jsonify({"message": msg}), 200
        flash(msg, 'info')
        return redirect(url_for('auth.login'))
        
    return render_template('auth/forgot_password.html')


@auth_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    """User profile management."""
    if request.method == 'POST':
        if request.is_json:
            data = request.get_json()
        else:
            data = request.form
            
        username = data.get('username')
        email = data.get('email')
        new_password = data.get('new_password')
        current_password = data.get('current_password')
        
        # Profile updates must verify current password
        if not current_user.check_password(current_password):
            error_msg = "Incorrect current password."
            if request.is_json:
                return jsonify({"error": error_msg}), 401
            flash(error_msg, 'danger')
            return redirect(url_for('auth.profile'))
            
        # Track changes
        changes = []
        if username and username != current_user.username:
            if User.query.filter_by(username=username).first():
                error_msg = "Username already taken."
                if request.is_json:
                    return jsonify({"error": error_msg}), 400
                flash(error_msg, 'danger')
                return redirect(url_for('auth.profile'))
            current_user.username = username
            changes.append("username")
            
        if email and email != current_user.email:
            if User.query.filter_by(email=email).first():
                error_msg = "Email already in use."
                if request.is_json:
                    return jsonify({"error": error_msg}), 400
                flash(error_msg, 'danger')
                return redirect(url_for('auth.profile'))
            current_user.email = email
            changes.append("email")
            
        if new_password:
            current_user.set_password(new_password)
            changes.append("password")
            
        if changes:
            db.session.commit()
            log = AuditLog(
                user_id=current_user.id,
                action=f"Profile updated: Changed {', '.join(changes)}",
                ip_address=request.remote_addr
            )
            db.session.add(log)
            db.session.commit()
            
            success_msg = "Profile updated successfully."
            if request.is_json:
                return jsonify({"message": success_msg}), 200
            flash(success_msg, 'success')
        else:
            msg = "No changes were made."
            if request.is_json:
                return jsonify({"message": msg}), 200
            flash(msg, 'info')
            
        return redirect(url_for('auth.profile'))
        
    return render_template('auth/profile.html')
