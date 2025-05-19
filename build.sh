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

# Initialize database if it doesn't exist
if [ ! -f instance/job_recommender.db ]; then
    python init_database.py
fi

# Output build complete message
echo "Build completed successfully!"
