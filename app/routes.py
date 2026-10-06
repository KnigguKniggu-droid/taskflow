"""HTTP routes for the TaskFlow JSON API."""

import json
from datetime import date

from flask import Blueprint, current_app, jsonify, request
from werkzeug.exceptions import HTTPException
from werkzeug.routing import IntegerConverter

from . import services

bp = Blueprint("api", __name__)


@bp.route("/")
def index():
    return current_app.send_static_file("index.html")


class IdConverter(IntegerConverter):
    """Like the built-in ``int`` converter, but accepts ASCII digits only."""

    regex = r"[0-9]+"


def _json_body():
    try:
        data = request.get_json(silent=True)
    except RecursionError:  # pathologically nested JSON
        data = None
    if not isinstance(data, dict):
        raise services.ValidationError("request body must be a valid JSON object")
    return data


@bp.get("/users")
def list_users():
    return jsonify({"users": services.list_users()})


@bp.post("/users")
def create_user():
    return jsonify(services.create_user(_json_body())), 201


@bp.post("/tasks")
def create_task():
    return jsonify(services.create_task(_json_body())), 201


@bp.get("/tasks")
def list_tasks():
    assignee_id = services.parse_id_param(request.args.get("assignee_id"), "assignee_id")
    tag = services.parse_tag_param(request.args.get("tag"))
    return jsonify({"tasks": services.list_tasks(assignee_id=assignee_id, tag=tag)})


@bp.get("/tasks/stats")
def get_task_stats():
    return jsonify(services.get_task_stats(date.today()))


@bp.get("/tasks/overdue")
def list_overdue_tasks():
    return jsonify({"tasks": services.list_overdue_tasks(date.today())})


@bp.get("/tasks/<id:task_id>")
def get_task(task_id):
    return jsonify(services.get_task(task_id))


@bp.post("/tasks/<id:task_id>/complete")
def complete_task(task_id):
    return jsonify(services.complete_task(task_id))


@bp.app_errorhandler(services.ValidationError)
def handle_validation_error(error):
    return jsonify({"error": str(error)}), 400


@bp.app_errorhandler(services.NotFoundError)
def handle_not_found(error):
    return jsonify({"error": str(error)}), 404


@bp.app_errorhandler(HTTPException)
def handle_http_exception(error):
    # Keep the status code and headers (e.g. Allow on 405) but answer in JSON.
    # Unhandled exceptions arrive here as a generic 500 that reveals no details.
    response = error.get_response()
    response.data = json.dumps({"error": error.description})
    response.content_type = "application/json"
    return response
