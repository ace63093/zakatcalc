"""Flask application factory for Zakat Calculator."""
import os
from flask import Flask


def create_app(config: dict | None = None) -> Flask:
    """Create and configure the Flask application.

    Args:
        config: Optional configuration dictionary to override defaults.

    Returns:
        Configured Flask application instance.
    """
    app = Flask(__name__)

    # Default configuration
    app.config.update(
        SECRET_KEY='dev-secret-key-change-in-production',
        JSON_SORT_KEYS=False,
        DATA_DIR=os.environ.get('DATA_DIR', os.path.join(os.path.dirname(__file__), '..', 'data')),
        # Pricing sync configuration
        PRICING_ALLOW_NETWORK=os.environ.get('PRICING_ALLOW_NETWORK', '0').lower() in ('1', 'true', 'yes'),
        PRICING_AUTO_FETCH_MISSING=os.environ.get('PRICING_AUTO_FETCH_MISSING', '0').lower() in ('1', 'true', 'yes'),
        PRICING_DATA_BASE_CCY='USD',
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

    # Register blueprints
    from app.routes.main import main_bp
    from app.routes.health import health_bp
    from app.routes.api import api_bp
    from app.routes.guides import guides_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(health_bp)
    app.register_blueprint(api_bp, url_prefix='/api/v1')
    app.register_blueprint(guides_bp)

    # Start background pricing sync (for single-container deployments)
    # Only starts if PRICING_AUTO_SYNC=1 (checked inside start_background_sync)
    if os.environ.get('PRICING_BACKGROUND_SYNC', '0').lower() in ('1', 'true', 'yes'):
        from app.services.background_sync import start_background_sync
        start_background_sync()

    return app
