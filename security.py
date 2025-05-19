"""
Security utilities for the Job Recommender System.

This module provides security-related functions and middleware for the application,
including security headers, CSRF protection, and other security enhancements.
"""
import os
from functools import wraps
from flask import Response, request, g, current_app

def set_secure_headers(response):
    """
    Add security headers to all responses.
    
    Args:
        response: Flask response object
        
    Returns:
        Response with security headers added
    """
    # Content Security Policy to prevent XSS
    csp = (
        "default-src 'self'; "
        "script-src 'self' https://cdn.jsdelivr.net 'unsafe-inline'; "
        "style-src 'self' https://cdn.jsdelivr.net 'unsafe-inline'; "
        "img-src 'self' data: https:; "
        "font-src 'self' https://cdn.jsdelivr.net; "
        "connect-src 'self';"
    )
    
    # Content-Security-Policy
    response.headers['Content-Security-Policy'] = csp
    
    # Prevent MIME type sniffing
    response.headers['X-Content-Type-Options'] = 'nosniff'
    
    # Prevent clickjacking
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    
    # Enable browser's XSS protection
    response.headers['X-XSS-Protection'] = '1; mode=block'
    
    # Referrer Policy
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    
    # Permissions Policy (formerly Feature-Policy)
    response.headers['Permissions-Policy'] = (
        'camera=(), microphone=(), geolocation=(self), '
        'interest-cohort=()'  # Disable FLoC
    )
    
    # Remove the Server header if possible
    response.headers['Server'] = ''
    
    # HTTP Strict Transport Security for HTTPS environments
    # Only add in production environments
    if os.environ.get('FLASK_ENV') == 'production':
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    
    return response

def require_https():
    """
    Middleware to require HTTPS in production.
    
    Should be used in app.before_request
    """
    # Only enforce in production
    if os.environ.get('FLASK_ENV') == 'production':
        if request.headers.get('X-Forwarded-Proto') == 'http':
            url = request.url.replace('http://', 'https://', 1)
            return Response(f"Redirecting to secure connection: {url}", 301, {'Location': url})
    
def limiter_handler(request, exception, *args, **kwargs):
    """
    Custom handler for rate limiting errors
    
    Args:
        request: Flask request object
        exception: The rate limit exception
        
    Returns:
        Flask response with error template
    """
    from flask import render_template, current_app
    
    # Log the rate limit event
    current_app.logger.warning(f"Rate limit exceeded: {request.remote_addr} - {request.path}")
    
    return render_template('error.html', 
                          code=429,
                          message="Rate limit exceeded. Please try again later."), 429
