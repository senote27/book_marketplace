from flask import Blueprint, request, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import jwt
from functools import wraps
from ..models.user import User
from ..utils.eth import EthereumHandler
from ..database import db
import os

auth_bp = Blueprint('auth', __name__)
eth_handler = EthereumHandler()

# Environment variables
JWT_SECRET = os.getenv('JWT_SECRET', 'your-secret-key')
JWT_EXPIRATION = int(os.getenv('JWT_EXPIRATION', 86400))  # 24 hours

def token_required(f):
    """Decorator to check valid JWT token."""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization')
        
        if not token:
            return jsonify({'message': 'Token is missing'}), 401
        
        try:
            token = token.split('Bearer ')[1]
            data = jwt.decode(token, JWT_SECRET, algorithms=['HS256'])
            current_user = User.query.filter_by(id=data['user_id']).first()
        except Exception as e:
            return jsonify({'message': 'Invalid token'}), 401
            
        return f(current_user, *args, **kwargs)
    return decorated

@auth_bp.route('/register', methods=['POST'])
async def register():
    """Register a new user."""
    try:
        data = request.get_json()
        required_fields = ['username', 'email', 'password', 'eth_address']
        
        if not all(field in data for field in required_fields):
            return jsonify({'message': 'Missing required fields'}), 400

        # Check if user exists
        if User.query.filter_by(email=data['email']).first():
            return jsonify({'message': 'Email already registered'}), 409
        
        if User.query.filter_by(username=data['username']).first():
            return jsonify({'message': 'Username already taken'}), 409

        # Verify Ethereum address signature if provided
        if 'signature' in data:
            message = f"Register {data['username']} with {data['eth_address']}"
            if not await eth_handler.verify_signature(
                message,
                data['signature'],
                data['eth_address']
            ):
                return jsonify({'message': 'Invalid Ethereum signature'}), 400

        # Create new user
        new_user = User(
            username=data['username'],
            email=data['email'],
            password=generate_password_hash(data['password']),
            eth_address=data['eth_address'],
            role=data.get('role', 'reader'),
            created_at=datetime.utcnow()
        )

        db.session.add(new_user)
        db.session.commit()

        return jsonify({
            'message': 'User registered successfully',
            'user_id': new_user.id
        }), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({'message': f'Registration failed: {str(e)}'}), 500

@auth_bp.route('/login', methods=['POST'])
async def login():
    """User login endpoint."""
    try:
        data = request.get_json()
        
        if not data.get('email') or not data.get('password'):
            return jsonify({'message': 'Missing email or password'}), 400

        user = User.query.filter_by(email=data['email']).first()

        if not user or not check_password_hash(user.password, data['password']):
            return jsonify({'message': 'Invalid credentials'}), 401

        # Generate JWT token
        token = jwt.encode({
            'user_id': user.id,
            'eth_address': user.eth_address,
            'role': user.role,
            'exp': datetime.utcnow() + timedelta(seconds=JWT_EXPIRATION)
        }, JWT_SECRET)

        return jsonify({
            'token': token,
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'eth_address': user.eth_address,
                'role': user.role
            }
        }), 200

    except Exception as e:
        return jsonify({'message': f'Login failed: {str(e)}'}), 500

@auth_bp.route('/profile', methods=['GET'])
@token_required
def get_profile(current_user):
    """Get user profile information."""
    return jsonify({
        'user': {
            'id': current_user.id,
            'username': current_user.username,
            'email': current_user.email,
            'eth_address': current_user.eth_address,
            'role': current_user.role,
            'created_at': current_user.created_at.isoformat()
        }
    }), 200

@auth_bp.route('/profile', methods=['PUT'])
@token_required
async def update_profile(current_user):
    """Update user profile."""
    try:
        data = request.get_json()
        
        if 'email' in data and data['email'] != current_user.email:
            if User.query.filter_by(email=data['email']).first():
                return jsonify({'message': 'Email already in use'}), 409
            current_user.email = data['email']

        if 'username' in data and data['username'] != current_user.username:
            if User.query.filter_by(username=data['username']).first():
                return jsonify({'message': 'Username already taken'}), 409
            current_user.username = data['username']

        if 'password' in data:
            current_user.password = generate_password_hash(data['password'])

        if 'eth_address' in data:
            if 'signature' not in data:
                return jsonify({'message': 'Signature required for address change'}), 400
                
            message = f"Update eth_address to {data['eth_address']}"
            if not await eth_handler.verify_signature(
                message,
                data['signature'],
                data['eth_address']
            ):
                return jsonify({'message': 'Invalid Ethereum signature'}), 400
                
            current_user.eth_address = data['eth_address']

        db.session.commit()
        return jsonify({'message': 'Profile updated successfully'}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({'message': f'Update failed: {str(e)}'}), 500

@auth_bp.route('/verify-signature', methods=['POST'])
async def verify_signature():
    """Verify an Ethereum signature."""
    try:
        data = request.get_json()
        required_fields = ['message', 'signature', 'address']
        
        if not all(field in data for field in required_fields):
            return jsonify({'message': 'Missing required fields'}), 400

        is_valid = await eth_handler.verify_signature(
            data['message'],
            data['signature'],
            data['address']
        )

        return jsonify({'valid': is_valid}), 200

    except Exception as e:
        return jsonify({'message': f'Verification failed: {str(e)}'}), 500