"""Utility functions for the job recommender system."""
from datetime import datetime, timedelta

def needs_refresh(last_scrape_time, hours_threshold=6):
    """
    Check if jobs need to be refreshed based on time elapsed.
    
    Args:
        last_scrape_time (str): ISO format datetime string of last scrape
        hours_threshold (int): Number of hours before refresh is needed
        
    Returns:
        bool: True if refresh is needed, False otherwise
    """
    if not last_scrape_time:
        return True
    
    try:
        last_scrape_dt = datetime.fromisoformat(last_scrape_time)
        elapsed = datetime.utcnow() - last_scrape_dt
        # Only refresh if it's been more than the threshold hours
        return elapsed > timedelta(hours=hours_threshold)
    except (ValueError, TypeError):
        # If we can't parse the date or it's invalid, assume refresh is needed
        return True
