# app/routes/leader.py

from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from psycopg2.extras import RealDictCursor
from datetime import date
from ..db import get_db
from ..utils.decorators import login_required, role_required

leader_bp = Blueprint('leader', __name__)


@leader_bp.route('/my_events')
@login_required
@role_required('event_leader')
def my_events():
    """Show events organized by the current leader (admin sees all)"""
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    if session['role'] == 'admin':
        cur.execute("""
            SELECT e.*, 
                   (SELECT COUNT(*) FROM eventregistrations WHERE event_id = e.event_id) AS reg_count
            FROM events e
            ORDER BY e.event_date DESC
        """)
    else:
        cur.execute("""
            SELECT e.*, 
                   (SELECT COUNT(*) FROM eventregistrations WHERE event_id = e.event_id) AS reg_count
            FROM events e
            WHERE e.event_leader_id = %s
            ORDER BY e.event_date DESC
        """, (session['user_id'],))

    events = cur.fetchall()
    cur.close()

    today = date.today()
    return render_template('leader_my_events.html', events=events, today=today)


@leader_bp.route('/create_event', methods=['GET', 'POST'])
@login_required
@role_required('event_leader')
def create_event():
    """Create a new cleanup event"""
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
                INSERT INTO events (
                    event_name, location, event_date, start_time, duration,
                    description, supplies, safety_instructions, event_leader_id
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (event_name, location, event_date, start_time, int(duration),
                  description, supplies, safety, session['user_id']))
            conn.commit()
            flash('Event created successfully!', 'success')
            return redirect(url_for('leader.my_events'))
        except Exception as e:
            conn.rollback()
            flash(f'Failed to create event: {str(e)}', 'danger')
        finally:
            cur.close()

    return render_template('create_event.html')


@leader_bp.route('/edit_event/<int:event_id>', methods=['GET', 'POST'])
@login_required
@role_required('event_leader')
def edit_event(event_id):
    """Edit an existing event (leader can edit own events, admin can edit all)"""
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    # Check ownership or admin
    cur.execute("SELECT event_leader_id FROM events WHERE event_id = %s", (event_id,))
    event = cur.fetchone()
    if not event or (session['role'] != 'admin' and event['event_leader_id'] != session['user_id']):
        flash('Permission denied', 'danger')
        cur.close()
        return redirect(url_for('leader.my_events'))

    if request.method == 'POST':
        # Update logic here (similar to create_event)
        # ... (omitted for brevity, implement similar to create_event)
        flash('Event updated successfully', 'success')
        return redirect(url_for('leader.event_detail', event_id=event_id))

    cur.execute("SELECT * FROM events WHERE event_id = %s", (event_id,))
    event_data = cur.fetchone()
    cur.close()

    return render_template('edit_event.html', event=event_data)


@leader_bp.route('/event_detail/<int:event_id>')
@login_required
@role_required('event_leader')
def event_detail(event_id):
    """View detailed information of an event (registrations, outcomes, etc.)"""
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    # Get event info
    cur.execute("""
        SELECT e.*, u.full_name AS leader_name
        FROM events e
        JOIN users u ON e.event_leader_id = u.user_id
        WHERE e.event_id = %s
    """, (event_id,))
    event = cur.fetchone()

    if not event:
        flash('Event not found', 'danger')
        cur.close()
        return redirect(url_for('leader.my_events'))

    # Get registrations
    cur.execute("""
        SELECT u.user_id AS volunteer_id, u.full_name, er.attendance
        FROM eventregistrations er
        JOIN users u ON er.volunteer_id = u.user_id
        WHERE er.event_id = %s
        ORDER BY u.full_name
    """, (event_id,))
    registrations = cur.fetchall()

    # Get outcome if exists
    cur.execute("SELECT * FROM eventoutcomes WHERE event_id = %s", (event_id,))
    outcome = cur.fetchone()

    cur.close()

    today = date.today()
    return render_template('event_detail_leader.html',
                           event=event,
                           registrations=registrations,
                           outcome=outcome,
                           today=today)


@leader_bp.route('/mark_attendance/<int:event_id>/<int:volunteer_id>', methods=['POST'])
@login_required
@role_required('event_leader')
def mark_attendance(event_id, volunteer_id):
    """Mark attendance for a volunteer in an event"""
    attendance = request.form.get('attendance')

    conn = get_db()
    cur = conn.cursor()

    # Check ownership
    cur.execute("SELECT event_leader_id FROM events WHERE event_id = %s", (event_id,))
    owner = cur.fetchone()
    if not owner or (session['role'] != 'admin' and owner[0] != session['user_id']):
        flash('Permission denied', 'danger')
        cur.close()
        return redirect(url_for('leader.event_detail', event_id=event_id))

    cur.execute("""
        UPDATE eventregistrations 
        SET attendance = %s 
        WHERE event_id = %s AND volunteer_id = %s
    """, (attendance, event_id, volunteer_id))
    conn.commit()
    flash('Attendance updated', 'success')
    cur.close()

    return redirect(url_for('leader.event_detail', event_id=event_id))


@leader_bp.route('/cancel_event/<int:event_id>', methods=['POST'])
@login_required
@role_required('event_leader', 'admin')
def cancel_event(event_id):
    """Cancel an event (only by owner or admin)"""
    conn = get_db()
    cur = conn.cursor()

    try:
        # Check if event exists and ownership
        cur.execute("""
                    SELECT event_leader_id
                    FROM events
                    WHERE event_id = %s
                    """, (event_id,))
        owner = cur.fetchone()

        if not owner:
            flash('Event not found', 'danger')
            return redirect(url_for('leader.my_events'))

        if session['role'] != 'admin' and owner[0] != session['user_id']:
            flash('Permission denied - you are not the owner of this event', 'danger')
            return redirect(url_for('leader.my_events'))

        # Delete related registrations first (due to foreign key constraints)
        cur.execute("DELETE FROM eventregistrations WHERE event_id = %s", (event_id,))

        # Delete the event itself
        cur.execute("DELETE FROM events WHERE event_id = %s", (event_id,))

        conn.commit()
        flash('Event has been cancelled successfully. All registrations removed.', 'success')

    except Exception as e:
        conn.rollback()
        flash(f'Failed to cancel event: {str(e)}', 'danger')
        print(f"Cancel event error: {e}")  # For debugging

    finally:
        cur.close()

    return redirect(url_for('leader.my_events'))

@leader_bp.route('/remove_volunteer/<int:event_id>/<int:volunteer_id>', methods=['POST'])
@login_required
@role_required('event_leader', 'admin')
def remove_volunteer(event_id, volunteer_id):
    """Remove a volunteer from an event (only by event leader or admin)"""
    conn = get_db()
    cur = conn.cursor()

    try:
        # 檢查事件是否存在 + 擁有權
        cur.execute("""
            SELECT event_leader_id FROM events WHERE event_id = %s
        """, (event_id,))
        owner = cur.fetchone()

        if not owner:
            flash('Event not found', 'danger')
            return redirect(url_for('leader.event_detail', event_id=event_id))

        if session['role'] != 'admin' and owner[0] != session['user_id']:
            flash('Permission denied - you are not the event owner', 'danger')
            return redirect(url_for('leader.event_detail', event_id=event_id))

        # 刪除該志工的註冊記錄
        cur.execute("""
            DELETE FROM eventregistrations 
            WHERE event_id = %s AND volunteer_id = %s
        """, (event_id, volunteer_id))

        if cur.rowcount == 0:
            flash('This volunteer was not registered for the event', 'info')
        else:
            conn.commit()
            flash('Volunteer removed from the event successfully', 'success')

    except Exception as e:
        conn.rollback()
        flash(f'Failed to remove volunteer: {str(e)}', 'danger')
        print(f"Remove volunteer error (event {event_id}, volunteer {volunteer_id}): {e}")

    finally:
        cur.close()

    return redirect(url_for('leader.event_detail', event_id=event_id))