import sqlite3
import os
import json
from datetime import datetime
import logging
import traceback

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Database file path - use absolute path
basedir = os.path.abspath(os.path.dirname(__file__))
instance_dir = os.path.join(basedir, 'instance')
DB_PATH = os.path.join(instance_dir, 'job_recommender.db')

def get_db_connection():
    """Create a connection to the SQLite database."""
    # Ensure the instance directory exists
    if not os.path.exists(instance_dir):
        try:
            os.makedirs(instance_dir, exist_ok=True)
            logger.info(f"Created instance directory at {instance_dir}")
        except Exception as e:
            logger.error(f"Error creating instance directory: {e}")
    
    # Log database access attempt
    logger.info(f"Attempting to connect to database at {DB_PATH}")
    
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row  # This enables column access by name
        logger.info("Database connection successful")
        return conn
    except sqlite3.Error as e:
        logger.error(f"Database connection error: {e}")
        raise

def initialize_database():
    """Initialize database tables if they don't exist."""
    conn = None
    try:
        # Ensure the instance directory exists
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        logger.info("Starting database initialization...")
        
        # Enable foreign key support
        cursor.execute('PRAGMA foreign_keys = ON')
        
        # Drop old users table if it exists
        cursor.execute("DROP TABLE IF EXISTS users")
        
        # Create user table first since other tables reference it
        logger.info("Creating user table...")
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                skills TEXT,
                resume_skills TEXT,
                location TEXT,
                certifications TEXT,
                summary TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_resume_update TIMESTAMP
            )
        ''')
        
        # Create work experience table
        logger.info("Creating work_experience table...")
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS work_experience (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                company TEXT NOT NULL,
                title TEXT NOT NULL,
                start_date DATE NOT NULL,
                end_date DATE,
                description TEXT,
                current_job BOOLEAN DEFAULT FALSE,
                FOREIGN KEY (user_id) REFERENCES user (id)
            )
        ''')
        
        # Create education table
        logger.info("Creating education table...")
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS education (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                institution TEXT NOT NULL,
                degree TEXT NOT NULL,
                field_of_study TEXT,
                start_date DATE NOT NULL,
                end_date DATE,
                gpa REAL,
                description TEXT,
                FOREIGN KEY (user_id) REFERENCES user (id)
            )
        ''')
          # Create jobs table
        logger.info("Creating jobs table...")
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,  /* Allow NULL for backward compatibility */
                job_id TEXT,
                title TEXT,
                company TEXT,
                location TEXT,
                url TEXT,
                description TEXT,
                required_skills TEXT,
                nice_to_have_skills TEXT,
                salary_min INTEGER,
                salary_max INTEGER,
                salary_currency TEXT,
                salary_period TEXT,
                job_type TEXT,
                employment_type TEXT,
                source_url TEXT,
                date_posted TIMESTAMP,
                date_scraped TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_remote BOOLEAN DEFAULT FALSE,
                experience_level TEXT,
                education_required TEXT,
                company_industry TEXT,
                location_type TEXT,
                skills TEXT,
                is_new BOOLEAN DEFAULT TRUE,
                is_urgent BOOLEAN DEFAULT FALSE,
                is_saved BOOLEAN DEFAULT FALSE,
                status TEXT DEFAULT 'new',
                FOREIGN KEY (user_id) REFERENCES user (id),
                UNIQUE (user_id, source_url) ON CONFLICT REPLACE
            )
        ''')
        
        # Create job_skills table
        logger.info("Creating job_skills table...")
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS job_skills (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id INTEGER NOT NULL,
                skill TEXT NOT NULL,
                is_required BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (job_id) REFERENCES jobs (id) ON DELETE CASCADE
            )
        ''')
        
        conn.commit()
        logger.info("Database tables created successfully!")
        
        # Check for test user and create if needed
        cursor.execute('SELECT id FROM user WHERE username = ?', ('testuser',))
        if not cursor.fetchone():
            logger.info("Creating test user...")
            create_test_user()
            
        # Verify all tables were created
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        logger.info(f"Created tables: {[t[0] for t in tables]}")
        
        return True
        
    except sqlite3.Error as e:
        logger.error(f"SQLite error initializing database: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        if conn:
            conn.rollback()
        return False
        
    except Exception as e:
        logger.error(f"Unexpected error initializing database: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        if conn:
            conn.rollback()
        return False
        
    finally:
        if conn:
            conn.close()

def create_test_user():
    """Create a test user for development."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Enable foreign keys
        cursor.execute('PRAGMA foreign_keys = ON')
        
        # Verify the user table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='user'")
        if not cursor.fetchone():
            logger.error("Cannot create test user: 'user' table does not exist")
            return None
            
        # Check if test user already exists
        cursor.execute('SELECT id FROM user WHERE username = ?', ('testuser',))
        existing_user = cursor.fetchone()
        if existing_user:
            logger.info(f"Test user already exists with ID {existing_user[0]}")
            return existing_user[0]
            
        # Insert test user with created_at
        cursor.execute('''
            INSERT INTO user (username, email, password, skills, created_at)
            VALUES (?, ?, ?, ?, datetime('now'))
        ''', ('testuser', 'test@example.com', 'testpass', json.dumps(['Python', 'SQL', 'JavaScript'])))
        
        user_id = cursor.lastrowid
        logger.info(f"Created test user with ID {user_id}")
        
        conn.commit()
        return user_id
        
    except sqlite3.Error as e:
        logger.error(f"SQLite error creating test user: {e}")
        logger.error(traceback.format_exc())
        if conn:
            conn.rollback()
        return None
        
    except Exception as e:
        logger.error(f"Unexpected error creating test user: {e}")
        logger.error(traceback.format_exc())
        if conn:
            conn.rollback()
        return None
        
    finally:
        if conn:
            conn.close()

def check_database():
    """Check database tables and user."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get list of tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        logger.info(f"Tables in database: {tables}")
        
        # Check user table
        cursor.execute("SELECT * FROM user")
        users = cursor.fetchall()
        logger.info(f"Users in database: {users}")
        
        return True
        
    except sqlite3.Error as e:
        logger.error(f"Error checking database: {e}")
        return False
        
    finally:
        if conn:
            conn.close()

def clear_jobs_table():
    """Clear all jobs from the database to prepare for fresh scraping."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM jobs")
        conn.commit()
        print("Jobs table cleared for fresh scraping.")
    except sqlite3.Error as e:
        print(f"Error clearing jobs table: {e}")
        conn.rollback()  # Rollback any changes in case of error
        raise  # Re-raise the exception to be handled upstream
    finally:
        conn.close()

def clear_jobs_database():
    """
    Clear all jobs from the database before a new scraping session
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("DELETE FROM jobs")
        conn.commit()
        print("Jobs database cleared successfully")
    except Exception as e:
        print(f"Error clearing jobs database: {e}")
        conn.rollback()
    finally:
        conn.close()
        
def save_job_to_db(job_data, user_id):
    """
    Save a job to the database.
    
    Args:
        job_data (dict): Dictionary containing job information including skills
        user_id (int): ID of the user who scraped/saved the job
        
    Returns:
        int: ID of the saved job, or None if there was an error
    """
    if not job_data:
        logger.error("No job data provided.")
        return None
        
    # Ensure user_id is set either from parameter or from job_data
    if not user_id and 'user_id' in job_data:
        user_id = job_data['user_id']
        
    if not user_id:
        logger.warning("No user_id provided for job. Using default user.")
        user_id = 1  # Use default user if none provided
        
    conn = None
    try:
        # First verify the user exists in the user table
        conn = get_db_connection()
        cursor = conn.cursor()
          # Set foreign key support and verify it's working
        cursor.execute('PRAGMA foreign_keys = ON')
        cursor.execute('PRAGMA foreign_keys')
        if cursor.fetchone()[0] == 0:
            logger.error("Foreign key support is not enabled")
            return None
            
        # Verify the 'user' table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='user'")
        if not cursor.fetchone():
            logger.error("The 'user' table does not exist. Database may not be properly initialized.")
            return None
            
        # Check if user exists
        cursor.execute('SELECT id FROM user WHERE id = ?', (user_id,))
        user = cursor.fetchone()
        if not user:
            logger.error(f"User with ID {user_id} does not exist in user table")
            return None
        
        # Clean and prepare job data
        job_data = _clean_job_data(job_data)
        if not job_data:
            return None
            
        job_data['user_id'] = user_id
        job_data['date_scraped'] = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
        
        # Serialize lists as JSON strings
        if 'required_skills' in job_data and isinstance(job_data['required_skills'], list):
            job_data['required_skills'] = json.dumps(job_data['required_skills'])
        if 'nice_to_have_skills' in job_data and isinstance(job_data['nice_to_have_skills'], list):
            job_data['nice_to_have_skills'] = json.dumps(job_data['nice_to_have_skills'])
        if 'skills' in job_data and isinstance(job_data['skills'], list):
            job_data['skills'] = json.dumps(job_data['skills'])

        # Remove any fields that don't exist in the table
        cursor.execute("PRAGMA table_info(jobs)")
        valid_columns = {row[1] for row in cursor.fetchall()}
        job_data = {k: v for k, v in job_data.items() if k in valid_columns}

        # Check if job already exists for this user
        cursor.execute('''
            SELECT id FROM jobs 
            WHERE (source_url = ? AND source_url IS NOT NULL AND user_id = ?)
            OR (title = ? AND company = ? AND user_id = ?)
        ''', (
            job_data.get('source_url'),
            user_id,
            job_data.get('title'),
            job_data.get('company'),
            user_id
        ))
        existing_job = cursor.fetchone()

        if existing_job:
            # Update existing job
            job_id = existing_job[0]
            update_fields = []
            update_values = []
            
            for key, value in job_data.items():
                if key != 'id' and value is not None:
                    update_fields.append(f"{key} = ?")
                    update_values.append(value)
            
            if update_fields:
                update_query = f'''
                    UPDATE jobs 
                    SET {', '.join(update_fields)}
                    WHERE id = ? AND user_id = ?
                '''
                cursor.execute(update_query, update_values + [job_id, user_id])
                conn.commit()
                return job_id
        else:
            # Insert new job
            fields = []
            values = []
            placeholders = []
            
            for key, value in job_data.items():
                if value is not None:
                    fields.append(key)
                    values.append(value)
                    placeholders.append('?')
            
            insert_query = f'''
                INSERT INTO jobs ({', '.join(fields)})
                VALUES ({', '.join(placeholders)})
            '''
            try:
                cursor.execute(insert_query, values)
                job_id = cursor.lastrowid
                conn.commit()
                return job_id
            except sqlite3.IntegrityError as e:
                if "FOREIGN KEY constraint failed" in str(e):
                    # Handle case where user_id doesn't exist
                    logger.warning(f"Foreign key constraint failed. Using default user instead. Error: {e}")
                    # Update job_data to use default user (ID 1)
                    for i, field in enumerate(fields):
                        if field == 'user_id':
                            values[i] = 1
                            break
                    # Try one more time with the default user
                    try:
                        cursor.execute(insert_query, values)
                        job_id = cursor.lastrowid
                        conn.commit()
                        return job_id
                    except sqlite3.Error as e2:
                        logger.error(f"Still failed with default user: {e2}")
                        conn.rollback()
                        return None
                else:
                    logger.error(f"Failed to insert job '{job_data.get('title')}': {e}")
                    logger.error(f"Job data: {job_data}")
                    conn.rollback()
                    return None

        return None

    except sqlite3.Error as e:
        logger.error(f"Database error while saving job '{job_data.get('title')}': {str(e)}")
        logger.error(f"Job data: {job_data}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        if conn:
            conn.rollback()
        return None
        
    except Exception as e:
        logger.error(f"Unexpected error while saving job '{job_data.get('title')}': {str(e)}")
        logger.error(f"Job data: {job_data}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        if conn:
            conn.rollback()
        return None
        
    finally:
        if conn:
            conn.close()

def add_job(job_data, skills_list=None):
    """Add a job to the database."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Get column names from the job_data dictionary
        columns = ', '.join(job_data.keys())
        placeholders = ', '.join(['?' for _ in job_data])
        values = list(job_data.values())
        
        query = f"INSERT INTO jobs ({columns}) VALUES ({placeholders})"
        
        cursor.execute(query, values)
        job_id = cursor.lastrowid
        
        # Add skills to job_skills table if provided
        if skills_list:
            add_job_skills(job_id, skills_list)
        
        conn.commit()
        return job_id
    except sqlite3.Error as e:
        print(f"Error adding job: {e}")
        conn.rollback()
        return None
    finally:
        conn.close()

def add_job_skills(job_id, skills):
    """Add skills for a specific job to the job_skills table."""
    if not skills:
        return
    
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # First delete any existing skills for this job
        cursor.execute("DELETE FROM job_skills WHERE job_id = ?", (job_id,))
        
        # Insert new skills
        for skill in skills:
            cursor.execute(
                "INSERT INTO job_skills (job_id, skill) VALUES (?, ?)",
                (job_id, skill.strip())
            )
        conn.commit()
    except sqlite3.Error as e:
        print(f"Error adding job skills: {e}")
        conn.rollback()
    finally:
        conn.close()

def get_job_skills(job_id):
    """Get all skills for a specific job."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT skill FROM job_skills WHERE job_id = ?", (job_id,))
    skills = [row['skill'] for row in cursor.fetchall()]
    conn.close()
    return skills

def get_all_unique_skills():
    """Get a list of all unique skills from job_skills table."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT skill FROM job_skills ORDER BY skill")
    skills = [row['skill'] for row in cursor.fetchall()]
    conn.close()
    return skills

def get_all_jobs():
    """Get all jobs from the database."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get all jobs
    cursor.execute("SELECT * FROM jobs")
    
    jobs = cursor.fetchall()
    
    # Convert Row objects to dictionaries
    jobs_list = []
    for job in jobs:
        job_dict = dict(job)
        
        # Parse skills from JSON string if needed
        if 'skills' in job_dict and isinstance(job_dict['skills'], str):
            try:
                job_dict['skills'] = json.loads(job_dict['skills'])
            except json.JSONDecodeError:
                # If not valid JSON, try splitting by comma
                job_dict['skills'] = job_dict['skills'].split(',') if job_dict['skills'] else []
        
        jobs_list.append(job_dict)
    
    conn.close()
    return jobs_list

def search_jobs_db(query="All", location="All", resume_skills=None, user_id=None, job_type="All"):
    """Search jobs in the database with filtering and skill matching."""
    conn = get_db_connection()
    try:
        # Check if user_id column exists in jobs table
        cursor = conn.execute("PRAGMA table_info(jobs)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if "user_id" not in columns:
            # Add user_id column if it doesn't exist
            try:
                conn.execute("ALTER TABLE jobs ADD COLUMN user_id INTEGER")
                conn.commit()
                logger.info("Added user_id column to jobs table")
            except Exception as e:
                logger.error(f"Error adding user_id column: {e}")
        
        # Enable datetime parsing from SQLite
        conn.row_factory = sqlite3.Row
        
        if not user_id:
            print("Warning: No user_id provided for job search")
        
        # Normalize inputs
        if location:
            location = location.strip()
        if resume_skills:
            resume_skills = [skill.strip().lower() for skill in resume_skills]
        if job_type:
            job_type = job_type.strip()
        
        # Base query joining jobs with job_skills
        base_query = '''
        SELECT j.*, GROUP_CONCAT(js.skill) as job_skills,
               strftime('%Y-%m-%d %H:%M:%S', j.date_scraped) as date_scraped_str
        FROM jobs j
        LEFT JOIN job_skills js ON j.id = js.job_id
        '''
        
        where_clauses = []
        params = []
        
        # Add search term filters if not "All"
        if query.lower() != "all":
            search_terms = [term.strip() for term in query.split()]
            for search_term in search_terms:
                where_clauses.append('''
                (
                    LOWER(j.title) LIKE ? OR
                    LOWER(j.company) LIKE ? OR
                    LOWER(j.description) LIKE ? OR
                    EXISTS (
                        SELECT 1 FROM job_skills js2 
                        WHERE js2.job_id = j.id 
                        AND LOWER(js2.skill) LIKE ?
                    )
                )
                ''')
                search_pattern = f'%{search_term.lower()}%'
                params.extend([search_pattern, search_pattern, search_pattern, search_pattern])
          # Add location filter if not "All"
        if location.lower() != "all":
            # Split location into city and state/country if provided
            location_parts = [part.strip().lower() for part in location.split(',')]
            location_clause = []
            for part in location_parts:
                location_clause.append('(LOWER(j.location) LIKE ? OR LOWER(j.location) = ?)')
                params.extend([f'%{part}%', part])  # Add both fuzzy and exact match parameters
            where_clauses.append('(' + ' OR '.join(location_clause) + ')')        # Add user_id filter if provided
        if user_id:
            try:
                # Only add user_id filter if the column exists
                cursor = conn.execute("PRAGMA table_info(jobs)")
                columns = [column[1] for column in cursor.fetchall()]
                
                if "user_id" in columns:
                    if where_clauses:
                        where_clauses.append('j.user_id = ?')
                    else:
                        base_query += ' WHERE j.user_id = ?'
                    params.append(user_id)
                else:
                    logger.warning("user_id column not found in jobs table, skipping user_id filter")
            except Exception as e:
                logger.error(f"Error checking for user_id column: {e}")
                # Continue without the user_id filter
        
        # Add WHERE clause if we have other conditions
        if where_clauses and 'WHERE' not in base_query:
            base_query += ' WHERE ' + ' AND '.join(where_clauses)
        elif where_clauses:
            base_query += ' AND ' + ' AND '.join(where_clauses)
        
        # Group by job_id to combine skills
        base_query += ' GROUP BY j.id'
        
        # Execute query and fetch results
        cursor = conn.execute(base_query, params)
        jobs = cursor.fetchall()
          # Process results and calculate skill matches
        job_list = []
        for job in jobs:
            job_dict = dict(job)
            
            # Initialize match percentage early
            match_percentage = 0
              # Convert date_scraped_str to datetime object if it exists
            if 'date_scraped_str' in job_dict:
                try:
                    job_dict['date_scraped'] = datetime.strptime(job_dict['date_scraped_str'], '%Y-%m-%d %H:%M:%S')
                    del job_dict['date_scraped_str']  # Remove the string version
                except (ValueError, TypeError):
                    job_dict['date_scraped'] = None
            
            # Get job skills from either job_skills table or skills column
            job_skills = set()
            
            # Add skills from job_skills table
            if job_dict.get('job_skills'):
                job_skills.update(skill.strip() for skill in job_dict['job_skills'].split(','))
            
            # Add skills from skills column (if any)
            if job_dict.get('skills'):
                try:
                    skills_from_column = json.loads(job_dict['skills'])
                    if isinstance(skills_from_column, list):
                        job_skills.update(skill.strip().lower() for skill in skills_from_column)
                    elif isinstance(skills_from_column, str):
                        job_skills.update(skill.strip().lower() for skill in skills_from_column.split(','))
                except json.JSONDecodeError:
                    skills_from_column = job_dict['skills'].split(',')
                    job_skills.update(skill.strip().lower() for skill in skills_from_column)
            
            # Clean and normalize job skills
            job_skills = {s for s in job_skills if s and len(s) >= 2}
            job_dict['skills'] = sorted(job_skills)
              # Calculate skill matches if resume_skills provided
            if resume_skills:
                resume_skills_lower = [skill.lower() for skill in resume_skills]
                matching_skills = [skill for skill in job_skills if skill in resume_skills_lower]
                missing_skills = [skill for skill in job_skills if skill not in resume_skills_lower]
                
                # Calculate match percentage
                total_job_skills = len(job_skills)
                if total_job_skills > 0:
                    match_percentage = (len(matching_skills) / total_job_skills) * 100
                else:
                    match_percentage = 0
                
                # Only include jobs that have at least one matching skill
                if len(matching_skills) > 0:
                    job_dict.update({
                        'matching_resume_skills': len(matching_skills),
                        'match_percentage': round(match_percentage),
                        'matching_skills': matching_skills,
                        'missing_skills': missing_skills,
                        'total_required_skills': total_job_skills
                    })
                    job_list.append(job_dict)
                else:
                    job_list.append(job_dict)
            
            # Removed duplicate job_list.append(job_dict) here
          # Ensure we have unique job IDs in our result
        seen_job_ids = set()
        unique_job_list = []
        for job in job_list:
            if job['id'] not in seen_job_ids:
                seen_job_ids.add(job['id'])
                unique_job_list.append(job)
        
        job_list = unique_job_list
            
        # Sort jobs by match percentage if resume skills provided
        if resume_skills:
            job_list.sort(key=lambda x: (
                x.get('match_percentage', 0),
                x.get('matching_resume_skills', 0),
                len(x.get('skills', [])),
                x.get('title', '')
            ), reverse=True)
        
        return job_list
    finally:
        if conn:
            conn.close()

def get_job_by_id(job_id):
    """Get a job by its ID."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM jobs WHERE id = ?", (job_id,))
    job = cursor.fetchone()
    
    if job:
        job_dict = dict(job)
        
        # Parse skills from JSON string if needed
        if 'skills' in job_dict and isinstance(job_dict['skills'], str):
            try:
                job_dict['skills'] = json.loads(job_dict['skills'])
            except json.JSONDecodeError:
                # If not valid JSON, try splitting by comma
                job_dict['skills'] = job_dict['skills'].split(',') if job_dict['skills'] else []
        
        conn.close()
        return job_dict
    
    conn.close()
    return None

def add_work_experience(user_id, company, title, start_date, end_date=None, description=None, current_job=False):
    """Add a work experience entry for a user."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
    INSERT INTO work_experience (user_id, company, title, start_date, end_date, description, current_job)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (user_id, company, title, start_date, end_date, description, current_job))
    
    exp_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return exp_id

def update_work_experience(exp_id, user_id, company, title, start_date, end_date=None, description=None, current_job=False):
    """Update a work experience entry."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
    UPDATE work_experience 
    SET company = ?, title = ?, start_date = ?, end_date = ?, description = ?, current_job = ?
    WHERE id = ? AND user_id = ?
    ''', (company, title, start_date, end_date, description, current_job, exp_id, user_id))
    
    success = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return success

def delete_work_experience(exp_id, user_id):
    """Delete a work experience entry."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('DELETE FROM work_experience WHERE id = ? AND user_id = ?', (exp_id, user_id))
    
    success = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return success

def get_user_work_experience(user_id):
    """Get all work experience entries for a user."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM work_experience WHERE user_id = ? ORDER BY start_date DESC', (user_id,))
    experiences = cursor.fetchall()
    
    conn.close()
    return [dict(exp) for exp in experiences]

def add_education(user_id, institution, degree, field_of_study=None, start_date=None, 
                 end_date=None, gpa=None, description=None):
    """Add an education entry for a user."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
    INSERT INTO education (user_id, institution, degree, field_of_study, 
                         start_date, end_date, gpa, description)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (user_id, institution, degree, field_of_study, 
          start_date, end_date, gpa, description))
    
    edu_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return edu_id

def update_education(edu_id, user_id, institution, degree, field_of_study=None, 
                    start_date=None, end_date=None, gpa=None, description=None):
    """Update an education entry."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
    UPDATE education 
    SET institution = ?, degree = ?, field_of_study = ?, 
        start_date = ?, end_date = ?, gpa = ?, description = ?
    WHERE id = ? AND user_id = ?
    ''', (institution, degree, field_of_study, start_date, 
          end_date, gpa, description, edu_id, user_id))
    
    success = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return success

def delete_education(edu_id, user_id):
    """Delete an education entry."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('DELETE FROM education WHERE id = ? AND user_id = ?', (edu_id, user_id))
    
    success = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return success

def get_user_education(user_id):
    """Get all education entries for a user."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM education WHERE user_id = ? ORDER BY start_date DESC', (user_id,))
    education = cursor.fetchall()
    
    conn.close()
    return [dict(edu) for edu in education]

def update_user_profile(user_id, username=None, email=None, skills=None, 
                       certifications=None, summary=None):
    """Update a user's profile information."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    update_fields = []
    params = []
    
    if username is not None:
        update_fields.append('username = ?')
        params.append(username)
    if email is not None:
        update_fields.append('email = ?')
        params.append(email)
    if skills is not None:
        update_fields.append('skills = ?')
        params.append(skills)
    if certifications is not None:
        update_fields.append('certifications = ?')
        params.append(certifications)
    if summary is not None:
        update_fields.append('summary = ?')
        params.append(summary)
    
    if update_fields:
        params.append(user_id)
        query = f'''        UPDATE user 
        SET {', '.join(update_fields)}
        WHERE id = ?
        '''
        cursor.execute(query, params)
        
        success = cursor.rowcount > 0
        conn.commit()
        conn.close()
        return success
    
    conn.close()
    return False

def jobs_need_refresh(hours=24):
    """Check if jobs data is stale and needs refreshing."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Get most recent job's timestamp
        cursor.execute("SELECT MAX(date_scraped) FROM jobs")
        last_scraped = cursor.fetchone()[0]
        
        if not last_scraped:
            return True
        
        # Convert string to datetime
        try:
            last_scraped_dt = datetime.strptime(last_scraped, '%Y-%m-%d %H:%M:%S')
        except (ValueError, TypeError):
            return True
            
        # Check if data is older than specified hours
        time_diff = datetime.utcnow() - last_scraped_dt
        return time_diff.total_seconds() > (hours * 3600)
        
    except Exception as e:
        print(f"Error checking job refresh status: {e}")
        return True
    finally:
        conn.close()

def _serialize_skills(skills):
    """Convert skills list to JSON string for database storage."""
    if skills is None:
        return '[]'
    if isinstance(skills, str):
        try:
            # Check if it's already a JSON string
            json.loads(skills)
            return skills
        except json.JSONDecodeError:
            # If it's a comma-separated string, convert to list
            skills_list = [s.strip() for s in skills.split(',') if s.strip()]
            return json.dumps(skills_list)
    return json.dumps(list(skills))

def _deserialize_skills(skills_str):
    """Convert skills JSON string from database to list."""
    if not skills_str:
        return []
    try:
        if isinstance(skills_str, str):
            return json.loads(skills_str)
        return list(skills_str)
    except json.JSONDecodeError:
        logger.warning(f"Failed to parse skills JSON: {skills_str}")
        return []

def _clean_job_data(job_data):
    """Clean and validate job data before saving to database."""
    try:
        cleaned = job_data.copy()
        
        # Ensure required fields exist
        required_fields = ['title', 'company']
        if not all(cleaned.get(field) for field in required_fields):
            logger.error(f"Missing required fields. Data: {cleaned}")
            return None
            
        # Clean text fields
        text_fields = ['title', 'company', 'location', 'description']
        for field in text_fields:
            if field in cleaned:
                cleaned[field] = cleaned[field].strip()
                
        # Ensure lists are properly formatted
        list_fields = ['required_skills', 'nice_to_have_skills', 'skills']
        for field in list_fields:
            if field in cleaned:
                if isinstance(cleaned[field], str):
                    try:
                        cleaned[field] = json.loads(cleaned[field])
                    except json.JSONDecodeError:
                        cleaned[field] = [s.strip() for s in cleaned[field].split(',') if s.strip()]
                elif not isinstance(cleaned[field], list):
                    cleaned[field] = []
                    
        return cleaned
        
    except Exception as e:
        logger.error(f"Error cleaning job data: {str(e)}")
        logger.error(f"Original data: {job_data}")
        return None

# If this file is run directly, initialize the database
if __name__ == "__main__":
    initialize_database()
    print("Database initialized. No sample jobs added.")
