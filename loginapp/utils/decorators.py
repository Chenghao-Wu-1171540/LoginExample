"""
app/utils/decorators.py - Custom Flask decorators for authentication and authorization

Contains:
- login_required: Ensure user is logged in
- role_required: Role-based access control with hierarchy
"""

from functools import wraps
from flask import flash, redirect, url_for, session


def login_required(f):
    """
    Decorator: Require user to be logged in.
    Redirects to login page if not authenticated.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in first', 'warning')
            return redirect(url_for('auth.login'))  # 假设登录路由在 auth 蓝图
        return f(*args, **kwargs)
    return decorated_function


def role_required(*min_roles):
    """
    Decorator: Role-based access control with hierarchy.
    Role levels: volunteer (1) < event_leader (2) < admin (3)

    Usage:
        @role_required('volunteer')     # volunteer + higher
        @role_required('event_leader')  # leader + admin
        @role_required('admin')         # only admin
    """
    role_hierarchy = {'volunteer': 1, 'event_leader': 2, 'admin': 3}

    def decorator(f):
        @wraps(f)
        @login_required
        def decorated_function(*args, **kwargs):
            user_role = session.get('role')
            if not user_role:
                flash('Session expired. Please log in again.', 'danger')
                return redirect(url_for('auth.login'))

            user_level = role_hierarchy.get(user_role, 0)
            required_level = max(role_hierarchy.get(r, 0) for r in min_roles)

            if user_level < required_level:
                flash('You do not have permission to access this page.', 'danger')
                return redirect(url_for('home'))

            return f(*args, **kwargs)
        return decorated_function
    return decorator