"""Main routes for the Zakat Calculator UI."""
from flask import Blueprint, render_template, redirect, request, send_from_directory, current_app

from app.services.config import get_feature_flags
from app.content.charities import COUNTRY_OPTIONS
from app.services.charities_service import get_charities

main_bp = Blueprint('main', __name__)


@main_bp.route('/ads.txt')
def ads_txt():
    """Redirect to Ezoic's managed ads.txt file."""
    return redirect('https://srv.adstxtmanager.com/19390/whatismyzakat.com', code=301)


@main_bp.route('/favicon.ico')
def favicon():
    """Serve favicon from static assets for browser/crawler compatibility."""
    return send_from_directory(current_app.static_folder, 'favicon.ico', mimetype='image/x-icon')


@main_bp.route('/')
def calculator():
    """Render the Zakat calculator UI."""
    return render_template('calculator.html', feature_flags=get_feature_flags())


@main_bp.route('/about-zakat')
def about_zakat():
    """Render the About Zakat informational page."""
    return render_template('about_zakat.html')


@main_bp.route('/faq')
def faq():
    """Render the Zakat FAQ page."""
    return render_template('faq.html')


@main_bp.route('/methodology')
def methodology():
    """Render the Calculation Methodology page."""
    return render_template('methodology.html')


@main_bp.route('/contact')
def contact():
    """Render the Contact Us page."""
    return render_template('contact.html')


@main_bp.route('/privacy-policy')
def privacy_policy():
    """Render the Privacy Policy page."""
    return render_template('privacy_policy.html')


@main_bp.route('/cad-to-bdt')
def cad_to_bdt():
    """Render the CAD to BDT conversion page."""
    return render_template('cad_to_bdt.html')


@main_bp.route('/charities')
def charities():
    from app.services.r2_client import get_r2_client
    charities_list = get_charities(r2_client=get_r2_client())
    # Pre-select the visitor's country if we have charities for it
    user_country = request.headers.get('CF-IPCountry', '').upper().strip()
    country_codes = {opt['code'] for opt in COUNTRY_OPTIONS}
    if user_country not in country_codes:
        user_country = ''
    return render_template(
        'charities.html',
        charities=charities_list,
        country_options=COUNTRY_OPTIONS,
        user_country=user_country,
    )


@main_bp.route('/summary')
def summary():
    """Render the printable summary page.

    This page is designed to be loaded via JavaScript with state passed
    in the URL fragment. The page reads the state client-side and renders
    a printable summary without sending data to the server.
    """
    feature_flags = get_feature_flags()
    if not feature_flags.get('print_summary_enabled', True):
        return render_template('feature_disabled.html',
                               feature_name='Printable Summary'), 403
    return render_template('summary.html', feature_flags=feature_flags)
