from flask import Flask
from flask_cors import CORS
from .config import Config
from .database import db
from .routes import init_routes
import logging
import os

def create_app(config_class=Config):
    """Initialize and configure the Flask application."""
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Ensure the instance folder exists
    os.makedirs(app.instance_path, exist_ok=True)

    # Initialize extensions
    CORS(app)
    db.init_app(app)

    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Initialize routes
    init_routes(app)

    # Create database tables
    with app.app_context():
        db.create_all()

    return app