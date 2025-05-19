/**
 * Navigation bar functionality script
 * This script ensures consistent navbar behavior across all pages
 */
document.addEventListener('DOMContentLoaded', function() {
    // Function to mark the current active page in the navbar
    function highlightCurrentPage() {
        // Get the current URL path
        const currentPath = window.location.pathname;
        
        // Handle special cases
        let pathToHighlight = currentPath;
        
        // Special case handling for specific pages
        // This ensures the correct navigation item is highlighted
        if (currentPath.includes('upload_resume')) {
            pathToHighlight = '/upload_resume';
        } else if (currentPath.includes('login')) {
            pathToHighlight = '/login';
        } else if (currentPath.includes('register')) {
            pathToHighlight = '/register';
        }
        
        // Find all nav links in the main navigation
        const navLinks = document.querySelectorAll('.navbar-nav .nav-link');
        
        // Process each link
        navLinks.forEach(link => {
            const href = link.getAttribute('href');
            
            // Skip empty hrefs
            if (!href) return;
            
            // Match exact path or paths that contain the href
            // (but avoid matching '/' with everything)
            if (href === pathToHighlight || 
                (href !== '/' && href.length > 1 && pathToHighlight.includes(href))) {
                link.classList.add('active');
                
                // Also add aria attributes for accessibility
                link.setAttribute('aria-current', 'page');
            } else {
                link.classList.remove('active');
                link.removeAttribute('aria-current');
            }
        });
    }
    
    // Initialize page highlighting
    highlightCurrentPage();
    
    // Handle navbar toggler for mobile views
    const navbarToggler = document.querySelector('.navbar-toggler');
    const navbarCollapse = document.querySelector('.navbar-collapse');
    
    if (navbarToggler && navbarCollapse) {
        navbarToggler.addEventListener('click', function() {
            navbarCollapse.classList.toggle('show');
        });
    }
    
    // Close mobile menu when a link is clicked
    const mobileNavLinks = document.querySelectorAll('.navbar-collapse .nav-link');
    mobileNavLinks.forEach(link => {
        link.addEventListener('click', function() {
            const navbar = document.querySelector('.navbar-collapse.show');
            if (navbar) {
                navbar.classList.remove('show');
            }
        });
    });
});
