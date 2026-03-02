# loginapp/routes/events.py

from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from psycopg2.extras import RealDictCursor
from ..db import get_db
from ..utils.decorators import login_required, role_required

events_bp = Blueprint('events', __name__)


@events_bp.route('/events')
@login_required
def list_events():
    """Display list of upcoming events with optional filters"""
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    location_filter = request.args.get('location', '').strip()
    date_filter = request.args.get('date', '')

    query = """
        SELECT e.*, u.full_name AS leader_name,
               CASE WHEN er.volunteer_id IS NOT NULL THEN TRUE ELSE FALSE END AS registered
        FROM events e
        JOIN users u ON e.event_leader_id = u.user_id
        LEFT JOIN eventregistrations er 
               ON e.event_id = er.event_id AND er.volunteer_id = %s
        WHERE e.event_date >= CURRENT_DATE
    """
    params = [session['user_id']]

    if location_filter:
        query += " AND e.location ILIKE %s"
        params.append(f"%{location_filter}%")

    if date_filter:
        query += " AND e.event_date = %s"
        params.append(date_filter)

    query += " ORDER BY e.event_date, e.start_time"

    cur.execute(query, params)
    events = cur.fetchall()
    cur.close()

    return render_template('events.html',
                           events=events,
                           search_location=location_filter,
                           search_date=date_filter)


@events_bp.route('/register/<int:event_id>', methods=['POST'])
@login_required
@role_required('volunteer')
def register_event(event_id):
    """Register current volunteer for an event (with time conflict check)"""
    # Re-confirm role (extra safety)
    if session.get('role') != 'volunteer':
        flash('Only volunteers can register for events', 'danger')
        return redirect(url_for('events.list_events'))

    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    try:
        # Fetch event details
        cur.execute("""
            SELECT event_id, event_date, start_time, duration, event_name
            FROM events 
            WHERE event_id = %s AND event_date >= CURRENT_DATE
        """, (event_id,))
        event = cur.fetchone()

        if not event:
            flash('Event not found or has already passed', 'danger')
            return redirect(url_for('events.list_events'))

        # Check for time conflict
        conflict_query = """
            SELECT 1
            FROM events e
            JOIN eventregistrations er ON e.event_id = er.event_id
            WHERE er.volunteer_id = %s
              AND e.event_date = %s
              AND e.start_time < (%s + interval '1 minute' * %s)
              AND (e.start_time + interval '1 minute' * e.duration) > %s
            LIMIT 1
        """
        cur.execute(conflict_query, (
            session['user_id'],
            event['event_date'],
            event['start_time'],
            event['duration'],
            event['start_time']
        ))

        if cur.fetchone():
            flash('Time conflict: You are already registered for another event at the same time.', 'danger')
            return redirect(url_for('events.list_events'))

        # Attempt to register
        cur.execute("""
            INSERT INTO eventregistrations (event_id, volunteer_id)
            VALUES (%s, %s)
            ON CONFLICT DO NOTHING
        """, (event_id, session['user_id']))

        conn.commit()

        if cur.rowcount > 0:
            flash(f'Successfully registered for "{event["event_name"]}"!', 'success')
        else:
            flash('You are already registered for this event.', 'info')

    except Exception as e:
        conn.rollback()
        flash('Registration failed. Please try again later.', 'danger')
        print(f"Registration error for event {event_id}: {e}")

    finally:
        cur.close()

    return redirect(url_for('events.list_events'))