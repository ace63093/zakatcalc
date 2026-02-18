"""Flask application factory for Zakat Calculator."""
import logging
import os
from flask import Flask, request, g, redirect
from werkzeug.middleware.proxy_fix import ProxyFix


logger = logging.getLogger('app')


def create_app(config: dict | None = None) -> Flask:
    """Create and configure the Flask application.

    Args:
        config: Optional configuration dictionary to override defaults.

    Returns:
        Configured Flask application instance.
    """
    app = Flask(__name__)

    # Trust X-Forwarded-For from reverse proxy
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    # Default configuration
    app.config.update(
        SECRET_KEY='dev-secret-key-change-in-production',
        JSON_SORT_KEYS=False,
        DATA_DIR=os.environ.get('DATA_DIR', os.path.join(os.path.dirname(__file__), '..', 'data')),
        # Pricing sync configuration
        PRICING_ALLOW_NETWORK=os.environ.get('PRICING_ALLOW_NETWORK', '0').lower() in ('1', 'true', 'yes'),
        PRICING_AUTO_FETCH_MISSING=os.environ.get('PRICING_AUTO_FETCH_MISSING', '0').lower() in ('1', 'true', 'yes'),
        PRICING_DATA_BASE_CCY='USD',
        # Canonical URL configuration
        CANONICAL_HOST=os.environ.get('CANONICAL_HOST', 'whatismyzakat.com'),
    )

    # Override with provided config
    if config:
        app.config.update(config)

    # Initialize database
    from app import db
    db.init_app(app)

    # Register CLI commands
    from app import cli
    cli.register_cli(app)

    # Initialize geolocation index (SQLite -> R2 -> empty)
    from app.services.config import is_geolocation_enabled
    if is_geolocation_enabled() and not app.config.get('TESTING'):
        from app.services.geolocation import init_geolocation
        init_geolocation(app)

    # Restore visitor logs from R2 if SQLite is empty (ephemeral storage recovery)
    from app.services.config import is_visitor_logging_enabled
    if is_visitor_logging_enabled() and not app.config.get('TESTING'):
        try:
            from app.services.r2_client import get_r2_client
            r2 = get_r2_client()
            if r2:
                with app.app_context():
                    from app.db import get_db
                    from app.services.visitor_logging import restore_visitors_from_r2
                    restore_visitors_from_r2(get_db(), r2)
        except Exception as e:
            logger.warning(f"Failed to restore visitors from R2: {e}")

    # Register blueprints
    from app.routes.main import main_bp
    from app.routes.health import health_bp
    from app.routes.api import api_bp
    from app.routes.guides import guides_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(health_bp)
    app.register_blueprint(api_bp, url_prefix='/api/v1')
    app.register_blueprint(guides_bp)

    # Redirect non-canonical domains (e.g. .net, .org) to canonical host
    @app.before_request
    def _redirect_to_canonical():
        canonical = app.config['CANONICAL_HOST']
        host = request.host.split(':')[0]  # strip port
        if host != canonical and host != 'localhost' and host != '127.0.0.1':
            # Skip health checks so DigitalOcean probes still work
            if request.path == '/healthz':
                return
            return redirect(
                f"https://{canonical}{request.full_path}" if request.query_string else f"https://{canonical}{request.path}",
                code=301,
            )

    # Visitor logging before_request hook
    @app.before_request
    def _log_visitor():
        path = request.path
        # Skip static files, API, and health checks
        if path.startswith('/static/') or path.startswith('/api/') or path == '/healthz':
            return

        if not is_visitor_logging_enabled():
            return

        try:
            from app.db import get_db
            from app.services.visitor_logging import log_visitor
            result = log_visitor(
                get_db(),
                request.remote_addr,
                request.user_agent.string,
                request.host,
            )
            g.visitor_geo = result
        except Exception:
            # Visitor logging must never break page loads
            pass

    # Start background pricing sync (for single-container deployments)
    # Only starts if PRICING_AUTO_SYNC=1 (checked inside start_background_sync)
    if os.environ.get('PRICING_BACKGROUND_SYNC', '0').lower() in ('1', 'true', 'yes'):
        from app.services.background_sync import start_background_sync
        start_background_sync(app)

    # Start geodb refresh thread
    if is_geolocation_enabled() and not app.config.get('TESTING'):
        from app.services.geodb_sync import start_geodb_refresh
        start_geodb_refresh()

    return app
