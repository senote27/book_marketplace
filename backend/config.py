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
    
    # IPFS Configuration
    IPFS_HOST = os.getenv('IPFS_HOST', '/ip4/127.0.0.1/tcp/5001')
    IPFS_CONNECT_TIMEOUT = 10  # seconds
    
    # Ethereum Configuration
    WEB3_PROVIDER_URI = os.getenv(
        'WEB3_PROVIDER_URI',
        'http://localhost:8545'  # Default local Ganache instance
    )
    WEB3_PROVIDER = Web3(Web3.HTTPProvider(WEB3_PROVIDER_URI))
    
    # Smart Contract
    CONTRACT_ADDRESS = os.getenv('CONTRACT_ADDRESS')
    CONTRACT_ABI_PATH = os.path.join(basedir, 'smart_contracts/build/contracts/BookMarket.json')
    
    # Gas Configuration
    GAS_LIMIT = 2000000
    GAS_PRICE_STRATEGY = 'medium'
    
    # Cache Configuration
    CACHE_TYPE = 'simple'
    CACHE_DEFAULT_TIMEOUT = 300
    
    @staticmethod
    def init_app(app):
        """Initialize application configuration."""
        # Create upload folder if it doesn't exist
        if not os.path.exists(Config.UPLOAD_FOLDER):
            os.makedirs(Config.UPLOAD_FOLDER)
        
        # Initialize Web3
        if not Config.WEB3_PROVIDER.is_connected():
            raise Exception("Unable to connect to Ethereum network")


class DevelopmentConfig(Config):
    """Development configuration."""
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = os.getenv(
        'DEV_DATABASE_URL',
        f'sqlite:///{os.path.join(basedir, "bookmarket_dev.db")}'
    )
    SQLALCHEMY_ECHO = True


class TestingConfig(Config):
    """Testing configuration."""
    TESTING = True
    SQLALCHEMY_DATABASE_URI = os.getenv(
        'TEST_DATABASE_URL',
        f'sqlite:///{os.path.join(basedir, "bookmarket_test.db")}'
    )
    WEB3_PROVIDER_URI = 'http://localhost:8545'  # Local Ganache for testing


class ProductionConfig(Config):
    """Production configuration."""
    DEBUG = False
    SQLALCHEMY_DATABASE_URI = os.getenv(
        'DATABASE_URL',
        f'sqlite:///{os.path.join(basedir, "bookmarket_prod.db")}'
    )

    @classmethod
    def init_app(cls, app):
        Config.init_app(app)
        
        # Log to file
        import logging
        from logging.handlers import RotatingFileHandler
        
        log_file = os.path.join(basedir, 'logs', 'bookmarket.log')
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=10240,
            backupCount=10
        )
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s '
            '[in %(pathname)s:%(lineno)d]'
        ))
        file_handler.setLevel(logging.INFO)
        app.logger.addHandler(file_handler)


config = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}