from flask import Blueprint, jsonify, request, current_app
from web3 import Web3
from ..utils.eth import EthereumHandler
from ..models import Book, Transaction, User
from ..middleware import require_auth
from ..database import db
from datetime import datetime
import logging
from typing import Dict, Any

payment_bp = Blueprint('payment', __name__)
eth_handler = EthereumHandler()

# Set up logging
logger = logging.getLogger(__name__)

@payment_bp.route('/purchase/<int:book_id>', methods=['POST'])
@require_auth
async def purchase_book(book_id: int):
    """
    Purchase a book using cryptocurrency.
    """
    try:
        # Get user from session/token
        user = request.user
        
        # Get book details
        book = Book.query.get_or_404(book_id)
        if not book.is_available:
            return jsonify({
                'status': 'error',
                'message': 'Book is not available for purchase'
            }), 400

        # Verify payment data
        data = request.get_json()
        if not data or 'buyer_address' not in data or 'signature' not in data:
            return jsonify({
                'status': 'error',
                'message': 'Missing payment information'
            }), 400

        buyer_address = data['buyer_address']
        signature = data['signature']
        private_key = data.get('private_key')  # Only for testing environment

        # Verify signature
        message = f"Purchase book {book_id} for {book.price} wei"
        if not eth_handler.verify_signature(message, signature, buyer_address):
            return jsonify({
                'status': 'error',
                'message': 'Invalid signature'
            }), 401

        # Execute purchase transaction
        purchase_result = await eth_handler.purchase_book(
            buyer_address=buyer_address,
            book_id=book.blockchain_id,
            value=book.price,
            private_key=private_key
        )

        if purchase_result['status'] != 'success':
            return jsonify({
                'status': 'error',
                'message': 'Blockchain transaction failed'
            }), 400

        # Record transaction in database
        transaction = Transaction(
            book_id=book_id,
            buyer_id=user.id,
            seller_id=book.author_id,
            amount=book.price,
            transaction_hash=purchase_result['transaction_hash'],
            status='completed',
            timestamp=datetime.utcnow()
        )
        db.session.add(transaction)
        db.session.commit()

        return jsonify({
            'status': 'success',
            'transaction': {
                'hash': purchase_result['transaction_hash'],
                'block_number': purchase_result['block_number'],
                'gas_used': purchase_result['gas_used']
            }
        }), 200

    except Exception as e:
        logger.error(f"Purchase error: {str(e)}")
        db.session.rollback()
        return jsonify({
            'status': 'error',
            'message': 'Internal server error'
        }), 500

@payment_bp.route('/royalties', methods=['GET'])
@require_auth
async def get_royalties():
    """
    Get available royalties for the authenticated author.
    """
    try:
        user = request.user
        if not user.is_author:
            return jsonify({
                'status': 'error',
                'message': 'Only authors can view royalties'
            }), 403

        royalties = await eth_handler.get_royalties(user.ethereum_address)
        
        return jsonify({
            'status': 'success',
            'royalties': royalties,
            'address': user.ethereum_address
        }), 200

    except Exception as e:
        logger.error(f"Royalties fetch error: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': 'Failed to fetch royalties'
        }), 500

@payment_bp.route('/royalties/withdraw', methods=['POST'])
@require_auth
async def withdraw_royalties():
    """
    Withdraw available royalties for the authenticated author.
    """
    try:
        user = request.user
        if not user.is_author:
            return jsonify({
                'status': 'error',
                'message': 'Only authors can withdraw royalties'
            }), 403

        data = request.get_json()
        if not data or 'signature' not in data:
            return jsonify({
                'status': 'error',
                'message': 'Missing signature'
            }), 400

        signature = data['signature']
        private_key = data.get('private_key')  # Only for testing environment

        # Verify signature
        message = f"Withdraw royalties for {user.ethereum_address}"
        if not eth_handler.verify_signature(message, signature, user.ethereum_address):
            return jsonify({
                'status': 'error',
                'message': 'Invalid signature'
            }), 401

        # Execute withdrawal
        withdrawal_result = await eth_handler.withdraw_royalties(
            author_address=user.ethereum_address,
            private_key=private_key
        )

        if withdrawal_result['status'] != 'success':
            return jsonify({
                'status': 'error',
                'message': 'Withdrawal transaction failed'
            }), 400

        # Record withdrawal transaction
        transaction = Transaction(
            seller_id=user.id,
            amount=withdrawal_result.get('amount', 0),
            transaction_hash=withdrawal_result['transaction_hash'],
            status='completed',
            timestamp=datetime.utcnow(),
            type='withdrawal'
        )
        db.session.add(transaction)
        db.session.commit()

        return jsonify({
            'status': 'success',
            'transaction': {
                'hash': withdrawal_result['transaction_hash'],
                'block_number': withdrawal_result['block_number'],
                'gas_used': withdrawal_result['gas_used']
            }
        }), 200

    except Exception as e:
        logger.error(f"Withdrawal error: {str(e)}")
        db.session.rollback()
        return jsonify({
            'status': 'error',
            'message': 'Internal server error'
        }), 500

@payment_bp.route('/transactions', methods=['GET'])
@require_auth
async def get_transactions():
    """
    Get transaction history for the authenticated user.
    """
    try:
        user = request.user
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)

        # Query transactions
        transactions = Transaction.query.filter(
            (Transaction.buyer_id == user.id) | 
            (Transaction.seller_id == user.id)
        ).order_by(
            Transaction.timestamp.desc()
        ).paginate(
            page=page, 
            per_page=per_page
        )

        return jsonify({
            'status': 'success',
            'transactions': [{
                'id': tx.id,
                'type': tx.type,
                'amount': tx.amount,
                'status': tx.status,
                'timestamp': tx.timestamp.isoformat(),
                'transaction_hash': tx.transaction_hash,
                'book_title': tx.book.title if tx.book_id else None
            } for tx in transactions.items],
            'pagination': {
                'total': transactions.total,
                'pages': transactions.pages,
                'current_page': transactions.page,
                'per_page': transactions.per_page
            }
        }), 200

    except Exception as e:
        logger.error(f"Transaction history error: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': 'Failed to fetch transaction history'
        }), 500

@payment_bp.route('/balance', methods=['GET'])
@require_auth
async def get_balance():
    """
    Get the current balance for the authenticated user.
    """
    try:
        user = request.user
        if not user.ethereum_address:
            return jsonify({
                'status': 'error',
                'message': 'No ethereum address associated with account'
            }), 400

        balance = Web3.from_wei(
            eth_handler.w3.eth.get_balance(user.ethereum_address),
            'ether'
        )

        return jsonify({
            'status': 'success',
            'balance': str(balance),
            'address': user.ethereum_address
        }), 200

    except Exception as e:
        logger.error(f"Balance fetch error: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': 'Failed to fetch balance'
        }), 500