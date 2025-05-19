import json
import logging
import os
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend for server environment
import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
from io import BytesIO
import base64
from collections import Counter, defaultdict
from datetime import datetime, timedelta
import numpy as np
from database_manager import get_db_connection, get_all_jobs, get_all_unique_skills

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

def get_job_insights(user_id, filter_by_skills=None, user_skills=None):
    """
    Generate insights from job data
    
    Args:
        user_id (int): The user ID to get jobs for
        filter_by_skills (list): Optional list of skills to filter by
        user_skills (list): Optional list of user's skills from resume/profile
        
    Returns:
        dict: Dictionary containing various insights and graph paths
      conn = None
    """  
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        # Get all jobs for this user - don't use GROUP BY to match job_list page count
        if user_id:
            cursor.execute("SELECT * FROM jobs WHERE user_id = ?", (user_id,))
        else:
            # Only for admin or testing
            cursor.execute("SELECT * FROM jobs")
            
        jobs = cursor.fetchall()
        logger.info(f"Found {len(jobs)} jobs for insights")
        
        if not jobs:
            logger.info(f"No jobs found for user {user_id}")
            return {
                "has_data": False,
                "message": "No job data available. Please scrape some jobs first."
            }
        
        # Convert to pandas DataFrame for easier analysis
        jobs_df = pd.DataFrame([dict(job) for job in jobs])
          # Clean and process the DataFrame
        insights = _process_job_data(jobs_df, filter_by_skills, user_skills)
        insights["has_data"] = True
        
        # Add user skills to insights if provided
        if user_skills:
            insights["user_skills"] = user_skills
        
        return insights
    
    except Exception as e:
        logger.error(f"Error generating job insights: {str(e)}")
        return {
            "has_data": False,
            "message": f"Error generating insights: {str(e)}"
        }
    finally:
        if conn:
            conn.close()

def _process_job_data(jobs_df, filter_by_skills=None, user_skills=None):
    """Process job data and generate visualizations"""
    insights = {}
    
    # Include user skills in insights if provided
    if user_skills:
        insights["user_resume_skills"] = user_skills
    
    # Apply skills filter if provided
    if filter_by_skills:
        # Normalize filter skills
        filter_by_skills = [s.lower() for s in filter_by_skills if s]
        filtered_jobs = []
        
        for _, job in jobs_df.iterrows():
            # Check if any of the required skills match
            req_skills = _parse_skills(job.get('required_skills', '[]'))
            nice_skills = _parse_skills(job.get('nice_to_have_skills', '[]'))
            all_skills = _parse_skills(job.get('skills', '[]'))
            
            all_job_skills = set(req_skills + nice_skills + all_skills)
            
            # If any skill matches, include this job
            if any(skill.lower() in filter_by_skills for skill in all_job_skills):
                filtered_jobs.append(job)
        
        if filtered_jobs:
            jobs_df = pd.DataFrame(filtered_jobs)
        else:
            # No jobs match the skills filter
            return {
                "has_data": False,
                "message": f"No jobs match the selected skills filter"
            }
      
    # Convert DataFrame to list of dictionaries for job_counter
    jobs_list = jobs_df.to_dict('records')
      # Import job_counter here to avoid circular imports
    try:
        from job_counter import get_job_counts
        # Extract user_id from first job in list if available
        user_id = None
        if jobs_list and len(jobs_list) > 0 and 'user_id' in jobs_list[0]:
            user_id = jobs_list[0]['user_id']
            
        job_counts = get_job_counts(jobs_list, user_id=user_id)
        insights.update(job_counts)  # Add all job counts to insights
    except ImportError:
        # Fallback if import fails
        insights["total_jobs"] = len(jobs_df)
    
    # Generate various insights and visualizations
    insights.update(_get_skill_trends(jobs_df, user_skills))
    insights.update(_get_location_trends(jobs_df))
    insights.update(_get_company_trends(jobs_df))
    insights.update(_get_salary_trends(jobs_df))
    insights.update(_get_job_type_trends(jobs_df))
    
    return insights

def _parse_skills(skills_str):
    """Parse skills from JSON string or return empty list"""
    if not skills_str:
        return []
    
    try:
        if isinstance(skills_str, str):
            skills = json.loads(skills_str)
            if isinstance(skills, list):
                return skills
            elif isinstance(skills, dict):
                return list(skills.values())
            else:
                return []
        elif isinstance(skills_str, list):
            return skills_str
        else:
            return []
    except json.JSONDecodeError:
        # If not valid JSON, try splitting by comma
        return [s.strip() for s in skills_str.split(',') if s.strip()]
    except:
        return []

def _get_skill_trends(jobs_df, user_skills=None):
    """Generate skill trend visualizations"""
    result = {}
    
    # Extract all skills from jobs
    all_skills = []
    required_skills = []
    nice_skills = []
    
    for _, job in jobs_df.iterrows():
        req = _parse_skills(job.get('required_skills', '[]'))
        nice = _parse_skills(job.get('nice_to_have_skills', '[]'))
        all_job = _parse_skills(job.get('skills', '[]'))
        
        required_skills.extend(req)
        nice_skills.extend(nice)
        all_skills.extend(req + nice + all_job)
    
    # Get the most common skills
    skill_counts = Counter(all_skills)
    top_skills = skill_counts.most_common(15)
    
    if not top_skills:
        result["skill_trends_graph"] = None
        result["top_skills"] = []
        return result
    
    # Process user skills if provided
    user_skills_set = set()
    if user_skills:
        # Store the original user skills in the result
        result["original_user_skills"] = user_skills
        
        # Normalize user skills for matching
        user_skills_set = {s.lower().strip() for s in user_skills if s}
        result["user_skills_count"] = len(user_skills_set)
        
        # Calculate how many top skills the user has
        top_skills_set = {s.lower().strip() for s, _ in top_skills}
        user_has_skills = top_skills_set.intersection(user_skills_set)
        result["user_has_top_skills"] = len(user_has_skills)
        result["user_top_skills_percentage"] = int((len(user_has_skills) / len(top_skills_set)) * 100) if top_skills_set else 0
        
        # Create a "missing skills" list for explicit skill gap analysis
        missing_skills = [skill for skill, _ in top_skills if skill.lower().strip() not in user_skills_set]
        result["missing_skills"] = missing_skills[:5]  # Top 5 missing skills
    
    # Generate skills bar chart
    plt.figure(figsize=(10, 6))
    plt.style.use('fivethirtyeight')
    
    skills, counts = zip(*top_skills)
    y_pos = np.arange(len(skills))
    
    # Color bars based on whether the user has the skill (if user_skills provided)
    bar_colors = []
    if user_skills_set:
        for skill in skills:
            if skill.lower().strip() in user_skills_set:
                bar_colors.append('green')  # User has this skill
            else:
                bar_colors.append('red')    # User doesn't have this skill
    else:
        bar_colors = ['skyblue'] * len(skills)  # Default color if no user skills
    
    bars = plt.barh(y_pos, counts, align='center', alpha=0.7, color=bar_colors)
    plt.yticks(y_pos, [s[:30] for s in skills])  # Truncate long skill names
    plt.xlabel('Number of Jobs')
    plt.title('Most In-Demand Skills' + (' (Green: You have the skill)' if user_skills_set else ''))
    
    # Add count labels to bars
    for i, bar in enumerate(bars):
        plt.text(bar.get_width() + 0.2, bar.get_y() + bar.get_height()/2, 
                 str(counts[i]), va='center')
    plt.tight_layout()
    
    # Save to memory buffer instead of file
    buffer = BytesIO()
    plt.savefig(buffer, format='png')
    buffer.seek(0)
    
    # Convert to base64 for direct embedding in HTML
    image_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
    result["skill_trends_graph"] = f"data:image/png;base64,{image_base64}"
    plt.close()
    buffer.close()
    
    result["top_skills"] = [{"skill": s, "count": c, "user_has": s.lower().strip() in user_skills_set if user_skills_set else False} for s, c in top_skills]
    
    # Add a user skill coverage chart if user skills are provided
    if user_skills_set:
        # Calculate skill coverage pie chart
        plt.figure(figsize=(8, 8))
        user_coverage = result.get("user_top_skills_percentage", 0)
        missing_coverage = 100 - user_coverage
        
        plt.pie([user_coverage, missing_coverage], 
                labels=['Skills You Have', 'Skills to Learn'], 
                colors=['green', 'red'],
                autopct='%1.1f%%',
                startangle=90,
                shadow=False)
        plt.axis('equal')
        plt.title('Your Skill Coverage of Top In-Demand Skills')
        
        buffer = BytesIO()
        plt.savefig(buffer, format='png')
        buffer.seek(0)
        image_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
        result["user_skill_coverage_graph"] = f"data:image/png;base64,{image_base64}"
        plt.close()
        buffer.close()
    
    # Required vs Nice-to-Have skills chart
    req_count = Counter(required_skills)
    nice_count = Counter(nice_skills)
    
    # Find skills that appear in both categories
    common_skills = set(req_count.keys()) & set(nice_count.keys())
    top_common_skills = sorted(common_skills, key=lambda s: req_count[s] + nice_count[s], reverse=True)[:10]
    if top_common_skills:
        req_counts = [req_count[s] for s in top_common_skills]
        nice_counts = [nice_count[s] for s in top_common_skills]
        
        x = np.arange(len(top_common_skills))
        width = 0.35
        
        fig, ax = plt.subplots(figsize=(12, 7))
        rects1 = ax.bar(x - width/2, req_counts, width, label='Required', color='crimson')
        rects2 = ax.bar(x + width/2, nice_counts, width, label='Nice to Have', color='royalblue')
        
        ax.set_xlabel('Skills')
        ax.set_ylabel('Number of Jobs')
        ax.set_title('Required vs Nice-to-Have Skills')
        ax.set_xticks(x)
        ax.set_xticklabels([s[:20] for s in top_common_skills], rotation=45, ha='right')
        ax.legend()
        plt.tight_layout()
        
        # Save to memory buffer instead of file
        buffer = BytesIO()
        plt.savefig(buffer, format='png')
        buffer.seek(0)
        
        # Convert to base64 for direct embedding in HTML
        image_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
        result["skill_comparison_graph"] = f"data:image/png;base64,{image_base64}"
        plt.close()
        buffer.close()
    
    return result

def _get_location_trends(jobs_df):
    """Generate location trend visualizations"""
    result = {}
    
    if 'location' not in jobs_df.columns or jobs_df['location'].isna().all():
        return result
    
    # Clean and standardize locations (extract cities)
    locations = []
    for loc in jobs_df['location'].dropna():
        if isinstance(loc, str):
            parts = loc.split(',')
            locations.append(parts[0].strip())
    
    location_counts = Counter(locations)
    top_locations = location_counts.most_common(10)
    
    if not top_locations:
        return result
    plt.figure(figsize=(10, 6))
    locations, counts = zip(*top_locations)
    
    # Create a horizontal bar chart instead of a pie chart to avoid label overlap
    y_pos = np.arange(len(locations))
    plt.barh(y_pos, counts, align='center', alpha=0.7, color='green')
    plt.yticks(y_pos, [loc[:20] for loc in locations])  # Truncate long location names
    plt.xlabel('Number of Jobs')
    plt.title('Job Distribution by Location')
    
    # Add count labels to bars
    for i, count in enumerate(counts):
        plt.text(count + 0.1, i, str(count), va='center')
    
    plt.tight_layout()
    
    # Save to memory buffer instead of file
    buffer = BytesIO()
    plt.savefig(buffer, format='png', bbox_inches='tight')
    buffer.seek(0)
    
    # Convert to base64 for direct embedding in HTML
    image_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
    result["location_trends_graph"] = f"data:image/png;base64,{image_base64}"
    plt.close()
    buffer.close()
    result["top_locations"] = [{"location": l, "count": c} for l, c in top_locations]
    
    return result

def _get_company_trends(jobs_df):
    """Generate company trend visualizations"""
    result = {}
    
    if 'company' not in jobs_df.columns or jobs_df['company'].isna().all():
        return result
    
    company_counts = Counter(jobs_df['company'].dropna())
    top_companies = company_counts.most_common(10)
    
    if not top_companies:
        return result
    
    plt.figure(figsize=(10, 6))
    plt.style.use('seaborn-v0_8-darkgrid')
    
    companies, counts = zip(*top_companies)
    y_pos = np.arange(len(companies))
    
    plt.barh(y_pos, counts, align='center', alpha=0.8, color='purple')
    plt.yticks(y_pos, [c[:30] for c in companies])  # Truncate long company names
    plt.xlabel('Number of Job Postings')
    plt.title('Companies with Most Job Openings')
    plt.tight_layout()
      # Save to memory buffer instead of file
    buffer = BytesIO()
    plt.savefig(buffer, format='png')
    buffer.seek(0)
    
    # Convert to base64 for direct embedding in HTML
    image_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
    result["company_trends_graph"] = f"data:image/png;base64,{image_base64}"
    plt.close()
    buffer.close()
    result["top_companies"] = [{"company": c, "count": n} for c, n in top_companies]
    
    return result

def _get_salary_trends(jobs_df):
    """Generate salary trend visualizations"""
    result = {}
    
    salary_fields = ['salary_min', 'salary_max']
    if not all(field in jobs_df.columns for field in salary_fields):
        return result
    
    # Filter for jobs that have salary information
    salary_df = jobs_df[jobs_df['salary_min'].notna() & jobs_df['salary_max'].notna()].copy()
    
    if len(salary_df) == 0:
        return result
    
    # Convert salary columns to numeric if they aren't already
    for field in salary_fields:
        if salary_df[field].dtype == 'object':
            salary_df[field] = pd.to_numeric(salary_df[field], errors='coerce')
    
    # Filter out unreasonable values
    salary_df = salary_df[(salary_df['salary_min'] > 0) & (salary_df['salary_min'] < 10000000) &
                          (salary_df['salary_max'] > 0) & (salary_df['salary_max'] < 10000000)]
    
    if len(salary_df) == 0:
        return result
    
    # Calculate average salary
    salary_df['avg_salary'] = (salary_df['salary_min'] + salary_df['salary_max']) / 2
    
    # If we have skills data, examine salary by skill
    has_skills_data = False
    skill_salary_data = []
    
    for _, job in salary_df.iterrows():
        skills = set()
        for skill_field in ['required_skills', 'nice_to_have_skills', 'skills']:
            if skill_field in job and job[skill_field]:
                skills.update(_parse_skills(job[skill_field]))
        
        for skill in skills:
            skill_salary_data.append({
                'skill': skill,
                'salary': job['avg_salary']
            })
    
    if skill_salary_data:
        has_skills_data = True
        skill_salary_df = pd.DataFrame(skill_salary_data)
        
        # Group by skill and calculate average salary
        skill_avg_salary = skill_salary_df.groupby('skill')['salary'].agg(['mean', 'count'])
        skill_avg_salary = skill_avg_salary[skill_avg_salary['count'] >= 5]  # Only skills with at least 5 job postings
        skill_avg_salary = skill_avg_salary.sort_values('mean', ascending=False).head(15)
        
        if len(skill_avg_salary) > 0:
            plt.figure(figsize=(12, 8))
            
            bars = plt.barh(skill_avg_salary.index, skill_avg_salary['mean'], color='green', alpha=0.7)
            plt.xlabel('Average Salary')
            plt.title('Average Salary by Skill (Top 15)')
              # Format salary numbers
            plt.gca().xaxis.set_major_formatter(plt.FuncFormatter(lambda x, loc: f"${int(x):,}"))
            
            # Add count labels
            for i, bar in enumerate(bars):
                skill = skill_avg_salary.index[i]
                plt.text(bar.get_width() + 1000, bar.get_y() + bar.get_height()/2, 
                         f"n={skill_avg_salary.loc[skill, 'count']}", va='center')
            plt.tight_layout()
            
            # Save to memory buffer instead of file
            buffer = BytesIO()
            plt.savefig(buffer, format='png')
            buffer.seek(0)
            
            # Convert to base64 for direct embedding in HTML
            image_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
            result["skill_salary_graph"] = f"data:image/png;base64,{image_base64}"
            plt.close()
            buffer.close()
    
    # Overall salary distribution
    plt.figure(figsize=(10, 6))
    
    sns.histplot(salary_df['avg_salary'], kde=True, bins=20, color='green')
    plt.xlabel('Average Salary')
    plt.ylabel('Number of Jobs')
    plt.title('Salary Distribution')
    
    # Format salary numbers on x-axis
    plt.gca().xaxis.set_major_formatter(plt.FuncFormatter(lambda x, loc: f"${int(x):,}"))
    plt.tight_layout()
    
    # Save to memory buffer instead of file
    buffer = BytesIO()
    plt.savefig(buffer, format='png')
    buffer.seek(0)
    
    # Convert to base64 for direct embedding in HTML
    image_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
    result["salary_dist_graph"] = f"data:image/png;base64,{image_base64}"
    plt.close()
    buffer.close()
    
    # Calculate summary statistics
    result["salary_stats"] = {
        "min": int(salary_df['salary_min'].min()),
        "max": int(salary_df['salary_max'].max()),
        "avg": int(salary_df['avg_salary'].mean()),
        "median": int(salary_df['avg_salary'].median())
    }
    
    return result

def _get_job_type_trends(jobs_df):
    """Generate job type trend visualizations"""
    result = {}
    
    # Check if we have data on job types, employment types, or remote work
    type_fields = ['job_type', 'employment_type', 'is_remote', 'experience_level']
    available_fields = [field for field in type_fields if field in jobs_df.columns]
    
    if not available_fields:
        return result
    
    # Process employment type data
    if 'employment_type' in available_fields and not jobs_df['employment_type'].isna().all():
        emp_types = jobs_df['employment_type'].dropna().tolist()
        emp_type_counts = Counter(emp_types)
        
        if emp_type_counts:
            plt.figure(figsize=(8, 8))
            
            labels = emp_type_counts.keys()
            sizes = emp_type_counts.values()
            colors = plt.cm.Paired(np.linspace(0, 1, len(labels)))
            plt.pie(sizes, labels=labels, autopct='%1.1f%%', startangle=140, colors=colors)
            plt.axis('equal')
            plt.title('Jobs by Employment Type')
            
            # Save to memory buffer instead of file
            buffer = BytesIO()
            plt.savefig(buffer, format='png', bbox_inches='tight')
            buffer.seek(0)
            
            # Convert to base64 for direct embedding in HTML
            image_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
            result["employment_type_graph"] = f"data:image/png;base64,{image_base64}"
            plt.close()
            buffer.close()
      # Process remote work data
    if 'is_remote' in available_fields:
        # Detect remote jobs using both is_remote column and keyword search for completeness
        remote_jobs = jobs_df.apply(
            lambda job: (job.get('is_remote') == 1 or 
                        'remote' in str(job.get('title', '')).lower() or
                        'remote' in str(job.get('location', '')).lower() or
                        'remote' in str(job.get('description', '')).lower()),
            axis=1
        )
        # Create a temporary column for this analysis
        jobs_df['temp_is_remote'] = remote_jobs
        remote_counts = Counter(jobs_df['temp_is_remote'])
        
        # Log detection method for debugging
        logger.info(f"Remote detection: is_remote=1 count: {Counter(jobs_df['is_remote']).get(1, 0)}, keyword count: {sum(remote_jobs) - Counter(jobs_df['is_remote']).get(1, 0)}")
        
        if remote_counts:
            plt.figure(figsize=(8, 6))
            
            remote_count = remote_counts.get(True, 0)
            onsite_count = jobs_df.shape[0] - remote_count
            
            # Log the counts for debugging
            logger.info(f"Remote jobs: {remote_count}, On-site jobs: {onsite_count}")
            
            labels = ['Remote', 'On-site']
            sizes = [remote_count, onsite_count]
            colors = ['#66b3ff', '#ff9999']
            
            # Create a better-looking pie chart with proper sizing
            plt.pie(sizes, labels=labels, autopct='%1.1f%%', startangle=140, 
                   colors=colors, shadow=False, textprops={'fontsize': 14})
            plt.axis('equal')            
            plt.title('Remote vs On-site Jobs', fontsize=16)
            
            # Save to memory buffer instead of file
            buffer = BytesIO()
            plt.savefig(buffer, format='png', bbox_inches='tight')
            buffer.seek(0)
            
            # Convert to base64 for direct embedding in HTML
            image_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
            result["remote_work_graph"] = f"data:image/png;base64,{image_base64}"
            plt.close()
            buffer.close()
      # Process experience level data
    if 'experience_level' in available_fields and not jobs_df['experience_level'].isna().all():
        exp_levels = jobs_df['experience_level'].dropna().tolist()
        exp_level_counts = Counter(exp_levels)
        
        if exp_level_counts:
            plt.figure(figsize=(10, 6))
            
            levels, counts = zip(*sorted(exp_level_counts.items()))
            x_pos = np.arange(len(levels))
            
            plt.bar(x_pos, counts, align='center', alpha=0.7)
            plt.xticks(x_pos, levels, rotation=45, ha='right')
            plt.xlabel('Experience Level')            
            plt.ylabel('Number of Jobs')
            plt.title('Jobs by Experience Level')
            plt.tight_layout()
            
            # Save to memory buffer instead of file
            buffer = BytesIO()
            plt.savefig(buffer, format='png')
            buffer.seek(0)
            
            # Convert to base64 for direct embedding in HTML
            image_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
            result["experience_level_graph"] = f"data:image/png;base64,{image_base64}"
            plt.close()
            buffer.close()
    
    return result

def get_skill_options():
    """Get all skills available for filtering"""
    try:
        # Get unique skills from the job_skills table
        skills = get_all_unique_skills()
        return sorted(skills)
    except Exception as e:
        logger.error(f"Error getting skill options: {str(e)}")
        return []
