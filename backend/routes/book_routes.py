from flask import Blueprint, request, jsonify, current_app, g
from werkzeug.utils import secure_filename
import os
from datetime import datetime
from functools import wraps
import jwt
from ..utils import IPFSHandler, EthereumHandler
from ..models.book import Book, BookSchema
from ..models.user import User
from ..extensions import db
import logging

# Initialize Blueprint
book_routes = Blueprint('book_routes', __name__)

# Initialize handlers
ipfs_handler = IPFSHandler()
eth_handler = EthereumHandler()

# Setup logging
logger = logging.getLogger('book_routes')

def token_required(f):
    @wraps(f)
    async def decorated(*args, **kwargs):
        token = None
        if 'Authorization' in request.headers:
            token = request.headers['Authorization'].split(' ')[1]
        
        if not token:
            return jsonify({'message': 'Token is missing'}), 401
        
        try:
            data = jwt.decode(token, current_app.config['SECRET_KEY'], algorithms=["HS256"])
            current_user = User.query.filter_by(id=data['user_id']).first()
            g.current_user = current_user
        except:
            return jsonify({'message': 'Token is invalid'}), 401
        
        return await f(*args, **kwargs)
    return decorated

def allowed_file(filename):
    """Check if file extension is allowed."""
    ALLOWED_EXTENSIONS = {'pdf', 'epub', 'mobi'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@book_routes.route('/books', methods=['POST'])
@token_required
async def create_book():
    """
    Create a new book listing.
    Required fields:
    - title: string
    - description: string
    - price: float (in ETH)
    - royalty: int (percentage)
    - book_file: file (PDF/EPUB/MOBI)
    - cover_image: file (JPG/PNG)
    """
    try:
        # Validate form data
        if 'book_file' not in request.files or 'cover_image' not in request.files:
            return jsonify({'error': 'Missing files'}), 400
        
        book_file = request.files['book_file']
        cover_image = request.files['cover_image']
        
        if not book_file or not cover_image:
            return jsonify({'error': 'No file selected'}), 400
            
        if not allowed_file(book_file.filename):
            return jsonify({'error': 'Invalid file type'}), 400

        # Save files temporarily
        book_filename = secure_filename(book_file.filename)
        cover_filename = secure_filename(cover_image.filename)
        
        temp_book_path = os.path.join(current_app.config['UPLOAD_FOLDER'], book_filename)
        temp_cover_path = os.path.join(current_app.config['UPLOAD_FOLDER'], cover_filename)
        
        book_file.save(temp_book_path)
        cover_image.save(temp_cover_path)

        # Upload to IPFS
        book_hash, book_success = await ipfs_handler.upload_file(temp_book_path)
        cover_hash, cover_success = await ipfs_handler.upload_file(temp_cover_path)

        if not book_success or not cover_success:
            raise Exception("IPFS upload failed")

        # Clean up temporary files
        os.remove(temp_book_path)
        os.remove(temp_cover_path)

        # Convert price to wei
        price_wei = int(float(request.form['price']) * 10**18)
        royalty = int(request.form['royalty'])

        # List book on blockchain
        tx_result = await eth_handler.list_book(
            g.current_user.eth_address,
            book_hash,
            price_wei,
            royalty,
            g.current_user.eth_private_key  # This should be properly secured
        )

        if tx_result['status'] != 'success':
            raise Exception("Blockchain transaction failed")

        # Create database entry
        new_book = Book(
            title=request.form['title'],
            description=request.form['description'],
            price=float(request.form['price']),
            royalty=royalty,
            book_hash=book_hash,
            cover_hash=cover_hash,
            author_id=g.current_user.id,
            tx_hash=tx_result['transaction_hash'],
            created_at=datetime.utcnow()
        )

        db.session.add(new_book)
        db.session.commit()

        return jsonify({
            'message': 'Book created successfully',
            'book_id': new_book.id,
            'transaction_hash': tx_result['transaction_hash']
        }), 201

    except Exception as e:
        logger.error(f"Error creating book: {str(e)}")
        return jsonify({'error': str(e)}), 500

@book_routes.route('/books', methods=['GET'])
async def get_books():
    """Get all available books."""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)
        
        books = Book.query.filter_by(is_active=True).paginate(
            page=page, per_page=per_page, error_out=False
        )
        
        book_schema = BookSchema(many=True)
        return jsonify({
            'books': book_schema.dump(books.items),
            'total': books.total,
            'pages': books.pages,
            'current_page': books.page
        }), 200

    except Exception as e:
        logger.error(f"Error fetching books: {str(e)}")
        return jsonify({'error': str(e)}), 500

@book_routes.route('/books/<int:book_id>', methods=['GET'])
async def get_book(book_id):
    """Get specific book details."""
    try:
        book = Book.query.get_or_404(book_id)
        book_schema = BookSchema()
        return jsonify(book_schema.dump(book)), 200

    except Exception as e:
        logger.error(f"Error fetching book {book_id}: {str(e)}")
        return jsonify({'error': str(e)}), 500

@book_routes.route('/books/<int:book_id>', methods=['PUT'])
@token_required
async def update_book(book_id):
    """Update book details (only title, description, and price)."""
    try:
        book = Book.query.get_or_404(book_id)
        
        if book.author_id != g.current_user.id:
            return jsonify({'error': 'Unauthorized'}), 403

        if 'title' in request.json:
            book.title = request.json['title']
        if 'description' in request.json:
            book.description = request.json['description']
        if 'price' in request.json:
            new_price_wei = int(float(request.json['price']) * 10**18)
            
            # Update price on blockchain
            tx_result = await eth_handler.update_book_price(
                g.current_user.eth_address,
                book_id,
                new_price_wei,
                g.current_user.eth_private_key
            )
            
            if tx_result['status'] != 'success':
                raise Exception("Failed to update price on blockchain")
                
            book.price = float(request.json['price'])
            book.tx_hash = tx_result['transaction_hash']

        book.updated_at = datetime.utcnow()
        db.session.commit()

        return jsonify({'message': 'Book updated successfully'}), 200

    except Exception as e:
        logger.error(f"Error updating book {book_id}: {str(e)}")
        return jsonify({'error': str(e)}), 500

@book_routes.route('/books/<int:book_id>', methods=['DELETE'])
@token_required
async def delete_book(book_id):
    """Deactivate a book (soft delete)."""
    try:
        book = Book.query.get_or_404(book_id)
        
        if book.author_id != g.current_user.id:
            return jsonify({'error': 'Unauthorized'}), 403

        # Deactivate on blockchain
        tx_result = await eth_handler.deactivate_book(
            g.current_user.eth_address,
            book_id,
            g.current_user.eth_private_key
        )

        if tx_result['status'] != 'success':
            raise Exception("Failed to deactivate book on blockchain")

        book.is_active = False
        book.updated_at = datetime.utcnow()
        db.session.commit()

        return jsonify({'message': 'Book deactivated successfully'}), 200

    except Exception as e:
        logger.error(f"Error deleting book {book_id}: {str(e)}")
        return jsonify({'error': str(e)}), 500

@book_routes.route('/author/books', methods=['GET'])
@token_required
async def get_author_books():
    """Get all books by the authenticated author."""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)
        
        books = Book.query.filter_by(
            author_id=g.current_user.id
        ).paginate(page=page, per_page=per_page, error_out=False)
        
        book_schema = BookSchema(many=True)
        return jsonify({
            'books': book_schema.dump(books.items),
            'total': books.total,
            'pages': books.pages,
            'current_page': books.page
        }), 200

    except Exception as e:
        logger.error(f"Error fetching author books: {str(e)}")
        return jsonify({'error': str(e)}), 500

@book_routes.route('/books/<int:book_id>/download', methods=['GET'])
@token_required
async def download_book(book_id):
    """Download a purchased book."""
    try:
        book = Book.query.get_or_404(book_id)
        
        # Verify purchase
        is_purchased = await eth_handler.verify_purchase(
            g.current_user.eth_address,
            book_id
        )
        
        if not is_purchased and book.author_id != g.current_user.id:
            return jsonify({'error': 'Not purchased'}), 403

        # Get book content from IPFS
        content, success = await ipfs_handler.get_file(book.book_hash)
        
        if not success:
            raise Exception("Failed to retrieve book from IPFS")

        return jsonify({
            'book_content': content.decode('utf-8'),
            'filename': f"{book.title}.pdf"
        }), 200

    except Exception as e:
        logger.error(f"Error downloading book {book_id}: {str(e)}")
        return jsonify({'error': str(e)}), 500

# Additional routes for search and filtering
@book_routes.route('/books/search', methods=['GET'])
async def search_books():
    """Search books by title or description."""
    try:
        query = request.args.get('q', '')
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)
        
        books = Book.query.filter(
            (Book.title.ilike(f'%{query}%') | Book.description.ilike(f'%{query}%')) &
            (Book.is_active == True)
        ).paginate(page=page, per_page=per_page, error_out=False)
        
        book_schema = BookSchema(many=True)
        return jsonify({
            'books': book_schema.dump(books.items),
            'total': books.total,
            'pages': books.pages,
            'current_page': books.page
        }), 200

    except Exception as e:
        logger.error(f"Error searching books: {str(e)}")
        return jsonify({'error': str(e)}), 500