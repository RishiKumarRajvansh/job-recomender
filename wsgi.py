#!/usr/bin/env python3
"""
WSGI entry point for production deployment with Gunicorn.
This file should be the target of gunicorn for production deployment.
Example:
  gunicorn --workers=3 --bind=0.0.0.0:8000 --timeout=120 --worker-class=gthread --threads=4 wsgi:app

For HTTPS (in production):
  gunicorn --workers=3 --bind=0.0.0.0:443 --certfile=/path/to/cert.pem --keyfile=/path/to/key.pem wsgi:app
"""
import os
import sys
import logging
import traceback
import multiprocessing
from dotenv import load_dotenv

# Load environment variables before importing app
load_dotenv()

# Ensure FLASK_ENV is set to production
os.environ['FLASK_ENV'] = 'production'
os.environ['FLASK_DEBUG'] = 'False'

# Import app after environment setup
from app import app

# Configure logging for WSGI
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Ensure instance directory exists when directly running this file
# This won't run when the file is imported by Gunicorn
def init_application():
    """Initialize the application for production."""
    try:
        from app import db, init_db, cleanup_static_graphs
        from security import set_secure_headers
        
        # Set recommended number of worker processes based on CPU cores
        cpu_count = multiprocessing.cpu_count()
        recommended_workers = (2 * cpu_count) + 1
        logger.info(f"System has {cpu_count} CPU cores, recommended Gunicorn workers: {recommended_workers}")
        
        # Ensure instance directory exists
        instance_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'instance')
        if not os.path.exists(instance_dir):
            logger.info(f"Creating instance directory at {instance_dir}")
            os.makedirs(instance_dir, exist_ok=True)
            
            # Set proper permissions for production
            try:
                import stat
                os.chmod(instance_dir, stat.S_IRWXU | stat.S_IRGRP | stat.S_IXGRP)  # Owner all, group read/execute
                logger.info(f"Set permissions on instance directory: {instance_dir}")
            except Exception as e:
                logger.warning(f"Could not set permissions on instance directory: {e}")
        
        # Ensure logs directory exists
        log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
        if not os.path.exists(log_dir):
            logger.info(f"Creating logs directory at {log_dir}")
            os.makedirs(log_dir, exist_ok=True)
        
        # Initialize database
        with app.app_context():
            db.create_all()
            
            # Check if database needs initialization
            # This avoids resetting database on each restart
            from sqlalchemy import inspect
            inspector = inspect(db.engine)
            if not inspector.has_table("user"):
                logger.info("User table not found. Initializing database.")
                init_db()  # Initialize database tables
            
            # Clean up old graph files on startup
            graphs_dir = os.path.join('static', 'graphs')
            if os.path.exists(graphs_dir):
                logger.info(f"Cleaning up old graph files in {graphs_dir}")
                cleanup_static_graphs(graphs_dir, older_than_days=3)
                
        logger.info("Application initialization complete")
        return True
    except Exception as e:
        logger.error(f"Error initializing application: {e}")
        logger.error(traceback.format_exc())
        return False

# Set up production configuration
if not app.debug:
    # Set up file handler for production logging
    log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
    if not os.path.exists(log_dir):
        os.makedirs(log_dir, exist_ok=True)
    
    file_handler = logging.FileHandler(os.path.join(log_dir, 'app.log'))
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    file_handler.setLevel(logging.INFO)
    app.logger.addHandler(file_handler)
    app.logger.setLevel(logging.INFO)
    app.logger.info('Job Recommender startup')

# Initialize application at import time for production WSGI servers
# when not in debug mode
if os.environ.get('FLASK_ENV') == 'production':
    # Initialize once at import time (for Gunicorn/uWSGI)
    init_application()

# Main entry point WSGI servers
if __name__ == "__main__":
    # Only initialize when run directly, not when imported by WSGI server
    init_application()
    
    # Run with production-appropriate settings when executed directly
    port = int(os.environ.get('PORT', 5000))
    # In direct execution, use 127.0.0.1 for security
    # In production, Gunicorn should be used instead
    debug = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'
    app.run(debug=debug, port=port)
