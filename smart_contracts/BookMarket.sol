// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/security/ReentrancyGuard.sol";
import "@openzeppelin/contracts/security/Pausable.sol";
import "@openzeppelin/contracts/utils/Counters.sol";

contract BookMarket is Ownable, ReentrancyGuard, Pausable {
    using Counters for Counters.Counter;
    Counters.Counter private _bookIds;

    struct Book {
        uint256 id;
        string title;
        string ipfsHash;
        uint256 price;
        uint8 royaltyPercentage;
        address payable author;
        bool isAvailable;
        uint256 totalSales;
        uint256 createdAt;
    }

    // Mappings
    mapping(uint256 => Book) private books;
    mapping(address => uint256[]) private authorBooks;
    mapping(address => mapping(uint256 => bool)) private bookPurchases;
    mapping(address => uint256) private authorRoyalties;

    // Events
    event BookListed(uint256 indexed bookId, string title, address indexed author, uint256 price);
    event BookPurchased(uint256 indexed bookId, address indexed buyer, address indexed author, uint256 price);
    event RoyaltyPaid(address indexed author, uint256 amount);
    event BookRemoved(uint256 indexed bookId);
    event PriceUpdated(uint256 indexed bookId, uint256 newPrice);

    // Constants
    uint8 public constant PLATFORM_FEE_PERCENTAGE = 10;
    uint8 public constant MAX_ROYALTY_PERCENTAGE = 25;

    constructor() {
        _bookIds.increment(); // Start book IDs at 1
    }

    // Modifiers
    modifier bookExists(uint256 bookId) {
        require(books[bookId].author != address(0), "Book does not exist");
        _;
    }

    modifier onlyAuthor(uint256 bookId) {
        require(books[bookId].author == msg.sender, "Only book author can perform this action");
        _;
    }

    modifier validPrice(uint256 price) {
        require(price > 0, "Price must be greater than 0");
        _;
    }

    modifier notPurchased(uint256 bookId) {
        require(!bookPurchases[msg.sender][bookId], "Book already purchased");
        _;
    }

    // Main functions
    function listBook(
        string memory title,
        string memory ipfsHash,
        uint256 price,
        uint8 royaltyPercentage
    ) external whenNotPaused validPrice(price) returns (uint256) {
        require(bytes(title).length > 0, "Title cannot be empty");
        require(bytes(ipfsHash).length > 0, "IPFS hash cannot be empty");
        require(royaltyPercentage <= MAX_ROYALTY_PERCENTAGE, "Royalty percentage too high");

        uint256 newBookId = _bookIds.current();

        books[newBookId] = Book({
            id: newBookId,
            title: title,
            ipfsHash: ipfsHash,
            price: price,
            royaltyPercentage: royaltyPercentage,
            author: payable(msg.sender),
            isAvailable: true,
            totalSales: 0,
            createdAt: block.timestamp
        });

        authorBooks[msg.sender].push(newBookId);
        _bookIds.increment();

        emit BookListed(newBookId, title, msg.sender, price);
        return newBookId;
    }

    function purchaseBook(uint256 bookId) 
        external 
        payable
        whenNotPaused
        bookExists(bookId)
        notPurchased(bookId)
        nonReentrant
    {
        Book storage book = books[bookId];
        require(book.isAvailable, "Book is not available");
        require(msg.value >= book.price, "Insufficient payment");

        bookPurchases[msg.sender][bookId] = true;
        book.totalSales++;

        // Calculate fees and royalties
        uint256 platformFee = (msg.value * PLATFORM_FEE_PERCENTAGE) / 100;
        uint256 royalty = (msg.value * book.royaltyPercentage) / 100;
        uint256 authorPayment = msg.value - platformFee - royalty;

        // Update author's royalties
        authorRoyalties[book.author] += royalty;

        // Transfer payments
        (bool success, ) = book.author.call{value: authorPayment}("");
        require(success, "Author payment failed");

        emit BookPurchased(bookId, msg.sender, book.author, msg.value);

        // Refund excess payment
        if (msg.value > book.price) {
            (bool refundSuccess, ) = msg.sender.call{value: msg.value - book.price}("");
            require(refundSuccess, "Refund failed");
        }
    }

    function withdrawRoyalties() external nonReentrant {
        uint256 amount = authorRoyalties[msg.sender];
        require(amount > 0, "No royalties to withdraw");

        authorRoyalties[msg.sender] = 0;
        (bool success, ) = msg.sender.call{value: amount}("");
        require(success, "Royalty withdrawal failed");

        emit RoyaltyPaid(msg.sender, amount);
    }

    // Book management functions
    function updateBookPrice(uint256 bookId, uint256 newPrice) 
        external 
        bookExists(bookId) 
        onlyAuthor(bookId)
        validPrice(newPrice) 
    {
        books[bookId].price = newPrice;
        emit PriceUpdated(bookId, newPrice);
    }

    function removeBook(uint256 bookId) 
        external 
        bookExists(bookId) 
        onlyAuthor(bookId) 
    {
        books[bookId].isAvailable = false;
        emit BookRemoved(bookId);
    }

    // View functions
    function getBook(uint256 bookId) 
        external 
        view 
        bookExists(bookId) 
        returns (
            string memory title,
            string memory ipfsHash,
            uint256 price,
            uint8 royaltyPercentage,
            address author,
            bool isAvailable,
            uint256 totalSales
        ) 
    {
        Book memory book = books[bookId];
        return (
            book.title,
            book.ipfsHash,
            book.price,
            book.royaltyPercentage,
            book.author,
            book.isAvailable,
            book.totalSales
        );
    }

    function getAuthorBooks(address author) external view returns (uint256[] memory) {
        return authorBooks[author];
    }

    function hasUserPurchased(address user, uint256 bookId) external view returns (bool) {
        return bookPurchases[user][bookId];
    }

    function getAuthorRoyalties(address author) external view returns (uint256) {
        return authorRoyalties[author];
    }

    // Admin functions
    function pause() external onlyOwner {
        _pause();
    }

    function unpause() external onlyOwner {
        _unpause();
    }

    function withdrawPlatformFees() external onlyOwner {
        uint256 balance = address(this).balance;
        require(balance > 0, "No fees to withdraw");
        (bool success, ) = owner().call{value: balance}("");
        require(success, "Platform fee withdrawal failed");
    }
}