// main.js - Core JavaScript Functionality

// Initialize on document ready
$(document).ready(function() {
    console.log('WaterPoint AI System initialized successfully');
    
    // Initialize AOS animations if available
    if (typeof AOS !== 'undefined') {
        AOS.init({
            duration: 800,
            once: true,
            offset: 100,
            easing: 'ease-in-out'
        });
    }
    
    // Initialize tooltips
    initializeTooltips();
    
    // Initialize popovers
    initializePopovers();
    
    // Handle scroll events
    handleScroll();
    
    // Check for saved user preferences
    loadUserPreferences();
});

// ==================== Utility Functions ====================

/**
 * Format number with commas
 * @param {number} num - Number to format
 * @returns {string} Formatted number
 */
function formatNumber(num) {
    if (num === null || num === undefined) return '0';
    return num.toString().replace(/(\d)(?=(\d{3})+(?!\d))/g, '$1,');
}

/**
 * Format date to readable string
 * @param {Date|string} date - Date to format
 * @returns {string} Formatted date
 */
function formatDate(date) {
    const d = new Date(date);
    return d.toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    });
}

/**
 * Debounce function for performance optimization
 * @param {Function} func - Function to debounce
 * @param {number} wait - Wait time in milliseconds
 * @returns {Function} Debounced function
 */
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

/**
 * Throttle function for performance optimization
 * @param {Function} func - Function to throttle
 * @param {number} limit - Limit in milliseconds
 * @returns {Function} Throttled function
 */
function throttle(func, limit) {
    let inThrottle;
    return function(...args) {
        if (!inThrottle) {
            func.apply(this, args);
            inThrottle = true;
            setTimeout(() => inThrottle = false, limit);
        }
    };
}

// ==================== UI Functions ====================

/**
 * Initialize Bootstrap tooltips
 */
function initializeTooltips() {
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function(tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl, {
            animation: true,
            delay: { show: 100, hide: 50 }
        });
    });
}

/**
 * Initialize Bootstrap popovers
 */
function initializePopovers() {
    const popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
    popoverTriggerList.map(function(popoverTriggerEl) {
        return new bootstrap.Popover(popoverTriggerEl, {
            animation: true,
            html: true,
            sanitize: false
        });
    });
}

/**
 * Handle scroll events for navbar
 */
function handleScroll() {
    const navbar = document.getElementById('mainNav');
    if (!navbar) return;
    
    window.addEventListener('scroll', throttle(() => {
        if (window.scrollY > 50) {
            navbar.classList.add('scrolled');
        } else {
            navbar.classList.remove('scrolled');
        }
    }, 100));
}

/**
 * Load user preferences from localStorage
 */
function loadUserPreferences() {
    // Theme preference
    const theme = localStorage.getItem('theme') || 'dark';
    document.body.classList.toggle('light-theme', theme === 'light');
    
    // Map layer preference
    const lastLayer = localStorage.getItem('lastMapLayer');
    if (lastLayer && typeof setBaseLayer === 'function') {
        setBaseLayer(lastLayer);
    }
}

/**
 * Show loading spinner
 * @param {string} selector - Element selector to show spinner in
 */
function showLoading(selector) {
    const element = $(selector);
    if (!element.length) return;
    
    element.html(`
        <div class="spinner-container">
            <div class="spinner"></div>
            <p class="mt-3">Loading...</p>
        </div>
    `);
}

/**
 * Hide loading spinner
 * @param {string} selector - Element selector to hide spinner from
 */
function hideLoading(selector) {
    const element = $(selector);
    if (!element.length) return;
    
    element.find('.spinner-container').remove();
}

/**
 * Show notification toast
 * @param {string} message - Message to display
 * @param {string} type - Type of notification (success, error, warning, info)
 */
function showNotification(message, type = 'info') {
    const icons = {
        success: 'check-circle',
        error: 'exclamation-circle',
        warning: 'exclamation-triangle',
        info: 'info-circle'
    };
    
    const notification = $(`
        <div class="alert alert-${type} animate__animated animate__fadeInRight" role="alert">
            <i class="fas fa-${icons[type]} me-2"></i>
            ${message}
            <button type="button" class="btn-close btn-close-white" data-bs-dismiss="alert" aria-label="Close"></button>
        </div>
    `);
    
    $('.message-container').append(notification);
    
    // Auto dismiss after 5 seconds
    setTimeout(() => {
        notification.fadeOut(300, function() {
            $(this).remove();
        });
    }, 5000);
}

/**
 * Show confirmation dialog
 * @param {string} message - Confirmation message
 * @param {Function} onConfirm - Callback function on confirm
 * @param {Function} onCancel - Callback function on cancel
 */
function confirmAction(message, onConfirm, onCancel) {
    // Create modal dynamically
    const modalId = 'confirmModal_' + Date.now();
    const modal = $(`
        <div class="modal-overlay" id="${modalId}">
            <div class="modal-content">
                <div class="modal-header">
                    <h5 class="modal-title">Confirm Action</h5>
                    <button type="button" class="btn-close btn-close-white" onclick="closeModal('${modalId}')"></button>
                </div>
                <div class="modal-body">
                    <p>${message}</p>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-outline" onclick="closeModal('${modalId}')">Cancel</button>
                    <button type="button" class="btn btn-primary" onclick="confirmAndClose('${modalId}')">Confirm</button>
                </div>
            </div>
        </div>
    `);
    
    $('body').append(modal);
    
    // Store callback
    modal.data('onConfirm', onConfirm);
    modal.data('onCancel', onCancel);
}

/**
 * Close modal
 * @param {string} modalId - Modal ID
 */
function closeModal(modalId) {
    $(`#${modalId}`).fadeOut(300, function() {
        $(this).remove();
    });
}

/**
 * Confirm and close modal
 * @param {string} modalId - Modal ID
 */
function confirmAndClose(modalId) {
    const modal = $(`#${modalId}`);
    const onConfirm = modal.data('onConfirm');
    
    if (typeof onConfirm === 'function') {
        onConfirm();
    }
    
    closeModal(modalId);
}

// ==================== Data Functions ====================

/**
 * Copy text to clipboard
 * @param {string} text - Text to copy
 */
function copyToClipboard(text) {
    navigator.clipboard.writeText(text).then(function() {
        showNotification('Copied to clipboard!', 'success');
    }, function() {
        showNotification('Failed to copy!', 'error');
    });
}

/**
 * Export data as CSV
 * @param {Array} data - Array of objects to export
 * @param {string} filename - Output filename
 */
function exportToCSV(data, filename) {
    if (!data || !data.length) {
        showNotification('No data to export', 'warning');
        return;
    }
    
    // Get headers
    const headers = Object.keys(data[0]);
    
    // Create CSV rows
    const csvRows = [];
    csvRows.push(headers.join(','));
    
    for (const row of data) {
        const values = headers.map(header => {
            const value = row[header] || '';
            return typeof value === 'string' && value.includes(',') ? `"${value}"` : value;
        });
        csvRows.push(values.join(','));
    }
    
    const csv = csvRows.join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename.endsWith('.csv') ? filename : filename + '.csv';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    window.URL.revokeObjectURL(url);
    
    showNotification('Data exported successfully', 'success');
}

/**
 * Export data as JSON
 * @param {Object} data - Data to export
 * @param {string} filename - Output filename
 */
function exportToJSON(data, filename) {
    const json = JSON.stringify(data, null, 2);
    const blob = new Blob([json], { type: 'application/json' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename.endsWith('.json') ? filename : filename + '.json';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    window.URL.revokeObjectURL(url);
    
    showNotification('Data exported successfully', 'success');
}

/**
 * Import data from file
 * @param {File} file - File to import
 * @param {Function} callback - Callback with parsed data
 */
function importFromFile(file, callback) {
    const reader = new FileReader();
    
    reader.onload = function(e) {
        try {
            const extension = file.name.split('.').pop().toLowerCase();
            
            if (extension === 'json') {
                const data = JSON.parse(e.target.result);
                callback(null, data);
            } else if (extension === 'csv') {
                const lines = e.target.result.split('\n');
                const headers = lines[0].split(',');
                const data = [];
                
                for (let i = 1; i < lines.length; i++) {
                    if (!lines[i].trim()) continue;
                    
                    const values = lines[i].split(',');
                    const row = {};
                    
                    headers.forEach((header, index) => {
                        row[header.trim()] = values[index]?.trim() || '';
                    });
                    
                    data.push(row);
                }
                
                callback(null, data);
            } else {
                callback(new Error('Unsupported file format'));
            }
        } catch (error) {
            callback(error);
        }
    };
    
    reader.onerror = function() {
        callback(new Error('Error reading file'));
    };
    
    reader.readAsText(file);
}

// ==================== Chart Functions ====================

/**
 * Create a chart
 * @param {string} canvasId - Canvas element ID
 * @param {string} type - Chart type
 * @param {Object} data - Chart data
 * @param {Object} options - Chart options
 * @returns {Chart} Chart instance
 */
function createChart(canvasId, type, data, options = {}) {
    const ctx = document.getElementById(canvasId)?.getContext('2d');
    if (!ctx) return null;
    
    const defaultOptions = {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
            legend: {
                labels: {
                    color: 'rgba(255, 255, 255, 0.7)'
                }
            }
        },
        scales: {
            x: {
                grid: {
                    color: 'rgba(255, 255, 255, 0.1)'
                },
                ticks: {
                    color: 'rgba(255, 255, 255, 0.7)'
                }
            },
            y: {
                grid: {
                    color: 'rgba(255, 255, 255, 0.1)'
                },
                ticks: {
                    color: 'rgba(255, 255, 255, 0.7)'
                }
            }
        }
    };
    
    const chartOptions = { ...defaultOptions, ...options };
    
    return new Chart(ctx, {
        type: type,
        data: data,
        options: chartOptions
    });
}

// ==================== API Functions ====================

/**
 * Make API request with error handling
 * @param {string} url - API endpoint
 * @param {Object} options - Fetch options
 * @returns {Promise} API response
 */
async function apiRequest(url, options = {}) {
    const defaultOptions = {
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCookie('csrftoken')
        }
    };
    
    const fetchOptions = { ...defaultOptions, ...options };
    
    try {
        showLoading('#loadingSpinner');
        
        const response = await fetch(url, fetchOptions);
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.message || 'API request failed');
        }
        
        return data;
    } catch (error) {
        showNotification(error.message, 'error');
        throw error;
    } finally {
        hideLoading('#loadingSpinner');
    }
}

/**
 * Get CSRF token from cookies
 * @param {string} name - Cookie name
 * @returns {string} CSRF token
 */
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

// ==================== Map Functions ====================

/**
 * Calculate distance between two points in km
 * @param {number} lat1 - Latitude of first point
 * @param {number} lon1 - Longitude of first point
 * @param {number} lat2 - Latitude of second point
 * @param {number} lon2 - Longitude of second point
 * @returns {number} Distance in kilometers
 */
function calculateDistance(lat1, lon1, lat2, lon2) {
    const R = 6371; // Earth's radius in km
    const dLat = (lat2 - lat1) * Math.PI / 180;
    const dLon = (lon2 - lon1) * Math.PI / 180;
    const a = 
        Math.sin(dLat/2) * Math.sin(dLat/2) +
        Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) * 
        Math.sin(dLon/2) * Math.sin(dLon/2);
    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
    return R * c;
}

/**
 * Convert coordinates between different formats
 * @param {Array|Object} coords - Coordinates to convert
 * @param {string} fromFormat - Source format (latlng, lnglat, utm, etc.)
 * @param {string} toFormat - Target format
 * @returns {Object} Converted coordinates
 */
function convertCoordinates(coords, fromFormat, toFormat) {
    // Implementation depends on your needs
    // This is a placeholder
    return coords;
}

// Export functions for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        formatNumber,
        formatDate,
        debounce,
        throttle,
        showNotification,
        confirmAction,
        copyToClipboard,
        exportToCSV,
        exportToJSON,
        importFromFile,
        createChart,
        apiRequest,
        calculateDistance
    };
}