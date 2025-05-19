#!/usr/bin/env bash
# build.sh for Render.com deployment

# Exit on error
set -o errexit

# Create necessary directories
mkdir -p instance
mkdir -p static/graphs
mkdir -p uploads
mkdir -p logs

# Install Python dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Make sure we have BeautifulSoup for web scraping
pip install beautifulsoup4 requests lxml

# Always initialize the database to ensure proper schema
python <<EOL
import sqlite3
import os
import traceback

print("Starting database setup for deployment...")

# Check if database exists and add user_id column if needed
db_path = 'instance/job_recommender.db'
if os.path.exists(db_path):
    try:
        print("Checking for user_id column in jobs table...")
        conn = sqlite3.connect(db_path)
        cursor = conn.execute("PRAGMA table_info(jobs)")
        columns = [column[1] for column in cursor.fetchall()]
        
        # Add user_id column if it's missing
        if "user_id" not in columns:
            print("Adding user_id column to jobs table...")
            conn.execute("ALTER TABLE jobs ADD COLUMN user_id INTEGER")
            conn.commit()
            print("Successfully added user_id column to jobs table")
            
            # Update existing records to have a default user_id
            print("Updating existing job records with default user_id...")
            conn.execute("UPDATE jobs SET user_id = 1 WHERE user_id IS NULL")
            conn.commit()
            print("Updated existing jobs with default user_id")
        else:
            print("user_id column already exists in jobs table")
            
        # Make sure the type of user_id allows NULL values
        print("Ensuring user_id column allows NULL values...")
        table_info = conn.execute("PRAGMA table_info(jobs)").fetchall()
        for col in table_info:
            if col[1] == 'user_id' and col[3] == 1:  # col[3] = notnull
                print("Recreating jobs table to allow NULL user_id...")
                # We need to recreate the table because SQLite doesn't support ALTER COLUMN
                conn.close()
                # Let the initialization handle the table recreation
                os.remove(db_path)
                print("Removed database file to force recreation with correct schema.")
                break
        
        if os.path.exists(db_path):
            conn.close()
    except Exception as e:
        print(f"Error checking/updating database schema: {e}")
        print(traceback.format_exc())
        # Continue with normal initialization
        
# Run the full database initialization
print("Running database initialization...")
EOL

# Initialize database
python init_database.py

# Fix scraper issues directly in the database
python <<EOL
import sqlite3
import os
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

try:
    # Connect to database
    db_path = 'instance/job_recommender.db'
    if os.path.exists(db_path):
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Check if jobs table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='jobs'")
        if cursor.fetchone():
            # Check if user_id column exists and is properly configured
            cursor.execute("PRAGMA table_info(jobs)")
            columns = [column for column in cursor.fetchall()]
            user_id_column = None
            
            for column in columns:
                if column[1] == 'user_id':
                    user_id_column = column
                    break
                    
            if user_id_column is None:
                logger.info("Adding user_id column to jobs table...")
                cursor.execute("ALTER TABLE jobs ADD COLUMN user_id INTEGER")
                conn.commit()
                logger.info("Added user_id column to jobs table")
            
            # Update any NULL user_id values to default user
            cursor.execute("UPDATE jobs SET user_id = 1 WHERE user_id IS NULL")
            conn.commit()
            logger.info("Updated any NULL user_id values to default user (1)")
            
            # Check if any jobs exist
            cursor.execute("SELECT COUNT(*) FROM jobs")
            job_count = cursor.fetchone()[0]
            logger.info(f"Found {job_count} jobs in the database")
        
        conn.close()
        logger.info("Database schema update complete")
    else:
        logger.info("Database file not found. Will be created by application.")
except Exception as e:
    logger.error(f"Error updating database schema: {e}")
EOL

# Output build complete message
echo "Build completed successfully!"
