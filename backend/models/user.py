from datetime import datetime
from ..database import db
from werkzeug.security import generate_password_hash, check_password_hash
from typing import List

class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    ethereum_address = db.Column(db.String(42), unique=True, nullable=True)
    is_author = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    books = db.relationship('Book', backref='author', lazy='dynamic')
    purchases = db.relationship('Transaction', foreign_keys='Transaction.buyer_id', backref='buyer', lazy='dynamic')
    sales = db.relationship('Transaction', foreign_keys='Transaction.seller_id', backref='seller', lazy='dynamic')

    def __init__(self, username: str, email: str, password: str, ethereum_address: str = None):
        self.username = username
        self.email = email
        self.set_password(password)
        self.ethereum_address = ethereum_address

    def set_password(self, password: str) -> None:
        """Set password hash."""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        """Verify password."""
        return check_password_hash(self.password_hash, password)

    def to_dict(self) -> dict:
        """Convert user to dictionary."""
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'ethereum_address': self.ethereum_address,
            'is_author': self.is_author,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }

    def __repr__(self) -> str:
        return f'<User {self.username}>'