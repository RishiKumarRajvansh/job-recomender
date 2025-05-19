from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from sqlalchemy.sql import func
import os
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Initialize SQLAlchemy with no Flask app yet (will be registered later)
db = SQLAlchemy()

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(60), nullable=False)
    skills = db.Column(db.Text, nullable=True, default='')
    resume_skills = db.Column(db.Text, nullable=True, default='')  # Skills extracted from resume
    location = db.Column(db.String(255), nullable=True, default='')
    certifications = db.Column(db.Text, nullable=True, default='')
    summary = db.Column(db.Text, nullable=True, default='')
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    last_resume_update = db.Column(db.DateTime, nullable=True)
    
    # Define relationships
    work_experience = db.relationship('WorkExperience', backref='user', lazy=True)
    education = db.relationship('Education', backref='user', lazy=True)

    def __repr__(self):
        return f"User('{self.username}', '{self.email}')"

class WorkExperience(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    company = db.Column(db.String(255), nullable=False)
    title = db.Column(db.String(255), nullable=False)
    start_date = db.Column(db.Date, nullable=True)
    end_date = db.Column(db.Date, nullable=True)
    description = db.Column(db.Text, nullable=True)
    current_job = db.Column(db.Boolean, default=False)

class Education(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    institution = db.Column(db.String(255), nullable=False)
    degree = db.Column(db.String(255), nullable=False)
    field_of_study = db.Column(db.String(255), nullable=True)
    start_date = db.Column(db.DateTime, nullable=True)
    end_date = db.Column(db.DateTime, nullable=True)
    gpa = db.Column(db.Float, nullable=True)
    description = db.Column(db.Text, nullable=True)

    @property
    def start_date_formatted(self):
        return self.start_date.strftime('%Y-%m-%d') if self.start_date else None

    @property
    def end_date_formatted(self):
        return self.end_date.strftime('%Y-%m-%d') if self.end_date else None

class Job(db.Model):
    __tablename__ = 'jobs'  # Explicitly set the table name
    
    id = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.String(255))
    title = db.Column(db.String(255), nullable=False)
    company = db.Column(db.String(255))
    location = db.Column(db.String(255))
    url = db.Column(db.String(512))
    description = db.Column(db.Text)
    required_skills = db.Column(db.Text)  # JSON array of required skills
    nice_to_have_skills = db.Column(db.Text)  # JSON array of preferred skills
    salary_min = db.Column(db.Float)
    salary_max = db.Column(db.Float)
    salary_currency = db.Column(db.String(10))
    salary_period = db.Column(db.String(20))  # yearly, monthly, hourly
    job_type = db.Column(db.String(50))
    employment_type = db.Column(db.String(50))  # full-time, part-time, contract
    source_url = db.Column(db.String(512), unique=True)
    date_posted = db.Column(db.String(50))
    date_scraped = db.Column(db.DateTime, default=datetime.utcnow)
    is_remote = db.Column(db.Boolean, default=False)
    experience_level = db.Column(db.String(50))  # entry, mid, senior
    education_required = db.Column(db.Text)
    company_industry = db.Column(db.String(100))
    location_type = db.Column(db.String(20))  # remote, hybrid, onsite

    def __repr__(self):
        return f'<Job {self.title} at {self.company}>'

class JobSkill(db.Model):
    __tablename__ = 'job_skills'  # Explicitly set the table name

    id = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.Integer, db.ForeignKey('jobs.id'), nullable=False)
    skill = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<JobSkill {self.skill}>'
