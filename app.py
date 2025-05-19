import os
import sys
import re
import traceback
import logging
from datetime import datetime
from flask import Flask, request, jsonify, render_template, flash, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
import sqlalchemy
from flask_migrate import Migrate
from flask_login import LoginManager, UserMixin, login_user, current_user, logout_user, login_required
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.utils import secure_filename
from database_manager import search_jobs_db, initialize_database as init_db, clear_jobs_table
from courses import fetch_courses_by_skills
from scraper import scrape_jobs
from insights import get_job_insights, get_skill_options
from cleanup_utils import cleanup_static_graphs, cleanup_job_related_data
import json
import subprocess
import time
import spacy
from job_utils import count_user_jobs, get_user_skills
from job_counter import get_job_counts
from flask_bcrypt import Bcrypt

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)
from werkzeug.utils import secure_filename
from werkzeug.exceptions import BadRequest
from nlp_utils import extract_skills_from_text, extract_location_from_text
from database_manager import (
    get_all_jobs,
    add_work_experience, update_work_experience, delete_work_experience, get_user_work_experience,
    add_education, update_education, delete_education, get_user_education,
    update_user_profile, jobs_need_refresh
)
from resume_parser import parse_resume, extract_text_from_pdf, extract_text_from_docx, extract_text_from_txt
from flask_wtf.csrf import CSRFProtect
from forms import (
    LoginForm, RegistrationForm, JobSearchForm, ProfileForm,
    WorkExperienceForm, EducationForm, ResumeUploadForm
)

# Define constants
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'doc', 'docx'}

# Ensure spaCy and its model are available
try:
    import spacy
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "spacy"])
    import spacy

try:
    nlp = spacy.load("en_core_web_sm")
except OSError:
    subprocess.check_call([sys.executable, "-m", "spacy", "download", "en_core_web_sm"])
    nlp = spacy.load("en_core_web_sm")

# Initialize Flask app
app = Flask(__name__)

# Load configuration based on environment
# Set base directory and instance path before config loading
basedir = os.path.abspath(os.path.dirname(__file__))
instance_dir = os.path.join(basedir, 'instance')

# Configure Flask instance path explicitly
app = Flask(__name__, 
           instance_path=instance_dir)  # Explicitly set instance path

# Load configuration
from config import get_config
app.config.from_object(get_config())

# Ensure instance directory exists and has proper permissions
if not os.path.exists(instance_dir):
    try:
        os.makedirs(instance_dir, exist_ok=True)
        logger.info(f"Created instance directory at {instance_dir}")
        # Ensure directory has proper permissions
        import stat
        os.chmod(instance_dir, stat.S_IRWXU)
    except Exception as e:
        logger.error(f"Error creating/setting permissions on instance directory: {e}")
        logger.error(traceback.format_exc())

# Set upload folder
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Fix the SQLite URI format - use posix-style paths even on Windows
db_path = os.path.join(instance_dir, 'job_recommender.db')
db_uri = f'sqlite:///{db_path.replace(os.sep, "/")}'
app.config['SQLALCHEMY_DATABASE_URI'] = db_uri
logger.info(f"Using database at: {db_path} with URI: {app.config['SQLALCHEMY_DATABASE_URI']}")

# Add connection pooling and timeout settings
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'connect_args': {
        'check_same_thread': False,  # Allow multithreaded access
        'timeout': 30  # Increase timeout for busy situations
    },
    'pool_pre_ping': True  # Check connections before using them
}

# Create instance folder if it doesn't exist
with app.app_context():
    if not os.path.exists(app.instance_path):
        os.makedirs(app.instance_path, exist_ok=True)
        logger.info(f"Created Flask instance directory at {app.instance_path}")

# Verify database path exists
if not os.path.exists(db_path):
    logger.warning(f"Database file not found at {db_path}. It will be created on first access.")

# Initialize CSRF protection
csrf = CSRFProtect(app)

# Import security utilities
from security import limiter_handler

# Initialize Flask-Limiter for rate limiting
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://",
    strategy="fixed-window",
    on_breach=limiter_handler
)

# Initialize SQLAlchemy
from models import db, User  # Import db and User from models.py
db.init_app(app)

# Create tables if they don't exist
with app.app_context():
    try:
        logger.info("Creating database tables if they don't exist...")
        db.create_all()
        logger.info("Database tables created/verified successfully.")
    except Exception as e:
        logger.error(f"Error creating database tables: {e}")
        logger.error(traceback.format_exc())

# Initialize Flask-Migrate
migrate = Migrate(app, db)

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Initialize Flask-Bcrypt
bcrypt = Bcrypt(app)

# Import and set up security features
from security import set_secure_headers, require_https, limiter_handler

# Configure security response headers
@app.after_request
def add_security_headers(response):
    """Add security headers to all responses"""
    return set_secure_headers(response)

# Require HTTPS in production
@app.before_request
def enforce_https():
    """Enforce HTTPS in production environments"""
    return require_https()

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Create upload folder if it doesn't exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def ensure_spacy_installed():
    """Ensure spaCy is installed."""
    try:
        import spacy
        logger.info("spaCy is already installed.")
        return True
    except ImportError:
        logger.info("spaCy not found. Installing...")
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", "spacy"],
                capture_output=True, 
                text=True,
                check=False
            )
            
            if result.returncode != 0:
                logger.error(f"Error installing spaCy: {result.stderr}")
                return False
            
            # Verify installation worked
            try:
                import spacy
                return True
            except ImportError:
                logger.error("spaCy still not available after installation.")
                return False
        except Exception as e:
            logger.error(f"Failed to install spaCy: {e}")
            return False


def ensure_model_downloaded(model_name='en_core_web_sm'):
    """Ensure the spaCy model is downloaded."""
    try:
        import spacy
        try:
            spacy.load(model_name)
            logger.info(f"spaCy model '{model_name}' is already downloaded.")
            return True
        except OSError:
            logger.info(f"spaCy model '{model_name}' not found. Downloading...")
            try:
                # Use a more robust download command with full output capture
                result = subprocess.run(
                    [sys.executable, "-m", "spacy", "download", model_name],
                    capture_output=True,
                    text=True,
                    check=False  # Don't raise exception on non-zero exit
                )
                
                if result.returncode != 0:
                    logger.error(f"Error downloading spaCy model: {result.stderr}")
                    return False
                    
                logger.info(f"Model download output: {result.stdout}")
                logger.info(f"Model '{model_name}' downloaded successfully.")
                
                # Verify model was downloaded by trying to load it
                try:
                    spacy.load(model_name)
                    return True
                except OSError:
                    logger.error(f"Model '{model_name}' still not available after download.")
                    return False
            except Exception as e:
                logger.error(f"Failed to download model: {e}")
                return False
    except ImportError:
        logger.error("Cannot download model because spaCy is not installed.")
        return False


def run_scraper(query="All", location="All"):
    """
    Run the job scraper with the specified query and location.
    
    Args:
        query (str): Job search query
        location (str): Location to search in
        
    Returns:
        bool: True if successful, False otherwise
    """
    logger.info(f"Starting job scraper with query='{query}', location='{location}'")
    try:
        logger.info(f"Running scraper with query='{query}', location='{location}'")
        
        # Initialize database and ensure tables exist
        init_db()
        clear_jobs_table()
        
        # Ensure spaCy is installed and model is downloaded
        ensure_spacy_installed()
        
        # Prepare and run the scraper process
        scraper_command = [sys.executable, "scraper.py", "--query", query, "--location", location]
        logger.info(f"Running scraper with command: {' '.join(scraper_command)}")
        
        result = subprocess.run(scraper_command, capture_output=True, text=True)
        if result.returncode != 0:
            logger.error(f"Scraper failed with error: {result.stderr}")
            return False
        
        logger.info("Scraper completed successfully")
        return True
    except Exception as e:
        logger.error(f"Error running scraper: {str(e)}")
        logger.error(traceback.format_exc())
        return False


def jobs_need_refresh():
    """Check if jobs need to be refreshed based on time elapsed."""
    # Get the last scrape time from the session
    last_scrape = session.get('last_scrape_time')
    if not last_scrape:
        return True
    
    try:
        elapsed = (datetime.utcnow() - datetime.fromisoformat(last_scrape)).total_seconds()
        # Only refresh if it's been more than 6 hours
        return elapsed > 21600  # 6 hours
    except:
        return True


# Add template filters
@app.template_filter('from_json')
def from_json_filter(value):
    """Convert a JSON string to Python object."""
    if not value:
        return []
    try:
        if isinstance(value, str):
            # If it looks like a JSON array or object
            if value.startswith('[') or value.startswith('{'):
                return json.loads(value)
            # If it's just a comma-separated string
            return [s.strip() for s in value.split(',') if s.strip()]
        return value if isinstance(value, (list, tuple)) else []
    except (json.JSONDecodeError, AttributeError):
        # If it's not JSON and not a string, return empty list
        return []


@app.template_filter('nl2br')
def nl2br(value):
    """Convert newlines to HTML line breaks."""
    if not value:
        return value
    return value.replace('\n', '<br>')


@app.route('/')
def index():
    """Landing page - redirects to dashboard if user is logged in"""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return render_template('index.html')


@app.route('/dashboard')
@login_required
def dashboard():
    """Dashboard page showing user stats and recommendations"""
    # Get user's resume skills from session
    resume_skills = session.get(f'user_{current_user.id}_resume_skills', [])
    
    # Also check for skills in user profile
    profile_skills = []
    if current_user.skills:
        profile_skills = [s.strip() for s in current_user.skills.split(',') if s.strip()]
    
    # Combine all skills and remove duplicates
    all_skills = list(set(resume_skills + profile_skills))
    
    # Calculate profile completion
    profile_completion = 0
    if all_skills:  # Check if user has any skills (from resume or profile)
        profile_completion += 25
    
    # Check work experience safely
    try:
        if current_user.work_experience and len(current_user.work_experience) > 0:
            profile_completion += 25
    except Exception as e:
        logger.error(f"Error checking work experience: {e}")
    
    # Check education safely
    try:
        if current_user.education and len(current_user.education) > 0:
            profile_completion += 25
    except Exception as e:
        logger.error(f"Error checking education: {e}")
    
    # Check if profile summary exists
    if current_user.summary:
        profile_completion += 25
      # Get matching jobs using all available skills
    jobs = search_jobs_db(query="All", location="All", resume_skills=all_skills, user_id=current_user.id)
    
    # Process jobs to ensure proper data format
    for job in jobs:
        # Handle required skills to ensure it's a list
        if isinstance(job.get('required_skills'), str):
            try:
                job['required_skills'] = json.loads(job['required_skills'])
            except:
                job['required_skills'] = []
        elif job.get('required_skills') is None:
            job['required_skills'] = []
            
        # Handle nice to have skills to ensure it's a list
        if isinstance(job.get('nice_to_have_skills'), str):
            try:
                job['nice_to_have_skills'] = json.loads(job['nice_to_have_skills'])
            except:
                job['nice_to_have_skills'] = []
        elif job.get('nice_to_have_skills') is None:
            job['nice_to_have_skills'] = []
            
        # Process date for proper sorting
        if 'date_posted' in job and job['date_posted']:
            try:
                # Try to parse the date if it's a string
                if isinstance(job['date_posted'], str):
                    job['date_obj'] = datetime.strptime(job['date_posted'], '%Y-%m-%d')
                else:
                    job['date_obj'] = job['date_posted']
            except (ValueError, TypeError):
                # If date can't be parsed, use current date
                job['date_obj'] = datetime.now()
        else:
            job['date_obj'] = datetime.now()
      # First sort by date - most recent first
    jobs.sort(key=lambda x: x.get('date_obj', datetime.now()), reverse=True)
      # Use the job_counter utility to get standardized job counts
    job_counts = get_job_counts(jobs, user_id=current_user.id)
    
    # Get the matching jobs with score > 40% from the job counts
    matching_jobs = [job for job in jobs if job.get('match_percentage', 0) > 40]
      # Get missing skills (skills that appear most in jobs but user doesn't have)
    all_required_skills = []
    for job in jobs:        
        all_required_skills.extend(job.get('required_skills', []))
        all_required_skills.extend(job.get('nice_to_have_skills', []))
    
    # Convert all skills to lowercase for case-insensitive comparison
    all_skills_lower = [skill.lower() for skill in all_skills if skill]
    
    # Count skill frequencies
    from collections import Counter
    skill_freq = Counter(all_required_skills)
    
    # Get missing skills (case-insensitive comparison)
    missing_skills = [skill for skill, freq in skill_freq.most_common() 
                     if skill and skill.lower() not in all_skills_lower and freq > 1]
    
    # Store missing skills in session for use in other parts of the app
    session[f'user_{current_user.id}_missing_skills'] = missing_skills    # Dashboard data loaded successfully
    return render_template('dashboard.html',
                           profile_completion=profile_completion,
                           user_skills_count=len(all_skills),
                           missing_skills_count=len(missing_skills),
                           recent_jobs=matching_jobs[:5] if matching_jobs else [],
                           missing_skills=missing_skills[:10] if missing_skills else [],
                           resume_skills=all_skills,        # Pass ALL skills for display
                           job_counts=job_counts,           # Pass all job counts for consistency
                           active_page='dashboard')


@app.route('/register', methods=['GET', 'POST'])
@limiter.limit("10 per hour")
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = RegistrationForm()
    if form.validate_on_submit():
        try:
            hashed_password = bcrypt.generate_password_hash(form.password.data).decode('utf-8')
            user = User(username=form.username.data, email=form.email.data, password=hashed_password)
            db.session.add(user)
            db.session.commit()
            flash('Your account has been created! You are now able to log in', 'success')
            return redirect(url_for('login'))
        except sqlalchemy.exc.IntegrityError as e:
            db.session.rollback()
            if "UNIQUE constraint failed: user.username" in str(e):
                flash(f'Username "{form.username.data}" is already taken. Please choose a different username.', 'danger')
            elif "UNIQUE constraint failed: user.email" in str(e):
                flash(f'Email address "{form.email.data}" is already registered. Please use a different email or try logging in.', 'danger')
            else:
                flash('An error occurred during registration. Please try again.', 'danger')
            
    return render_template('register.html', title='Register', form=form, current_year=datetime.now().year, page_class='register-page')


@app.route('/login', methods=['GET', 'POST'])
@limiter.limit("10 per minute")
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = LoginForm()
    if form.validate_on_submit():
        try:
            logger.info(f"Attempting login for user with email: {form.email.data}")
            
            # Ensure database connection
            from sqlalchemy import inspect
            inspector = inspect(db.engine)
            if not inspector.has_table("user"):
                logger.error("User table not found in database. Database may not be initialized correctly.")
                flash('System error: Database not properly set up. Please contact support.', 'danger')
                return render_template('login.html', title='Login', form=form, current_year=datetime.now().year, page_class='login-page')
            
            user = User.query.filter_by(email=form.email.data).first()
            if user and bcrypt.check_password_hash(user.password, form.password.data):
                login_user(user, remember=form.remember.data)
                logger.info(f"User {user.username} (ID: {user.id}) logged in successfully.")
                next_page = request.args.get('next')
                return redirect(next_page) if next_page else redirect(url_for('index'))
            else:
                logger.warning(f"Failed login attempt for email: {form.email.data}")
                flash('Login Unsuccessful. Please check email and password', 'danger')
        except Exception as e:
            db.session.rollback()
            logger.error(f"Login error: {str(e)}")
            logger.error(traceback.format_exc())
            flash('An error occurred during login. Please try again later.', 'danger')
    return render_template('login.html', title='Login', form=form, current_year=datetime.now().year, page_class='login-page')


@app.route('/logout')
def logout():
    if current_user.is_authenticated:
        # Clear user-specific session data
        for key in [f'user_{current_user.id}_resume_skills', 
                   f'user_{current_user.id}_missing_skills',
                   f'user_{current_user.id}_last_resume_update',
                   'last_scrape_time']:
            if key in session:
                session.pop(key)
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))


# Error handlers for production
@app.errorhandler(404)
def page_not_found(e):
    """Handle 404 errors"""
    logger.warning(f"404 error: {request.url}")
    return render_template('error.html', code=404, message="The page you're looking for doesn't exist."), 404


@app.errorhandler(403)
def forbidden(e):
    """Handle 403 errors"""
    logger.warning(f"403 error: {request.url}")
    return render_template('error.html', code=403, message="You don't have permission to access this resource."), 403


@app.errorhandler(500)
def server_error(e):
    """Handle 500 errors"""
    logger.error(f"500 error: {str(e)}")
    logger.error(traceback.format_exc())
    return render_template('error.html', code=500, message="Something went wrong on our end. Please try again later."), 500


@app.route("/profile", methods=['GET', 'POST'])
@login_required
def profile():
    form = ProfileForm()
    
    if form.validate_on_submit():
        # Check for changes and only update fields that have changed
        updates = {}
        if form.username.data != current_user.username:
            # Check if new username is already taken
            existing_user = User.query.filter_by(username=form.username.data).first()
            if existing_user and existing_user.id != current_user.id:
                flash('Username already taken.', 'danger')
                return redirect(url_for('profile'))
            updates['username'] = form.username.data

        if form.email.data != current_user.email:
            # Check if new email is already taken
            existing_user = User.query.filter_by(email=form.email.data).first()
            if existing_user and existing_user.id != current_user.id:
                flash('Email already registered.', 'danger')
                return redirect(url_for('profile'))
            updates['email'] = form.email.data

        # For non-unique fields, update if they've changed
        if form.skills.data != current_user.skills:
            updates['skills'] = form.skills.data
        if form.location.data != current_user.location:
            updates['location'] = form.location.data
        if form.certifications.data != current_user.certifications:
            updates['certifications'] = form.certifications.data
        if form.summary.data != current_user.summary:
            updates['summary'] = form.summary.data

        # Track if we need to trigger a scrape
        need_scrape = False

        # Only update if there are actual changes
        if updates:
            try:
                # Update SQLAlchemy model
                if 'username' in updates:
                    current_user.username = updates['username']
                if 'email' in updates:
                    current_user.email = updates['email']
                if 'skills' in updates:
                    current_user.skills = updates['skills']
                    need_scrape = True  # Skills changed, need to refresh jobs
                if 'location' in updates:
                    current_user.location = updates['location']
                    need_scrape = True  # Location changed, need to refresh jobs
                if 'certifications' in updates:
                    current_user.certifications = updates['certifications']
                if 'summary' in updates:
                    current_user.summary = updates['summary']
                  # Commit SQLAlchemy changes
                db.session.commit()
                
                flash('Your profile has been updated!', 'success')
                if need_scrape:
                    # Update user skills in session
                    user_skills = [s.strip() for s in current_user.skills.split(',')] if current_user.skills else []
                    session[f'user_{current_user.id}_resume_skills'] = user_skills
                    
                    # Force a fresh scrape by removing last scrape time
                    session.pop('last_scrape_time', None)
                    
                    # Remove any cached job results to ensure fresh data
                    from job_utils import count_user_jobs
                    if count_user_jobs(current_user.id) > 0:
                        flash('Your skills have been updated. The system will find new job matches for you.', 'info')
                    
                    # Redirect to jobs page with scraper enabled
                    return redirect(url_for('list_all_jobs', run_scraper='true'))
                
                return redirect(url_for('profile'))
                
            except Exception as e:
                db.session.rollback()
                flash(f'Error updating profile: {str(e)}', 'danger')
                return redirect(url_for('profile'))
        return redirect(url_for('profile'))
        
    elif request.method == 'GET':
        # Populate form with current user data
        form.username.data = current_user.username
        form.email.data = current_user.email
        form.location.data = current_user.location
        form.skills.data = current_user.skills
        form.certifications.data = current_user.certifications
        form.summary.data = current_user.summary

    # Get resume skills from user-specific session key
    resume_skills = session.get(f'user_{current_user.id}_resume_skills', [])
    
    return render_template('profile.html',
                         form=form,
                         resume_skills=resume_skills)


@app.route("/add_experience", methods=['POST'])
@login_required
def add_experience():
    form = WorkExperienceForm()
    if form.validate_on_submit():
        start_date = datetime.strptime(form.start_date.data, '%m/%Y')
        end_date = None if form.current_job.data else datetime.strptime(form.end_date.data, '%m/%Y')
        
        exp_id = add_work_experience(
            user_id=current_user.id,
            company=form.company.data,
            title=form.title.data,
            start_date=start_date,
            end_date=end_date,
            description=form.description.data,
            current_job=form.current_job.data
        )
        
        if exp_id:
            flash('Work experience added successfully!', 'success')
        else:
            flash('Error adding work experience.', 'danger')
    return redirect(url_for('profile'))


@app.route("/edit_experience/<int:id>", methods=['POST'])
@login_required
def edit_experience(id):
    form = WorkExperienceForm()
    if form.validate_on_submit():
        start_date = datetime.strptime(form.start_date.data, '%m/%Y')
        end_date = None if form.current_job.data else datetime.strptime(form.end_date.data, '%m/%Y')
        
        success = update_work_experience(
            exp_id=id,
            user_id=current_user.id,
            company=form.company.data,
            title=form.title.data,
            start_date=start_date,
            end_date=end_date,
            description=form.description.data,
            current_job=form.current_job.data
        )
        
        return jsonify({'success': success})
    return jsonify({'success': False, 'errors': form.errors}), 400


@app.route("/delete_experience/<int:id>", methods=['POST'])
@login_required
def delete_experience(id):
    success = delete_work_experience(id, current_user.id)
    return jsonify({'success': success})


@app.route("/add_education", methods=['POST'])
@login_required
def add_education_route():
    form = EducationForm()
    if form.validate_on_submit():
        start_date = datetime.strptime(form.start_date.data, '%m/%Y') if form.start_date.data else None
        end_date = datetime.strptime(form.end_date.data, '%m/%Y') if form.end_date.data else None
        gpa = float(form.gpa.data) if form.gpa.data else None
        
        edu_id = add_education(
            user_id=current_user.id,
            institution=form.institution.data,
            degree=form.degree.data,
            field_of_study=form.field_of_study.data,
            start_date=start_date,
            end_date=end_date,
            gpa=gpa,
            description=form.description.data
        )
        
        if edu_id:
            flash('Education entry added successfully!', 'success')
        else:
            flash('Error adding education entry.', 'danger')
    return redirect(url_for('profile'))


@app.route("/edit_education/<int:id>", methods=['POST'])
@login_required
def edit_education(id):
    form = EducationForm()
    if form.validate_on_submit():
        start_date = datetime.strptime(form.start_date.data, '%m/%Y') if form.start_date.data else None
        end_date = datetime.strptime(form.end_date.data, '%m/%Y') if form.end_date.data else None
        gpa = float(form.gpa.data) if form.gpa.data else None
        
        success = update_education(
            edu_id=id,
            user_id=current_user.id,
            institution=form.institution.data,
            degree=form.degree.data,
            field_of_study=form.field_of_study.data,
            start_date=start_date,
            end_date=end_date,
            gpa=gpa,
            description=form.description.data
        )
        
        return jsonify({'success': success})
    return jsonify({'success': False, 'errors': form.errors}), 400


@app.route("/delete_education/<int:id>", methods=['POST'])
@login_required
def delete_education_route(id):
    success = delete_education(id, current_user.id)
    return jsonify({'success': success})


@app.route('/jobs')
@app.route('/list_all_jobs')
@login_required
def list_all_jobs():
    """Display the list of jobs."""
    
    query = request.args.get('query', 'All')
    location = request.args.get('location', 'All')
    job_type = request.args.get('job_type', 'All')  # New parameter for Remote/Onsite filter
    run_scraper = request.args.get('run_scraper', 'false').lower() == 'true'
    force_refresh = request.args.get('force_refresh', 'false').lower() == 'true'
    
    # Pagination parameters
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 20))
    
    # Initialize skills lists
    resume_skills = []
    profile_skills = []
    
    # Get skills from session
    session_skills = session.get(f'user_{current_user.id}_resume_skills', [])
    if session_skills:
        if isinstance(session_skills, str):
            resume_skills.extend(s.strip() for s in session_skills.split(',') if s.strip())
        elif isinstance(session_skills, list):
            resume_skills.extend(s.strip() for s in session_skills if s.strip())
    
    # Get skills from user profile
    if current_user.skills:
        profile_skills = [s.strip() for s in current_user.skills.split(',') if s.strip()]
    
    # Combine all skills and remove duplicates
    all_skills = list(set(resume_skills + profile_skills))
    
    # Check if user has any skills
    if not all_skills:
        flash('⚠️ Please add skills to your profile or upload your resume to see relevant job matches.', 'warning')
        return render_template(
            'jobs_list.html',
            jobs=[],
            query=query,
            location=location,
            run_scraper=False,
            resume_skills=[],
            missing_skills=[],
            is_loading=False,
            has_skills=False  # Flag to control template display
        )
    
    # If we have skills, update resume_skills for the rest of the function
    resume_skills = all_skills
    has_skills = bool(resume_skills)  # Define has_skills based on resume_skills
    
    # Count existing jobs for this user
    job_count = count_user_jobs(current_user.id)
    
    # Get the last scrape time from session
    last_scrape_time = session.get('last_scrape_time')
      # Import the utility function to check if jobs need refresh
    from utils import needs_refresh
    
    # Check if we need to scrape:
    # - Manual refresh requested via button
    # - First time visit (no jobs in DB)
    # - Explicit run_scraper parameter set (from search form)
    # - Last scrape was too long ago (more than 6 hours)
    need_scrape = (
        force_refresh or                             # Manual refresh requested
        run_scraper or                               # Search with new query
        job_count == 0 or                            # No jobs in database yet
        needs_refresh(last_scrape_time, hours_threshold=6)  # Last scrape was over 6 hours ago
    )
    if need_scrape and has_skills:
        try:
            # Show loading state
            session['is_loading'] = True
            
            # Clean up any data that needs refreshing when jobs change
            cleanup_job_related_data()
            
            # Use scrape_jobs to get fresh data
            jobs = scrape_jobs(
                query=query,
                location=location,
                user_skills=resume_skills,
                pages=3,  # Scrape 3 pages by default
                force_clear=force_refresh,
                user_id=current_user.id
            )
              # Update last scrape time
            session['last_scrape_time'] = datetime.utcnow().isoformat()
            
            if not jobs:
                flash('No jobs found. Try adjusting your search criteria.', 'info')
                jobs = []
            else:
                flash(f'Successfully found {len(jobs)} jobs!', 'success')
        except Exception as e:
            flash(f'Error while scraping jobs: {str(e)}', 'error')
            jobs = []
        finally:
            # Clear loading state
            session.pop('is_loading', None)
    # Get existing jobs from database
    jobs = search_jobs_db(query, location, resume_skills, user_id=current_user.id, job_type=job_type)
    
    # Check if jobs were found in database and set appropriate message
    # Don't show "No jobs found" message if jobs were actually found
    if jobs:
        # Clear any "No jobs found" messages if jobs are found in the database
        # This prevents showing contradictory messages
        flashes_to_keep = []
        for category, message in session.get('_flashes', []):
            if 'No jobs found' not in message:
                flashes_to_keep.append((category, message))
        session['_flashes'] = flashes_to_keep

    # Process jobs to ensure proper skill formatting and matching
    missing_skills_set = set()
    
    for job in jobs:
        # Handle required skills
        if isinstance(job.get('required_skills'), str):
            try:
                job['required_skills'] = json.loads(job['required_skills'])
            except (json.JSONDecodeError, TypeError):
                job['required_skills'] = []
        elif job.get('required_skills') is None:
            job['required_skills'] = []

        # Handle nice to have skills
        if isinstance(job.get('nice_to_have_skills'), str):
            try:
                job['nice_to_have_skills'] = json.loads(job['nice_to_have_skills'])
            except (json.JSONDecodeError, TypeError):
                job['nice_to_have_skills'] = []
        elif job.get('nice_to_have_skills') is None:
            job['nice_to_have_skills'] = []

        # Handle all skills
        if isinstance(job.get('skills'), str):
            try:
                job['skills'] = json.loads(job['skills'])
            except (json.JSONDecodeError, TypeError):
                job['skills'] = []
        elif job.get('skills') is None:
            job['skills'] = []

        # Calculate matching skills for required and nice-to-have if resume skills exist
        if resume_skills:
            # Normalize all skills to lowercase for matching
            resume_skills_set = set(s.lower().strip() for s in resume_skills if s)
            required_skills_set = set(s.lower().strip() for s in job.get('required_skills', []) if s)
            nice_to_have_set = set(s.lower().strip() for s in job.get('nice_to_have_skills', []) if s)
            all_skills_set = required_skills_set | nice_to_have_set
            
            # Find matching and missing skills while preserving original case
            job['matching_required_skills'] = [s for s in job['required_skills'] if s and s.lower().strip() in resume_skills_set]
            job['matching_nice_to_have_skills'] = [s for s in job['nice_to_have_skills'] if s and s.lower().strip() in resume_skills_set]
            job['missing_skills'] = [s for s in job['required_skills'] if s and s.lower().strip() not in resume_skills_set]
            
            # Only count it as a skill gap if the skill appears frequently in job requirements
            if len(job['missing_skills']) > 0:
                missing_skills_set.update(s for s in job['missing_skills'] if s)
            
            # Calculate match percentages
            if required_skills_set or nice_to_have_set:
                required_weight = 0.7  # 70% weight for required skills
                nice_to_have_weight = 0.3  # 30% weight for nice-to-have skills
                
                required_match = (len([s for s in job['matching_required_skills']]) / len(required_skills_set) * 100 * required_weight
                                if required_skills_set else 0)
                nice_to_have_match = (len([s for s in job['matching_nice_to_have_skills']]) / len(nice_to_have_set) * 100 * nice_to_have_weight
                                    if nice_to_have_set else 0)
                                    
                job['match_percentage'] = int(required_match + nice_to_have_match)
    
    # Sort jobs by match percentage and other criteria
    if resume_skills:
        jobs.sort(key=lambda x: (
            x.get('match_percentage', 0),
            x.get('is_new', False),
            x.get('is_urgent', False),
            x.get('date_scraped', '')
        ), reverse=True)
    else:
        jobs.sort(key=lambda x: (
            x.get('is_new', False),
            x.get('is_urgent', False),
            x.get('date_scraped', '')
        ), reverse=True)    # Convert missing_skills_set back to a sorted list for template
    missing_skills = sorted(list(missing_skills_set))
      # Store missing skills in session for use in course recommendations, using user-specific key
    session[f'user_{current_user.id}_missing_skills'] = missing_skills
    
    # Apply job type filter if specified
    if job_type != 'All':
        job_type_lower = job_type.lower()
        filtered_jobs = []
        for job in jobs:
            # Check if job is remote by looking for 'remote' in various fields
            is_remote = False
            if 'remote' in str(job.get('title', '')).lower() or 'remote' in str(job.get('location', '')).lower() or 'remote' in str(job.get('description', '')).lower():
                is_remote = True
            
            # Filter based on job type
            if (job_type_lower == 'remote' and is_remote) or (job_type_lower == 'onsite' and not is_remote):
                filtered_jobs.append(job)
        jobs = filtered_jobs    # Get consistent job counts using our utility
    job_counts = get_job_counts(jobs, user_id=current_user.id)
    total_jobs = job_counts["total_jobs"]  # Keep for pagination calculation
    
    # Check for contradictory messages - if we have jobs but also a "No jobs found" flash message
    if total_jobs > 0:
        # Remove any "No jobs found" flash messages to avoid confusion
        flashes_to_keep = []
        for category, message in session.get('_flashes', []):
            if 'No jobs found' not in message:
                flashes_to_keep.append((category, message))
        session['_flashes'] = flashes_to_keep
        
    # Apply pagination
    if per_page != 0:  # If per_page is 0, show all jobs
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        paginated_jobs = jobs[start_idx:end_idx]
    else:
        paginated_jobs = jobs
    
    # Calculate total pages for pagination
    total_pages = (total_jobs + per_page - 1) // per_page if per_page > 0 else 1
      # Fetch course recommendations if we have missing skills
    course_recommendations = {}
    if missing_skills:
        try:
            course_recommendations = fetch_courses_by_skills(missing_skills)
        except Exception as e:
            logger.error(f"Error fetching course recommendations: {e}")
            course_recommendations = {}    
    return render_template(
        'jobs_list.html',
        jobs=paginated_jobs,
        # removed total_jobs parameter - using job_counts.total_jobs instead
        page=page,
        per_page=per_page,
        total_pages=total_pages,
        job_type=job_type,
        course_recommendations=course_recommendations,
        query=query,
        location=location,
        run_scraper=need_scrape,
        resume_skills=resume_skills,
        missing_skills=missing_skills,
        job_counts=job_counts,  # Pass the complete job counts
        is_loading=session.get('is_loading', False)
    )


@app.route("/upload_resume", methods=['GET', 'POST'])
@login_required
def upload_resume():
    form = ResumeUploadForm()
    if form.validate_on_submit():
        if not form.resume.data:
            flash('Please select a resume file to upload.', 'warning')
            return redirect(url_for('upload_resume'))
            
        temp_file = None
        try:
            # Get file and create safe filename
            uploaded_file = form.resume.data
            filename = secure_filename(uploaded_file.filename)
            
            # Create path in upload folder
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            
            # Save the file
            uploaded_file.save(file_path)
            temp_file = file_path  # Keep track for cleanup
            
            # Parse resume using global nlp model
            resume_data = parse_resume(file_path, nlp)
            
            if resume_data and 'skills' in resume_data:
                # Clear old skills data
                if 'resume_skills' in session:
                    session.pop('resume_skills')
                if 'missing_skills' in session:
                    session.pop('missing_skills')
                  # Clean and validate skills
                cleaned_skills = [skill.strip() for skill in resume_data['skills'] if skill.strip()]
                  # Update session with fresh skills using user-specific keys
                session[f'user_{current_user.id}_resume_skills'] = cleaned_skills
                session[f'user_{current_user.id}_last_resume_update'] = datetime.utcnow().isoformat()
                
                # Update user profile with all resume data
                current_user.resume_skills = ','.join(cleaned_skills)  # Store as comma-separated string
                current_user.skills = ','.join(cleaned_skills)  # Also update regular skills
                current_user.last_resume_update = datetime.utcnow()
                
                # Update location if found
                if resume_data.get('location'):
                    current_user.location = resume_data['location']
                
                # Update summary if found
                if resume_data.get('summary'):
                    current_user.summary = resume_data['summary']
                
                # Update work experience
                if resume_data.get('work_experience'):
                    # Clear existing work experience if any was parsed
                    # Get existing experience IDs
                    existing_experience = get_user_work_experience(current_user.id)
                    for exp in existing_experience:
                        delete_work_experience(exp['id'], current_user.id)
                    
                    # Add new experience entries
                    for exp in resume_data['work_experience']:
                        start_date = datetime.strptime(exp['start_date'], '%m/%Y')            if exp.get('start_date') else None
                        
                        # Handle current job and end date
                        is_current = exp.get('current_job', False) or 'present' in str(exp.get('end_date', '')).lower()
                        end_date = None if is_current else (
                            datetime.strptime(exp['end_date'], '%m/%Y') if exp.get('end_date') else None
                        )
                        
                        add_work_experience(
                            user_id=current_user.id,
                            company=exp['company'],
                            title=exp['title'],
                            start_date=start_date,
                            end_date=end_date,
                            description=exp.get('description'),
                            current_job=is_current
                        )
                
                # Update education
                if resume_data.get('education'):
                    # Clear existing education if any was parsed
                    existing_education = get_user_education(current_user.id)
                    for edu in existing_education:
                        delete_education(edu['id'], current_user.id)
                    
                    # Add new education entries
                    for edu in resume_data['education']:
                        start_date = datetime.strptime(edu['start_date'], '%m/%Y') if edu.get('start_date') else None
                        end_date = datetime.strptime(edu['end_date'], '%m/%Y') if edu.get('end_date') else None
                        add_education(
                            user_id=current_user.id,
                            institution=edu['institution'],
                            degree=edu['degree'],
                            field_of_study=edu.get('field_of_study'),
                            start_date=start_date,
                            end_date=end_date,
                            gpa=edu.get('gpa'),
                            description=edu.get('description')
                        )
                
                db.session.commit()
                
                flash('Resume uploaded and all information updated successfully!', 'success')
                return redirect(url_for('profile'))
            else:
                flash('No skills found in resume. Please update your profile manually.', 'warning')
                return redirect(url_for('profile'))
                
        except Exception as e:
            flash(f'Error analyzing resume: {str(e)}', 'danger')
            return redirect(url_for('upload_resume'))
            
        finally:            # Clean up the temporary file
            if temp_file and os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                except Exception as e:
                    logger.warning(f"Could not remove temporary file {temp_file}: {e}")
                    
    return render_template('upload_resume.html', form=form, page_class='upload-resume-page', current_year=datetime.now().year)


@app.route("/course_recommendations")
@login_required
def course_recommendations():
    # Check if the user has uploaded a resume
    has_uploaded_resume = current_user.last_resume_update is not None
    
    # Clear recommendations cache if force refresh
    if request.args.get('force_refresh'):
        session.pop(f'user_{current_user.id}_course_recommendations', None)
        
    # Get the user's skills
    user_skills = []
    if current_user.skills:
        user_skills = [skill.strip() for skill in current_user.skills.split(',')]
    
    # Get skills from user-specific session key
    session_skills = session.get(f'user_{current_user.id}_resume_skills', [])
    if session_skills:
        if isinstance(session_skills, str):
            resume_skills = [s.strip() for s in session_skills.split(',')]
        else:
            resume_skills = session_skills
    else:
        resume_skills = []
    
    # Combine user's profile skills and resume skills
    all_skills = list(set(user_skills + resume_skills))
    
    # If user hasn't uploaded a resume and has no skills defined in profile, 
    # show a message prompting them to upload a resume first
    if not has_uploaded_resume and not user_skills:
        flash("Please upload your resume or add skills to your profile to get personalized course recommendations.", "info")
        return render_template(
            'course_recommendations.html',
            course_recommendations={},
            user_skills=[],
            missing_skills=[],
            needs_resume=True
        )
      # Get missing skills from user-specific session key
    missing_skills = session.get(f'user_{current_user.id}_missing_skills', [])
    
    # Force refresh missing skills if the last_resume_update is newer than the session data
    resume_update_time = None
    if current_user.last_resume_update:
        resume_update_time = current_user.last_resume_update.isoformat()
        
    session_update_time = session.get(f'user_{current_user.id}_last_resume_update')
      # Always recalculate missing skills for the course recommendations page
    # to ensure they are based on the most up-to-date user skills
    if True:
        logger.info(f"Resume updated since last missing skills calculation, refreshing missing skills")
        
        # Get jobs data
        from database_manager import search_jobs_db
        jobs = search_jobs_db(query="All", location="All", resume_skills=all_skills, user_id=current_user.id)
        
        # Calculate missing skills from job requirements
        all_required_skills = []
        for job in jobs:
            # Handle required skills
            if isinstance(job.get('required_skills'), str):
                try:
                    required = json.loads(job['required_skills'])
                    all_required_skills.extend(required)
                except:
                    pass
            elif isinstance(job.get('required_skills'), list):
                all_required_skills.extend(job.get('required_skills', []))
                
        # Convert all skills to lowercase for case-insensitive comparison
        all_skills_lower = [skill.lower() for skill in all_skills if skill]
        
        # Count skill frequencies
        from collections import Counter
        skill_freq = Counter(all_required_skills)
        
        # Get missing skills (case-insensitive comparison)
        missing_skills = [skill for skill, freq in skill_freq.most_common() 
                         if skill and skill.lower() not in all_skills_lower and freq > 1]
        
        # Update missing skills in session
        session[f'user_{current_user.id}_missing_skills'] = missing_skills
        
        # Update the session's resume update timestamp
        if resume_update_time:
            session[f'user_{current_user.id}_last_resume_update'] = resume_update_time
    
    # Initialize course recommendations dictionary
    course_recommendations = {}
    
    # If user hasn't uploaded a resume and has no skills defined in profile, 
    # show a message prompting them to upload a resume first
    if not has_uploaded_resume and not user_skills:
        flash("Please upload your resume or add skills to your profile to get personalized course recommendations.", "info")
        return render_template(
            'course_recommendations.html',
            course_recommendations={},
            user_skills=[],
            missing_skills=[],
            needs_resume=True
        )
      # First, get recommendations for missing skills
    if missing_skills:
        try:
            course_recommendations = fetch_courses_by_skills(missing_skills)
        except Exception as e:
            logger.error(f"Error fetching course recommendations for missing skills: {e}")
      # If we have space for more recommendations or no missing skills,
    # add courses for existing skills as well
    if not missing_skills or len(course_recommendations) < len(all_skills) * 3:
        existing_skills = [s for s in all_skills if s not in missing_skills]
        if existing_skills:
            try:
                additional_courses = fetch_courses_by_skills(existing_skills)
                # Add non-duplicate courses
                for skill, courses in additional_courses.items():
                    if skill not in course_recommendations:
                        course_recommendations[skill] = courses
            except Exception as e:
                logger.error(f"Error fetching additional course recommendations: {e}")
    
    return render_template(
        'course_recommendations.html',
        course_recommendations=course_recommendations,
        user_skills=all_skills,
        missing_skills=missing_skills,
        needs_resume=False
    )


@app.route('/reset_skills')
@login_required
def reset_skills():
    # Clear skills from session using user-specific keys
    for key in [f'user_{current_user.id}_resume_skills', 
                f'user_{current_user.id}_missing_skills',
                f'user_{current_user.id}_last_resume_update']:
        if key in session:
            session.pop(key)
    
    # Clear skills from user profile
    if current_user.is_authenticated:
        current_user.skills = None
        current_user.resume_skills = None
        db.session.commit()
        flash('Skills have been reset', 'info')
    
    return redirect(url_for('list_all_jobs'))


@app.route('/refresh_jobs')
@login_required
def refresh_jobs():
    """Force refresh of job listings"""
    try:
        # Set loading state
        session['is_loading'] = True
        
        # Get existing query and location
        query = request.args.get('query', 'All')
        location = request.args.get('location', 'All')
        
        # Get user's skills from session and profile
        resume_skills = []
        profile_skills = []
        
        # Get skills from session with user-specific key
        session_skills = session.get(f'user_{current_user.id}_resume_skills', [])
        if session_skills:
            if isinstance(session_skills, str):
                resume_skills.extend(s.strip() for s in session_skills.split(',') if s.strip())
            elif isinstance(session_skills, list):
                resume_skills.extend(s.strip() for s in session_skills if s.strip())
        
        # Get skills from user profile
        if current_user.skills:
            profile_skills = [s.strip() for s in current_user.skills.split(',') if s.strip()]
            
        # Combine all skills and remove duplicates
        all_skills = list(set(resume_skills + profile_skills))
        
        # Check if user has any skills
        if not all_skills:
            flash('⚠️ Please add skills to your profile or upload your resume to see relevant job matches.', 'warning')
            session.pop('is_loading', None)
            return jsonify({'success': False, 'message': 'No skills found'})
        
        # Clear any existing flash messages to avoid contradictory messaging
        session['_flashes'] = []
        
        # Clean up any data that needs refreshing when jobs change
        cleanup_job_related_data()
        
        # Run the scraper with force_clear=True to get fresh data
        jobs = scrape_jobs(
            query=query,
            location=location,
            user_skills=all_skills,
            pages=3,
            force_clear=True,  # Always force clear for refresh operation
            user_id=current_user.id
        )
        
        # Update last scrape time - do this even if no jobs were found
        session['last_scrape_time'] = datetime.utcnow().isoformat()
        
        if jobs:
            flash(f'Successfully found {len(jobs)} jobs!', 'success')
            result = {'success': True, 'count': len(jobs)}
        else:
            flash('No jobs found. Try adjusting your search criteria.', 'info')
            result = {'success': True, 'count': 0}
            
    except Exception as e:
        error_message = str(e)
        flash(f'Error refreshing jobs: {error_message}', 'danger')
        result = {'success': False, 'error': error_message}
    finally:
        # Clear loading state
        session.pop('is_loading', None)
    
    # Check if this is an AJAX request
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify(result)
    else:
        return redirect(request.referrer or url_for('list_all_jobs'))


@app.route('/scrape_jobs_with_profile', methods=['GET'])
@login_required
def scrape_jobs_with_profile():
    """Scrape jobs using the user's profile information."""
    try:
        # Set loading state
        session['is_loading'] = True
        
        if not current_user.is_authenticated:
            flash('Please login to search jobs.', 'warning')
            return redirect(url_for('login'))

        # Get user profile information
        user = User.query.get(current_user.id)
        if not user:
            flash('User profile not found.', 'error')
            return redirect(url_for('profile'))
        
        # Get skills from session and profile
        resume_skills = []
        profile_skills = []
        
        # Get skills from session with user-specific key
        session_skills = session.get(f'user_{current_user.id}_resume_skills', [])
        if session_skills:
            if isinstance(session_skills, str):
                resume_skills.extend(s.strip() for s in session_skills.split(',') if s.strip())
            elif isinstance(session_skills, list):
                resume_skills.extend(s.strip() for s in session_skills if s.strip())
        
        # Get skills from user profile
        if user.skills:
            profile_skills = [s.strip() for s in user.skills.split(',') if s.strip()]
            
        # Combine all skills and remove duplicates
        all_skills = list(set(resume_skills + profile_skills))
        
        # Check if user has any skills
        if not all_skills:
            flash('⚠️ Please add skills to your profile or upload your resume to see relevant job matches.', 'warning')
            session.pop('is_loading', None)
            return redirect(url_for('profile'))
        
        user_location = user.location if user.location else "All"
        
        # Clean up any data that needs refreshing when jobs change
        cleanup_job_related_data()
        
        # Run the job scraper with the user's profile data
        jobs = scrape_jobs(
            query="All",  # Use "All" since we're using skills directly
            location=user_location,
            user_skills=all_skills,
            pages=3,  # Scrape 3 pages by default
            force_clear=True,  # Clear existing jobs to get fresh results
            user_id=user.id  # Explicitly pass user.id
        )
        
        # Update last scrape time
        session['last_scrape_time'] = datetime.utcnow().isoformat()
        
        if jobs:
            flash(f'Successfully scraped {len(jobs)} jobs matching your profile!', 'success')
        else:
            flash('No jobs found matching your profile. Try adjusting your skills or location.', 'info')
        
        # Clear loading state
        session.pop('is_loading', None)
        return redirect(url_for('list_all_jobs'))
        
    except Exception as e:
        flash(f'Error scraping jobs: {str(e)}', 'error')
        # Clear loading state
        session.pop('is_loading', None)
        return redirect(url_for('list_all_jobs'))


@app.route('/check_refresh_status', methods=['GET'])
@login_required
def check_refresh_status():
    """Check if jobs are still being loaded."""
    from utils import needs_refresh
    
    # Get loading status
    is_loading = session.get('is_loading', False)
    
    # Get job count for current user
    job_count = count_user_jobs(current_user.id)
    
    # Get last scrape time
    last_scrape = session.get('last_scrape_time')
    
    # Format last scrape time for display
    formatted_last_scrape = None
    if last_scrape:
        try:
            last_scrape_dt = datetime.fromisoformat(last_scrape)
            formatted_last_scrape = last_scrape_dt.strftime('%Y-%m-%d %H:%M:%S')
        except:
            formatted_last_scrape = last_scrape
    
    # Check if we need a refresh based on time
    needs_time_refresh = needs_refresh(last_scrape, hours_threshold=6)
    
    return jsonify({
        'loading': is_loading,
        'job_count': job_count,
        'last_scrape': last_scrape,
        'formatted_last_scrape': formatted_last_scrape,
        'needs_refresh': job_count == 0 or needs_time_refresh
    })


@app.route('/insights')
@login_required
def insights():
    """Display insights and visualizations based on job data."""
    logger.info("Starting insights route handler")
    
    # Check if the user has uploaded a resume or has skills in their profile
    has_uploaded_resume = current_user.last_resume_update is not None
    has_profile_skills = current_user.skills and len(current_user.skills.strip()) > 0
    
    # If new user with no resume or skills, prompt them to upload resume first
    if not has_uploaded_resume and not has_profile_skills:
        flash("Please upload your resume or add skills to your profile to get personalized job insights.", "info")
        return render_template(
            'insights.html',
            insights={"has_data": False, "needs_resume": True},
            available_skills=[],
            selected_skills=[]
        )
    
    # Get selected skills from the request
    selected_skills = request.args.getlist('skills')
    logger.info(f"Selected skills: {selected_skills}")
    
    # Get all skills for the filter dropdown
    available_skills = get_skill_options()
    logger.info(f"Available skills count: {len(available_skills)}")
    try:
        # Get user's skills from session and profile
        resume_skills = []
        profile_skills = []
        
        # Get skills from session with user-specific key
        session_skills = session.get(f'user_{current_user.id}_resume_skills', [])
        if session_skills:
            if isinstance(session_skills, str):
                resume_skills = [s.strip() for s in session_skills.split(',') if s.strip()]
            elif isinstance(session_skills, list):
                resume_skills = [s.strip() for s in session_skills if s.strip()]
        
        # Get skills from user profile
        if current_user.skills:
            profile_skills = [s.strip() for s in current_user.skills.split(',') if s.strip()]
        
        # Combine all skills and remove duplicates
        all_skills = list(set(resume_skills + profile_skills))
          # Generate insights based on jobs data
        logger.info(f"Getting job insights for user ID: {current_user.id} with {len(all_skills)} skills")
        insights_data = get_job_insights(
            user_id=current_user.id,
            filter_by_skills=selected_skills if selected_skills else None,
            user_skills=all_skills
        )
        insights_data["needs_resume"] = False
      # Get the same job data and counts used in list_all_jobs and dashboard to ensure consistency
        jobs = search_jobs_db(query="All", location="All", resume_skills=all_skills, user_id=current_user.id)
        job_counts = get_job_counts(jobs, user_id=current_user.id)
        
        # Use consistent job counts from job_counts utility
        insights_data.update(job_counts)  # This will ensure we use the same count everywhere
            
        logger.info(f"Insights data has_data: {insights_data.get('has_data', False)}")
    except Exception as e:
        logger.error(f"Error generating insights: {str(e)}")
        logger.error(traceback.format_exc())
        insights_data = {
            "has_data": False, 
            "needs_resume": False,
            "message": f"Error generating insights: {str(e)}"
        }
    
    return render_template(
        'insights.html',
        insights=insights_data,
        available_skills=available_skills,
        selected_skills=selected_skills
    )


@app.route('/health')
def health_check():
    """Simple health check endpoint for monitoring."""
    from health_check import check_database_health
    
    try:
        # Check database connection
        db_healthy, db_message = check_database_health(app.config['SQLALCHEMY_DATABASE_URI'])
        
        if db_healthy:
            return jsonify({
                'status': 'ok',
                'timestamp': datetime.utcnow().isoformat(),
                'database': 'connected',
                'message': 'Service is healthy'
            }), 200
        else:
            return jsonify({
                'status': 'warning',
                'timestamp': datetime.utcnow().isoformat(),
                'database': 'error',
                'message': db_message
            }), 200  # Still return 200 to prevent Render from restarting
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return jsonify({
            'status': 'error',
            'timestamp': datetime.utcnow().isoformat(),
            'message': f'Health check error: {str(e)}'
        }), 200  # Still return 200 to prevent Render from restarting


# Flask CLI commands
@app.cli.command("init-db")
def init_db_command():
    """Clear existing data and create new tables."""
    try:
        # Get absolute path to the instance directory
        basedir = os.path.abspath(os.path.dirname(__file__))
        instance_dir = os.path.join(basedir, 'instance')
        
        # Create instance directory if it doesn't exist
        if not os.path.exists(instance_dir):
            logger.info(f"Creating instance directory at {instance_dir}")
            os.makedirs(instance_dir, exist_ok=True)
            
        # Print out the path for debugging
        db_path = os.path.join(instance_dir, 'job_recommender.db')
        logger.info(f"Using database at: {db_path}")
        
        # Initialize database
        with app.app_context():
            db.create_all()
            init_db()
            logger.info("Database initialized successfully!")
    except Exception as e:
        logger.error(f"Error initializing database: {e}")
        logger.error(traceback.format_exc())

if __name__ == '__main__':
    try:
        # Ensure the instance directory exists
        instance_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'instance')
        if not os.path.exists(instance_dir):
            logger.info(f"Creating instance directory at {instance_dir}")
            os.makedirs(instance_dir)
        
        with app.app_context():
            db.create_all()
            init_db()  # Initialize database tables
            
            # Clean up old graph files on startup
            graphs_dir = os.path.join('static', 'graphs')
            if os.path.exists(graphs_dir):
                logger.info(f"Cleaning up old graph files in {graphs_dir}")
                cleanup_static_graphs(graphs_dir, older_than_days=3)
        
        # For local development
        app.run(host='127.0.0.1', port=5000, debug=os.environ.get('FLASK_DEBUG', 'True') == 'True')
    except Exception as e:
        logger.error(f"Error starting application: {e}")
        logger.error(traceback.format_exc())
