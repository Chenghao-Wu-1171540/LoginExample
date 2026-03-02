# app/routes/auth.py

from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app
from flask_bcrypt import generate_password_hash, check_password_hash
from psycopg2.extras import RealDictCursor
import os
import uuid
from ..db import get_db
from ..utils.decorators import login_required
from ..utils.helpers import allowed_file

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """User login endpoint"""
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        conn = get_db()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            SELECT * FROM users 
            WHERE username = %s AND status = 'active'
        """, (username,))
        user = cur.fetchone()
        cur.close()

        if user and check_password_hash(user['password_hash'], password):
            session['user_id'] = user['user_id']
            session['role'] = user['role']
            session.permanent = True

            flash('Login successful!', 'success')

            # Redirect based on role
            if user['role'] == 'admin':
                return redirect(url_for('admin.manage_users'))
            elif user['role'] == 'event_leader':
                return redirect(url_for('leader.my_events'))
            else:
                return redirect(url_for('home'))
        else:
            flash('Invalid username/password or account is inactive', 'danger')

    return render_template('login.html')


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """Volunteer registration endpoint"""
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        full_name = request.form.get('full_name')
        email = request.form.get('email')
        home_address = request.form.get('home_address')
        contact_number = request.form.get('contact_number')
        interests = request.form.get('environmental_interests')

        if password != confirm_password:
            flash('Passwords do not match', 'danger')
            return redirect(url_for('auth.register'))

        conn = get_db()
        cur = conn.cursor(cursor_factory=RealDictCursor)

        # Check for duplicate username
        cur.execute("SELECT 1 FROM users WHERE username = %s", (username,))
        if cur.fetchone():
            flash('Username already taken', 'danger')
            cur.close()
            return redirect(url_for('auth.register'))

        # Check for duplicate email
        cur.execute("SELECT 1 FROM users WHERE email = %s", (email,))
        if cur.fetchone():
            flash('Email already registered', 'danger')
            cur.close()
            return redirect(url_for('auth.register'))

        # Handle profile image upload
        profile_image = 'default_profile.jpg'
        if 'profile_image' in request.files:
            file = request.files['profile_image']
            if file and allowed_file(file.filename):
                ext = file.filename.rsplit('.', 1)[1].lower()
                filename = f"{uuid.uuid4()}.{ext}"
                file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
                file.save(file_path)
                profile_image = filename

        # Create new user account
        password_hash = generate_password_hash(password).decode('utf-8')

        try:
            cur.execute("""
                INSERT INTO users (
                    username, password_hash, full_name, email, home_address,
                    contact_number, profile_image, environmental_interests, role
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'volunteer')
            """, (username, password_hash, full_name, email, home_address,
                  contact_number, profile_image, interests))
            conn.commit()
            flash('Registration successful! Please log in.', 'success')
            return redirect(url_for('auth.login'))
        except Exception as e:
            conn.rollback()
            flash(f'Registration failed: {str(e)}', 'danger')
        finally:
            cur.close()

    return render_template('register.html')


@auth_bp.route('/logout')
@login_required
def logout():
    """Log out the current user"""
    session.clear()
    flash('You have been logged out successfully', 'info')
    return redirect(url_for('auth.login'))