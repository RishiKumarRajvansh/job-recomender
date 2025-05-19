// JavaScript for equalizing course card heights and styling empty states

document.addEventListener('DOMContentLoaded', function() {
    // Set up click handlers for skill badges
    setupSkillBadgeClickHandlers();
    
    // Function to equalize card heights
    function equalizeCardHeights() {
        // First, handle the skill sections (each contains multiple course cards)
        const skillSections = document.querySelectorAll('.course-recommendations .card');
        
        // Reset all heights to auto first to get natural sizes
        document.querySelectorAll('.card-body').forEach(cardBody => {
            cardBody.style.height = 'auto';
        });
        
        // Equalize card bodies within each section
        skillSections.forEach(section => {
            // Get all the course cards within this section
            const courseCards = section.querySelectorAll('.card-body .card');
            const courseCardBodies = section.querySelectorAll('.card-body .card .card-body');
            
            // Also check for the empty state card in this section
            const emptyCard = section.querySelector('.empty-course-card');
            
            let maxHeight = 0;
            
            // Get max height from course cards
            courseCardBodies.forEach(cardBody => {
                if (cardBody.scrollHeight > maxHeight) {
                    maxHeight = cardBody.scrollHeight;
                }
            });
            
            // Apply max height to all course card bodies in this section
            if (maxHeight > 0 && maxHeight < 300) { // Reasonable max height limit
                courseCardBodies.forEach(cardBody => {
                    cardBody.style.height = `${maxHeight}px`;
                });
                
                // Also apply to empty card if it exists in this section
                if (emptyCard) {
                    const emptyCardBody = emptyCard.querySelector('.card-body');
                    if (emptyCardBody) {
                        emptyCardBody.style.height = `${maxHeight}px`;
                    }
                }
            }
        });
          // Style empty state messages
        styleEmptyStates();
        
        // Global equalization of empty cards across all sections
        const allEmptyCards = document.querySelectorAll('.empty-course-card');
        if (allEmptyCards.length > 1) {
            // Get the tallest empty card
            let tallestEmptyCardHeight = 0;
            allEmptyCards.forEach(card => {
                if (card.offsetHeight > tallestEmptyCardHeight) {
                    tallestEmptyCardHeight = card.offsetHeight;
                }
            });
            
            // Apply the same height to all empty cards
            if (tallestEmptyCardHeight > 0) {
                allEmptyCards.forEach(card => {
                    card.style.height = `${tallestEmptyCardHeight}px`;
                });
            }
        }
    }
    
    // Function to style empty states
    function styleEmptyStates() {
        // Style the skill category "No courses available" messages
        const emptySkillSections = document.querySelectorAll('.empty-skill-category');
        
        // Apply consistent styling to empty skill categories
        emptySkillSections.forEach(section => {
            // Add shadow and border styling
            section.classList.add('shadow-sm');
            
            // Ensure consistent height with course cards
            const nearestCourseCard = document.querySelector('.course-recommendations .card');
            if (nearestCourseCard) {
                // Match the height of the nearest course card
                const courseCardHeight = nearestCourseCard.offsetHeight;
                section.style.minHeight = courseCardHeight + 'px';
            }
        });
        
        // Make sure all empty course cards are the same height
        const emptyCards = document.querySelectorAll('.empty-course-card');
        let maxEmptyCardHeight = 0;
        
        emptyCards.forEach(card => {
            if (card.offsetHeight > maxEmptyCardHeight) {
                maxEmptyCardHeight = card.offsetHeight;
            }
        });
        
        if (maxEmptyCardHeight > 0) {
            emptyCards.forEach(card => {
                card.style.height = `${maxEmptyCardHeight}px`;
            });
        }
    }
    
    // Apply consistent styling to all skill categories
    function applyConsistentStyling() {
        // Get all skill category badges
        const skillBadges = document.querySelectorAll('.card-header .badge');
        
        // Add animation to badges
        skillBadges.forEach(badge => {
            badge.classList.add('badge-animated');
        });
        
        // Add hover effect to course cards
        const courseCards = document.querySelectorAll('.card-body .card:not(.empty-course-card)');
        courseCards.forEach(card => {
            card.classList.add('course-card-hover');
        });
        
        // Add matching hover effect to empty cards
        const emptyCards = document.querySelectorAll('.empty-course-card');
        emptyCards.forEach(card => {
            card.classList.add('course-card-hover');
        });
    }
      // Function to setup click handlers for skill badges
    function setupSkillBadgeClickHandlers() {
        // Get all skill badge links
        const skillBadgeLinks = document.querySelectorAll('.card-body a[href^="#skill-"]');
        
        // Add click event handler to each badge
        skillBadgeLinks.forEach(link => {
            link.addEventListener('click', function(event) {
                // Prevent default anchor behavior
                event.preventDefault();
                
                // Get the target section id from the href
                const targetId = this.getAttribute('href');
                const targetSection = document.querySelector(targetId);
                  if (targetSection) {
                    // Get the y position of the target section accounting for header height
                    const headerOffset = 80; // Adjust this value based on your header height
                    const elementPosition = targetSection.getBoundingClientRect().top;
                    const offsetPosition = elementPosition + window.pageYOffset - headerOffset;
                    
                    // Scroll to the adjusted position
                    window.scrollTo({
                        top: offsetPosition,
                        behavior: 'smooth'
                    });
                    
                    // Add a highlight effect to draw attention
                    targetSection.classList.add('highlight-section');
                    
                    // Remove the highlight after a short delay
                    setTimeout(() => {
                        targetSection.classList.remove('highlight-section');
                    }, 2000);
                }
            });
        });
    }
    
    // Run all styling functions on page load
    equalizeCardHeights();
    applyConsistentStyling();
    setupSkillBadgeClickHandlers();
    
    // Reapply on window resize
    window.addEventListener('resize', equalizeCardHeights);
});
