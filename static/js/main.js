// Main JavaScript for Profiler Agentic Automation

// ============================================================================
// PROFESSIONAL TOAST NOTIFICATIONS
// ============================================================================

function showToast(message, type = 'info') {
    const toastContainer = document.getElementById('toast-container');
    if (!toastContainer) {
        console.warn('Toast container not found');
        return;
    }

    // Icon mapping
    const icons = {
        success: 'fa-check-circle',
        error: 'fa-exclamation-circle',
        warning: 'fa-exclamation-triangle',
        info: 'fa-info-circle'
    };

    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.innerHTML = `
        <i class="fas ${icons[type] || icons.info}"></i>
        <div class="toast-content">${escapeHtml(message)}</div>
    `;

    toastContainer.appendChild(toast);

    // Animate in
    setTimeout(() => {
        toast.style.opacity = '1';
        toast.style.transform = 'translateX(0)';
    }, 10);

    // Auto remove after 4 seconds
    const removeToast = () => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateX(400px)';
        setTimeout(() => {
            if (toast.parentNode) {
                toast.parentNode.removeChild(toast);
            }
        }, 300);
    };

    setTimeout(removeToast, 4000);

    // Click to dismiss
    toast.addEventListener('click', removeToast);
}

// ============================================================================
// UTILITY FUNCTIONS
// ============================================================================

// Escape HTML to prevent XSS
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Format file size
function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round((bytes / Math.pow(k, i)) * 100) / 100 + ' ' + sizes[i];
}

// Format date
function formatDate(dateString) {
    const date = new Date(dateString);
    const options = {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    };
    return date.toLocaleDateString('en-US', options);
}

// Format time ago
function timeAgo(dateString) {
    const date = new Date(dateString);
    const now = new Date();
    const seconds = Math.floor((now - date) / 1000);

    const intervals = {
        year: 31536000,
        month: 2592000,
        week: 604800,
        day: 86400,
        hour: 3600,
        minute: 60,
        second: 1
    };

    for (const [unit, secondsInUnit] of Object.entries(intervals)) {
        const interval = Math.floor(seconds / secondsInUnit);
        if (interval >= 1) {
            return interval + ' ' + unit + (interval === 1 ? '' : 's') + ' ago';
        }
    }

    return 'just now';
}

// Debounce function
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

// Copy to clipboard with visual feedback
function copyToClipboard(text, successMessage = 'Copied to clipboard!') {
    if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text).then(() => {
            showToast(successMessage, 'success');
        }).catch(err => {
            console.error('Failed to copy:', err);
            showToast('Failed to copy to clipboard', 'error');
        });
    } else {
        // Fallback for older browsers
        const textArea = document.createElement('textarea');
        textArea.value = text;
        textArea.style.position = 'fixed';
        textArea.style.left = '-9999px';
        document.body.appendChild(textArea);
        textArea.select();
        try {
            document.execCommand('copy');
            showToast(successMessage, 'success');
        } catch (err) {
            console.error('Failed to copy:', err);
            showToast('Failed to copy to clipboard', 'error');
        }
        document.body.removeChild(textArea);
    }
}

// ============================================================================
// LOADING STATES
// ============================================================================

function showLoading(elementId) {
    const element = document.getElementById(elementId);
    if (!element) return;

    element.innerHTML = `
        <div class="loading-spinner">
            <div class="spinner"></div>
            <p>Loading...</p>
        </div>
    `;
}

function hideLoading(elementId) {
    const element = document.getElementById(elementId);
    if (!element) return;
    element.innerHTML = '';
}

// ============================================================================
// SYSTEM HEALTH CHECK
// ============================================================================

function loadSystemStats() {
    fetch('/api/health')
        .then(response => {
            if (!response.ok) {
                throw new Error('Health check failed');
            }
            return response.json();
        })
        .then(data => {
            console.log('System health:', data);

            // Update stats if elements exist
            const docsStat = document.getElementById('stat-documents');
            const chunksStat = document.getElementById('stat-chunks');
            const modelStat = document.getElementById('stat-model');

            if (docsStat) {
                docsStat.textContent = (data.total_documents || 0).toLocaleString();
            }
            if (chunksStat) {
                chunksStat.textContent = (data.total_chunks || 0).toLocaleString();
            }
            if (modelStat) {
                const modelName = data.model || 'Unknown';
                const formattedModel = modelName.toUpperCase().replace(/-/g, ' ').replace(/\s+/g, ' ').trim();
                modelStat.textContent = formattedModel;
            }
        })
        .catch(error => {
            console.error('Error loading system stats:', error);

            // Set to default values on error
            const docsStat = document.getElementById('stat-documents');
            const chunksStat = document.getElementById('stat-chunks');
            const modelStat = document.getElementById('stat-model');

            if (docsStat) docsStat.textContent = '0';
            if (chunksStat) chunksStat.textContent = '0';
            if (modelStat) modelStat.textContent = 'Unavailable';
        });
}

// ============================================================================
// FORM VALIDATION
// ============================================================================

function validateForm(formId) {
    const form = document.getElementById(formId);
    if (!form) return false;

    const inputs = form.querySelectorAll('input[required], textarea[required], select[required]');
    let isValid = true;

    inputs.forEach(input => {
        if (!input.value.trim()) {
            isValid = false;
            input.classList.add('error');

            // Remove error class after interaction
            input.addEventListener('input', () => {
                input.classList.remove('error');
            }, { once: true });
        }
    });

    if (!isValid) {
        showToast('Please fill in all required fields', 'error');
    }

    return isValid;
}

// ============================================================================
// ANIMATION HELPERS
// ============================================================================

function animateCounter(elementId, targetValue, duration = 1000) {
    const element = document.getElementById(elementId);
    if (!element) return;

    const startValue = parseInt(element.textContent) || 0;
    const increment = (targetValue - startValue) / (duration / 16);
    let currentValue = startValue;

    const updateCounter = () => {
        currentValue += increment;
        if ((increment > 0 && currentValue >= targetValue) ||
            (increment < 0 && currentValue <= targetValue)) {
            element.textContent = targetValue.toLocaleString();
        } else {
            element.textContent = Math.floor(currentValue).toLocaleString();
            requestAnimationFrame(updateCounter);
        }
    };

    requestAnimationFrame(updateCounter);
}

// ============================================================================
// INITIALIZATION
// ============================================================================

document.addEventListener('DOMContentLoaded', function() {
    console.log('Profiler Agentic Automation - Professional UI loaded');

    // Load system stats if on home page
    if (window.location.pathname === '/' || window.location.pathname === '/index') {
        loadSystemStats();
    }

    // Add smooth scroll behavior
    document.documentElement.style.scrollBehavior = 'smooth';

    // Add keyboard shortcuts
    document.addEventListener('keydown', function(e) {
        // Ctrl/Cmd + K for search (if search exists)
        if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
            e.preventDefault();
            const searchInput = document.querySelector('input[type="search"]');
            if (searchInput) {
                searchInput.focus();
            }
        }
    });

    // Add form submission prevention for Enter key in single-line inputs
    const inputs = document.querySelectorAll('input:not([type="submit"]):not([type="button"])');
    inputs.forEach(input => {
        input.addEventListener('keypress', function(e) {
            if (e.key === 'Enter' && input.tagName === 'INPUT' && input.type !== 'textarea') {
                const form = input.closest('form');
                if (form && !form.querySelector('button[type="submit"]:focus')) {
                    e.preventDefault();
                }
            }
        });
    });
});

// ============================================================================
// ERROR HANDLING
// ============================================================================

// Global error handler
window.addEventListener('error', function(e) {
    console.error('Global error:', e.error);
    // Don't show toast for every error, only critical ones
});

// Handle unhandled promise rejections
window.addEventListener('unhandledrejection', function(e) {
    console.error('Unhandled promise rejection:', e.reason);
});

// ============================================================================
// EXPORT FOR USE IN OTHER SCRIPTS
// ============================================================================

window.AppUtils = {
    showToast,
    formatFileSize,
    formatDate,
    timeAgo,
    copyToClipboard,
    debounce,
    showLoading,
    hideLoading,
    validateForm,
    animateCounter,
    escapeHtml
};
