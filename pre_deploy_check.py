#!/usr/bin/env python3
"""
Pre-deployment check script for Job Recommender System.
Ensures the application is ready for deployment to Hostinger.
"""

import os
import sys
import sqlite3
import importlib.util

def green(text):
    return f"\033[92m{text}\033[0m"

def red(text):
    return f"\033[91m{text}\033[0m"

def yellow(text):
    return f"\033[93m{text}\033[0m"

def check_file_exists(filepath, critical=True):
    exists = os.path.exists(filepath)
    if exists:
        print(f"{green('✓')} Found {filepath}")
    else:
        if critical:
            print(f"{red('✗')} Critical file missing: {filepath}")
        else:
            print(f"{yellow('!')} Optional file missing: {filepath}")
    return exists

def check_directory_exists(dirpath, create=False):
    if os.path.exists(dirpath) and os.path.isdir(dirpath):
        print(f"{green('✓')} Found directory {dirpath}")
        return True
    elif create:
        try:
            os.makedirs(dirpath, exist_ok=True)
            print(f"{yellow('!')} Created directory {dirpath}")
            return True
        except Exception as e:
            print(f"{red('✗')} Failed to create directory {dirpath}: {e}")
            return False
    else:
        print(f"{red('✗')} Directory missing: {dirpath}")
        return False

def check_module_importable(module_name):
    try:
        importlib.import_module(module_name)
        print(f"{green('✓')} Module {module_name} is importable")
        return True
    except ImportError as e:
        print(f"{red('✗')} Cannot import {module_name}: {e}")
        return False

def check_database():
    db_path = "instance/job_recommender.db"
    if not os.path.exists(db_path):
        print(f"{red('✗')} Database file not found at {db_path}")
        return False
        
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if tables exist
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        
        if not tables:
            print(f"{red('✗')} Database exists but has no tables")
            conn.close()
            return False
            
        print(f"{green('✓')} Database verified with {len(tables)} tables")
        conn.close()
        return True
    except Exception as e:
        print(f"{red('✗')} Database error: {e}")
        return False

def main():
    print("\nPre-deployment Check for Job Recommender System")
    print("============================================\n")
    
    # Check critical files
    critical_files = [
        "app.py", "wsgi.py", "passenger_wsgi.py", ".env.production",
        "deploy.sh", ".htaccess", "requirements.txt"
    ]
    
    missing_critical = False
    for file in critical_files:
        if not check_file_exists(file):
            missing_critical = True
    
    # Check directories
    directories = ["static", "templates", "instance", "uploads", "logs"]
    for directory in directories:
        check_directory_exists(directory, create=True)
    
    # Check database
    db_ok = check_database()
    
    # Check essential modules
    essential_modules = ["flask", "dotenv", "sqlalchemy"]
    for module in essential_modules:
        check_module_importable(module)
    
    print("\nSummary:")
    if missing_critical:
        print(f"{red('✗')} Critical files are missing. Deployment will likely fail.")
    elif not db_ok:
        print(f"{yellow('!')} Database issues detected. You may need to initialize it on the server.")
        print(f"{yellow('!')} Make sure to run init_database.py during deployment.")
    else:
        print(f"{green('✓')} All critical components verified. Ready for deployment.")
    
    print("\nNext steps:")
    print("1. Create a ZIP file of your project")
    print("2. Upload to Hostinger's File Manager")
    print("3. Extract the ZIP in your public_html directory")
    print("4. SSH into your server and run deploy.sh")
    print("5. Configure Python in Hostinger's control panel")
    print("6. Test your application\n")

if __name__ == "__main__":
    main()
