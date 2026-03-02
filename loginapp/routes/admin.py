# app/routes/admin.py

from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app
from psycopg2.extras import RealDictCursor
from datetime import date
from ..db import get_db
from ..utils.decorators import login_required, role_required
import os
import uuid

admin_bp = Blueprint('admin', __name__)


@admin_bp.route('/users')
@login_required
@role_required('admin')
def manage_users():
    """Manage all users - search and list view"""
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


@admin_bp.route('/toggle_user_status/<int:user_id>', methods=['GET'])
@login_required
@role_required('admin')
def toggle_user_status(user_id):
    """Toggle user status (active / inactive)"""
    if user_id == session['user_id']:
        flash('Cannot deactivate yourself', 'danger')
        return redirect(url_for('admin.manage_users'))

    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute("SELECT status FROM users WHERE user_id = %s", (user_id,))
    user = cur.fetchone()

    if not user:
        flash('User not found', 'danger')
        cur.close()
        return redirect(url_for('admin.manage_users'))

    new_status = 'inactive' if user['status'] == 'active' else 'active'

    cur.execute("""
        UPDATE users 
        SET status = %s 
        WHERE user_id = %s
    """, (new_status, user_id))

    conn.commit()
    cur.close()

    flash(f'User status updated to {new_status}', 'success')
    return redirect(url_for('admin.manage_users'))


@admin_bp.route('/events')
@login_required
@role_required('admin')
def manage_all_events():
    """Manage all events on the platform (admin overview)"""
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute("""
        SELECT e.*,
               u.full_name AS leader_name,
               (SELECT COUNT(*) FROM eventregistrations WHERE event_id = e.event_id) AS reg_count
        FROM events e
        JOIN users u ON e.event_leader_id = u.user_id
        ORDER BY e.event_date DESC
    """)
    events = cur.fetchall()
    cur.close()

    today = date.today()

    return render_template('admin_events.html',
                           events=events,
                           today=today)


@admin_bp.route('/reports')
@login_required
@role_required('admin')
def reports():
    """Platform-wide statistics and reports"""
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    # User statistics
    cur.execute("""
        SELECT 
            COUNT(*) AS total_users,
            COUNT(CASE WHEN role = 'volunteer' THEN 1 END) AS volunteer,
            COUNT(CASE WHEN role = 'event_leader' THEN 1 END) AS event_leader,
            COUNT(CASE WHEN role = 'admin' THEN 1 END) AS admin,
            COUNT(CASE WHEN status = 'active' THEN 1 END) AS active_users
        FROM users
    """)
    user_stats = cur.fetchone()

    # Event statistics
    cur.execute("""
        SELECT 
            COUNT(*) AS total_events,
            COUNT(CASE WHEN event_date >= CURRENT_DATE THEN 1 END) AS upcoming,
            COUNT(CASE WHEN event_date < CURRENT_DATE THEN 1 END) AS past
        FROM events
    """)
    event_stats = cur.fetchone()

    # Total registrations and feedback
    cur.execute("SELECT COUNT(*) AS total_registrations FROM eventregistrations")
    total_reg = cur.fetchone()['total_registrations']

    cur.execute("SELECT AVG(rating) AS avg_rating FROM feedback")
    avg_rating = cur.fetchone()['avg_rating'] or 0

    # Recent events with outcomes
    cur.execute("""
        SELECT e.event_name, e.event_date, e.location,
               COALESCE(o.num_attendees, 0) AS num_attendees,
               COALESCE(o.bags_collected, 0) AS bags_collected,
               (SELECT COUNT(*) FROM eventregistrations WHERE event_id = e.event_id) AS registrations
        FROM events e
        LEFT JOIN eventoutcomes o ON e.event_id = o.event_id
        ORDER BY e.event_date DESC
        LIMIT 5
    """)
    recent_events = cur.fetchall()

    cur.close()

    # Prepare stats for template
    stats = {
        'total_users': user_stats['total_users'],
        'users_by_role': {
            'volunteer': user_stats['volunteer'],
            'event_leader': user_stats['event_leader'],
            'admin': user_stats['admin'],
        },
        'active_users': user_stats['active_users'],
        'total_events': event_stats['total_events'],
        'upcoming_events': event_stats['upcoming'],
        'past_events': event_stats['past'],
        'total_registrations': total_reg,
        'avg_rating': round(avg_rating, 1) if avg_rating else 'N/A',
    }

    return render_template('admin_reports.html',
                           stats=stats,
                           recent_events=recent_events)
