import os
from datetime import timedelta

class Config:
    """Base configuration settings."""
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev_secret_key_change_me_in_prod_12345')
    
    # Database
    BASE_DIR = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        'DATABASE_URL', 
        f"sqlite:///{os.path.join(BASE_DIR, 'webscrape_pro.db')}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Scraper settings
    DEFAULT_REQUEST_TIMEOUT = 15  # seconds
    DEFAULT_MAX_RETRIES = 3
    DEFAULT_RATE_LIMIT = 1.0  # delay between requests in seconds
    DEFAULT_USER_AGENT = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    
    # Session / Cookies
    REMEMBER_COOKIE_DURATION = timedelta(days=14)
    PERMANENT_SESSION_LIFETIME = timedelta(days=1)
    
    # Export directory
    EXPORT_DIR = os.path.join(BASE_DIR, 'exports')
    os.makedirs(EXPORT_DIR, exist_ok=True)


class DevelopmentConfig(Config):
    """Development configuration."""
    DEBUG = True
    SQLALCHEMY_ECHO = False


class ProductionConfig(Config):
    """Production configuration."""
    DEBUG = False
    # In production, secret key MUST be overridden via environment variables
    # Database URL should be PostgreSQL or MySQL on platforms like Render/AWS


class TestingConfig(Config):
    """Testing configuration."""
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    DEBUG = False


config_by_name = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}
