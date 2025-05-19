"""
Database initialization and server starter script.
This script:
1. Creates the instance directory if necessary
2. Initializes the database
3. Runs the Flask app
"""
import os
import sys
import logging
import traceback

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

def setup_database():
    """Setup the database - handles creation and validation."""
    # 1. Ensure instance directory exists with proper permissions
    basedir = os.path.abspath(os.path.dirname(__file__))
    instance_dir = os.path.join(basedir, 'instance')
    db_path = os.path.join(instance_dir, 'job_recommender.db')
    
    # Make sure instance directory exists
    if not os.path.exists(instance_dir):
        logger.info(f"Creating instance directory at {instance_dir}")
        os.makedirs(instance_dir, exist_ok=True)
        # Set proper permissions
        try:
            import stat
            os.chmod(instance_dir, stat.S_IRWXU)  # 0o700 permissions (rwx for user only)
            logger.info("Set permissions on instance directory")
        except Exception as e:
            logger.warning(f"Could not set permissions on instance directory: {e}")
    
    # 2. Determine if we need to initialize the database
    initialize_db = False
    
    if not os.path.exists(db_path):
        logger.info("Database not found, will initialize it...")
        initialize_db = True
    else:
        # Verify database is accessible and has the correct schema
        try:
            import sqlite3
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            # Check for at least one critical table
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='user';")
            if not cursor.fetchone():
                logger.warning("Database exists but appears to be corrupt or incomplete. Will reinitialize...")
                os.remove(db_path)
                initialize_db = True
            else:
                logger.info("Database validation successful")
            conn.close()
        except sqlite3.Error as e:
            logger.error(f"Database verification failed: {e}")
            logger.info("Will recreate the database...")
            try:
                # If file exists but can't be opened, try to remove it
                if os.path.exists(db_path):
                    os.remove(db_path)
                initialize_db = True
            except Exception as inner_e:
                logger.error(f"Failed to remove corrupted database: {inner_e}")
                return False
    
    # 3. Initialize database if needed
    if initialize_db:
        logger.info("Initializing database...")
        try:
            import init_database
            success = init_database.main()
            if not success:
                logger.error("Database initialization failed!")
                return False
            logger.info("Database initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing database: {e}")
            logger.error(traceback.format_exc())
            return False
    
    # 4. Set proper permissions on the database file
    try:
        import stat
        os.chmod(db_path, stat.S_IRUSR | stat.S_IWUSR)  # 0o600 permissions (rw for user only)
        logger.info(f"Set permissions on database file: {db_path}")
    except Exception as e:
        logger.warning(f"Could not set permissions on database file: {e}")
    
    return True

def main():
    """Main entry point for the application."""
    try:
        # 1. Setup and validate the database
        if not setup_database():
            logger.error("Database setup failed. Exiting...")
            return False
        
        # 2. Print environment details
        basedir = os.path.abspath(os.path.dirname(__file__))
        instance_dir = os.path.join(basedir, 'instance')
        db_path = os.path.join(instance_dir, 'job_recommender.db')
        logger.info(f"Using database at: {db_path}")
        logger.info(f"Current directory: {os.getcwd()}")
        logger.info(f"Python version: {sys.version}")
        
        # 3. Run tests to ensure everything is working properly
        try:
            logger.info("Running quick connectivity tests before starting app")
            import sqlite3
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("PRAGMA integrity_check;")
            integrity_result = cursor.fetchone()
            if integrity_result and integrity_result[0] == 'ok':
                logger.info("Database integrity check passed")
            else:
                logger.warning(f"Database integrity check result: {integrity_result}")
            conn.close()
        except Exception as e:
            logger.error(f"Pre-flight check failed: {e}")
          # 4. Import and run the Flask app
        from app import app
        from dotenv import load_dotenv
        
        # Load environment variables again to ensure they're available
        load_dotenv()
        
        # Get host and port from environment variables or use defaults
        host = os.environ.get('FLASK_HOST', '127.0.0.1')
        port = int(os.environ.get('FLASK_PORT', 5000))
        debug = os.environ.get('FLASK_DEBUG', 'False').lower() in ('true', '1', 't')
        
        logger.info(f"Starting Flask application on {host}:{port} (debug={debug})...")
        app.run(host=host, port=port, debug=debug, use_reloader=debug)
        
    except Exception as e:
        logger.error(f"Error: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False
        
    return True

if __name__ == "__main__":
    main()
