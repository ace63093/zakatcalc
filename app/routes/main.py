"""Main routes for the Zakat Calculator UI."""
from flask import Blueprint, render_template

main_bp = Blueprint('main', __name__)


@main_bp.route('/')
def calculator():
    """Render the Zakat calculator UI."""
    return render_template('calculator.html')
