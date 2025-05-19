import os
import re
import PyPDF2
import docx
import traceback
from datetime import datetime
from dateutil import parser as date_parser
from nlp_utils import extract_skills_from_text, extract_location_from_text


def parse_resume(file_path, nlp_model, skill_keywords=None):
    """
    Parse resume file and extract comprehensive profile information.
    """
    try:
        print(f"Starting resume parsing for file: {file_path}")
        extracted_text = extract_text_by_file_type(file_path)
        extracted_text = clean_text(extracted_text)

        if len(extracted_text) < 100:
            print("Warning: Extracted text is very short, may indicate parsing issues")
            return None

        # Parse all profile components
        profile_data = {
            'skills': extract_skills_from_text(extracted_text, nlp_model),
            'location': extract_location_from_text(extracted_text, nlp_model),
            'work_experience': extract_work_experience(extracted_text, nlp_model),
            'education': extract_education(extracted_text, nlp_model),
            'certifications': extract_certifications(extracted_text),
            'extracted_text': extracted_text,
            'summary': extract_summary(extracted_text)  # New field
        }

        # Validate extracted data
        if not profile_data['skills']:
            print("Warning: No skills extracted from resume")
        if not profile_data['work_experience']:
            print("Warning: No work experience extracted from resume")
        if not profile_data['education']:
            print("Warning: No education information extracted from resume")

        return profile_data

    except Exception as e:
        print(f"Error parsing resume: {e}")
        print(traceback.format_exc())
        return None


def extract_work_experience(text, nlp_model):
    experiences = []
    # Common section headers for work experience
    work_headers = [
        r'work\s+experience',
        r'professional\s+experience',
        r'employment\s+history',
        r'work\s+history',
        r'career\s+history',
    ]
    
    # Try to find the work experience section
    experience_section = extract_section(text, work_headers)
    if not experience_section:
        return experiences

    # Process the text with spaCy for better entity recognition
    doc = nlp_model(experience_section)
    
    # Split into potential job entries (look for date patterns or company names)
    job_entries = split_into_entries(experience_section)
    
    for entry in job_entries:
        job = {}
          # Extract dates
        dates = extract_dates(entry)
        if dates:
            job['start_date'] = dates[0]
            job['end_date'] = dates[1] if len(dates) > 1 else None
            job['current_job'] = bool('present' in entry.lower() or not job.get('end_date'))
        
        # Extract company and title
        company_title = extract_company_and_title(entry, nlp_model)
        if company_title:
            job['company'] = company_title['company']
            job['title'] = company_title['title']
        
        # Extract description
        job['description'] = extract_job_description(entry)
        
        if job.get('company') and job.get('title'):
            experiences.append(job)
    
    return experiences


def extract_education(text, nlp_model):
    education = []
    # Common section headers for education
    edu_headers = [
        r'education',
        r'academic\s+background',
        r'academic\s+qualifications',
        r'educational\s+background',
    ]
    
    # Try to find the education section
    education_section = extract_section(text, edu_headers)
    if not education_section:
        return education

    # Process the text with spaCy
    doc = nlp_model(education_section)
    
    # Split into potential education entries
    edu_entries = split_into_entries(education_section)
    
    for entry in edu_entries:
        edu = {}
        
        # Extract institution and degree
        edu_info = extract_institution_and_degree(entry, nlp_model)
        if edu_info:
            edu.update(edu_info)
        
        # Extract dates
        dates = extract_dates(entry)
        if dates:
            edu['start_date'] = dates[0]
            edu['end_date'] = dates[1] if len(dates) > 1 else None
        
        # Extract GPA if available
        edu['gpa'] = extract_gpa(entry)
        
        if edu.get('institution') and edu.get('degree'):
            education.append(edu)
    
    return education


def extract_certifications(text):
    certifications = []
    # Common section headers for certifications
    cert_headers = [
        r'certifications?',
        r'professional\s+certifications?',
        r'technical\s+certifications?',
        r'certificates?',
    ]
    
    # Try to find the certifications section
    cert_section = extract_section(text, cert_headers)
    if not cert_section:
        return certifications

    # Look for certification patterns
    cert_patterns = [
        r'([A-Za-z0-9]+(?:[-\s][A-Za-z0-9]+)*\s+Certification)',
        r'(?:Certified|Licensed)\s+([A-Za-z0-9]+(?:[-\s][A-Za-z0-9]+)*)',
        r'([A-Za-z0-9]+(?:[-\s][A-Za-z0-9]+)*)\s+Certificate',
    ]
    
    for pattern in cert_patterns:
        matches = re.finditer(pattern, cert_section, re.IGNORECASE)
        for match in matches:
            cert = match.group(1).strip()
            if cert and cert not in certifications:
                certifications.append(cert)
    
    return certifications


def extract_summary(text):
    """Extract professional summary or objective from resume text."""
    summary_patterns = [
        r'(?i)(?:SUMMARY|PROFILE|OBJECTIVE)[:\s]*((?:[^\n]*\n?)*?)(?=\n\s*\n|\Z)',
        r'(?i)(?:PROFESSIONAL\s+SUMMARY|CAREER\s+OBJECTIVE)[:\s]*((?:[^\n]*\n?)*?)(?=\n\s*\n|\Z)'
    ]
    
    for pattern in summary_patterns:
        match = re.search(pattern, text)
        if match:
            summary = match.group(1).strip()
            # Clean up the summary
            summary = re.sub(r'\s+', ' ', summary)
            return summary[:500]  # Limit length
    
    return ""


# Helper functions for section extraction
def extract_section(text, headers, next_section_min_lines=2):
    text = text.strip()
    section_text = ""
    
    # Try to find the section header
    for header in headers:
        matches = list(re.finditer(header, text, re.IGNORECASE))
        if matches:
            start_pos = matches[0].end()
            # Look for the next section header
            next_header_pos = find_next_section(text[start_pos:])
            if next_header_pos > 0:
                section_text = text[start_pos:start_pos + next_header_pos].strip()
            else:
                section_text = text[start_pos:].strip()
            break
    
    return section_text


def find_next_section(text):
    # Common section headers that might follow
    next_headers = [
        r'\n[A-Z][A-Z\s]+(?:\:|$)',  # Capitalized words followed by colon or end of line
        r'\n(?:WORK|EMPLOYMENT|EDUCATION|SKILLS|CERTIFICATIONS|PROJECTS|REFERENCES)(?:\s+|$)',
    ]
    
    min_pos = float('inf')
    for pattern in next_headers:
        matches = list(re.finditer(pattern, text, re.IGNORECASE))
        if matches:
            pos = matches[0].start()
            if pos > 0 and pos < min_pos:
                min_pos = pos
    
    return min_pos if min_pos != float('inf') else -1


def extract_dates(text):
    dates = []
    # Various date patterns
    date_patterns = [
        # Full month names or abbreviations with year
        r'(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)[,\s]+\d{4}',
        # MM/DD/YYYY or MM/YYYY formats 
        r'\d{1,2}/(?:\d{1,2}/)\d{4}',
        r'\d{1,2}/\d{4}',
        # YYYY-MM-DD or YYYY-MM formats
        r'\d{4}-\d{1,2}(?:-\d{1,2})?',
        # Just year as fallback
        r'\d{4}'
    ]
    
    for pattern in date_patterns:
        matches = re.finditer(pattern, text, re.IGNORECASE)
        for match in matches:
            try:
                date_str = match.group(0).strip()
                # Special handling for standalone years
                if re.match(r'^\d{4}$', date_str):
                    date_str = f'01/01/{date_str}'
                
                # Parse the date string
                parsed_date = date_parser.parse(date_str).date()
                
                # Format as MM/YYYY
                formatted_date = parsed_date.strftime('%m/%Y')
                if formatted_date not in dates:
                    dates.append(formatted_date)
            except (ValueError, date_parser.ParserError):
                continue
    
    # Sort dates chronologically
    return sorted(dates)


def extract_company_and_title(text, nlp_model):
    doc = nlp_model(text)
    company = None
    title = None
    
    # Look for organization entities
    for ent in doc.ents:
        if ent.label_ == "ORG" and not company:
            company = ent.text
            break
    
    # Look for job titles using common patterns
    title_patterns = [
        # Common tech roles
        r'(?:^|\n|\s)([A-Z][a-zA-Z\s]+(?:Engineer|Engineering|Developer|Programmer|Architect|Specialist|Lead|Manager|Director|Analyst|Consultant|Designer|Administrator|DevOps|Scientist|Researcher))',
        # Software-specific roles
        r'(?:^|\n|\s)(Software\s+[A-Za-z\s]+)',
        r'(?:^|\n|\s)((?:Senior|Junior|Principal|Staff|Technical|Lead|Chief|Head)\s+[A-Za-z\s]+)',
        # Other professional titles
        r'(?:^|\n|\s)([A-Z][a-zA-Z\s]+(?:Professional|Expert|Coordinator|Supervisor|Officer|Chief|Head))',
        # Fallback for any capitalized role that looks like a title
        r'(?:^|\n)([A-Z][a-zA-Z\s]{2,}(?=\s*(?:at|for|with|in)\s))'
    ]
    
    for pattern in title_patterns:
        match = re.search(pattern, text)
        if match:
            title = match.group(1).strip()
            break
    
    # Fallback company detection if spaCy didn't find it
    if not company:
        company_patterns = [
            r'(?:at|for|with)\s+([A-Z][A-Za-z0-9\s&.,]+?)(?=\s*(?:in|from|until|as|\n|$))',
            r'(?<=\n)([A-Z][A-Za-z0-9\s&.,]+?)(?=\s*(?:•|\n|$))',
        ]
        for pattern in company_patterns:
            match = re.search(pattern, text)
            if match:
                potential_company = match.group(1).strip()
                if potential_company and len(potential_company) > 1:
                    company = potential_company
                    break
    
    if company or title:
        return {'company': company, 'title': title}
    return None


def extract_institution_and_degree(text, nlp_model):
    doc = nlp_model(text)
    education = {}
    
    # Look for educational institution entities
    for ent in doc.ents:
        if ent.label_ == "ORG" and not education.get('institution'):
            education['institution'] = ent.text
            break
    
    # Look for degree patterns
    degree_patterns = [
        r'(?:Bachelor|Master|PhD|B\.?S\.?|M\.?S\.?|B\.?A\.?|M\.?A\.?|Ph\.?D\.?|M\.?B\.?A\.?)(?:\sin\s|\sof\s)?([A-Za-z\s]+)',
        r'(?:Associate|Bachelor\'s|Master\'s|Doctorate)\s(?:in|of)\s([A-Za-z\s]+)'
    ]
    
    for pattern in degree_patterns:
        match = re.search(pattern, text)
        if match:
            education['degree'] = match.group(0).strip()
            education['field_of_study'] = match.group(1).strip()
            break
    
    return education if education.get('institution') or education.get('degree') else None


def extract_gpa(text):
    gpa_patterns = [
        r'GPA\s*(?:of\s*)?(\d+\.\d+)',
        r'Grade Point Average:\s*(\d+\.\d+)',
    ]
    
    for pattern in gpa_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            try:
                return float(match.group(1))
            except ValueError:
                continue
    return None


def extract_text_by_file_type(file_path):
    """Extract text based on file extension"""
    file_extension = os.path.splitext(file_path)[1].lower()
    
    if file_extension == '.pdf':
        return extract_text_from_pdf(file_path)
    elif file_extension == '.docx':
        return extract_text_from_docx(file_path)
    elif file_extension == '.txt':
        return extract_text_from_txt(file_path)
    else:
        raise ValueError(f"Unsupported file format: {file_extension}")


def extract_text_from_pdf(file_path):
    """Extract text from PDF file"""
    text = ""
    try:
        with open(file_path, 'rb') as file:
            reader = PyPDF2.PdfReader(file)
            for page_num in range(len(reader.pages)):
                page = reader.pages[page_num]
                text += page.extract_text() + "\n"

        print(f"Extracted {len(text)} characters from PDF")
        return text
    except Exception as e:
        print(f"Error extracting text from PDF: {e}")
        return text


def extract_text_from_docx(file_path):
    """Extract text from DOCX file"""
    text = ""
    try:
        doc = docx.Document(file_path)
        text = "\n".join([paragraph.text for paragraph in doc.paragraphs])

        print(f"Extracted {len(text)} characters from DOCX")
        return text
    except Exception as e:
        print(f"Error extracting text from DOCX: {e}")
        return text


def extract_text_from_txt(file_path):
    """Extract text from TXT file"""
    text = ""
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            text = file.read()

        print(f"Extracted {len(text)} characters from TXT")
        return text
    except UnicodeDecodeError:
        # Try with a different encoding if UTF-8 fails
        try:
            with open(file_path, 'r', encoding='latin-1') as file:
                text = file.read()

            print(f"Extracted {len(text)} characters from TXT (latin-1 encoding)")
            return text
        except Exception as e:
            print(f"Error extracting text from TXT with latin-1 encoding: {e}")
            return text
    except Exception as e:
        print(f"Error extracting text from TXT: {e}")
        return text


def clean_text(text):
    """Clean extracted text."""
    if not text:
        return ""

    # Replace multiple newlines with a single one
    text = re.sub(r'\n+', '\n', text)

    # Replace multiple spaces with a single one
    text = re.sub(r'\s+', ' ', text)

    return text.strip()


def split_into_entries(section_text):
    """Split a section into individual entries based on common patterns"""
    entries = []
    
    # Try to split by date patterns first
    date_splits = re.split(r'\n(?=(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)[,\s]+\d{4})', section_text)
    
    if len(date_splits) > 1:
        entries.extend(date_splits)
    else:
        # Try splitting by bullet points or numbers
        bullet_splits = re.split(r'\n(?=(?:•|\*|\-|\d+\.))', section_text)
        if len(bullet_splits) > 1:
            entries.extend(bullet_splits)
        else:
            # As a last resort, split by double newlines
            entries.extend([entry.strip() for entry in section_text.split('\n\n') if entry.strip()])
    
    return [entry.strip() for entry in entries if entry.strip()]


def extract_job_description(entry):
    """Extract job description from an entry"""
    # Remove any dates
    desc = re.sub(r'(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)[,\s]+\d{4}', '', entry)
    
    # Remove job title and company name patterns
    desc = re.sub(r'^[A-Z][a-zA-Z\s]+(?:Engineer|Developer|Manager|Director|Analyst|Consultant|Designer|Architect)', '', desc)
    desc = re.sub(r'^[A-Z][a-zA-Z\s]+,?\s+(?:Inc\.|LLC|Ltd\.|Corporation|Corp\.|Limited)?', '', desc)
    
    # Clean up the description
    desc = desc.strip()
    
    # Look for bullet points
    bullet_points = re.findall(r'(?:^|\n)[•\-\*]\s*(.+?)(?=(?:\n[•\-\*]|\n\n|$))', desc, re.DOTALL)
    if bullet_points:
        return '\n'.join('• ' + point.strip() for point in bullet_points)
    
    return desc
