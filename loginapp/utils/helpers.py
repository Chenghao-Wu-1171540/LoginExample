"""
app/utils/helpers.py - General helper functions for the application

Contains:
- allowed_file: Validate file extensions for uploads
- (you can add more helpers here later)
"""

from flask import current_app


def allowed_file(filename):
    """
    Check if the uploaded file has an allowed extension.

    Args:
        filename (str): Name of the uploaded file

    Returns:
        bool: True if extension is allowed, False otherwise
    """
    if not filename:
        return False

    return '.' in filename and \
        filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']