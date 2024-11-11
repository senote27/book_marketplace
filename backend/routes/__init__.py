from flask import Blueprint
from .auth_routes import auth_bp
from .book_routes import book_bp
from .payment_routes import payment_bp

def init_routes(app):
    """Initialize all route blueprints."""
    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(book_bp, url_prefix='/api/books')
    app.register_blueprint(payment_bp, url_prefix='/api/payments')