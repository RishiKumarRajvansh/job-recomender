import os
import logging
from dotenv import load_dotenv

# Load environment variables from .env file if it exists
load_dotenv()

# Configure logging
logger = logging.getLogger(__name__)

class Config:
    """Base configuration."""
    SECRET_KEY = os.environ.get('SECRET_KEY', 'rishi-123#@')
    
    # Get absolute paths using __file__ to ensure consistency
    basedir = os.path.abspath(os.path.dirname(__file__))
    instance_dir = os.path.join(basedir, 'instance')
    db_path = os.path.join(instance_dir, 'job_recommender.db')
    
    # Ensure the instance directory exists and is writable
    if not os.path.exists(instance_dir):
        try:
            os.makedirs(instance_dir, exist_ok=True)
            logger.info(f"Config: Created instance directory at {instance_dir}")
            # Set proper directory permissions
            import stat
            os.chmod(instance_dir, stat.S_IRWXU)  # Read, write, execute for user only (0o700)
            logger.info(f"Config: Set permissions on instance directory")
        except Exception as e:
            logger.error(f"Config: Error creating instance directory: {e}")
    
    # Use absolute path for SQLite database with proper format for cross-platform compatibility
    # Convert Windows backslashes to forward slashes for SQLite URI compatibility
    db_uri = f'sqlite:///{db_path.replace(os.sep, "/")}'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', db_uri)
    
    # Additional SQLite optimizations
    SQLALCHEMY_ENGINE_OPTIONS = {
        'connect_args': {
            'check_same_thread': False,  # Allow multithreaded access
            'timeout': 30  # Increase timeout for busy situations
        },
        'pool_recycle': 3600,  # Recycle connections after 1 hour
        'pool_pre_ping': True  # Check connections before using them
    }
    
    # Log the database URI being used
    logger.info(f"SQLite database URI: {SQLALCHEMY_DATABASE_URI}")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

class DevelopmentConfig(Config):
    """Development configuration."""
    DEBUG = True
    
class ProductionConfig(Config):
    """Production configuration."""
    DEBUG = False
    
    # Production security settings
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SECURE = True
    REMEMBER_COOKIE_HTTPONLY = True

# Set configuration based on environment variable
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}

def get_config():
    """Returns the appropriate configuration object based on the environment."""
    config_name = os.environ.get('FLASK_ENV', 'default')
    return config[config_name]
