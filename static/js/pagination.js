// Handle pagination and filter controls for job listings
document.addEventListener('DOMContentLoaded', function() {
    // Job type filter functionality
    const jobTypeFilter = document.getElementById('jobTypeFilter');
    if (jobTypeFilter) {
        jobTypeFilter.addEventListener('change', function() {
            applyFiltersAndPagination();
        });
    }

    // Per page selector functionality
    const perPageSelector = document.getElementById('perPageSelector');
    if (perPageSelector) {
        perPageSelector.addEventListener('change', function() {
            applyFiltersAndPagination();
        });
    }

    // Function to apply filters and pagination
    function applyFiltersAndPagination() {
        const jobType = jobTypeFilter ? jobTypeFilter.value : 'All';
        const perPage = perPageSelector ? perPageSelector.value : '20';
        
        // Get current URL and parameters
        const url = new URL(window.location);
        
        // Update or set the job_type parameter
        url.searchParams.set('job_type', jobType);
        
        // Update or set the per_page parameter
        url.searchParams.set('per_page', perPage);
        
        // Reset to page 1 when changing filters
        url.searchParams.set('page', '1');
        
        // Navigate to the new URL
        window.location.href = url.toString();
    }
});
