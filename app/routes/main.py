"""Main routes for the Zakat Calculator UI."""
from flask import Blueprint, render_template

main_bp = Blueprint('main', __name__)


@main_bp.route('/')
def calculator():
    """Render the Zakat calculator UI."""
    return render_template('calculator.html')


@main_bp.route('/about-zakat')
def about_zakat():
    """Render the About Zakat informational page."""
    return render_template('about_zakat.html')


@main_bp.route('/faq')
def faq():
    """Render the Zakat FAQ page."""
    return render_template('faq.html')


@main_bp.route('/contact')
def contact():
    """Render the Contact Us page."""
    return render_template('contact.html')
