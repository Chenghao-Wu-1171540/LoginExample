"""
EcoCleanUp Hub - COMP639 S1 2026 Individual Assignment
Full Flask app with role-based access, PostgreSQL, bcrypt.
Author: Chenghao Wu (Student ID: 1171540)
"""

from flask import Flask, render_template, request, redirect, url_for, flash, session, send_from_directory
from flask_bcrypt import Bcrypt
from functools import wraps
from datetime import datetime, timedelta
import os
import uuid
import psycopg2
from psycopg2.extras import RealDictCursor

# Import the proper DB helpers
from loginapp.db import init_db, get_db

app = Flask(__name__)
app.secret_key = 'your-secret-key-change-this-in-production-2026'
app.config['UPLOAD_FOLDER'] = 'static/profile_images'
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif'}
app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024  # 2 MB

bcrypt = Bcrypt(app)
init_db(app)  # loads connect.py params into app.config

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in first', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


def role_required(*roles):
    def decorator(f):
        @wraps(f)
        @login_required
        def decorated_function(*args, **kwargs):
            if session.get('role') not in roles:
                flash('You do not have permission to access this page', 'danger')
                return redirect(url_for('home'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator


# ────────────────────────────────────────────────
# HOME
# ────────────────────────────────────────────────
@app.route('/')
def home():
    upcoming = []
    if 'user_id' in session and session.get('role') == 'volunteer':
        conn = get_db()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            SELECT e.event_id, e.event_name, e.event_date, e.start_time, e.location
            FROM events e
            JOIN eventregistrations er ON e.event_id = er.event_id
            WHERE er.volunteer_id = %s
              AND e.event_date >= CURRENT_DATE
            ORDER BY e.event_date, e.start_time
            LIMIT 3
        """, (session['user_id'],))
        upcoming = cur.fetchall()
        cur.close()

    return render_template('home.html', upcoming=upcoming)


# ────────────────────────────────────────────────
# LOGIN
# ────────────────────────────────────────────────
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        conn = get_db()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT * FROM users WHERE username = %s AND status = 'active'", (username,))
        user = cur.fetchone()
        cur.close()

        if user and bcrypt.check_password_hash(user['password_hash'], password):
            session['user_id'] = user['user_id']
            session['role'] = user['role']
            session['username'] = user['username']
            flash('Login successful!', 'success')
            return redirect(url_for('home'))
        else:
            flash('Invalid username or password', 'danger')

    return render_template('login.html')


# ────────────────────────────────────────────────
# LOGOUT
# ────────────────────────────────────────────────
@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out', 'info')
    return redirect(url_for('home'))


# ────────────────────────────────────────────────
# REGISTER (volunteer only)
# ────────────────────────────────────────────────
@app.route('/register', methods=['GET', 'POST'])
def register():
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
            return redirect(url_for('register'))

        if len(password) < 8 or not any(c.isupper() for c in password) or \
           not any(c.islower() for c in password) or not any(c.isdigit() for c in password) or \
           not any(c in "!@#$%^&*()_+-=[]{}|;:,.<>/? " for c in password):
            flash('Password must be at least 8 characters with upper, lower, digit and special character', 'danger')
            return redirect(url_for('register'))

        password_hash = bcrypt.generate_password_hash(password).decode('utf-8')

        profile_image = 'default_profile.jpg'
        if 'profile_image' in request.files:
            file = request.files['profile_image']
            if file and allowed_file(file.filename):
                ext = file.filename.rsplit('.', 1)[1].lower()
                filename = f"{uuid.uuid4()}.{ext}"
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                profile_image = filename

        conn = get_db()
        cur = conn.cursor()
        try:
            cur.execute("""
                INSERT INTO users (username, password_hash, full_name, email, home_address,
                                   contact_number, environmental_interests, profile_image, role)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'volunteer')
            """, (username, password_hash, full_name, email, home_address,
                  contact_number, interests, profile_image))
            conn.commit()
            flash('Registration successful! Please log in', 'success')
            return redirect(url_for('login'))
        except psycopg2.IntegrityError:
            conn.rollback()
            flash('Username or email already taken', 'danger')
        finally:
            cur.close()

    return render_template('register.html')


# ────────────────────────────────────────────────
# PROFILE
# ────────────────────────────────────────────────
@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT * FROM users WHERE user_id = %s", (session['user_id'],))
    user = cur.fetchone()

    if request.method == 'POST':
        full_name = request.form.get('full_name')
        email = request.form.get('email')
        home_address = request.form.get('home_address')
        contact_number = request.form.get('contact_number')
        interests = request.form.get('environmental_interests')

        profile_image = user['profile_image']
        if 'profile_image' in request.files:
            file = request.files['profile_image']
            if file and allowed_file(file.filename):
                ext = file.filename.rsplit('.', 1)[1].lower()
                filename = f"{uuid.uuid4()}.{ext}"
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                profile_image = filename

        try:
            cur.execute("""
                UPDATE users
                SET full_name = %s, email = %s, home_address = %s,
                    contact_number = %s, environmental_interests = %s,
                    profile_image = %s
                WHERE user_id = %s
            """, (full_name, email, home_address, contact_number, interests, profile_image, session['user_id']))
            conn.commit()
            flash('Profile updated successfully', 'success')
        except psycopg2.IntegrityError:
            conn.rollback()
            flash('Email already in use', 'danger')

    cur.close()
    return render_template('profile.html', user=user)


# ────────────────────────────────────────────────
# CHANGE PASSWORD
# ────────────────────────────────────────────────
@app.route('/change_password', methods=['GET', 'POST'])
@login_required
def change_password():
    if request.method == 'POST':
        current_pw = request.form.get('current_password')
        new_pw = request.form.get('new_password')
        confirm_pw = request.form.get('confirm_password')

        conn = get_db()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT password_hash FROM users WHERE user_id = %s", (session['user_id'],))
        user = cur.fetchone()

        if not bcrypt.check_password_hash(user['password_hash'], current_pw):
            flash('Current password is incorrect', 'danger')
        elif new_pw != confirm_pw:
            flash('New passwords do not match', 'danger')
        elif len(new_pw) < 8 or not any(c.isupper() for c in new_pw) or \
             not any(c.islower() for c in new_pw) or not any(c.isdigit() for c in new_pw) or \
             not any(c in "!@#$%^&*()_+-=[]{}|;:,.<>/? " for c in new_pw):
            flash('New password must be at least 8 characters with upper, lower, digit and special character', 'danger')
        else:
            new_hash = bcrypt.generate_password_hash(new_pw).decode('utf-8')
            cur.execute("UPDATE users SET password_hash = %s WHERE user_id = %s", (new_hash, session['user_id']))
            conn.commit()
            flash('Password changed successfully', 'success')

        cur.close()

    return render_template('change_password.html')


# ────────────────────────────────────────────────
# EVENTS LIST (for volunteers)
# ────────────────────────────────────────────────
@app.route('/events')
@login_required
def events():
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    # Basic filter support
    location_filter = request.args.get('location', '').strip()
    date_filter = request.args.get('date', '')

    query = """
        SELECT e.*, u.full_name AS leader_name
        FROM events e
        JOIN users u ON e.event_leader_id = u.user_id
        WHERE e.event_date >= CURRENT_DATE
    """
    params = []

    if location_filter:
        query += " AND e.location ILIKE %s"
        params.append(f"%{location_filter}%")
    if date_filter:
        query += " AND e.event_date = %s"
        params.append(date_filter)

    query += " ORDER BY e.event_date, e.start_time"

    cur.execute(query, params)
    events_list = cur.fetchall()

    registered_ids = set()
    if session.get('role') == 'volunteer':
        cur.execute("SELECT event_id FROM eventregistrations WHERE volunteer_id = %s", (session['user_id'],))
        registered_ids = {row['event_id'] for row in cur.fetchall()}

    # Add 'registered' flag to each event dict
    for event in events_list:
        event['registered'] = event['event_id'] in registered_ids

    cur.close()

    return render_template('events.html', events=events_list,
                           search_location=location_filter, search_date=date_filter)


# ────────────────────────────────────────────────
# REGISTER FOR EVENT (volunteer only)
# ────────────────────────────────────────────────
@app.route('/events/register/<int:event_id>', methods=['POST'])
@login_required
@role_required('volunteer')
def register_event(event_id):
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    # Get event details
    cur.execute("SELECT event_date, start_time, duration FROM events WHERE event_id = %s", (event_id,))
    event = cur.fetchone()
    if not event:
        flash('Event not found', 'danger')
        cur.close()
        return redirect(url_for('events'))

    # Check for time conflict
    conflict_query = """
        SELECT e.event_id
        FROM events e
        JOIN eventregistrations er ON e.event_id = er.event_id
        WHERE er.volunteer_id = %s
          AND e.event_date = %s
          AND e.start_time < %s + interval '1 minute' * %s
          AND e.start_time + interval '1 minute' * e.duration > %s
    """
    cur.execute(conflict_query, (
        session['user_id'],
        event['event_date'],
        event['start_time'],
        event['duration'],
        event['start_time']
    ))
    if cur.fetchone():
        flash('Time conflict: You are already registered for another event at the same time', 'danger')
        cur.close()
        return redirect(url_for('events'))

    try:
        cur.execute("""
            INSERT INTO eventregistrations (event_id, volunteer_id)
            VALUES (%s, %s)
        """, (event_id, session['user_id']))
        conn.commit()
        flash('Successfully registered for the event!', 'success')
    except psycopg2.IntegrityError:
        conn.rollback()
        flash('You are already registered for this event', 'info')

    cur.close()
    return redirect(url_for('events'))


# ────────────────────────────────────────────────
# MY PARTICIPATION (volunteer)
# ────────────────────────────────────────────────
@app.route('/my_participation')
@login_required
@role_required('volunteer')
def my_participation():
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("""
        SELECT 
            e.event_id, e.event_name, e.location, e.event_date, e.start_time, e.duration,
            er.registered_at, er.attendance,
            f.rating, f.comments, f.submitted_at AS feedback_submitted
        FROM eventregistrations er
        JOIN events e ON er.event_id = e.event_id
        LEFT JOIN feedback f ON er.event_id = f.event_id AND er.volunteer_id = f.volunteer_id
        WHERE er.volunteer_id = %s
        ORDER BY e.event_date DESC
    """, (session['user_id'],))
    registrations = cur.fetchall()
    cur.close()

    today = datetime.now().date()

    return render_template('my_participation.html', registrations=registrations, today=today)


# ────────────────────────────────────────────────
# SUBMIT FEEDBACK
# ────────────────────────────────────────────────
@app.route('/feedback/submit/<int:event_id>', methods=['GET', 'POST'])
@login_required
@role_required('volunteer')
def submit_feedback(event_id):
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    # Check if already submitted
    cur.execute("SELECT * FROM feedback WHERE event_id = %s AND volunteer_id = %s", (event_id, session['user_id']))
    if cur.fetchone():
        flash('You have already submitted feedback for this event', 'info')
        cur.close()
        return redirect(url_for('my_participation'))

    if request.method == 'POST':
        rating = request.form.get('rating')
        comments = request.form.get('comments')

        try:
            cur.execute("""
                INSERT INTO feedback (event_id, volunteer_id, rating, comments)
                VALUES (%s, %s, %s, %s)
            """, (event_id, session['user_id'], int(rating), comments))
            conn.commit()
            flash('Feedback submitted successfully', 'success')
        except Exception as e:
            conn.rollback()
            flash('Error submitting feedback', 'danger')

        cur.close()
        return redirect(url_for('my_participation'))

    # GET: show form
    cur.execute("SELECT event_name FROM events WHERE event_id = %s", (event_id,))
    event = cur.fetchone()
    cur.close()

    return render_template('submit_feedback.html', event=event, event_id=event_id)


# ────────────────────────────────────────────────
# LEADER - MY EVENTS
# ────────────────────────────────────────────────
@app.route('/leader/my_events')
@login_required
@role_required('event_leader')
def leader_my_events():
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("""
        SELECT e.*, 
               (SELECT COUNT(*) FROM eventregistrations WHERE event_id = e.event_id) AS reg_count
        FROM events e
        WHERE e.event_leader_id = %s
        ORDER BY e.event_date DESC
    """, (session['user_id'],))
    events = cur.fetchall()
    cur.close()

    today = datetime.now().date()

    return render_template('leader_my_events.html', events=events, today=today)


# ────────────────────────────────────────────────
# LEADER - CREATE EVENT
# ────────────────────────────────────────────────
@app.route('/leader/create_event', methods=['GET', 'POST'])
@login_required
@role_required('event_leader')
def create_event():
    if request.method == 'POST':
        event_name = request.form.get('event_name')
        location = request.form.get('location')
        event_date = request.form.get('event_date')
        start_time = request.form.get('start_time')
        duration = request.form.get('duration')
        description = request.form.get('description')
        supplies = request.form.get('supplies')
        safety = request.form.get('safety_instructions')

        conn = get_db()
        cur = conn.cursor()
        try:
            cur.execute("""
                INSERT INTO events (event_name, location, event_date, start_time, duration,
                                    description, supplies, safety_instructions, event_leader_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (event_name, location, event_date, start_time, int(duration),
                  description, supplies, safety, session['user_id']))
            conn.commit()
            flash('Event created successfully', 'success')
            return redirect(url_for('leader_my_events'))
        except Exception as e:
            conn.rollback()
            flash('Error creating event', 'danger')
        finally:
            cur.close()

    return render_template('create_event.html')


# ────────────────────────────────────────────────
# SERVE UPLOADED PROFILE IMAGES
# ────────────────────────────────────────────────
@app.route('/profile_images/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


# ────────────────────────────────────────────────
# ADMIN - MANAGE USERS
# ────────────────────────────────────────────────
@app.route('/admin/users')
@login_required
@role_required('admin')
def admin_users():
    search = request.args.get('search', '').strip()

    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    query = """
        SELECT user_id, username, full_name, email, role, status, created_at
        FROM users
        WHERE 1=1
    """
    params = []

    if search:
        query += """
            AND (
                username ILIKE %s OR
                full_name ILIKE %s OR
                email ILIKE %s
            )
        """
        like_pattern = f"%{search}%"
        params.extend([like_pattern, like_pattern, like_pattern])

    query += " ORDER BY created_at DESC"

    cur.execute(query, params)
    users_list = cur.fetchall()
    cur.close()

    return render_template('admin_users.html', users=users_list, search=search)


# ────────────────────────────────────────────────
# ADMIN - TOGGLE USER STATUS (activate / deactivate)
# ────────────────────────────────────────────────
@app.route('/admin/users/toggle/<int:user_id>')
@login_required
@role_required('admin')
def toggle_user(user_id):
    if user_id == session['user_id']:
        flash('You cannot change your own status', 'warning')
        return redirect(url_for('admin_users'))

    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute("SELECT status FROM users WHERE user_id = %s", (user_id,))
    user = cur.fetchone()

    if not user:
        flash('User not found', 'danger')
        cur.close()
        return redirect(url_for('admin_users'))

    new_status = 'inactive' if user['status'] == 'active' else 'active'

    try:
        cur.execute("UPDATE users SET status = %s WHERE user_id = %s", (new_status, user_id))
        conn.commit()
        flash(f"User status changed to {new_status}", 'success')
    except Exception as e:
        conn.rollback()
        flash('Error updating user status', 'danger')

    cur.close()
    return redirect(url_for('admin_users'))


# ────────────────────────────────────────────────
# ADMIN - PLATFORM REPORTS
# ────────────────────────────────────────────────
@app.route('/admin/reports')
@login_required
@role_required('admin')
def admin_reports():
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    stats = {}

    # 1. 用户统计
    cur.execute("SELECT role, COUNT(*) AS count FROM users GROUP BY role")
    stats['users_by_role'] = {row['role']: row['count'] for row in cur.fetchall()}

    cur.execute("SELECT status, COUNT(*) AS count FROM users GROUP BY status")
    stats['users_by_status'] = {row['status']: row['count'] for row in cur.fetchall()}

    # 2. 活动统计
    cur.execute("SELECT COUNT(*) AS total FROM events")
    stats['total_events'] = cur.fetchone()['total']

    cur.execute("SELECT COUNT(*) AS upcoming FROM events WHERE event_date >= CURRENT_DATE")
    stats['upcoming_events'] = cur.fetchone()['upcoming']

    cur.execute("SELECT COUNT(*) AS past FROM events WHERE event_date < CURRENT_DATE")
    stats['past_events'] = cur.fetchone()['past']

    # 3. 报名统计
    cur.execute("SELECT COUNT(*) AS total_registrations FROM eventregistrations")
    stats['total_registrations'] = cur.fetchone()['total_registrations']

    # 4. 成果统计（所有活动总和）
    cur.execute("""
        SELECT 
            COALESCE(SUM(num_attendees), 0) AS total_attendees,
            COALESCE(SUM(bags_collected), 0) AS total_bags,
            COALESCE(SUM(recyclables_sorted), 0) AS total_recyclables
        FROM eventoutcomes
    """)
    outcomes = cur.fetchone()
    stats['total_attendees'] = outcomes['total_attendees']
    stats['total_bags'] = outcomes['total_bags']
    stats['total_recyclables'] = outcomes['total_recyclables']

    # 5. 平均评分（所有反馈）
    cur.execute("SELECT AVG(rating) AS avg_rating FROM feedback")
    avg = cur.fetchone()['avg_rating']
    stats['average_rating'] = round(avg, 2) if avg is not None else "N/A"

    # 6. 最近 5 个活动（按日期降序）
    cur.execute("""
        SELECT e.event_id, e.event_name, e.event_date, e.location,
               COUNT(er.volunteer_id) AS registrations,
               eo.num_attendees, eo.bags_collected
        FROM events e
        LEFT JOIN eventregistrations er ON e.event_id = er.event_id
        LEFT JOIN eventoutcomes eo ON e.event_id = eo.event_id
        GROUP BY e.event_id, eo.outcome_id
        ORDER BY e.event_date DESC
        LIMIT 5
    """)
    recent_events = cur.fetchall()

    cur.close()

    return render_template('admin_reports.html', stats=stats, recent_events=recent_events)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)