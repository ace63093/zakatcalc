"""Health check endpoint."""
from flask import Blueprint, jsonify

health_bp = Blueprint('health', __name__)


@health_bp.route('/healthz')
def healthz():
    """Return health status of the application."""
    return jsonify({'status': 'ok'})
