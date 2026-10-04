"""TaskFlow: a small task-tracking JSON API."""

import os

from flask import Flask

from . import db, routes


def create_app(test_config=None):
    """Create and configure a TaskFlow application instance."""
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        DATABASE=os.environ.get("TASKFLOW_DATABASE")
        or os.path.join(app.instance_path, "taskflow.sqlite"),
        MAX_CONTENT_LENGTH=64 * 1024,
    )
    if test_config is not None:
        app.config.update(test_config)
    app.json.sort_keys = False

    os.makedirs(os.path.dirname(os.path.abspath(app.config["DATABASE"])), exist_ok=True)
    db.init_app(app)
    app.url_map.converters["id"] = routes.IdConverter
    app.register_blueprint(routes.bp)
    return app
