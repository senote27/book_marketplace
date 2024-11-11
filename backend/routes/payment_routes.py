# backend/routes/payment_routes.py

from fastapi import APIRouter, HTTPException, Depends
from web3 import Web3
from typing import Dict
from ..database import get_db
from ..models import User, Book, Transaction
from ..utils.eth import get_contract
from sqlalchemy.orm import Session
import json

router = APIRouter()
w3 = Web3(Web3.HTTPProvider('http://127.0.0.1:8545'))  # Local Ganache for testing

@router.post("/purchase/{book_id}")
async def purchase_book(
    book_id: int,
    buyer_address: str,
    db: Session = Depends(get_db)
):
    try:
        # Get book details
        book = db.query(Book).filter(Book.id == book_id).first()
        if not book:
            raise HTTPException(status_code=404, detail="Book not found")

        # Get seller and author details
        seller = db.query(User).filter(User.id == book.seller_id).first()
        author = db.query(User).filter(User.id == book.author_id).first()

        # Get contract instance
        contract = get_contract()

        # Calculate royalty
        royalty_amount = int(float(book.price) * (book.royalty_percentage / 100))
        seller_amount = int(float(book.price) - royalty_amount)

        # Create transaction in smart contract
        tx_hash = contract.functions.purchaseBook(
            book_id,
            seller.eth_address,
            author.eth_address,
            seller_amount,
            royalty_amount
        ).transact({'from': buyer_address, 'value': book.price})

        # Store transaction in database
        transaction = Transaction(
            book_id=book_id,
            buyer_address=buyer_address,
            seller_address=seller.eth_address,
            amount=book.price,
            status="completed",
            tx_hash=tx_hash.hex()
        )
        db.add(transaction)
        db.commit()

        return {
            "status": "success",
            "tx_hash": tx_hash.hex(),
            "message": "Book purchased successfully"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/transaction/{tx_hash}")
async def get_transaction_status(tx_hash: str, db: Session = Depends(get_db)):
    try:
        # Get transaction receipt from blockchain
        tx_receipt = w3.eth.get_transaction_receipt(tx_hash)
        
        # Get transaction from database
        transaction = db.query(Transaction).filter(Transaction.tx_hash == tx_hash).first()
        
        if not transaction:
            raise HTTPException(status_code=404, detail="Transaction not found")

        return {
            "status": "confirmed" if tx_receipt else "pending",
            "block_number": tx_receipt["blockNumber"] if tx_receipt else None,
            "transaction": {
                "book_id": transaction.book_id,
                "amount": transaction.amount,
                "buyer": transaction.buyer_address,
                "seller": transaction.seller_address,
                "timestamp": transaction.created_at.isoformat()
            }
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/royalties/{author_id}")
async def get_author_royalties(author_id: int, db: Session = Depends(get_db)):
    try:
        # Get all transactions for author's books
        author_books = db.query(Book).filter(Book.author_id == author_id).all()
        book_ids = [book.id for book in author_books]
        
        transactions = db.query(Transaction).filter(
            Transaction.book_id.in_(book_ids)
        ).all()

        total_royalties = sum([
            t.amount * (b.royalty_percentage/100) 
            for t in transactions 
            for b in author_books 
            if b.id == t.book_id
        ])

        return {
            "total_royalties": total_royalties,
            "transaction_count": len(transactions),
            "books_sold": len(set([t.book_id for t in transactions]))
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))