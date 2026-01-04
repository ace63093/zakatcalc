"""Flask application factory for Zakat Calculator."""
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
    )

    # Override with provided config
    if config:
        app.config.update(config)

    # Register blueprints
    from app.routes.main import main_bp
    from app.routes.health import health_bp
    from app.routes.api import api_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(health_bp)
    app.register_blueprint(api_bp, url_prefix='/api/v1')

    return app
