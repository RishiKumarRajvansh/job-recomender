/**
 * Auth pages specific JavaScript
 * This script enhances the user experience on login/register/upload resume pages
 */
document.addEventListener('DOMContentLoaded', function() {
    // Add specific styling for auth form fields
    const authInputs = document.querySelectorAll('.auth-card input.form-control');
    if (authInputs.length > 0) {
        authInputs.forEach(input => {
            // Add focus effects
            input.addEventListener('focus', function() {
                this.parentElement.classList.add('input-focused');
            });
            
            input.addEventListener('blur', function() {
                this.parentElement.classList.remove('input-focused');
            });
        });
    }
    
    // Fix any navbar height inconsistencies
    const navbar = document.querySelector('.navbar');
    if (navbar) {
        // Force consistent height
        const navbarHeight = navbar.offsetHeight;
        document.documentElement.style.setProperty('--navbar-height', navbarHeight + 'px');
    }
});
