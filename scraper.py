import os
import sys
import io
import json
import time
import random
import logging
import argparse
import requests
import traceback
import re
import sqlite3
from typing import List, Dict, Any
from nlp_utils import load_spacy_model
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from database_manager import (
    initialize_database,
    save_job_to_db,
    add_job_skills,
    clear_jobs_table,
    get_all_jobs,
    get_db_connection
)
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Set stdout to handle Unicode properly
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# Add the current directory to the path to ensure imports work correctly
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

# --- spaCy Model Loading ---
# Load spaCy model and skill keywords at the module level
nlp_model, skill_keywords = load_spacy_model()

def fetch_page(url, params=None, retries=3, delay=5):
    """Fetches HTML content from a URL with retries and headers."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36 JobScraper/1.0 (cody@sourcegraph.com)'
    }
    for attempt in range(retries):
        try:
            # Only log this at INFO level for significant page fetches
            if attempt == 0:
                logger.info(f"Fetching jobs data from: {url}")
            response = requests.get(url, headers=headers, params=params, timeout=20)
            response.raise_for_status()
            return response.text
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP error fetching {url} (attempt {attempt + 1}/{retries}): {e.response.status_code} {e.response.reason}")
            if e.response.status_code in [404, 403, 410]:
                logger.warning(f"Page not found/forbidden/gone ({e.response.status_code}). Skipping this URL.")
                return None
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching {url} (attempt {attempt + 1}/{retries}): {e}")
            if attempt < retries - 1:
                actual_delay = delay + random.uniform(0, delay * 0.5)
                logger.info(f"Retrying in {actual_delay:.2f} seconds...")
                time.sleep(actual_delay)
            else:
                logger.error(f"Failed to fetch {url} after {retries} attempts.")
    return None

def parse_job_detail_page_adzuna(full_job_url):
    logger.info(f"Fetching details from Adzuna landing page: {full_job_url}")
    html_content = fetch_page(full_job_url)    # Even if we can't get the detail page, return a basic description
    if not html_content:
        logger.warning(f"Could not fetch detail page for {full_job_url} - using basic description")
        return "Click the job title to view the full description.", "Adzuna"
        
    soup = BeautifulSoup(html_content, 'html.parser')
    site_name = "Adzuna"
        
    redirect_message_h2 = soup.find('h2', string=lambda t: t and "you are being redirected to" in t.lower())
    if redirect_message_h2 and redirect_message_h2.strong:
        site_name_from_page = redirect_message_h2.strong.text.strip()
        return "Full description not found on Adzuna landing page (this is expected).", site_name

def parse_job_listing(job_listing, user_id, user_skills=None):
    """Parse a job listing and return the job ID."""
    # Import at the top level to avoid UnboundLocalError
    from database_manager import save_job_to_db
    
    if not user_id:
        logger.error("No user_id provided to parse_job_listing")
        return None
        
    try:
        # Check if job_listing is already a dictionary (from database)
        if isinstance(job_listing, dict):
            logger.info("Job listing is already a dictionary, saving directly")
            # Make a copy to avoid modifying the original
            job_data = job_listing.copy()
            # Ensure user_id is set
            job_data['user_id'] = user_id
            
            # If it's already a dictionary, just save it directly
            try:
                job_id = save_job_to_db(job_data, user_id)
                logger.info(f"Saved job directly from dictionary with ID: {job_id}")
                return job_id
            except Exception as save_err:
                logger.error(f"Error saving job from dictionary: {save_err}")
                return None
            
        # If we get here, job_listing is a BeautifulSoup element
        
        # Initialize job data with required fields
        job_data = {
            'user_id': user_id,
            'date_scraped': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        # Extract job ID if available
        if hasattr(job_listing, 'get'):
            job_data['job_id'] = job_listing.get('data-aid', '')
          # Extract title and URL
        try:        # Check if job_listing is a dictionary (already parsed or from DB)
            if isinstance(job_listing, dict):
                # Dictionary already has all the data we need
                job_listing['user_id'] = user_id  # Ensure user_id is set
                return save_job_to_db(job_listing, user_id)                
            # Otherwise, proceed with BeautifulSoup parsing
            title_elem = job_listing.select_one('h2[itemprop="title"], h2.job-title, .a-title, a[data-aid="jobTitle"]')
            if not title_elem:
                title_elem = job_listing.select_one('h2 a')
            if not title_elem or not title_elem.get_text().strip():
                logger.warning("No title found for job listing")
                return None
        except AttributeError:
            logger.error(f"Error parsing job listing: 'dict' object has no attribute 'select_one'")
            logger.error(f"Traceback: {traceback.format_exc()}")
            # If it's a dictionary but we tried to use BeautifulSoup methods
            if isinstance(job_listing, dict):
                job_listing['user_id'] = user_id
                return save_job_to_db(job_listing, user_id)
            return None
            
        job_data['title'] = title_elem.get_text().strip()
        
        # Get URL
        url_elem = title_elem if title_elem.name == 'a' else title_elem.find('a')
        if url_elem and url_elem.has_attr('href'):
            job_data['url'] = urljoin('https://www.adzuna.in', url_elem['href'])
            job_data['source_url'] = job_data['url']
        else:
            logger.warning(f"No URL found for job: {job_data['title']}")
            return None
            
        # Extract other job details
        # Company
        company_elem = job_listing.select_one('div.ui-company')
        job_data['company'] = company_elem.get_text().strip() if company_elem else None
        
        # Location
        location_elem = job_listing.select_one('div.ui-location')
        job_data['location'] = location_elem.get_text().strip() if location_elem else None
        
        # Description
        desc_elem = job_listing.select_one('span.max-snippet-height')
        if desc_elem:
            job_data['description'] = desc_elem.get_text().strip()
        elif job_data.get('url'):
            full_desc, source = parse_job_detail_page_adzuna(job_data['url'])
            if full_desc:
                job_data['description'] = full_desc
        
        # Extract skills from description if available
        if job_data.get('description'):
            skills = extract_skills_from_text(job_data['description'], nlp_model)
            job_data['skills'] = skills
            
            # Classify skills as required or nice-to-have
            required, nice_to_have = classify_skills(job_data['description'], skills)
            job_data['required_skills'] = required
            job_data['nice_to_have_skills'] = nice_to_have
        
        # Set other job attributes
        job_data['is_remote'] = False  # Default value
        job_data['is_new'] = False
        job_data['is_urgent'] = False
        job_data['experience_level'] = 'mid'  # Default value
        
        # Save to database
        job_id = save_job_to_db(job_data, user_id)
        if job_id:
            logger.info(f"Successfully saved job: {job_data['title']}")
            return job_id
        else:
            logger.warning(f"Failed to save job: {job_data['title']}. Data: {json.dumps(job_data)}")
            return None
            
    except Exception as e:
        logger.error(f"Error parsing job listing: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return None

def classify_skills(desc_text, skills):
    """Classify skills as required or nice-to-have based on context."""
    required_skills = []
    nice_to_have_skills = []
    
    # Context markers for required skills
    required_markers = {
        # Section headers
        'required skills', 'requirements', 'must have', 'essential skills',
        'key skills', 'necessary skills', 'required:', 'required competencies',
        'you must have', 'mandatory skills', 'core competencies',
        'minimum requirements', 'basic requirements', 'key requirements',
        'technical requirements', 'job requirements',
        
        # Requirement phrases
        'must possess', 'required to have', 'should have', 'needs to have',
        'must be proficient', 'required experience', 'working knowledge',
        'strong background', 'solid understanding', 'expertise in',
        'proven experience', 'demonstrated ability', 'proven track record',
        'must demonstrate', 'required knowledge', 'must understand',
        'required proficiency', 'required skills include'
    }
    
    # Context markers for nice-to-have skills
    nice_to_have_markers = {
        # Section headers
        'nice to have', 'preferred skills', 'desirable skills', 'plus points',
        'additional skills', 'beneficial skills', 'bonus skills', 'advantageous',
        'preferred qualifications', 'desirable:', 'would be nice', 'good to have',
        'optional skills', 'preferences', 'desired qualifications',
        
        # Preference phrases
        'familiarity with', 'exposure to', 'nice to know', 'beneficial to have',
        'preferably', 'ideally', 'would be a plus', 'added advantage',
        'good to know', 'helpful to have', 'preferred experience',
        'additionally', 'bonus points', 'would be beneficial',
        'would be helpful', 'a plus if', 'bonus if', 'great if'
    }
    
    # Convert text to lowercase for matching
    desc_text = desc_text.lower()
    
    # Split into sections and sentences
    sections = desc_text.split('\n\n')  # Split by double newline to find major sections
    sentences = [s.strip() for s in desc_text.split('.')]  # Split into sentences
    
    for skill in skills:
        skill_lower = skill.lower()
        is_required = False
        is_nice_to_have = False
        
        # First check in structured sections
        for section in sections:
            section = section.strip()
            if skill_lower in section:
                # Check section headers
                if any(marker in section[:50].lower() for marker in required_markers):
                    is_required = True
                    break
                elif any(marker in section[:50].lower() for marker in nice_to_have_markers):
                    is_nice_to_have = True
                    break
        
        # If not found in sections, check individual sentences
        if not (is_required or is_nice_to_have):
            for sentence in sentences:
                if skill_lower in sentence:
                    # Look for requirement phrases
                    if any(marker in sentence for marker in required_markers):
                        is_required = True
                        break
                    # Look for nice-to-have phrases
                    elif any(marker in sentence for marker in nice_to_have_markers):
                        is_nice_to_have = True
                        break
        
        # If still not classified, look for nearby context (±50 characters)
        if not (is_required or is_nice_to_have):
            skill_pos = desc_text.find(skill_lower)
            if skill_pos != -1:
                context = desc_text[max(0, skill_pos - 50):min(len(desc_text), skill_pos + len(skill_lower) + 50)]
                
                # Check context for requirement indicators
                if any(marker in context for marker in required_markers):
                    is_required = True
                elif any(marker in context for marker in nice_to_have_markers):
                    is_nice_to_have = True
                else:
                    # Default classification based on language strength
                    strong_requirement_words = {'must', 'need', 'require', 'essential', 'necessary'}
                    preference_words = {'prefer', 'ideal', 'nice', 'plus', 'bonus', 'good'}
                    
                    if any(word in context for word in strong_requirement_words):
                        is_required = True
                    elif any(word in context for word in preference_words):
                        is_nice_to_have = True
                    else:
                        # Default to required if no clear indication
                        is_required = True
        
        # Add the skill to the appropriate list
        if is_required:
            required_skills.append(skill)
        elif is_nice_to_have:
            nice_to_have_skills.append(skill)
        else:
            required_skills.append(skill)  # Default to required if unclear
    
    # Remove duplicates while preserving order
    required_skills = list(dict.fromkeys(required_skills))
    nice_to_have_skills = list(dict.fromkeys(nice_to_have_skills))
    
    # If a skill appears in both lists, keep it only in required_skills
    nice_to_have_skills = [s for s in nice_to_have_skills if s not in required_skills]
    
    return required_skills, nice_to_have_skills

def extract_skills_from_text(text, nlp_model):
    """Extract skills from text using NLP and pattern matching."""
    skills = set()
    
    # Comprehensive list of technical skills, frameworks, and tools
    common_skills = {
        # Programming Languages
        'python', 'java', 'javascript', 'typescript', 'c++', 'c#', 'ruby', 'php', 'scala', 'kotlin', 'swift',
        'r programming', 'go', 'rust', 'perl', 'matlab', 'julia', 'haskell', 'dart',
        
        # Web Development
        'html', 'css', 'sass', 'less', 'jquery', 'bootstrap', 'tailwind', 'material-ui', 'webpack', 'babel',
        'react', 'angular', 'vue.js', 'svelte', 'next.js', 'gatsby', 'nuxt.js', 'redux', 'graphql',
        'rest api', 'soap', 'oauth', 'jwt', 'webrtc', 'websocket',
        
        # Backend Development
        'node.js', 'express.js', 'django', 'flask', 'fastapi', 'spring', 'spring boot', 'laravel',
        'asp.net', '.net core', 'rails', 'hibernate', 'servlet', 'tomcat', 'websphere',
        
        # Database Technologies
        'sql', 'mysql', 'postgresql', 'mongodb', 'redis', 'elasticsearch', 'cassandra', 'oracle',
        'sqlite', 'mariadb', 'dynamodb', 'couchbase', 'neo4j', 'hbase', 
        
        # Cloud & DevOps
        'aws', 'azure', 'gcp', 'docker', 'kubernetes', 'jenkins', 'gitlab ci', 'travis ci',
        'terraform', 'ansible', 'puppet', 'chef', 'vagrant', 'prometheus', 'grafana',
        'nginx', 'apache', 'linux', 'unix', 'bash', 'shell scripting',
        
        # Data Science & AI
        'machine learning', 'deep learning', 'artificial intelligence', 'ai', 'natural language processing',
        'nlp', 'computer vision', 'neural networks', 'tensorflow', 'pytorch', 'keras', 'scikit-learn',
        'pandas', 'numpy', 'scipy', 'matplotlib', 'seaborn', 'opencv',
        
        # Testing & QA
        'testing', 'selenium', 'cypress', 'jest', 'mocha', 'junit', 'pytest', 'testng',
        'cucumber', 'postman', 'soapui', 'jmeter', 'loadrunner', 'gatling',
        
        # Version Control & Project Management
        'git', 'svn', 'mercurial', 'jira', 'confluence', 'trello', 'asana',
        'scrum', 'agile', 'kanban', 'waterfall', 'prince2', 'pmp',
        
        # Mobile Development
        'android', 'ios', 'react native', 'flutter', 'xamarin', 'ionic', 'cordova',
        'swift', 'objective-c', 'kotlin', 'android studio', 'xcode',
        
        # Big Data
        'hadoop', 'spark', 'hive', 'pig', 'kafka', 'storm', 'flink', 'airflow',
        'big data', 'etl', 'data warehouse', 'data lake', 'nosql',
        
        # Security
        'cybersecurity', 'encryption', 'oauth', 'jwt', 'kerberos', 'ldap',
        'penetration testing', 'security', 'firewall', 'ssl/tls',
        
        # Methodologies & Patterns
        'object oriented programming', 'oop', 'functional programming', 'design patterns',
        'mvc', 'mvvm', 'microservices', 'soa', 'rest', 'solid principles',
        
        # Soft Skills
        'problem solving', 'communication', 'team leadership', 'project management',
        'analytical skills', 'critical thinking', 'time management', 'teamwork'
    }
    
    # Normalize text
    text = text.lower()
    
    # Extract skills using pattern matching
    for skill in common_skills:
        if skill in text.lower():
            # Verify it's a standalone word/phrase
            pattern = r'\b' + re.escape(skill) + r'\b'
            if re.search(pattern, text.lower(), re.IGNORECASE):
                # Add skill with proper capitalization
                skills.add(' '.join(word.capitalize() for word in skill.split()))
    
    # Use NLP model to extract technical terms and noun phrases
    if nlp_model:
        doc = nlp_model(text)
        
        # Look for terms in the context of skill-related phrases
        skill_contexts = [
            'experience with', 'knowledge of', 'proficiency in', 'expertise in',
            'familiar with', 'background in', 'skills in', 'understanding of',
            'working with', 'development in', 'programming in', 'using'
        ]
        
        # Process each sentence
        for sent in doc.sents:
            sent_text = sent.text.lower()
            
            # Check if sentence contains skill context
            if any(context in sent_text for context in skill_contexts):
                # Extract potential skills from this sentence
                for token in sent:
                    if (token.pos_ in ['NOUN', 'PROPN'] and 
                        len(token.text) > 2 and  # Avoid short words
                        not token.is_stop):
                        skill_text = token.text.lower()
                        if skill_text in common_skills:
                            # Add skill with proper capitalization
                            skills.add(' '.join(word.capitalize() for word in skill_text.split()))
                            
                # Also check for compound noun phrases
                for chunk in sent.noun_chunks:
                    chunk_text = chunk.text.lower()
                    if chunk_text in common_skills:
                        # Add skill with proper capitalization
                        skills.add(' '.join(word.capitalize() for word in chunk_text.split()))
    
    # Convert set to sorted list with properly formatted strings
    return sorted(list(skills))

def scrape_adzuna_jobs(query="All", location="All", user_skills=None, pages=1, user_id=None):
    """Scrape jobs from Adzuna."""
    if not user_id:
        logger.error("No user_id provided to scrape_adzuna_jobs")
        return []

    logger.info(f"Starting Adzuna scrape for '{query}' in '{location}' with user skills for {pages} page(s) for user {user_id}.")
    
    search_query = query if query.lower() != "all" else ""
    
    if location and location.lower() != "all":
        # Use provided location
        pass
    else:
        location = "India" # Default location
    
    all_found_jobs_ids = []  # Stores job IDs from _do_search
    searched_urls = set()
    
    try:
        # Handle case where user_skills is string instead of list
        if isinstance(user_skills, str):
            user_skills = [skill.strip() for skill in user_skills.split(',') if skill.strip()]
            logger.info(f"Converted user_skills string to list: {user_skills}")
        
        if user_skills:
            logger.info(f"Performing skill-based search for user {user_id} with skills: {user_skills}")
            for skill in user_skills:
                skill_specific_query = f"{search_query} {skill}".strip()
                logger.info(f"Searching for skill: {skill} with query: '{skill_specific_query}' for user {user_id}")
                skill_jobs_ids = _do_search(
                    skill_specific_query, 
                    location, 
                    pages=1, # Typically 1 page per skill to broaden reach without excessive scraping
                    searched_urls=searched_urls,
                    skill=skill,
                    user_id=user_id,
                    user_skills=user_skills # Pass all user skills for context if _do_search uses them
                )
                if skill_jobs_ids:
                    all_found_jobs_ids.extend(job_id for job_id in skill_jobs_ids if job_id not in all_found_jobs_ids)
            
            # Optionally, also do a general search if a base query was provided
            if search_query:
                logger.info(f"Performing base search with query: '{search_query}' for user {user_id}")
                base_jobs_ids = _do_search(
                    search_query,
                    location,
                    pages, # Use specified pages for base query
                    searched_urls,
                    user_id=user_id,
                    user_skills=user_skills
                )
                if base_jobs_ids:
                    all_found_jobs_ids.extend(job_id for job_id in base_jobs_ids if job_id not in all_found_jobs_ids)
        else:
            # No user_skills provided, do a single general search
            logger.info(f"Performing general search (no specific skills) with query: '{search_query}' for user {user_id}")
            all_found_jobs_ids = _do_search(
                search_query,
                location,
                pages,
                searched_urls,
                user_id=user_id,
                user_skills=None # Pass None if no skills were provided
            )

        num_jobs_ids_found = len(all_found_jobs_ids)
        logger.info(f"Completed Adzuna scraping phase for user {user_id}, found {num_jobs_ids_found} unique job IDs to process.")
        
        if num_jobs_ids_found == 0:
            logger.warning(f"No job IDs found by Adzuna scraping phase for user {user_id}.")
            return [] # Return empty list of IDs
            
        return all_found_jobs_ids # Return the list of unique job IDs found in this scrape
        
    except Exception as e:
        logger.error(f"Error in scrape_adzuna_jobs: {str(e)}")
        logger.error(traceback.format_exc())
        return []

def _do_search(search_query, location, pages, searched_urls, skill=None, user_id=None, user_skills=None):
    """Helper function to perform a single search with given parameters."""
    base_url = "https://www.adzuna.in/search"
    jobs_found = []
    
    try:
        for page_num in range(1, pages + 1):
            params = {}
            if search_query:
                params['q'] = search_query
            params['w'] = location
            params['p'] = page_num
            
            logger.info(f"Scraping Adzuna page {page_num} for query: {search_query}...")
            try:
                html_content = fetch_page(base_url, params=params)
                if not html_content:
                    logger.warning(f"Failed to fetch Adzuna search results page {page_num}. Skipping.")
                    continue
            except Exception as e:
                logger.error(f"Error fetching search page {page_num}: {e}")
                continue
                
            # Process the HTML content for this page
            soup = BeautifulSoup(html_content, 'html.parser')            # Use the specific Adzuna article selector
            articles = soup.select('article.a')
            if not articles:
                logger.warning(f"No job listings found on page {page_num}. Trying alternative selectors...")
                # Try alternative selectors if the main one fails
                articles = soup.select('[data-aid]') or soup.select('.job-listing') or soup.select('.result')
            
            if not articles:
                logger.warning(f"No job listings found on page {page_num} with any selector")
                continue
                
            logger.info(f"Found {len(articles)} job listings on page {page_num}")
            for article in articles:
                try:
                    # First parse and save basic job details
                    job_id = None
                    if isinstance(article, dict):
                        # If article is already a dictionary, save directly
                        article['user_id'] = user_id
                        job_id = save_job_to_db(article, user_id)
                        logger.info(f"Saved dictionary job listing directly with user_id={user_id}")
                    else:
                        # Otherwise parse as BeautifulSoup element
                        job_id = parse_job_listing(article, user_id, user_skills=user_skills)
                    
                    if job_id:
                        # Add the current skill if provided
                        if skill:
                            add_job_skills(job_id, [skill])
                        jobs_found.append(job_id)
                        logger.info(f"Successfully processed job with ID: {job_id}")
                    else:
                        logger.warning("Job processing did not return a valid job_id")
                except Exception as e:
                    logger.error(f"Error processing job listing: {str(e)}")
                    logger.error(traceback.format_exc())
                    continue
                    
            # Random delay between pages
            if page_num < pages:
                delay = random.uniform(2, 5)
                logger.info(f"Waiting {delay:.2f} seconds before next page...")
                time.sleep(delay)
        
        return jobs_found
    except Exception as e:
        logger.error(f"Error in _do_search: {str(e)}")
        logger.error(traceback.format_exc())
        return jobs_found

def scrape_jobs(query="All", location="All", user_skills=None, pages=1, force_clear=False, user_id=None):
    """
    Scrape jobs from various sources.

    Args:
        query (str): The search query for jobs
        location (str): The location to search in
        user_skills (list): List of user's skills for better matching
        pages (int): Number of pages to scrape
        force_clear (bool): Whether to clear existing jobs before scraping
        user_id (int): The ID of the user scraping jobs

    Returns:
        list: List of scraped job dictionaries for the user, or empty list if none found/error.
    """
    if not user_id:
        logger.error("Cannot scrape jobs without user_id")
        return []

    logger.info(f"Starting job scrape for user {user_id} with query: '{query}', location: '{location}', skills: {user_skills}")
    
    conn = None # Initialize conn
    try:
        conn = get_db_connection()
        # Ensure row_factory is set for dictionary-like results
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        if force_clear:
            logger.info(f"Clearing existing jobs for user {user_id}")
            cursor.execute("DELETE FROM jobs WHERE user_id = ?", (user_id,))
            conn.commit()
            logger.info(f"Successfully cleared jobs for user {user_id}.")

        # adzuna_job_ids will be a list of job IDs scraped and saved by scrape_adzuna_jobs (via _do_search)
        adzuna_job_ids = scrape_adzuna_jobs(query, location, user_skills, pages, user_id)
        
        if not adzuna_job_ids:
            logger.warning(f"No job IDs returned from scrape_adzuna_jobs for user {user_id}.")
            if conn: conn.close()
            return [] # No jobs found by the scraping sources
        
        logger.info(f"scrape_adzuna_jobs returned {len(adzuna_job_ids)} job IDs for user {user_id}.")

        # Fetch the full job details for these IDs from the database.
        # The jobs should have been saved with the correct user_id by _do_search -> save_job_to_db.
        try:
            # Ensure adzuna_job_ids are distinct
            unique_job_ids = list(set(adzuna_job_ids))
            placeholders = ','.join(['?' for _ in unique_job_ids])
            sql_query = f"SELECT * FROM jobs WHERE id IN ({placeholders}) AND user_id = ?"
            params = [*unique_job_ids, user_id] 
            
            logger.info(f"Fetching jobs from DB with query: {sql_query}, params length: {len(params)}")
            cursor.execute(sql_query, params)
            
            jobs_from_db = cursor.fetchall() # Returns list of sqlite3.Row objects
            logger.info(f"Fetched {len(jobs_from_db)} job details from DB for user {user_id} matching scraped IDs.")
            
            # Convert Row objects to dictionaries with better error handling
            job_dicts = []
            for job in jobs_from_db:
                try:
                    job_dict = dict(job)
                    job_dicts.append(job_dict)
                except Exception as e:
                    logger.error(f"Failed to convert job to dict: {e}")
            
            if conn: conn.close()
            logger.info(f"Returning {len(job_dicts)} job dictionaries")
            return job_dicts
            
        except Exception as e:
            logger.error(f"Error fetching jobs from database: {e}")
            logger.error(traceback.format_exc())
            if conn: conn.close()
            return []

    except sqlite3.Error as db_err:
        logger.error(f"Database error during job scraping for user {user_id}: {db_err}")
        logger.error(traceback.format_exc())
        if conn: conn.close()
        return []
    except Exception as e:
        logger.error(f"Unexpected error during job scraping for user {user_id}: {str(e)}")
        logger.error(traceback.format_exc())
        if conn: conn.close() # Ensure connection is closed on other exceptions too
        return []

def main_adzuna(query="All", location="All", pages=1, user_id=None):
    """Main function to run the Adzuna scraper"""
    try:
        # Always initialize database first
        logger.info("Initializing database...")
        if not initialize_database():
            logger.error("Failed to initialize database. Aborting scraping.")
            return False
            
        if not user_id:
            logger.error("No user_id provided. Aborting scraping.")
            return False
            
        # Verify user exists, but continue even if not found
        conn = get_db_connection()
        cursor = conn.cursor()
        # First check if user table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='user'")
        if not cursor.fetchone():
            logger.warning("User table not found in database, continuing with provided user_id")
        else:
            cursor.execute('SELECT id FROM user WHERE id = ?', (user_id,))
            if not cursor.fetchone():
                logger.warning(f"User with ID {user_id} does not exist in database but continuing anyway")
                # We'll continue without failing - the user_id will be used for job attribution
            
        logger.info("Starting job scraping...")
        jobs = scrape_adzuna_jobs(query=query, location=location, pages=pages, user_id=user_id)
        
        if jobs:
            logger.info(f"Job scraping completed successfully! Found {len(jobs)} jobs.")
            return True
        else:
            logger.warning("No jobs were found during scraping.")
            return False
            
    except Exception as e:
        logger.error(f"Error in main_adzuna: {str(e)}")
        logger.error(traceback.format_exc())
        return False
    finally:
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    try:
        # Add command line argument parsing with updated defaults
        parser = argparse.ArgumentParser(description='Scrape jobs from Adzuna.')
        parser.add_argument('--query', type=str, default="All", help='Job query terms')
        parser.add_argument('--location', type=str, default="All", help='Job location')
        parser.add_argument('--pages', type=int, default=1, help='Number of pages to scrape')
        parser.add_argument('--user_id', type=int, default=None, help='User ID for job scraping')
        
        args = parser.parse_args()
        
        logger.info(f"Preparing to scrape Adzuna for query='{args.query}', location='{args.location}', pages={args.pages}, user_id={args.user_id}")
        
        try:
            main_adzuna(query=args.query, location=args.location, pages=args.pages, user_id=args.user_id)
            logger.info("All scraping finished successfully.")
        except Exception as e:
            logger.error(f"Error in main_adzuna: {str(e)}", exc_info=True)
            raise
            
    except Exception as e:
        logger.error(f"Critical error: {str(e)}", exc_info=True)
        raise
