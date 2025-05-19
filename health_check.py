"""
Health check utilities for the Job Recommender System.

This module provides functions to check the health of various system components 
including database connections, API services, and file system access.
"""

import os
import time
import logging
import sqlite3
import requests
from datetime import datetime
from typing import Dict, Any, Tuple

# Configure logging
logger = logging.getLogger(__name__)

def check_database_health(db_uri: str) -> Tuple[bool, str]:
    """
    Check if database is accessible and functioning properly
    
    Args:
        db_uri (str): Database URI
    
    Returns:
        Tuple[bool, str]: (success, message)
    """
    try:
        if db_uri.startswith('sqlite:///'):
            # Extract SQLite database path from URI
            db_path = db_uri.replace('sqlite:///', '')
            
            # Check if file exists
            if not os.path.exists(db_path):
                return False, f"Database file not found at {db_path}"
            
            # Try to connect and run a simple query
            start_time = time.time()
            conn = sqlite3.connect(db_path, timeout=5)
            cursor = conn.cursor()
            cursor.execute('SELECT 1')
            result = cursor.fetchone()
            conn.close()
            
            query_time = time.time() - start_time
            
            if result and result[0] == 1:
                return True, f"Database connection successful (query time: {query_time:.3f}s)"
            else:
                return False, "Database connection test failed"
        else:
            # For non-SQLite databases, use SQLAlchemy
            from sqlalchemy import create_engine, text
            
            engine = create_engine(db_uri)
            start_time = time.time()
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            
            query_time = time.time() - start_time
            return True, f"Database connection successful (query time: {query_time:.3f}s)"
            
    except Exception as e:
        logger.error(f"Database health check failed: {str(e)}")
        return False, f"Database error: {str(e)}"

def check_api_health() -> Dict[str, Any]:
    """
    Check if external APIs used by the system are accessible
    
    Returns:
        Dict[str, Any]: Status of each API
    """
    api_status = {}
    
    # Check Coursera API
    try:
        start_time = time.time()
        response = requests.get(
            "https://api.coursera.org/api/courses.v1", 
            params={"q": "search", "query": "python", "limit": 1},
            timeout=5
        )
        response_time = time.time() - start_time
        
        if response.status_code == 200:
            api_status["coursera"] = {
                "status": "healthy",
                "response_time": f"{response_time:.3f}s",
                "status_code": response.status_code
            }
        else:
            api_status["coursera"] = {
                "status": "degraded",
                "response_time": f"{response_time:.3f}s",
                "status_code": response.status_code
            }
    except Exception as e:
        logger.error(f"Coursera API health check failed: {str(e)}")
        api_status["coursera"] = {
            "status": "unhealthy",
            "error": str(e)
        }
    
    return api_status

def check_file_system_health() -> Tuple[bool, Dict[str, Any]]:
    """
    Check if important directories are accessible and have proper permissions
    
    Returns:
        Tuple[bool, Dict[str, Any]]: Overall status and detailed directory status
    """
    directories = {
        "instance": os.path.join(os.path.dirname(os.path.abspath(__file__)), 'instance'),
        "uploads": os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads'),
        "static": os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')
    }
    
    dir_status = {}
    all_healthy = True
    
    for name, path in directories.items():
        status = {
            "exists": os.path.exists(path),
            "writable": False,
            "readable": False
        }
        
        if status["exists"]:
            status["writable"] = os.access(path, os.W_OK)
            status["readable"] = os.access(path, os.R_OK)
            
            # Try to write and read a test file
            if status["writable"] and status["readable"]:
                try:
                    test_file = os.path.join(path, ".health_check_test")
                    with open(test_file, "w") as f:
                        f.write(f"Health check at {datetime.now().isoformat()}")
                    
                    with open(test_file, "r") as f:
                        content = f.read()
                        
                    os.remove(test_file)
                    status["test_passed"] = True
                except Exception as e:
                    status["test_passed"] = False
                    status["error"] = str(e)
            
        # Directory is only healthy if it exists, is writable and readable
        status["healthy"] = status["exists"] and status["writable"] and status["readable"]
        all_healthy = all_healthy and status["healthy"]
        
        dir_status[name] = status
    
    return all_healthy, dir_status

def check_environment_variables() -> Dict[str, bool]:
    """
    Check if required environment variables are set
    
    Returns:
        Dict[str, bool]: Status of each required environment variable
    """
    required_vars = [
        "FLASK_APP",
        "FLASK_ENV", 
        "SECRET_KEY",
        "DATABASE_URL",
        "COURSERA_CLIENT_ID",
        "COURSERA_CLIENT_SECRET"
    ]
    
    env_status = {}
    for var in required_vars:
        env_status[var] = var in os.environ and bool(os.environ[var])
    
    return env_status

def get_system_health() -> Dict[str, Any]:
    """
    Get comprehensive health status of the entire system
    
    Returns:
        Dict[str, Any]: Health status details
    """
    health_data = {
        "timestamp": datetime.utcnow().isoformat(),
        "environment": os.environ.get("FLASK_ENV", "development")
    }
    
    # Check database health
    db_uri = os.environ.get("DATABASE_URL", "sqlite:///instance/job_recommender.db")
    db_healthy, db_message = check_database_health(db_uri)
    health_data["database"] = {
        "status": "healthy" if db_healthy else "unhealthy",
        "message": db_message
    }
    
    # Check API health
    health_data["api"] = check_api_health()
    
    # Check file system health
    fs_healthy, fs_status = check_file_system_health()
    health_data["file_system"] = {
        "status": "healthy" if fs_healthy else "degraded",
        "details": fs_status
    }
    
    # Check environment variables
    env_status = check_environment_variables()
    missing_vars = [var for var, status in env_status.items() if not status]
    health_data["environment_vars"] = {
        "status": "healthy" if not missing_vars else "degraded",
        "missing_vars": missing_vars
    }
    
    # Calculate overall health
    components_healthy = [
        db_healthy,
        fs_healthy,
        not missing_vars,
        health_data["api"].get("coursera", {}).get("status") != "unhealthy"
    ]
    
    # Overall status is:
    # - healthy: everything is working
    # - degraded: some components have issues but system is operational
    # - unhealthy: critical components are down
    if all(components_healthy):
        health_data["status"] = "healthy"
    elif db_healthy:  # Database is critical, if it's up we're at least degraded
        health_data["status"] = "degraded"
    else:
        health_data["status"] = "unhealthy"
    
    return health_data
