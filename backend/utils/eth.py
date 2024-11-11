from web3 import Web3
from web3.middleware import geth_poa_middleware
import json
import os
from typing import Dict, Any, Optional, Tuple, List
import logging
from eth_account.messages import encode_defunct
from datetime import datetime

class EthereumHandler:
    # Ganache-specific configuration
    GANACHE_CONFIG = {
        'PROVIDER_URL': 'http://localhost:7545',
        'CHAIN_ID': 1337,
        'NETWORK_ID': '5777',
        'GAS_LIMIT': 6721975,
        'DEFAULT_GAS_PRICE': 20000000000  # 20 gwei
    }

    def __init__(self, provider_url: str = None):
        """Initialize Ethereum connection with Ganache."""
        self.provider_url = provider_url or self.GANACHE_CONFIG['PROVIDER_URL']
        self.w3 = Web3(Web3.HTTPProvider(self.provider_url))
        # Remove POA middleware for Ganache
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

            # Test account access
            accounts = self.w3.eth.accounts
            if not accounts:
                raise ValueError("No accounts available on Ganache")

            self.logger.info(f"Successfully connected to Ganache at {self.provider_url}")
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
            # Use Ganache network ID
            self.contract_address = contract_data['networks'][self.GANACHE_CONFIG['NETWORK_ID']]['address']
            
            self.contract = self.w3.eth.contract(
                address=self.contract_address,
                abi=self.contract_abi
            )
            self.logger.info(f"Contract loaded at {self.contract_address} on Ganache")

        except Exception as e:
            self.logger.error(f"Error loading contract on Ganache: {str(e)}")
            self.contract = None
            raise

    def get_gas_price(self) -> int:
        """Get current gas price with caching for Ganache."""
        current_time = datetime.now().timestamp()
        if current_time - self.gas_price_cache['timestamp'] > 60:  # Cache for 1 minute
            try:
                gas_price = self.w3.eth.gas_price
                self.gas_price_cache = {
                    'timestamp': current_time,
                    'price': gas_price
                }
            except Exception as e:
                self.logger.warning(f"Using default Ganache gas price: {str(e)}")
                self.gas_price_cache = {
                    'timestamp': current_time,
                    'price': self.GANACHE_CONFIG['DEFAULT_GAS_PRICE']
                }
        return self.gas_price_cache['price']

    async def list_book(
        self,
        sender_address: str,
        ipfs_hash: str,
        price: int,
        royalty: int,
        private_key: str
    ) -> Dict[str, Any]:
        """List a book on the Ganache marketplace."""
        try:
            nonce = self.w3.eth.get_transaction_count(sender_address)
            gas_price = self.get_gas_price()

            # Prepare transaction with Ganache-specific gas limits
            transaction = self.contract.functions.listBook(
                ipfs_hash,
                price,
                royalty
            ).build_transaction({
                'from': sender_address,
                'gas': min(2000000, self.GANACHE_CONFIG['GAS_LIMIT']),
                'gasPrice': gas_price,
                'nonce': nonce,
            })

            # Sign and send transaction
            signed_txn = self.w3.eth.account.sign_transaction(
                transaction, private_key
            )
            tx_hash = self.w3.eth.send_raw_transaction(signed_txn.rawTransaction)
            
            # Wait for transaction receipt with higher timeout for Ganache
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
            
            return {
                'status': 'success',
                'transaction_hash': tx_hash.hex(),
                'block_number': receipt['blockNumber'],
                'gas_used': receipt['gasUsed']
            }

        except Exception as e:
            self.logger.error(f"Error listing book on Ganache: {str(e)}")
            return {
                'status': 'error',
                'message': str(e)
            }

    async def purchase_book(
        self,
        buyer_address: str,
        book_id: int,
        value: int,
        private_key: str
    ) -> Dict[str, Any]:
        """Purchase a book from the Ganache marketplace."""
        try:
            nonce = self.w3.eth.get_transaction_count(buyer_address)
            gas_price = self.get_gas_price()

            transaction = self.contract.functions.purchaseBook(
                book_id
            ).build_transaction({
                'from': buyer_address,
                'gas': min(2000000, self.GANACHE_CONFIG['GAS_LIMIT']),
                'gasPrice': gas_price,
                'nonce': nonce,
                'value': value
            })

            signed_txn = self.w3.eth.account.sign_transaction(
                transaction, private_key
            )
            tx_hash = self.w3.eth.send_raw_transaction(signed_txn.rawTransaction)
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)

            return {
                'status': 'success',
                'transaction_hash': tx_hash.hex(),
                'block_number': receipt['blockNumber'],
                'gas_used': receipt['gasUsed']
            }

        except Exception as e:
            self.logger.error(f"Error purchasing book on Ganache: {str(e)}")
            return {
                'status': 'error',
                'message': str(e)
            }

    async def get_book_details(self, book_id: int) -> Dict[str, Any]:
        """Get details of a listed book from Ganache."""
        try:
            book = await self.contract.functions.books(book_id).call()
            return {
                'id': book_id,
                'ipfs_hash': book[0],
                'author': book[1],
                'price': book[2],
                'royalty': book[3],
                'is_available': book[4]
            }
        except Exception as e:
            self.logger.error(f"Error getting book details from Ganache: {str(e)}")
            return {}

    async def get_author_books(self, author_address: str) -> List[Dict[str, Any]]:
        """Get all books by an author from Ganache."""
        try:
            book_count = await self.contract.functions.getAuthorBookCount(
                author_address
            ).call()
            
            books = []
            for i in range(book_count):
                book_id = await self.contract.functions.authorBooks(
                    author_address, i
                ).call()
                book_details = await self.get_book_details(book_id)
                if book_details:
                    books.append(book_details)
            
            return books

        except Exception as e:
            self.logger.error(f"Error getting author books from Ganache: {str(e)}")
            return []

    async def get_royalties(self, author_address: str) -> int:
        """Get available royalties for an author from Ganache."""
        try:
            return await self.contract.functions.getRoyalties(
                author_address
            ).call()
        except Exception as e:
            self.logger.error(f"Error getting royalties from Ganache: {str(e)}")
            return 0

    async def withdraw_royalties(
        self,
        author_address: str,
        private_key: str
    ) -> Dict[str, Any]:
        """Withdraw available royalties from Ganache."""
        try:
            nonce = self.w3.eth.get_transaction_count(author_address)
            gas_price = self.get_gas_price()

            transaction = self.contract.functions.withdrawRoyalties(
            ).build_transaction({
                'from': author_address,
                'gas': min(2000000, self.GANACHE_CONFIG['GAS_LIMIT']),
                'gasPrice': gas_price,
                'nonce': nonce,
            })

            signed_txn = self.w3.eth.account.sign_transaction(
                transaction, private_key
            )
            tx_hash = self.w3.eth.send_raw_transaction(signed_txn.rawTransaction)
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)

            return {
                'status': 'success',
                'transaction_hash': tx_hash.hex(),
                'block_number': receipt['blockNumber'],
                'gas_used': receipt['gasUsed']
            }

        except Exception as e:
            self.logger.error(f"Error withdrawing royalties from Ganache: {str(e)}")
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
        """Verify an Ethereum signature on Ganache."""
        try:
            message_hash = encode_defunct(text=message)
            recovered_address = self.w3.eth.account.recover_message(
                message_hash,
                signature=signature
            )
            return recovered_address.lower() == address.lower()
        except Exception as e:
            self.logger.error(f"Error verifying signature on Ganache: {str(e)}")
            return False

    def get_ganache_accounts(self) -> List[str]:
        """Get list of available Ganache accounts."""
        try:
            return self.w3.eth.accounts
        except Exception as e:
            self.logger.error(f"Error getting Ganache accounts: {str(e)}")
            return []

    def get_account_balance(self, address: str) -> int:
        """Get balance of a Ganache account."""
        try:
            return self.w3.eth.get_balance(address)
        except Exception as e:
            self.logger.error(f"Error getting account balance from Ganache: {str(e)}")
            return 0