# app/routes/user.py
from datetime import date

from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app
from flask_bcrypt import check_password_hash, generate_password_hash
import os
import uuid
from psycopg2.extras import RealDictCursor
from ..db import get_db
from ..utils.decorators import login_required
from ..utils.helpers import allowed_file

user_bp = Blueprint('user', __name__)


@user_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    """View and update user profile"""
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

        # Handle profile image upload
        profile_image = user['profile_image']
        if 'profile_image' in request.files:
            file = request.files['profile_image']
            if file and allowed_file(file.filename):
                ext = file.filename.rsplit('.', 1)[1].lower()
                filename = f"{uuid.uuid4()}.{ext}"
                file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
                file.save(file_path)
                profile_image = filename

        try:
            cur.execute("""
                UPDATE users 
                SET full_name = %s, email = %s, home_address = %s,
                    contact_number = %s, environmental_interests = %s,
                    profile_image = %s
                WHERE user_id = %s
            """, (full_name, email, home_address, contact_number, interests,
                  profile_image, session['user_id']))
            conn.commit()
            flash('Profile updated successfully', 'success')
            return redirect(url_for('user.profile'))
        except Exception as e:
            conn.rollback()
            flash(f'Update failed: {str(e)}', 'danger')

    cur.close()
    return render_template('profile.html', user=user)


@user_bp.route('/change_password', methods=['GET', 'POST'])
@login_required
def change_password():
    """Change user's password"""
    if request.method == 'POST':
        current_pw = request.form.get('current_password')
        new_pw = request.form.get('new_password')
        confirm_pw = request.form.get('confirm_password')

        conn = get_db()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT password_hash FROM users WHERE user_id = %s", (session['user_id'],))
        user = cur.fetchone()

        if not check_password_hash(user['password_hash'], current_pw):
            flash('Current password is incorrect', 'danger')
        elif new_pw != confirm_pw:
            flash('New passwords do not match', 'danger')
        elif len(new_pw) < 8 or not any(c.isupper() for c in new_pw) or \
             not any(c.islower() for c in new_pw) or not any(c.isdigit() for c in new_pw) or \
             not any(c in "!@#$%^&*()_+-=[]{}|;:,.<>/? " for c in new_pw):
            flash('New password must be at least 8 characters with upper, lower, digit and special character', 'danger')
        else:
            new_hash = generate_password_hash(new_pw).decode('utf-8')
            cur.execute("UPDATE users SET password_hash = %s WHERE user_id = %s",
                        (new_hash, session['user_id']))
            conn.commit()
            flash('Password changed successfully', 'success')

        cur.close()

    return render_template('change_password.html')


@user_bp.route('/my_participation')
@login_required
def my_participation():
    """Show user's event participation history"""
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute("""
        SELECT e.event_id, e.event_name, e.location, e.event_date, e.start_time,
               er.attendance, f.rating, f.comments,
               CASE WHEN f.feedback_id IS NOT NULL THEN TRUE ELSE FALSE END AS feedback_submitted
        FROM eventregistrations er
        JOIN events e ON er.event_id = e.event_id
        LEFT JOIN feedback f ON e.event_id = f.event_id AND er.volunteer_id = f.volunteer_id
        WHERE er.volunteer_id = %s
        ORDER BY e.event_date DESC
    """, (session['user_id'],))
    registrations = cur.fetchall()
    cur.close()

    today = date.today()
    return render_template('my_participation.html', registrations=registrations, today=today)


@user_bp.route('/submit_feedback/<int:event_id>', methods=['GET', 'POST'])
@login_required
def submit_feedback(event_id):
    """Submit feedback for an attended event"""
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    # Check if already submitted
    cur.execute("SELECT * FROM feedback WHERE event_id = %s AND volunteer_id = %s",
                (event_id, session['user_id']))
    if cur.fetchone():
        flash('You have already submitted feedback for this event', 'info')
        cur.close()
        return redirect(url_for('user.my_participation'))

    # Get event info
    cur.execute("SELECT event_name, event_date FROM events WHERE event_id = %s", (event_id,))
    event = cur.fetchone()

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
        except Exception:
            conn.rollback()
            flash('Error submitting feedback', 'danger')

        cur.close()
        return redirect(url_for('user.my_participation'))

    cur.close()
    return render_template('submit_feedback.html', event=event, event_id=event_id)