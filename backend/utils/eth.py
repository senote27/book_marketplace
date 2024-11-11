from web3 import Web3
from web3.middleware import geth_poa_middleware
import json
import os
from typing import Dict, Any, Optional, Tuple, List
import logging
from eth_account.messages import encode_defunct
from datetime import datetime

class EthereumHandler:
    # Ganache-specific configurations
    GANACHE_CONFIG = {
        'PROVIDER_URL': 'http://localhost:7545',
        'CHAIN_ID': 1337,
        'NETWORK_ID': '5777',
        'GAS_LIMIT': 6721975,
        'DEFAULT_GAS_PRICE': 20000000000  # 20 gwei
    }

    def __init__(self, provider_url: str = GANACHE_CONFIG['PROVIDER_URL']):
        """Initialize Ethereum connection with Ganache."""
        self.w3 = Web3(Web3.HTTPProvider(provider_url))
        # Remove POA middleware as Ganache doesn't require it
        # self.w3.middleware_onion.inject(geth_poa_middleware, layer=0)
        self.setup_logging()
        self.verify_ganache_connection()
        self.load_contract()
        self.gas_price_cache = {'timestamp': 0, 'price': self.GANACHE_CONFIG['DEFAULT_GAS_PRICE']}

    def setup_logging(self):
        """Set up logging for Ethereum operations."""
        self.logger = logging.getLogger('ethereum_handler')
        self.logger.setLevel(logging.INFO)
        handler = logging.StreamHandler()
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)

    def verify_ganache_connection(self) -> bool:
        """Verify connection to Ganache network."""
        try:
            if not self.w3.is_connected():
                raise ConnectionError("Not connected to Ganache network")

            network_id = self.w3.net.version
            if network_id != self.GANACHE_CONFIG['NETWORK_ID']:
                raise ValueError(f"Connected to network {network_id}, expected Ganache network {self.GANACHE_CONFIG['NETWORK_ID']}")

            # Verify we have access to accounts (Ganache should provide 10 funded accounts)
            accounts = self.w3.eth.accounts
            if not accounts:
                raise ValueError("No accounts available on Ganache")

            self.logger.info(f"Successfully connected to Ganache. Available accounts: {len(accounts)}")
            return True

        except Exception as e:
            self.logger.error(f"Ganache connection verification failed: {str(e)}")
            raise

    def load_contract(self):
        """Load smart contract ABI and address for Ganache network."""
        try:
            contract_path = os.path.join(
                os.path.dirname(__file__),
                '../../smart_contracts/build/contracts/BookMarket.json'
            )
            
            with open(contract_path, 'r') as f:
                contract_data = json.load(f)
            
            self.contract_abi = contract_data['abi']
            
            # Specifically look for Ganache network deployment
            self.contract_address = contract_data['networks'][self.GANACHE_CONFIG['NETWORK_ID']]['address']
            
            self.contract = self.w3.eth.contract(
                address=self.contract_address,
                abi=self.contract_abi
            )
            self.logger.info(f"Contract loaded at {self.contract_address} on Ganache network")

        except Exception as e:
            self.logger.error(f"Error loading contract: {str(e)}")
            self.contract = None
            raise

    def get_gas_price(self) -> int:
        """Get current gas price with caching for Ganache."""
        current_time = datetime.now().timestamp()
        if current_time - self.gas_price_cache['timestamp'] > 60:  # Cache for 1 minute
            try:
                self.gas_price_cache = {
                    'timestamp': current_time,
                    'price': self.w3.eth.gas_price
                }
            except Exception as e:
                self.logger.warning(f"Failed to get gas price: {str(e)}. Using default Ganache gas price.")
                self.gas_price_cache = {
                    'timestamp': current_time,
                    'price': self.GANACHE_CONFIG['DEFAULT_GAS_PRICE']
                }
        return self.gas_price_cache['price']

    async def get_book_details(self, book_id: int) -> Dict[str, Any]:
        """Get details of a listed book."""
        try:
            # For Ganache, we don't need to await this call
            book = self.contract.functions.books(book_id).call()
            return {
                'id': book_id,
                'ipfs_hash': book[0],
                'author': book[1],
                'price': book[2],
                'royalty': book[3],
                'is_available': book[4]
            }
        except Exception as e:
            self.logger.error(f"Error getting book details: {str(e)}")
            return {}

    async def get_author_books(self, author_address: str) -> List[Dict[str, Any]]:
        """Get all books by an author."""
        try:
            # For Ganache, we don't need to await these calls
            book_count = self.contract.functions.getAuthorBookCount(
                author_address
            ).call()
            
            books = []
            for i in range(book_count):
                book_id = self.contract.functions.authorBooks(
                    author_address, i
                ).call()
                book_details = await self.get_book_details(book_id)
                if book_details:
                    books.append(book_details)
            
            return books

        except Exception as e:
            self.logger.error(f"Error getting author books: {str(e)}")
            return []

    async def get_royalties(self, author_address: str) -> int:
        """Get available royalties for an author."""
        try:
            # For Ganache, we don't need to await this call
            return self.contract.functions.getRoyalties(
                author_address
            ).call()
        except Exception as e:
            self.logger.error(f"Error getting royalties: {str(e)}")
            return 0

    async def withdraw_royalties(
        self,
        author_address: str,
        private_key: str
    ) -> Dict[str, Any]:
        """Withdraw available royalties."""
        try:
            nonce = self.w3.eth.get_transaction_count(author_address)
            gas_price = self.get_gas_price()

            # Build transaction with Ganache-specific gas settings
            transaction = self.contract.functions.withdrawRoyalties().build_transaction({
                'from': author_address,
                'gas': min(2000000, self.GANACHE_CONFIG['GAS_LIMIT']),
                'gasPrice': gas_price,
                'nonce': nonce,
                'chainId': self.GANACHE_CONFIG['CHAIN_ID']
            })

            signed_txn = self.w3.eth.account.sign_transaction(
                transaction, private_key
            )
            tx_hash = self.w3.eth.send_raw_transaction(signed_txn.rawTransaction)
            
            # Ganache mines blocks instantly, so we can wait for receipt
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)

            return {
                'status': 'success',
                'transaction_hash': tx_hash.hex(),
                'block_number': receipt['blockNumber'],
                'gas_used': receipt['gasUsed']
            }

        except Exception as e:
            self.logger.error(f"Error withdrawing royalties: {str(e)}")
            return {
                'status': 'error',
                'message': str(e)
            }

    def verify_signature(
        self,
        message: str,
        signature: str,
        address: str
    ) -> bool:
        """Verify an Ethereum signature."""
        try:
            message_hash = encode_defunct(text=message)
            recovered_address = self.w3.eth.account.recover_message(
                message_hash,
                signature=signature
            )
            return recovered_address.lower() == address.lower()
        except Exception as e:
            self.logger.error(f"Error verifying signature: {str(e)}")
            return False

    def get_ganache_accounts(self) -> List[str]:
        """Get list of available Ganache accounts."""
        try:
            return self.w3.eth.accounts
        except Exception as e:
            self.logger.error(f"Error getting Ganache accounts: {str(e)}")
            return []