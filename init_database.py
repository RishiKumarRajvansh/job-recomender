import os
import logging
import traceback
from database_manager import initialize_database, create_test_user, check_database, DB_PATH

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

def main():
    """Initialize the database and create test user."""
    try:        # Ensure the instance directory exists with proper permissions
        instance_dir = os.path.dirname(DB_PATH)
        os.makedirs(instance_dir, exist_ok=True)
        
        # Check if directory is writable
        if not os.access(instance_dir, os.W_OK):
            logger.error(f"Directory {instance_dir} is not writable!")
            return False
            
        # Set proper permissions on the instance directory
        try:
            import stat
            os.chmod(instance_dir, stat.S_IRWXU)  # 0o700 permissions (rwx for user only)
            logger.info(f"Set permissions on instance directory: {instance_dir}")
        except Exception as e:
            logger.warning(f"Could not set permissions on instance directory: {e}")
        # Remove existing database if it exists
        if os.path.exists(DB_PATH):
            logger.info(f"Removing existing database at {DB_PATH}")
            os.remove(DB_PATH)
            
        # Initialize database with all tables
        logger.info("Initializing database with all tables...")
        if not initialize_database():
            logger.error("Failed to initialize database")
            return False
            
        # Set proper permissions on the database file
        try:
            import stat
            os.chmod(DB_PATH, stat.S_IRUSR | stat.S_IWUSR)  # 0o600 permissions (rw for user only)
            logger.info(f"Set permissions on database file: {DB_PATH}")
        except Exception as e:
            logger.warning(f"Could not set permissions on database file: {e}")
            
        # Create test user
        logger.info("Creating test user...")
        user_id = create_test_user()
        if not user_id:
            logger.error("Failed to create test user")
            return False
        
        # Verify database setup
        logger.info("Verifying database setup...")
        if check_database():
            logger.info(f"Database initialized successfully with test user (ID: {user_id})")
            logger.info(f"Database location: {DB_PATH}")
            return True
        else:
            logger.error("Database verification failed")
            return False
        
    except Exception as e:
        logger.error(f"Error initializing database: {e}")
        logger.error(traceback.format_exc())
        return False

if __name__ == "__main__":
    success = main()
    if success:
        print("✅ Database initialized successfully!")
    else:
        print("❌ Database initialization failed. Check logs for details.")
