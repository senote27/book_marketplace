from web3 import Web3
from web3.middleware import geth_poa_middleware
import json
import os
from typing import Dict, Any, Optional, Tuple, List
import logging
from eth_account.messages import encode_defunct
from datetime import datetime, timedelta
from web3.exceptions import TransactionNotFound, TimeExhausted

class EthereumError(Exception):
    """Base exception for Ethereum-related errors"""
    pass

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
        self.setup_logging()
        self.verify_ganache_connection()
        self.load_contract()
        self.gas_price_cache = {
            'timestamp': 0,
            'price': self.GANACHE_CONFIG['DEFAULT_GAS_PRICE'],
            'cache_duration': 30  # Cache duration in seconds
        }

    def setup_logging(self):
        """Set up logging for Ethereum operations."""
        self.logger = logging.getLogger('ethereum_handler')
        self.logger.setLevel(logging.INFO)
        handler = logging.StreamHandler()
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)

    def verify_ganache_connection(self) -> bool:
        """Verify connection to Ganache network with enhanced error handling."""
        try:
            if not self.w3.is_connected():
                raise EthereumError("Not connected to Ganache network")

            network_id = self.w3.net.version
            if network_id != self.GANACHE_CONFIG['NETWORK_ID']:
                raise EthereumError(
                    f"Wrong network ID. Expected {self.GANACHE_CONFIG['NETWORK_ID']}, got {network_id}"
                )

            chain_id = self.w3.eth.chain_id
            if chain_id != self.GANACHE_CONFIG['CHAIN_ID']:
                raise EthereumError(
                    f"Wrong chain ID. Expected {self.GANACHE_CONFIG['CHAIN_ID']}, got {chain_id}"
                )

            # Verify we have access to accounts
            accounts = self.w3.eth.accounts
            if not accounts:
                raise EthereumError("No accounts available on Ganache")

            # Verify account balances
            for account in accounts[:1]:  # Check at least one account
                balance = self.w3.eth.get_balance(account)
                if balance == 0:
                    self.logger.warning(f"Account {account} has zero balance")

            self.logger.info(f"Successfully connected to Ganache. Available accounts: {len(accounts)}")
            return True

        except Exception as e:
            self.logger.error(f"Ganache connection verification failed: {str(e)}")
            raise EthereumError(f"Ganache connection error: {str(e)}")

    def load_contract(self):
        """Load smart contract ABI and address for Ganache network with error handling."""
        try:
            contract_path = os.path.join(
                os.path.dirname(__file__),
                '../../smart_contracts/build/contracts/BookMarket.json'
            )
            
            if not os.path.exists(contract_path):
                raise EthereumError(f"Contract file not found at {contract_path}")
            
            with open(contract_path, 'r') as f:
                contract_data = json.load(f)
            
            self.contract_abi = contract_data.get('abi')
            if not self.contract_abi:
                raise EthereumError("Contract ABI not found in contract file")
            
            # Get network-specific address
            networks = contract_data.get('networks', {})
            network_data = networks.get(self.GANACHE_CONFIG['NETWORK_ID'])
            
            if not network_data or 'address' not in network_data:
                raise EthereumError(
                    f"Contract not deployed on Ganache network {self.GANACHE_CONFIG['NETWORK_ID']}"
                )
            
            self.contract_address = network_data['address']
            self.contract = self.w3.eth.contract(
                address=self.contract_address,
                abi=self.contract_abi
            )
            
            # Verify contract code exists at address
            code = self.w3.eth.get_code(self.contract_address)
            if code == b'':
                raise EthereumError(f"No contract code found at {self.contract_address}")
            
            self.logger.info(f"Contract loaded at {self.contract_address} on Ganache network")

        except Exception as e:
            self.logger.error(f"Error loading contract: {str(e)}")
            raise EthereumError(f"Contract loading error: {str(e)}")

    def get_gas_price(self) -> int:
        """
        Get current gas price with caching and fallback mechanism.
        Returns:
            int: Gas price in Wei
        """
        current_time = datetime.now().timestamp()
        
        # Return cached price if still valid
        if (current_time - self.gas_price_cache['timestamp']) < self.gas_price_cache['cache_duration']:
            return self.gas_price_cache['price']
        
        try:
            # Get current gas price from network
            gas_price = self.w3.eth.gas_price
            
            # Validate gas price
            if gas_price < 1000000000:  # 1 gwei
                self.logger.warning("Gas price too low, using default")
                gas_price = self.GANACHE_CONFIG['DEFAULT_GAS_PRICE']
            elif gas_price > 500000000000:  # 500 gwei
                self.logger.warning("Gas price too high, using default")
                gas_price = self.GANACHE_CONFIG['DEFAULT_GAS_PRICE']
            
            # Update cache
            self.gas_price_cache.update({
                'timestamp': current_time,
                'price': gas_price
            })
            
            return gas_price
        
        except Exception as e:
            self.logger.error(f"Error getting gas price: {str(e)}")
            # Return last known price or default
            return self.gas_price_cache['price']

    async def deploy_contract(self, account: str, contract_path: str) -> str:
        """
        Deploy contract to Ganache network
        Args:
            account: Address to deploy from
            contract_path: Path to contract JSON file
        Returns:
            str: Deployed contract address
        """
        try:
            with open(contract_path) as f:
                contract_json = json.load(f)
            
            contract = self.w3.eth.contract(
                abi=contract_json['abi'],
                bytecode=contract_json['bytecode']
            )
            
            # Estimate gas for deployment
            gas_estimate = contract.constructor().estimate_gas()
            gas_price = self.get_gas_price()
            
            # Build transaction
            transaction = contract.constructor().build_transaction({
                'from': account,
                'gas': gas_estimate,
                'gasPrice': gas_price,
                'nonce': self.w3.eth.get_transaction_count(account)
            })
            
            # Sign and send transaction
            signed_txn = self.w3.eth.account.sign_transaction(
                transaction,
                private_key=self.w3.eth.account.from_key(account).key
            )
            
            # Send transaction and wait for receipt
            tx_hash = self.w3.eth.send_raw_transaction(signed_txn.rawTransaction)
            tx_receipt = self.w3.eth.wait_for_transaction_receipt(
                tx_hash,
                timeout=60,
                poll_latency=0.1
            )
            
            if tx_receipt['status'] != 1:
                raise EthereumError("Contract deployment failed")
            
            return tx_receipt.contractAddress
            
        except Exception as e:
            self.logger.error(f"Contract deployment failed: {str(e)}")
            raise EthereumError(f"Contract deployment error: {str(e)}")