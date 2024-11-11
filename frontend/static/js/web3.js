// web3.js
const Web3Handler = {
    web3: null,
    contract: null,
    account: null,

    // Contract ABI will need to be replaced with your actual contract ABI
    contractABI: [], // You'll add this after compiling your smart contract
    contractAddress: '', // You'll add this after deploying your contract

    async init() {
        try {
            // Check if MetaMask is installed
            if (typeof window.ethereum === 'undefined') {
                alert('Please install MetaMask to use this application');
                return false;
            }

            // Request account access
            this.account = await window.ethereum.request({ method: 'eth_requestAccounts' });
            this.web3 = new Web3(window.ethereum);
            
            // Update account when user changes account in MetaMask
            window.ethereum.on('accountsChanged', (accounts) => {
                this.account = accounts[0];
                this.updateUIWithAddress();
            });

            this.updateUIWithAddress();
            return true;
        } catch (error) {
            console.error('Error initializing Web3:', error);
            return false;
        }
    },

    updateUIWithAddress() {
        const addressElement = document.getElementById('wallet-address');
        if (addressElement && this.account) {
            addressElement.textContent = `${this.account[0].substr(0, 6)}...${this.account[0].substr(-4)}`;
        }
    },

    async sendTransaction(toAddress, amount) {
        try {
            const transaction = await this.web3.eth.sendTransaction({
                from: this.account[0],
                to: toAddress,
                value: this.web3.utils.toWei(amount.toString(), 'ether')
            });
            return transaction;
        } catch (error) {
            console.error('Transaction failed:', error);
            throw error;
        }
    }
};

// Initialize Web3 when the page loads
document.addEventListener('DOMContentLoaded', () => {
    Web3Handler.init();
});