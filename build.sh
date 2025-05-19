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

# Always initialize the database to ensure proper schema
python <<EOL
import sqlite3
import os

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
        else:
            print("user_id column already exists in jobs table")
        
        conn.close()
    except Exception as e:
        print(f"Error checking/updating database schema: {e}")
        # Continue with normal initialization
        
# Run the full database initialization
print("Running database initialization...")
EOL

# Initialize database
python init_database.py

# Output build complete message
echo "Build completed successfully!"
