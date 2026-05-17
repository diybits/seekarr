/**
 * Seekarr - Utility Functions
 * Shared functions for use across the application
 */

const SeekarrUtils = {
    /**
     * Fetch with timeout using the global settings
     * @param {string} url - The URL to fetch
     * @param {Object} options - Fetch options
     * @returns {Promise} - Fetch promise with timeout handling
     */
    fetchWithTimeout: function(url, options = {}) {
        // Get the API timeout from global settings, default to 120 seconds if not set
        let apiTimeout = 120000; // Default 120 seconds in milliseconds
        
        // Try to get timeout from seekarrUI if available
        if (window.seekarrUI && window.seekarrUI.originalSettings && 
            window.seekarrUI.originalSettings.general && 
            window.seekarrUI.originalSettings.general.api_timeout) {
            apiTimeout = window.seekarrUI.originalSettings.general.api_timeout * 1000;
        }
        
        // Create abort controller for timeout
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), apiTimeout);
        
        // Merge options with signal from AbortController
        const fetchOptions = {
            ...options,
            signal: controller.signal
        };
        
        return fetch(url, fetchOptions)
            .then(response => {
                clearTimeout(timeoutId);
                return response;
            })
            .catch(error => {
                clearTimeout(timeoutId);
                // Customize the error if it was a timeout
                if (error.name === 'AbortError') {
                    throw new Error(`Request timeout after ${apiTimeout / 1000} seconds`);
                }
                throw error;
            });
    },
    
    /**
     * Get the global API timeout value in seconds
     * @returns {number} - API timeout in seconds
     */
    getApiTimeout: function() {
        // Default value
        let timeout = 120;
        
        // Try to get from global settings
        if (window.seekarrUI && window.seekarrUI.originalSettings && 
            window.seekarrUI.originalSettings.general && 
            window.seekarrUI.originalSettings.general.api_timeout) {
            timeout = window.seekarrUI.originalSettings.general.api_timeout;
        }
        
        return timeout;
    }
};

// If running in Node.js environment
if (typeof module !== 'undefined' && module.exports) {
    module.exports = SeekarrUtils;
}
