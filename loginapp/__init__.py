"""
app/__init__.py - Application Factory for EcoCleanUp Hub

This file creates and configures the Flask application instance.
All extensions, configurations, and blueprints are registered here.
"""

from flask import Flask, render_template, session, send_from_directory
from flask_bcrypt import Bcrypt
from psycopg2.extras import RealDictCursor
import os

# Relative imports (all files are inside the same package)
from .db import init_db, get_db
from .routes.auth import auth_bp
from .routes.user import user_bp
from .routes.events import events_bp
from .routes.leader import leader_bp
from .routes.admin import admin_bp
from .utils.decorators import login_required, role_required
from .utils.helpers import allowed_file

# Global bcrypt instance
bcrypt = Bcrypt()


def create_app(config_name='default'):
    """
    Application factory function.
    Creates and configures the Flask app instance.
    """
    app = Flask(__name__, instance_relative_config=True)

    # Basic configuration (use environment variables in production!)
    app.config['SECRET_KEY'] = 'your-secret-key-change-this-in-production-2026'
    app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'static', 'profile_images')
    app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif'}
    app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024  # 2MB max upload size

    # Create upload folder if it doesn't exist
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    # Initialize extensions
    bcrypt.init_app(app)
    init_db(app)  # Initialize PostgreSQL connection pool

    # Register blueprints
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(user_bp)
    app.register_blueprint(events_bp)
    app.register_blueprint(leader_bp, url_prefix='/leader')
    app.register_blueprint(admin_bp, url_prefix='/admin')

    # Home page route (shows upcoming events reminder for volunteers)
    @app.route('/')
    def home():
        upcoming = []
        show_reminder = False
        upcoming_events_modal = []  # Data for the modal popup

        if 'user_id' in session and session.get('role') == 'volunteer':
            try:
                conn = get_db()
                cur = conn.cursor(cursor_factory=RealDictCursor)
                cur.execute("""
                    SELECT e.event_id, e.event_name, e.event_date, e.start_time, e.location
                    FROM events e
                    JOIN eventregistrations er ON e.event_id = er.event_id
                    WHERE er.volunteer_id = %s
                      AND e.event_date >= CURRENT_DATE
                    ORDER BY e.event_date, e.start_time
                    LIMIT 5
                """, (session['user_id'],))
                upcoming = cur.fetchall()
                cur.close()

                show_reminder = len(upcoming) > 0
                if show_reminder:
                    upcoming_events_modal = upcoming  # Pass to modal

            except Exception as e:
                print(f"Error querying upcoming events on home page: {e}")

        return render_template('home.html',
                               upcoming=upcoming,
                               show_reminder=show_reminder,
                               upcoming_events_modal=upcoming_events_modal)

    # Serve uploaded profile images
    @app.route('/profile_images/<filename>')
    def uploaded_file(filename):
        return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

    return app