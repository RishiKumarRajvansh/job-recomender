"""
Job counter utility module for consistent job counting across the application.
"""
import logging

# Configure logging
logger = logging.getLogger(__name__)

def get_job_counts(jobs_list, user_id=None):
    """
    Gets standardized job counts from a list of jobs
    
    Args:
        jobs_list (list): List of job dictionaries
        user_id (int, optional): User ID to filter jobs by
    
    Returns:
        dict: Dictionary with different job count types
            - total_jobs: Total number of jobs
            - matching_jobs: Number of jobs with match > 40%
            - remote_jobs: Number of remote jobs
            - onsite_jobs: Number of onsite jobs    """
    if not jobs_list:
        return {
            "total_jobs": 0,
            "matching_jobs": 0,
            "remote_jobs": 0,
            "onsite_jobs": 0
        }
    
    # Filter by user_id if provided
    if user_id is not None:
        jobs_list = [job for job in jobs_list if job.get('user_id') == user_id]
        if not jobs_list:
            logger.info(f"No jobs found for user_id {user_id}")
            return {
                "total_jobs": 0,
                "matching_jobs": 0, 
                "remote_jobs": 0,
                "onsite_jobs": 0
            }
    
    # Count matching jobs (with match percentage > 40%)
    matching_jobs = [job for job in jobs_list if job.get('match_percentage', 0) > 40]
    
    # Count remote and onsite jobs
    remote_jobs = []
    onsite_jobs = []
    
    for job in jobs_list:
        # Check if job is remote by looking for 'remote' in various fields
        is_remote = False
        if ('remote' in str(job.get('title', '')).lower() or 
            'remote' in str(job.get('location', '')).lower() or 
            'remote' in str(job.get('description', '')).lower()):
            is_remote = True
            remote_jobs.append(job)
        else:
            onsite_jobs.append(job)
    
    return {
        "total_jobs": len(jobs_list),
        "matching_jobs": len(matching_jobs),
        "remote_jobs": len(remote_jobs),
        "onsite_jobs": len(onsite_jobs)
    }
