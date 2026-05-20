/**
 * Seekarr - Utility Functions
 * Shared functions for use across the application
 */

const SeekarrUtils = {
    basePath: (function() {
        const meta = document.querySelector('meta[name="seekarr-base"]');
        return meta ? meta.content.replace(/\/$/, '') : '';
    })(),

    prependBase: function(url) {
        if (url && url.startsWith('/') && !url.startsWith('//')) {
            return this.basePath + url;
        }
        return url;
    },

    fetchWithTimeout: function(url, options = {}) {
        url = this.prependBase(url);
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
                if (response.status === 401) {
                    window.location.href = SeekarrUtils.basePath + '/login';
                }
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
    
    copyToClipboard: function(text) {
        if (navigator.clipboard && window.isSecureContext) {
            return navigator.clipboard.writeText(text);
        }
        // Fallback for HTTP non-localhost contexts (execCommand is deprecated but widely supported)
        const ta = document.createElement('textarea');
        ta.value = text;
        ta.style.cssText = 'position:fixed;opacity:0;pointer-events:none;';
        document.body.appendChild(ta);
        ta.focus();
        ta.select();
        try {
            document.execCommand('copy');
            document.body.removeChild(ta);
            return Promise.resolve();
        } catch (e) {
            document.body.removeChild(ta);
            return Promise.reject(e);
        }
    },

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

// Debug logger — silent in production; enable via browser console:
//   localStorage.setItem('seekarr_debug', 'true')  then reload
const seekarrLog = {
    _on: () => {
        try { return localStorage.getItem('seekarr_debug') === 'true'; }
        catch { return false; }
    },
    log:   function(...a) { if (this._on()) console.log(...a); },
    warn:  function(...a) { if (this._on()) console.warn(...a); },
    info:  function(...a) { if (this._on()) console.info(...a); },
    debug: function(...a) { if (this._on()) console.debug(...a); },
};
