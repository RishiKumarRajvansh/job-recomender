// Global loading indicator functions
let loadingOverlay;
let loadingMessage;

// Initialize these elements as soon as possible
document.addEventListener('DOMContentLoaded', function() {
    loadingOverlay = document.getElementById('loadingOverlay');
    loadingMessage = document.getElementById('loadingMessage');
    
    // Check if there was a loading state stored in sessionStorage
    const storedLoadingState = sessionStorage.getItem('loadingState');
    if (storedLoadingState) {
        const loadingState = JSON.parse(storedLoadingState);
        if (loadingState.isLoading) {
            showLoading(loadingState.message);
        }
        // Clear the stored state after using it
        sessionStorage.removeItem('loadingState');
    }
});

function showLoading(message = 'Loading...') {
    // Check if we're on an excluded page where loading shouldn't appear
    const currentUrl = window.location.pathname;
    const isExcludedPage = currentUrl === '/' || 
                          currentUrl === '/login' || 
                          currentUrl === '/register' || 
                          currentUrl.includes('/upload_resume');
    
    if (isExcludedPage) {
        // Don't show loading on these pages
        sessionStorage.removeItem('loadingState');
        return;
    }
    
    // Store loading state in case we navigate before DOM is ready
    sessionStorage.setItem('loadingState', JSON.stringify({
        isLoading: true,
        message: message
    }));
    
    if (loadingOverlay && loadingMessage) {
        loadingMessage.textContent = message;
        loadingOverlay.style.display = 'flex';
    } else {
        // If DOM is not ready, the DOMContentLoaded event will handle it
        console.log("Loading overlay elements not yet available");
    }
}

function hideLoading() {
    // Clear the stored loading state
    sessionStorage.removeItem('loadingState');
    
    if (loadingOverlay) {
        loadingOverlay.style.display = 'none';
    }
}

// Add loading indicators for various actions
document.addEventListener('DOMContentLoaded', function() {
    // Show loading on specific pages based on URL/content
    const currentUrl = window.location.pathname;
    
    // Skip loading indicator for login, register, index and upload_resume pages
    if (currentUrl === '/' || 
        currentUrl === '/login' || 
        currentUrl === '/register' || 
        currentUrl.includes('/upload_resume')) {
        // Don't show loading for these pages
        hideLoading();
        return;
    }
    
    // Show loading for jobs list page - allow time to load data
    if (currentUrl.includes('/list_all_jobs') || currentUrl.includes('/jobs')) {
        showLoading('Loading job listings...');
        // Hide after 5 seconds or when page is fully loaded, whichever comes first
        const timer = setTimeout(() => hideLoading(), 5000);
        window.addEventListener('load', function() {
            clearTimeout(timer);
            hideLoading();
        });
    }
    
    // Show loading for dashboard page when needed
    if (currentUrl.includes('/dashboard')) {
        // Only show if we have parameters that suggest data loading
        const needsDataLoad = document.documentElement.innerHTML.includes('Loading') || 
                             document.documentElement.innerHTML.includes('no-job-matches');
        if (needsDataLoad) {
            showLoading('Loading dashboard data...');
            // Hide after 5 seconds or when page is fully loaded
            const timer = setTimeout(() => hideLoading(), 5000);
            window.addEventListener('load', function() {
                clearTimeout(timer);
                hideLoading();
            });
        }
    }
    
    // Show loading for course recommendations page
    if (currentUrl.includes('/course_recommendations')) {
        showLoading('Loading course recommendations...');
        // Hide after 5 seconds or when page is fully loaded, whichever comes first
        const timer = setTimeout(() => hideLoading(), 5000);
        window.addEventListener('load', function() {
            clearTimeout(timer);
            hideLoading();
        });
    }
    
    // Show loading for insights page
    if (currentUrl.includes('/insights')) {
        showLoading('Analyzing job market data...');
        // Hide after 5 seconds or when page is fully loaded, whichever comes first
        const timer = setTimeout(() => hideLoading(), 5000);
        window.addEventListener('load', function() {
            clearTimeout(timer);
            hideLoading();
        });
    }

    // Job search form
    const searchForm = document.getElementById('job-search-form');
    if (searchForm) {
        searchForm.addEventListener('submit', function() {
            showLoading('Finding relevant jobs...');
        });
    }

    // Resume upload form - fix the ID to match the actual form ID
    const resumeForm = document.getElementById('resumeUploadForm');
    if (resumeForm) {
        // Remove any existing event listeners first
        const newResumeForm = resumeForm.cloneNode(true);
        resumeForm.parentNode.replaceChild(newResumeForm, resumeForm);
        
        // Now add the correct event listener that only shows loading on actual submit
        newResumeForm.addEventListener('submit', function(e) {
            // Only show loading if the form is actually being submitted with a file
            const fileInput = this.querySelector('input[type="file"]');
            if (fileInput && fileInput.files && fileInput.files.length > 0) {
                showLoading('Analyzing resume...');
            } else {
                // Prevent submission if no file selected
                e.preventDefault();
                alert('Please select a resume file to upload.');
            }
        });
    }

    // Show loading on all form submits unless explicitly disabled
    document.addEventListener('submit', function(e) {
        const form = e.target;
        // Don't show loading for forms with data-no-loading attribute
        // Also don't show loading for login, register and resume forms
        const isLoginForm = form.id === 'login-form' || form.action.includes('/login');
        const isRegisterForm = form.id === 'register-form' || form.action.includes('/register');
        // Check if this is the resume upload form
        const isResumeForm = form.id === 'resumeUploadForm' || form.action.includes('/upload_resume');
        
        if (!form.hasAttribute('data-no-loading') && !isLoginForm && !isRegisterForm && !isResumeForm) {
            showLoading('Processing your request...');
        }
    });

    // Show loading when clicking links with specific classes
    document.addEventListener('click', function(e) {
        // Find if the click was on an element with a specific class or its descendant
        const target = e.target.closest('.loading-trigger');
        if (target && !target.hasAttribute('data-no-loading')) {
            showLoading('Loading...');
        }
    });

    // Make sure loading state is saved when navigating away
    window.addEventListener('beforeunload', function() {
        // Don't persist loading state when navigating from login, register, index or upload_resume pages
        const isExcludedPage = currentUrl === '/' || 
                              currentUrl === '/login' || 
                              currentUrl === '/register' || 
                              currentUrl.includes('/upload_resume');
        
        if (loadingOverlay && loadingOverlay.style.display === 'flex' && !isExcludedPage) {
            // Save current loading state before navigation
            const message = loadingMessage ? loadingMessage.textContent : 'Loading...';
            sessionStorage.setItem('loadingState', JSON.stringify({
                isLoading: true,
                message: message
            }));
        } else {
            // Clear any existing loading state
            sessionStorage.removeItem('loadingState');
        }
    });
});
