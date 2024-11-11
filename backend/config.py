import os
from datetime import timedelta
from web3 import Web3
from pathlib import Path

# Get the base directory of the project
basedir = Path(__file__).parent.parent

class Config:
    """Base configuration."""
    
    # Flask
    SECRET_KEY = os.getenv('SECRET_KEY', 'your-secret-key-here')
    DEBUG = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    
    # Database - SQLite Configuration
    SQLALCHEMY_DATABASE_URI = os.getenv(
        'DATABASE_URL',
        f'sqlite:///{os.path.join(basedir, "bookmarket.db")}'
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # JWT Configuration
    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', 'your-jwt-secret-key')
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=1)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=30)
    
    # File Upload
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size
    UPLOAD_FOLDER = os.path.join(basedir, 'uploads')
    ALLOWED_EXTENSIONS = {'pdf', 'epub'}
    
    # IPFS Desktop Configuration
    IPFS_CONFIG = {
        'API_HOST': os.getenv('IPFS_API_HOST', '/ip4/127.0.0.1/tcp/5001'),
        'GATEWAY_HOST': os.getenv('IPFS_GATEWAY_HOST', 'http://127.0.0.1:8080'),
        'GATEWAY_PUBLIC': os.getenv('IPFS_GATEWAY_PUBLIC', 'https://ipfs.io/ipfs'),
        'CONNECT_TIMEOUT': 10,  # seconds
        'PIN_TIMEOUT': 30,  # seconds for pinning files
        'MAX_FILE_SIZE': 50 * 1024 * 1024,  # 50MB max file size for IPFS
        'CHUNK_SIZE': 1024 * 1024  # 1MB chunks for uploading
    }
    
    # Ganache Configuration
    GANACHE_CONFIG = {
        'PROVIDER_URI': os.getenv('WEB3_PROVIDER_URI', 'http://127.0.0.1:7545'),
        'CHAIN_ID': 1337,
        'NETWORK_ID': '5777',
        'GAS_LIMIT': 6721975,
        'GAS_PRICE': 20000000000,  # 20 gwei
        'BLOCK_TIME': 0,  # Instant mining
        'ACCOUNTS_TO_CREATE': 10,
        'DEFAULT_BALANCE_ETHER': 1000
    }
    
    # Web3 Provider Setup
    WEB3_PROVIDER = Web3(Web3.HTTPProvider(GANACHE_CONFIG['PROVIDER_URI']))
    
    # Smart Contract Configuration
    CONTRACT_CONFIG = {
        'ADDRESS': os.getenv('CONTRACT_ADDRESS'),
        'ABI_PATH': os.path.join(basedir, 'smart_contracts/build/contracts/BookMarket.json'),
        'GAS_LIMIT': 3000000,
        'GAS_PRICE_STRATEGY': 'medium',
        'CONFIRMATIONS_NEEDED': 1,
        'DEPLOYMENT_TIMEOUT': 60  # seconds
    }
    
    # Cache Configuration
    CACHE_TYPE = 'simple'
    CACHE_DEFAULT_TIMEOUT = 300
    
    @staticmethod
    def init_app(app):
        """Initialize application configuration."""
        # Create upload folder if it doesn't exist
        if not os.path.exists(Config.UPLOAD_FOLDER):
            os.makedirs(Config.UPLOAD_FOLDER)
        
        # Initialize Web3 and verify connection
        if not Config.WEB3_PROVIDER.is_connected():
            raise Exception("Unable to connect to Ethereum network")
        
        # Verify network is Ganache
        network_id = Config.WEB3_PROVIDER.net.version
        if network_id != Config.GANACHE_CONFIG['NETWORK_ID']:
            raise Exception(f"Connected to wrong network. Expected Ganache (ID: {Config.GANACHE_CONFIG['NETWORK_ID']}), got {network_id}")


class DevelopmentConfig(Config):
    """Development configuration."""
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = os.getenv(
        'DEV_DATABASE_URL',
        f'sqlite:///{os.path.join(basedir, "bookmarket_dev.db")}'
    )
    SQLALCHEMY_ECHO = True
    
    # Override IPFS settings for development
    IPFS_CONFIG = {
        **Config.IPFS_CONFIG,
        'GATEWAY_HOST': 'http://127.0.0.1:8080',  # Local IPFS gateway
        'PIN_TIMEOUT': 60  # Longer timeout for development
    }


class TestingConfig(Config):
    """Testing configuration."""
    TESTING = True
    SQLALCHEMY_DATABASE_URI = os.getenv(
        'TEST_DATABASE_URL',
        f'sqlite:///{os.path.join(basedir, "bookmarket_test.db")}'
    )
    
    # Test-specific Ganache settings
    GANACHE_CONFIG = {
        **Config.GANACHE_CONFIG,
        'PROVIDER_URI': 'http://127.0.0.1:7545',
        'ACCOUNTS_TO_CREATE': 20,  # More accounts for testing
        'DEFAULT_BALANCE_ETHER': 10000  # More ETH for testing
    }
    
    # Test-specific IPFS settings
    IPFS_CONFIG = {
        **Config.IPFS_CONFIG,
        'PIN_TIMEOUT': 5,  # Shorter timeout for tests
        'MAX_FILE_SIZE': 1 * 1024 * 1024  # 1MB max file size for tests
    }


class ProductionConfig(Config):
    """Production configuration."""
    DEBUG = False
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL')
    
    # Production-specific Ganache settings
    GANACHE_CONFIG = {
        **Config.GANACHE_CONFIG,
        'GAS_PRICE': 30000000000,  # 30 gwei - higher gas price for production
        'CONFIRMATIONS_NEEDED': 2  # More confirmations for production
    }
    
    # Production-specific IPFS settings
    IPFS_CONFIG = {
        **Config.IPFS_CONFIG,
        'GATEWAY_PUBLIC': os.getenv('IPFS_GATEWAY_PUBLIC', 'https://ipfs.io/ipfs'),
        'PIN_TIMEOUT': 120,  # Longer timeout for production
        'CONNECT_TIMEOUT': 30  # Longer connection timeout for production
    }

    @classmethod
    def init_app(cls, app):
        Config.init_app(app)
        
        # Production logging configuration
        import logging
        from logging.handlers import RotatingFileHandler
        
        file_handler = RotatingFileHandler(
            'bookmarket.log',
            maxBytes=1024 * 1024,  # 1MB
            backupCount=10
        )
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
        ))
        file_handler.setLevel(logging.INFO)
        app.logger.addHandler(file_handler)
        app.logger.setLevel(logging.INFO)
        app.logger.info('BookMarket startup')


# Configuration dictionary
config = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}