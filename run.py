# run.py
"""
run.py - Development server launcher for EcoCleanUp Hub

This file should be placed in the project ROOT directory (same level as 'loginapp/' folder).
Do NOT put application logic here — only use it to start the dev server.

Usage:
    python run.py
"""

import os
import sys

# Ensure the project root is in sys.path (helps when running from subdirectories)
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

try:
    # Import the application factory from the 'loginapp' package
    from loginapp import create_app
except ImportError as e:
    print("Error: Cannot import 'create_app' from 'loginapp'.")
    print("Possible causes:")
    print("  1. The 'loginapp/__init__.py' file does not exist or has no 'create_app' function")
    print("  2. You are running run.py from the wrong directory (must be in the project root)")
    print("  3. PyCharm / virtual environment cache issue")
    print(f"Current working directory: {os.getcwd()}")
    print(f"sys.path: {sys.path}")
    print(f"Detailed error: {e}")
    sys.exit(1)

# Create Flask app instance
app = create_app('development')  # Change to 'production' or 'testing' if needed

if __name__ == '__main__':
    print("Starting EcoCleanUp Hub development server...")
    print(f" * Running on http://127.0.0.1:5000 (Press CTRL+C to quit)")
    print(f" * Debug mode: ON")
    print(f" * Current working directory: {os.getcwd()}")

    app.run(
        debug=True,
        host='0.0.0.0',          # Allow access from local network / other devices
        port=5000,
        use_reloader=True,
        threaded=True
    )