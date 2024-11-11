from datetime import datetime
from ..database import db
from typing import List, Optional

class Book(db.Model):
    __tablename__ = 'books'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    price = db.Column(db.BigInteger, nullable=False)  # Price in wei
    royalty_percentage = db.Column(db.Integer, nullable=False)  # 0-100
    ipfs_hash = db.Column(db.String(64), unique=True, nullable=False)
    cover_ipfs_hash = db.Column(db.String(64), nullable=True)
    blockchain_id = db.Column(db.Integer, unique=True, nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # Status flags
    is_available = db.Column(db.Boolean, default=True)
    is_deleted = db.Column(db.Boolean, default=False)
    
    # Metadata
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Categories and tags (JSON fields)
    categories = db.Column(db.JSON, default=list)
    tags = db.Column(db.JSON, default=list)
    
    # Relationships
    transactions = db.relationship('Transaction', backref='book', lazy='dynamic')

    def __init__(self, title: str, price: int, royalty_percentage: int, 
                 ipfs_hash: str, blockchain_id: int, author_id: int,
                 description: Optional[str] = None, cover_ipfs_hash: Optional[str] = None,
                 categories: Optional[List[str]] = None, tags: Optional[List[str]] = None):
        self.title = title
        self.description = description
        self.price = price
        self.royalty_percentage = royalty_percentage
        self.ipfs_hash = ipfs_hash
        self.blockchain_id = blockchain_id
        self.author_id = author_id
        self.cover_ipfs_hash = cover_ipfs_hash
        self.categories = categories or []
        self.tags = tags or []

    def to_dict(self) -> dict:
        """Convert book to dictionary."""
        return {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'price': self.price,
            'royalty_percentage': self.royalty_percentage,
            'ipfs_hash': self.ipfs_hash,
            'cover_ipfs_hash': self.cover_ipfs_hash,
            'blockchain_id': self.blockchain_id,
            'author_id': self.author_id,
            'author_username': self.author.username,
            'is_available': self.is_available,
            'categories': self.categories,
            'tags': self.tags,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }

    def __repr__(self) -> str:
        return f'<Book {self.title}>'