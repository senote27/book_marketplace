# backend/routes/book_routes.py
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from typing import List, Optional
import ipfshttpclient
from datetime import datetime

from ..database import get_db
from ..models import Book, User, Transaction
from ..schemas import BookCreate, BookUpdate, BookResponse
from ..utils.auth import get_current_user
from ..utils.ipfs import IPFSManager

router = APIRouter()
ipfs = IPFSManager()

@router.post("/books/", response_model=BookResponse)
async def create_book(
    title: str = Form(...),
    description: str = Form(...),
    price: float = Form(...),
    royalty_percentage: float = Form(...),
    pdf_file: UploadFile = File(...),
    cover_file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role not in ['author', 'seller']:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    try:
        # Upload files to IPFS
        pdf_hash = await ipfs.add_file(pdf_file)
        cover_hash = await ipfs.add_file(cover_file)

        book = Book(
            title=title,
            description=description,
            price=price,
            royalty_percentage=royalty_percentage,
            pdf_hash=pdf_hash,
            cover_hash=cover_hash,
            author_id=current_user.id if current_user.role == 'author' else None,
            seller_id=current_user.id if current_user.role == 'seller' else None,
            is_active=True,
            created_at=datetime.utcnow()
        )
        
        db.add(book)
        db.commit()
        db.refresh(book)
        
        return book
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/books/", response_model=List[BookResponse])
async def list_books(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    books = db.query(Book).filter(Book.is_active == True).offset(skip).limit(limit).all()
    return books

@router.get("/books/{book_id}", response_model=BookResponse)
async def get_book(
    book_id: int,
    db: Session = Depends(get_db)
):
    book = db.query(Book).filter(Book.id == book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    return book

@router.put("/books/{book_id}", response_model=BookResponse)
async def update_book(
    book_id: int,
    book_update: BookUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    book = db.query(Book).filter(Book.id == book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    
    if (book.author_id != current_user.id and book.seller_id != current_user.id):
        raise HTTPException(status_code=403, detail="Not authorized")
    
    for key, value in book_update.dict(exclude_unset=True).items():
        setattr(book, key, value)
    
    db.commit()
    db.refresh(book)
    return book

@router.get("/author/books/", response_model=List[BookResponse])
async def get_author_books(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role != 'author':
        raise HTTPException(status_code=403, detail="Not authorized")
    
    books = db.query(Book).filter(Book.author_id == current_user.id).all()
    return books

@router.get("/seller/books/", response_model=List[BookResponse])
async def get_seller_books(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role != 'seller':
        raise HTTPException(status_code=403, detail="Not authorized")
    
    books = db.query(Book).filter(Book.seller_id == current_user.id).all()
    return books

@router.get("/books/{book_id}/download")
async def download_book(
    book_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    book = db.query(Book).filter(Book.id == book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    
    # Check if user has purchased the book
    purchase = db.query(Transaction).filter(
        Transaction.book_id == book_id,
        Transaction.buyer_address == current_user.eth_address,
        Transaction.status == "completed"
    ).first()
    
    if not purchase:
        raise HTTPException(status_code=403, detail="Book not purchased")
    
    return {"download_url": f"http://localhost:8080/ipfs/{book.pdf_hash}"}

@router.put("/books/{book_id}/status")
async def update_book_status(
    book_id: int,
    is_active: bool,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    book = db.query(Book).filter(Book.id == book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    
    if (book.author_id != current_user.id and book.seller_id != current_user.id):
        raise HTTPException(status_code=403, detail="Not authorized")
    
    book.is_active = is_active
    db.commit()
    
    return {"message": "Status updated successfully"}

@router.get("/books/{book_id}/sales")
async def get_book_sales(
    book_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    book = db.query(Book).filter(Book.id == book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    
    if (book.author_id != current_user.id and book.seller_id != current_user.id):
        raise HTTPException(status_code=403, detail="Not authorized")
    
    transactions = db.query(Transaction).filter(
        Transaction.book_id == book_id,
        Transaction.status == "completed"
    ).all()
    
    total_sales = len(transactions)
    total_revenue = sum(t.amount for t in transactions)
    total_royalties = sum(t.amount * (book.royalty_percentage/100) for t in transactions)
    
    return {
        "total_sales": total_sales,
        "total_revenue": total_revenue,
        "total_royalties": total_royalties,
        "transactions": transactions
    }