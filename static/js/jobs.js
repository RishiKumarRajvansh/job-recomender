document.addEventListener('DOMContentLoaded', function() {
    const jobsContent = document.getElementById('jobs-content');
    const jobsContainer = document.getElementById('jobs-container');
    const searchProfileBtn = document.getElementById('search-profile-btn');
    const runScraper = document.getElementById('run-scraper-flag')?.value === 'true';
    const query = document.getElementById('query-value')?.value;
    const location = document.getElementById('location-value')?.value;
    
    // Always show loading at first when jobs page loads
    showLoading('Loading job listings...');

    // Handle profile search button loading state
    if (searchProfileBtn) {
        searchProfileBtn.addEventListener('click', function(e) {
            e.preventDefault();
            showLoading('Searching profile...');
            setTimeout(() => {
                window.location.href = searchProfileBtn.href;
            }, 100);
        });
    }

    // Function to show error message
    function showError(message) {
        if (jobsContainer) {
            jobsContainer.innerHTML = `
                <div class="col-12">
                    <div class="alert alert-danger">
                        <i class="bi bi-exclamation-triangle me-2"></i>
                        ${message}
                    </div>
                </div>
            `;
        }
    }

    // Check for loading status on page load
    if (runScraper) {
        showLoading('Finding relevant jobs for you...');
        pollRefreshStatus();
    } else {
        // Even if not explicitly scraping, check if anything is loading
        checkLoadingStatus();
    }    // Function to poll refresh status
    function pollRefreshStatus() {
        fetch('/check_refresh_status')
            .then(response => response.json())
            .then(data => {
                if (data.loading) {
                    // Still loading, poll again in 2 seconds
                    setTimeout(pollRefreshStatus, 2000);
                } else {
                    // Loading complete, reload the page
                    hideLoading();
                    window.location.reload();
                }
            })
            .catch(error => {
                console.error('Error checking refresh status:', error);
                hideLoading();
                showError('Error checking job status. Please try again.');
            });
    }
    
    // Function to check if anything is loading
    function checkLoadingStatus() {
        fetch('/check_refresh_status')
            .then(response => response.json())
            .then(data => {
                if (data.loading) {
                    // Something is loading, start polling
                    showLoading('Loading job data...');
                    pollRefreshStatus();
                } else {
                    // Nothing is loading, just hide the indicator
                    setTimeout(() => hideLoading(), 1000);
                }
            })
            .catch(error => {
                console.error('Error checking loading status:', error);
                // Hide loading after error
                hideLoading();
            });
    }

    // Quick filter buttons
    const filterMatchingBtn = document.getElementById('filter-matching');
    const filterRecentBtn = document.getElementById('filter-recent');
    const filterNearbyBtn = document.getElementById('filter-nearby');

    if (filterMatchingBtn) {
        filterMatchingBtn.addEventListener('click', function() {
            // Show only jobs with match percentage > 0
            const jobCards = document.querySelectorAll('.job-card');
            jobCards.forEach(card => {
                const matchPercent = card.getAttribute('data-match-percentage');
                card.closest('.col-md-6').style.display = matchPercent > 0 ? 'block' : 'none';
            });
        });
    }

    if (filterRecentBtn) {
        filterRecentBtn.addEventListener('click', function() {
            // Show all jobs, sorted by date
            const jobCards = Array.from(document.querySelectorAll('.job-card'));
            const jobsContainer = document.getElementById('jobs-container');
            jobCards
                .sort((a, b) => {
                    const dateA = new Date(a.getAttribute('data-date'));
                    const dateB = new Date(b.getAttribute('data-date'));
                    return dateB - dateA;
                })
                .forEach(card => {
                    card.closest('.col-md-6').style.display = 'block';
                    jobsContainer.appendChild(card.closest('.col-md-6'));
                });
        });
    }

    if (filterNearbyBtn) {
        filterNearbyBtn.addEventListener('click', function() {
            // Show only jobs with matching location
            const jobCards = document.querySelectorAll('.job-card');
            jobCards.forEach(card => {
                const jobLocation = card.getAttribute('data-location').toLowerCase();
                const currentLocation = location.toLowerCase();
                card.closest('.col-md-6').style.display = 
                    jobLocation.includes(currentLocation) || jobLocation.includes('remote') ? 'block' : 'none';
            });
        });
    }
});
