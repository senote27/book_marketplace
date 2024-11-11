from datetime import datetime
from ..database import db
from enum import Enum

class TransactionType(Enum):
    PURCHASE = 'purchase'
    ROYALTY = 'royalty'
    WITHDRAWAL = 'withdrawal'

class TransactionStatus(Enum):
    PENDING = 'pending'
    COMPLETED = 'completed'
    FAILED = 'failed'

class Transaction(db.Model):
    __tablename__ = 'transactions'

    id = db.Column(db.Integer, primary_key=True)
    transaction_hash = db.Column(db.String(66), unique=True, nullable=False)
    book_id = db.Column(db.Integer, db.ForeignKey('books.id'), nullable=True)
    buyer_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    seller_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    amount = db.Column(db.BigInteger, nullable=False)  # Amount in wei
    
    # Transaction metadata
    type = db.Column(db.Enum(TransactionType), nullable=False, default=TransactionType.PURCHASE)
    status = db.Column(db.Enum(TransactionStatus), nullable=False, default=TransactionStatus.PENDING)
    gas_used = db.Column(db.BigInteger, nullable=True)
    block_number = db.Column(db.Integer, nullable=True)
    
    # Timestamps
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime, nullable=True)

    def __init__(self, transaction_hash: str, seller_id: int, amount: int,
                 buyer_id: int = None, book_id: int = None,
                 type: TransactionType = TransactionType.PURCHASE,
                 status: TransactionStatus = TransactionStatus.PENDING,
                 gas_used: int = None, block_number: int = None):
        self.transaction_hash = transaction_hash
        self.seller_id = seller_id
        self.amount = amount
        self.buyer_id = buyer_id
        self.book_id = book_id
        self.type = type
        self.status = status
        self.gas_used = gas_used
        self.block_number = block_number

    def complete(self, gas_used: int, block_number: int) -> None:
        """Mark transaction as completed."""
        self.status = TransactionStatus.COMPLETED
        self.gas_used = gas_used
        self.block_number = block_number
        self.completed_at = datetime.utcnow()

    def fail(self) -> None:
        """Mark transaction as failed."""
        self.status = TransactionStatus.FAILED
        self.completed_at = datetime.utcnow()

    def to_dict(self) -> dict:
        """Convert transaction to dictionary."""
        return {
            'id': self.id,
            'transaction_hash': self.transaction_hash,
            'book_id': self.book_id,
            'book_title': self.book.title if self.book else None,
            'buyer_id': self.buyer_id,
            'buyer_username': self.buyer.username if self.buyer else None,
            'seller_id': self.seller_id,
            'seller_username': self.seller.username,
            'amount': self.amount,
            'type': self.type.value,
            'status': self.status.value,
            'gas_used': self.gas_used,
            'block_number': self.block_number,
            'timestamp': self.timestamp.isoformat(),
            'completed_at': self.completed_at.isoformat() if self.completed_at else None
        }

    def __repr__(self) -> str:
        return f'<Transaction {self.transaction_hash}>'