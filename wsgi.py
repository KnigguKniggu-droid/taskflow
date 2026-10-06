"""WSGI entry point for PythonAnywhere (and any other WSGI host).

PythonAnywhere imports this file directly.  The platform's web-app settings
panel should set::

    TASKFLOW_DATABASE=/home/<username>/taskflow-data/taskflow.sqlite

so the SQLite file lives on the persistent home-directory disk, outside the
source tree.

Debug mode is intentionally never enabled here.  The Flask development server
(run.py) is used for local development only.
"""

from app import create_app

application = create_app()
