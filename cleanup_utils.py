import os
import logging
import shutil
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

def cleanup_static_graphs(directory_path, older_than_days=7, force_all=False):
    """
    Removes old graph files from the static/graphs directory
    
    Args:
        directory_path (str): Path to the static/graphs directory
        older_than_days (int): Remove files older than this many days
        force_all (bool): If True, removes all graph files regardless of age
    """
    try:
        if not os.path.exists(directory_path):
            logger.info(f"Directory {directory_path} does not exist. Nothing to clean up.")
            return
            
        # Get current date
        now = datetime.now()
        cutoff_date = now - timedelta(days=older_than_days)
        
        # Count for logging
        removed_count = 0
        # Check all files in the directory
        for filename in os.listdir(directory_path):
            file_path = os.path.join(directory_path, filename)
            
            # Skip if not a file
            if not os.path.isfile(file_path):
                continue
            
            should_remove = force_all
            
            if not should_remove:
                # Get file modification time
                file_mod_time = datetime.fromtimestamp(os.path.getmtime(file_path))
                # If file is older than cutoff, mark for deletion
                should_remove = file_mod_time < cutoff_date
            
            if should_remove:
                try:
                    os.remove(file_path)
                    removed_count += 1
                except Exception as e:
                    logger.error(f"Error removing file {file_path}: {str(e)}")
        
        logger.info(f"Cleanup complete. Removed {removed_count} old graph files.")
          # If directory is empty, delete it
        if os.path.exists(directory_path) and not os.listdir(directory_path):
            try:
                os.rmdir(directory_path)
                logger.info(f"Removed empty directory {directory_path}")
            except Exception as e:
                logger.error(f"Error removing empty directory {directory_path}: {str(e)}")
    except Exception as e:
        logger.error(f"Error during graph cleanup: {str(e)}")
        
def cleanup_job_related_data():
    """
    Cleanup any data that should be refreshed when jobs are updated.
    This function is called whenever jobs are scraped or refreshed.
    """
    try:
        # Clean up all graph files in the static/graphs directory
        graphs_dir = os.path.join('static', 'graphs')
        if os.path.exists(graphs_dir):
            logger.info("Cleaning up all graph files due to job data refresh")
            cleanup_static_graphs(graphs_dir, force_all=True)
            
        # Add any other cleanup operations here that should happen when job data changes
        
    except Exception as e:
        logger.error(f"Error during job-related cleanup: {str(e)}")
