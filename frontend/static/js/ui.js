// UI Handler Class
const UIHandler = {
    // Constants
    GANACHE_NETWORK: {
        chainId: '0x539', // 1337 in hex
        chainName: 'Ganache',
        nativeCurrency: {
            name: 'ETH',
            symbol: 'ETH',
            decimals: 18
        },
        rpcUrls: ['http://127.0.0.1:7545'],
        blockExplorerUrls: []
    },
    IPFS_GATEWAY: 'http://localhost:8080/ipfs',
    IPFS_GATEWAY_FALLBACK: 'https://ipfs.io/ipfs',

    // Initialize UI components
    async init() {
        this.setupEventListeners();
        await this.checkNetwork();
        await this.updateDashboard();
    },

    // Set up event listeners for UI interactions
    setupEventListeners() {
        // Connect wallet button
        const connectBtn = document.getElementById('connect-wallet');
        if (connectBtn) {
            connectBtn.addEventListener('click', async () => {
                await this.connectWallet();
            });
        }

        // Network switch listener
        if (window.ethereum) {
            window.ethereum.on('chainChanged', () => {
                window.location.reload();
            });
            window.ethereum.on('accountsChanged', () => {
                window.location.reload();
            });
        }

        // Book purchase buttons
        document.querySelectorAll('.purchase-btn').forEach(button => {
            button.addEventListener('click', async (e) => {
                await this.handleBookPurchase(e.target.dataset.bookId, e.target.dataset.price);
            });
        });

        // Upload book form
        const uploadForm = document.getElementById('book-upload-form');
        if (uploadForm) {
            uploadForm.addEventListener('submit', async (e) => {
                e.preventDefault();
                await this.handleBookUpload(e);
            });
        }
    },

    // Check and switch to Ganache network if needed
    async checkNetwork() {
        if (!window.ethereum) {
            this.showError('Please install MetaMask to use this application');
            return false;
        }

        try {
            // Get current chain ID
            const chainId = await window.ethereum.request({ method: 'eth_chainId' });
            
            if (chainId !== this.GANACHE_NETWORK.chainId) {
                await this.switchToGanache();
            }
            return true;
        } catch (error) {
            this.showError('Network switch failed: ' + error.message);
            return false;
        }
    },

    // Switch to Ganache network
    async switchToGanache() {
        try {
            // Try to switch to Ganache
            await window.ethereum.request({
                method: 'wallet_switchEthereumChain',
                params: [{ chainId: this.GANACHE_NETWORK.chainId }],
            });
        } catch (switchError) {
            // If network doesn't exist, add it
            if (switchError.code === 4902) {
                try {
                    await window.ethereum.request({
                        method: 'wallet_addEthereumChain',
                        params: [this.GANACHE_NETWORK],
                    });
                } catch (addError) {
                    throw new Error('Failed to add Ganache network: ' + addError.message);
                }
            } else {
                throw switchError;
            }
        }
    },

    // Connect wallet
    async connectWallet() {
        if (!window.ethereum) {
            this.showError('Please install MetaMask');
            return null;
        }

        try {
            await this.checkNetwork();
            const accounts = await window.ethereum.request({
                method: 'eth_requestAccounts'
            });
            
            if (accounts.length > 0) {
                document.getElementById('wallet-address').textContent = 
                    accounts[0].substring(0, 6) + '...' + accounts[0].substring(38);
                return accounts[0];
            }
        } catch (error) {
            this.showError('Failed to connect wallet: ' + error.message);
            return null;
        }
    },

    // Update dashboard based on user role
    async updateDashboard() {
        const dashboardContent = document.getElementById('dashboard-content');
        if (!dashboardContent) return;

        try {
            const response = await fetch('/api/dashboard/data');
            if (!response.ok) throw new Error('Failed to fetch dashboard data');
            
            const data = await response.json();
            
            switch (data.userRole) {
                case 'author':
                    await this.updateAuthorDashboard(data);
                    break;
                case 'seller':
                    await this.updateSellerDashboard(data);
                    break;
                default:
                    await this.updateBuyerDashboard(data);
            }
        } catch (error) {
            this.showError('Dashboard update failed: ' + error.message);
        }
    },

    // Update author dashboard
    async updateAuthorDashboard(data) {
        const container = document.getElementById('dashboard-content');
        const earnings = this.formatEther(data.totalEarnings);
        
        container.innerHTML = `
            <div class="dashboard-stats">
                <div class="stat-card">
                    <h3>Published Books</h3>
                    <p>${data.publishedBooks}</p>
                </div>
                <div class="stat-card">
                    <h3>Total Sales</h3>
                    <p>${data.totalSales}</p>
                </div>
                <div class="stat-card">
                    <h3>Earnings</h3>
                    <p>${earnings} ETH</p>
                </div>
            </div>
            <div class="books-list">
                ${await this.renderBooksList(data.books, true)}
            </div>
        `;
    },

    // Update seller dashboard
    async updateSellerDashboard(data) {
        const container = document.getElementById('dashboard-content');
        const revenue = this.formatEther(data.totalRevenue);
        
        container.innerHTML = `
            <div class="dashboard-stats">
                <div class="stat-card">
                    <h3>Listed Books</h3>
                    <p>${data.listedBooks}</p>
                </div>
                <div class="stat-card">
                    <h3>Active Sales</h3>
                    <p>${data.activeSales}</p>
                </div>
                <div class="stat-card">
                    <h3>Revenue</h3>
                    <p>${revenue} ETH</p>
                </div>
            </div>
            <div class="books-list">
                ${await this.renderBooksList(data.books, false)}
            </div>
        `;
    },

    // Update buyer dashboard
    async updateBuyerDashboard(data) {
        const container = document.getElementById('dashboard-content');
        
        container.innerHTML = `
            <div class="dashboard-stats">
                <div class="stat-card">
                    <h3>Purchased Books</h3>
                    <p>${data.purchasedBooks}</p>
                </div>
                <div class="stat-card">
                    <h3>Total Spent</h3>
                    <p>${this.formatEther(data.totalSpent)} ETH</p>
                </div>
            </div>
            <div class="books-list">
                ${await this.renderBooksList(data.books, false)}
            </div>
        `;
    },

    // Render books list with IPFS links
    async renderBooksList(books, isAuthor) {
        return books.map(book => `
            <div class="book-card">
                <img src="${this.getIPFSUrl(book.coverHash)}" alt="${book.title}" />
                <h3>${book.title}</h3>
                <p>${book.description}</p>
                <p>Price: ${this.formatEther(book.price)} ETH</p>
                ${isAuthor ? this.getAuthorControls(book) : this.getBuyerControls(book)}
            </div>
        `).join('');
    },

    // Get IPFS URL with fallback
    getIPFSUrl(hash) {
        const url = `${this.IPFS_GATEWAY}/${hash}`;
        return {
            url,
            fallback: `${this.IPFS_GATEWAY_FALLBACK}/${hash}`
        };
    },

    // Format ether value
    formatEther(wei) {
        return parseFloat(Web3.utils.fromWei(wei, 'ether')).toFixed(4);
    },

    // Show error message
    showError(message) {
        const errorDiv = document.createElement('div');
        errorDiv.className = 'error-message';
        errorDiv.textContent = message;
        document.body.appendChild(errorDiv);
        setTimeout(() => errorDiv.remove(), 5000);
    },

    // Show success message
    showSuccess(message) {
        const successDiv = document.createElement('div');
        successDiv.className = 'success-message';
        successDiv.textContent = message;
        document.body.appendChild(successDiv);
        setTimeout(() => successDiv.remove(), 3000);
    }
};

// Initialize UI when document is ready
document.addEventListener('DOMContentLoaded', () => {
    UIHandler.init().catch(error => {
        console.error('Initialization failed:', error);
        UIHandler.showError('Failed to initialize application');
    });
});