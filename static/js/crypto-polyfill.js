/**
 * crypto.randomUUID polyfill for older browsers
 * This polyfill provides a fallback implementation when crypto.randomUUID is not available
 */
(function() {
    'use strict';
    
    // Check if crypto.randomUUID is available
    if (typeof crypto !== 'undefined' && !crypto.randomUUID) {
        // Polyfill implementation
        crypto.randomUUID = function() {
            // UUID v4 format: xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx
            return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
                const r = Math.random() * 16 | 0;
                const v = c === 'x' ? r : (r & 0x3 | 0x8);
                return v.toString(16);
            });
        };
        
        console.log('[Polyfill] crypto.randomUUID polyfill loaded');
    } else if (typeof crypto !== 'undefined' && crypto.randomUUID) {
        console.log('[Info] crypto.randomUUID is natively supported');
    }
})();

