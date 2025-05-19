"""
Utility functions for job operations.
"""
import logging
from database_manager import get_db_connection

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def count_user_jobs(user_id):
    """
    Count how many jobs are in the database for a specific user.
    
    Args:
        user_id: The user ID to check
        
    Returns:
        int: The number of jobs for this user or 0 if none found
    """
    if not user_id:
        return 0
        
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM jobs WHERE user_id = ?", (user_id,))
        count = cursor.fetchone()[0]
        
        conn.close()
        return count
    except Exception as e:
        logger.error(f"Error counting user jobs: {e}")
        return 0

def has_any_jobs(user_id):
    """
    Check if the user has any jobs in the database.
    
    Args:
        user_id: The user ID to check
        
    Returns:
        bool: True if the user has any jobs, False otherwise
    """
    return count_user_jobs(user_id) > 0

def get_user_skills(user):
    """
    Extract skills from a user object and clean them.
    
    Args:
        user: User object with skills attribute
        
    Returns:
        list: List of cleaned skills
    """
    skills = []
    
    if hasattr(user, 'skills') and user.skills:
        if isinstance(user.skills, str):
            skills.extend(s.strip() for s in user.skills.split(',') if s.strip())
        elif isinstance(user.skills, list):
            skills.extend(s.strip() for s in user.skills if s.strip())
            
    return list(set(skills))  # Remove duplicates
