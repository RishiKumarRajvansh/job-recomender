import json
import os
import re
import spacy
from spacy.matcher import PhraseMatcher
import string
import nltk
from nltk.corpus import stopwords

# Try to download NLTK stopwords if needed
try:
    nltk.data.find('corpora/stopwords')
except (LookupError, ImportError):
    try:
        nltk.download('stopwords', quiet=True)
    except:
        pass  # Continue even if we can't download stopwords

# Path to skills data file - we'll include this as a JSON string in the code
# instead of creating a separate file
SKILLS_JSON = '''{
  "skills": [
    "python", "java", "javascript", "typescript", "c++", "c#", "ruby", "php", "swift", "kotlin", "go",
    "react", "angular", "vue", "node.js", "express", "django", "flask", "spring", "asp.net", "laravel",
    "sql", "mysql", "postgresql", "mongodb", "sqlite", "oracle", "cassandra", "dynamodb", "redis",
    "aws", "azure", "gcp", "docker", "kubernetes", "jenkins", "terraform", "git", "github", "gitlab",
    "jira", "bitbucket", "html", "css", "sass", "less", "bootstrap", "tailwind", "jquery",
    "rest api", "graphql", "json", "xml", "soap", "microservices", "serverless", "linux", "unix", "bash",
    "powershell", "agile", "scrum", "kanban", "devops", "ci/cd", "data science", "machine learning", "ai",
    "tensorflow", "pytorch", "keras", "numpy", "pandas", "scikit-learn", "matplotlib", "hadoop", "spark",
    "elasticsearch", "kibana", "logstash", "tableau", "power bi", "excel", "vba", "etl", "data warehousing",
    "big data", "data mining", "data analysis", "statistics", "r", "matlab", "sas", "spss", "scala", "kafka",
    "rabbitmq", "activemq", "celery", "redis queue", "pytest", "junit", "nunit", "selenium", "cypress",
    "jest", "mocha", "chai", "webpack", "babel", "eslint", "prettier", "npm", "yarn", "pip", "conda",
    "virtualenv", "docker-compose", "vagrant", "ansible", "puppet", "chef", "nginx", "apache", "iis",
    "tomcat", "websphere", "weblogic", "oauth", "jwt", "saml", "ldap", "active directory", "wordpress",
    "drupal", "magento", "shopify", "woocommerce", "seo", "sem", "google analytics", "google tag manager",
    "ux", "ui", "photoshop", "illustrator", "sketch", "figma", "swift ui", "flutter", "react native", 
    "xamarin", "ionic", "cordova", "objective-c", "kotlin", "android sdk", "ios sdk", "xcode", 
    "android studio", "firebase", "realm", "coredata", "sqllite", "room", "mvvm", "mvc",
    "clean architecture", "design patterns", "solid principles", "tdd", "bdd", "ddd", "functional programming",
    "object-oriented programming", "reactive programming", "concurrency", "multithreading", "async/await",
    "blockchain", "cryptocurrency", "smart contracts", "solidity", "web3", "ethereum", "hyperledger",
    "networking", "tcp/ip", "http/https", "dns", "dhcp", "ftp", "ssh", "vpn", "load balancing", "proxy",
    "caching", "cdn", "websockets", "webrtc", "grpc", "amqp", "mqtt", "iot", "embedded systems", "raspberry pi",
    "arduino", "plc", "scada", "cybersecurity", "penetration testing", "vulnerability assessment", "encryption",
    "authentication", "authorization", "firewall", "ids/ips", "siem", "dlp", "cloud security", "devsecops",
    "js", "ts", "golang", "rust", "perl", "r", "shell", "nosql", "next.js", "nextjs", "nuxt", "rails", 
    "symfony", "material-ui", "chakra-ui", "ember", "backbone", "jetpack compose", "swiftui", "mariadb", 
    "neo4j", "couchdb", "supabase", "datomic", "k8s", "gitlab ci", "github actions", "puppet", "chef", 
    "vagrant", "prometheus", "grafana", "lambda", "serverless", "ec2", "s3", "eks", "ecs", "rds", "cloudfront",
    "continuous integration", "continuous deployment", "ml", "deep learning", "dl", "computer vision", 
    "natural language processing", "data studio", "looker", "predictive analytics", "responsive design",
    "jamstack", "redux", "mobx", "context api", "webgl", "canvas", "svg", "unit testing", "integration testing",
    "e2e testing", "testing library", "testng", "rspec", "cucumber", "jasmine", "cybersecurity", "infosec",
    "penetration testing", "pentest", "oauth", "jwt", "hashing", "ssl", "tls", "https", "joomla", "contentful",
    "strapi", "sanity", "netlify cms", "ghost", "soap", "grpc", "websocket", "blockchain", "ar", "vr",
    "embedded systems", "virtualization", "web services", "paas", "iaas", "distributed systems", "caching",
    "memcached", "cdn", "soa", "etl", "message queue", "service bus", "oauth", "openid", "saml", "system design"
  ]
}'''

# Common words that might be falsely identified as skills
SKILL_STOPWORDS = {
    'able', 'about', 'across', 'after', 'detail', 'team', 'building',
    'using', 'used', 'well', 'work', 'working', 'works', 'year', 'years',
    'skills', 'skill', 'proficient', 'experience', 'experienced', 'familiar',
    'knowledge', 'background', 'understanding', 'proficiency',
    'right', 'left', 'up', 'down', 'top', 'bottom', 'ms', 'etc', 'new', 'good',
    'part', 'better', 'best', 'lot', 'need', 'high', 'low'
}

# Common technical context indicators to help identify skills
TECH_CONTEXT_WORDS = {
    'programming', 'coding', 'development', 'software', 'engineering', 'framework',
    'library', 'platform', 'stack', 'database', 'system', 'architecture', 'api',
    'backend', 'frontend', 'fullstack', 'devops', 'cloud', 'server', 'client',
    'web', 'mobile', 'desktop', 'algorithm', 'data structure', 'infrastructure'
}

# Function to check if text has technical context
def has_technical_context(text_before, text_after):
    """Check if the surrounding text indicates a technical context"""
    context = (text_before + ' ' + text_after).lower()
    return any(word in context for word in TECH_CONTEXT_WORDS)

def load_spacy_model(model_name="en_core_web_sm"):
    """
    Load the specified spaCy language model and return both the model and skill keywords.
    
    Args:
        model_name (str): Name of the spaCy model to load
        
    Returns:
        tuple: (spaCy language model, list of skill keywords)
    """
    try:
        nlp = spacy.load(model_name)
        print(f"Loaded spaCy model '{model_name}'")
    except OSError:
        print(f"spaCy model '{model_name}' not found. Downloading...")
        import subprocess
        subprocess.check_call([
            "python", "-m", "spacy", "download", model_name
        ])
        nlp = spacy.load(model_name)
        print(f"Successfully downloaded and loaded '{model_name}'")
    
    # Load skills data from the embedded JSON
    skills_data = json.loads(SKILLS_JSON)
    # Get just the skills list (no soft skills, software, certificates as requested)
    skill_keywords = skills_data["skills"]
    
    return nlp, skill_keywords

def extract_skills_from_text(text, nlp):
    """
    Extract technical skills from text using NLP and a predefined skills database.
    
    Args:
        text (str): The text to analyze
        nlp: spaCy loaded language model
        
    Returns:
        list: List of identified skills
    """
    if not text or not isinstance(text, str):
        return []
    
    # Load skills data from the embedded JSON
    skills_data = json.loads(SKILLS_JSON)
    all_skills = skills_data["skills"]
    
    # Create phrase patterns for multi-word skills
    matcher = PhraseMatcher(nlp.vocab, attr="LOWER")
    
    # Separate single and multi-word skills
    single_word_skills = set()
    multi_word_skills = []
    
    for skill in all_skills:
        skill_lower = skill.lower().strip()
        if not skill_lower or len(skill_lower) < 2:
            continue
            
        if ' ' in skill_lower:
            multi_word_skills.append(skill_lower)
            pattern = nlp(skill_lower)
            skill_key = skill_lower.replace(' ', '_')
            matcher.add(skill_key, [pattern])
        else:
            single_word_skills.add(skill_lower)
    
    # Process the document with spaCy
    doc = nlp(text.lower())
    
    # Find all skill matches
    matches = matcher(doc)
    matched_skills = set()
    
    # Extract multi-word skills with context validation
    for match_id, start, end in matches:
        span = doc[start:end]
        skill_text = span.text.lower()
        
        if skill_text in SKILL_STOPWORDS:
            continue
            
        # Get context before and after
        text_before = ' '.join(token.text for token in doc[max(0, start-5):start])
        text_after = ' '.join(token.text for token in doc[end:min(len(doc), end+5)])
        
        if has_technical_context(text_before, text_after):
            matched_skills.add(skill_text)
    
    # Extract single-word skills
    for i, token in enumerate(doc):
        token_text = token.text.lower()
        
        if (token.is_punct or token.is_stop or token.is_space or 
            len(token_text) < 2 or token_text in SKILL_STOPWORDS):
            continue
        
        if token_text in single_word_skills:
            # Get context for validation
            text_before = ' '.join(t.text for t in doc[max(0, i-5):i])
            text_after = ' '.join(t.text for t in doc[i+1:min(len(doc), i+6)])
            
            # Special handling for common ambiguous terms
            if token_text in {'c', 'r', 'go', 'js', 'ui', 'ux', 'qa'}:
                if has_technical_context(text_before, text_after):
                    matched_skills.add(token_text)
            else:
                matched_skills.add(token_text)
    
    # Additional pattern matching for skill extraction
    patterns = [
        # Programming language patterns
        r'\b(programming|coding|developing)\s+(in|with)\s+([A-Za-z\+\#\.]+)',
        # Technology/tool patterns
        r'\b(using|with|in)\s+([A-Za-z\+\#\.]+)\s+(framework|library|platform|stack)',
        # Version control and tools
        r'\b(git|svn|mercurial)(?:\s+version\s+control)?\b',
        # Cloud platforms
        r'\b(aws|azure|gcp|cloud)\s+(?:platform|services?|computing)\b',
        # Frameworks and tools with versions
        r'\b([A-Za-z]+(?:\.[js|ts])?)\s+(?:v?[\d\.]+)\b',
        # Containerization and deployment
        r'\b(docker|kubernetes|k8s|jenkins|ci/cd)\b',
        # Database systems
        r'\b(sql|nosql|mongodb|postgresql|mysql|oracle|redis)\b',
        # Web technologies
        r'\b(html5?|css3?|sass|less|webpack|babel|node(?:\.js)?)\b'
    ]
    
    for pattern in patterns:
        matches = re.finditer(pattern, text.lower(), re.IGNORECASE)
        for match in matches:
            # Get the last group if it exists, otherwise use the first match
            skill = match.group(match.lastindex if match.lastindex else 0).lower()
            if skill in single_word_skills and skill not in SKILL_STOPWORDS:
                matched_skills.add(skill)
    
    # Normalize the skills
    normalized_skills = []
    for skill in matched_skills:
        # Handle special cases for proper capitalization
        if skill.lower() in ['html', 'css', 'php', 'sql', 'aws', 'gcp', 'api', 'json', 'xml', 'ci/cd', 'qa']:
            normalized_skills.append(skill.upper())
        elif skill.lower() in ['javascript', 'typescript', 'python', 'java', 'nodejs', 'react', 'angular', 'vue']:
            normalized_skills.append(skill.capitalize())
        else:
            normalized_skills.append(skill)
    
    return sorted(normalized_skills)

def extract_location_from_text(text, nlp):
    """
    Extract location information from resume text.
    
    Args:
        text (str): The resume text
        nlp: spaCy loaded language model
        
    Returns:
        str: The identified location or empty string if none found
    """
    if not text or not isinstance(text, str):
        return ""
    
    # Process the document
    doc = nlp(text)
    
    # First try to find location patterns
    location_patterns = [
        r'(?i)Location\s*:\s*([A-Za-z\s,]+)',
        r'(?i)Address\s*:\s*([^,]+,\s*[A-Za-z\s]+)',
        r'(?i)(?:Based in|Located in|Living in)\s+([A-Za-z\s,]+)',
        r'(?i)([A-Za-z\s]+),\s*(?:AL|AK|AZ|AR|CA|CO|CT|DE|FL|GA|HI|ID|IL|IN|IA|KS|KY|LA|ME|MD|MA|MI|MN|MS|MO|MT|NE|NV|NH|NJ|NM|NY|NC|ND|OH|OK|OR|PA|RI|SC|SD|TN|TX|UT|VT|VA|WA|WV|WI|WY)\s*\d{5}?',
        r'(?i)City\s*:\s*([A-Za-z\s,]+)',
        r'(?i)based in\s+([A-Za-z\s,]+)',
        r'(?i)located in\s+([A-Za-z\s,]+)',
        r'(?i)(remote|work from home|wfh)'
    ]
    
    for pattern in location_patterns:
        match = re.search(pattern, text)
        if match:
            if len(match.groups()) > 0:
                location = match.group(1).strip()
                if location:
                    return location
            elif "remote" in match.group(0).lower():
                return "Remote"
    
    # Then try to find location entities using spaCy
    locations = []
    for ent in doc.ents:
        if ent.label_ in ["GPE", "LOC"]:
            locations.append(ent.text)
    
    # If entities found, return the most common one
    if locations:
        from collections import Counter
        location_counts = Counter(locations)
        return location_counts.most_common(1)[0][0]
    
    # If still no location found, look for addresses
    address_patterns = [
        r'\b\d+\s+[A-Za-z\s]+(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Lane|Ln|Drive|Dr)\b[^,]*,\s*([A-Za-z\s]+)',
        r'[A-Za-z\s]+,\s*(?:AL|AK|AZ|AR|CA|CO|CT|DE|FL|GA|HI|ID|IL|IN|IA|KS|KY|LA|ME|MD|MA|MI|MN|MS|MO|MT|NE|NV|NH|NJ|NM|NY|NC|ND|OH|OK|OR|PA|RI|SC|SD|TN|TX|UT|VT|VA|WA|WV|WI|WY)'
    ]
    
    for pattern in address_patterns:
        match = re.search(pattern, text)
        if match and match.groups():
            return match.group(1).strip()
    
    return ""

def parse_resume_for_skills(resume_text):
    """
    Extract skills from a resume.
    
    Args:
        resume_text (str): Text from a resume
    
    Returns:
        list: Extracted skills from the resume
    """
    nlp, _ = load_spacy_model()
    skills = extract_skills_from_text(resume_text, nlp)
    return skills

# If the script is run directly, test the functionality
if __name__ == "__main__":
    test_text = """
    Job Description:
    We are looking for a skilled Python developer with experience in Django and Flask frameworks.
    The ideal candidate should have 3+ years of experience with REST API development,
    good knowledge of SQL databases (MySQL or PostgreSQL), and be familiar with AWS services.
    Experience with JavaScript, React, and Docker is a plus.
    """
    
    print("Testing skill extraction:")
    nlp, _ = load_spacy_model()
    skills = extract_skills_from_text(test_text, nlp)
    print(f"Extracted {len(skills)} skills: {skills}")

