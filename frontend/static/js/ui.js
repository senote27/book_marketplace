// ui.js
const UIHandler = {
    // Initialize UI components
    init() {
        this.setupEventListeners();
        this.updateDashboard();
    },

    // Set up event listeners for UI interactions
    setupEventListeners() {
        // Toggle mobile menu
        const menuButton = document.getElementById('mobile-menu');
        if (menuButton) {
            menuButton.addEventListener('click', () => {
                const nav = document.querySelector('nav');
                nav.classList.toggle('active');
            });
        }

        // Book purchase buttons
        document.querySelectorAll('.purchase-btn').forEach(button => {
            button.addEventListener('click', async (e) => {
                const bookId = e.target.dataset.bookId;
                const price = e.target.dataset.price;
                await this.handleBookPurchase(bookId, price);
            });
        });

        // Upload book form
        const uploadForm = document.getElementById('book-upload-form');
        if (uploadForm) {
            uploadForm.addEventListener('submit', this.handleBookUpload.bind(this));
        }
    },

    // Handle book purchase
    async handleBookPurchase(bookId, price) {
        try {
            if (!Web3Handler.account) {
                alert('Please connect your MetaMask wallet first');
                return;
            }

            const response = await fetch('/api/books/purchase', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ bookId, price })
            });

            if (!response.ok) throw new Error('Purchase failed');
            
            alert('Purchase successful!');
            this.updateDashboard();
        } catch (error) {
            alert('Purchase failed: ' + error.message);
        }
    },

    // Handle book upload
    async handleBookUpload(e) {
        e.preventDefault();
        const formData = new FormData(e.target);
        
        try {
            // Upload file to IPFS first
            const file = formData.get('book-file');
            const ipfsHash = await IPFSHandler.uploadFile(file);

            // Then save book details
            const response = await fetch('/api/books/create', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    title: formData.get('title'),
                    price: formData.get('price'),
                    ipfsHash: ipfsHash
                })
            });

            if (!response.ok) throw new Error('Failed to save book details');

            alert('Book uploaded successfully!');
            this.updateDashboard();
        } catch (error) {
            alert('Upload failed: ' + error.message);
        }
    },

    // Update dashboard data
    async updateDashboard() {
        const dashboardContent = document.getElementById('dashboard-content');
        if (!dashboardContent) return;

        try {
            const response = await fetch('/api/dashboard/data');
            const data = await response.json();
            
            // Update UI based on user role
            if (data.userRole === 'author') {
                this.updateAuthorDashboard(data);
            } else if (data.userRole === 'seller') {
                this.updateSellerDashboard(data);
            } else {
                this.updateUserDashboard(data);
            }
        } catch (error) {
            console.error('Failed to update dashboard:', error);
        }
    },

    // Update author dashboard
    updateAuthorDashboard(data) {
        const container = document.getElementById('dashboard-content');
        if (!container) return;

        container.innerHTML = `
            <div class="stats">
                <div>Total Books: ${data.totalBooks}</div>
                <div>Total Sales: ${data.totalSales} ETH</div>
                <div>Total Royalties: ${data.totalRoyalties} ETH</div>
            </div>
            <div class="books-list">
                ${data.books.map(book => `
                    <div class="book-card">
                        <h3>${book.title}</h3>
                        <p>Price: ${book.price} ETH</p>
                        <p>Sales: ${book.sales}</p>
                    </div>
                `).join('')}
            </div>
        `;
    },

    // Update seller dashboard
    updateSellerDashboard(data) {
        // Similar to author dashboard but with seller-specific data
    },

    // Update user dashboard
    updateUserDashboard(data) {
        // Similar to author dashboard but with user-specific data
    }
};

// Initialize UI when page loads
document.addEventListener('DOMContentLoaded', () => {
    UIHandler.init();
});