// Main JavaScript for RAG Test Case Generator

// Toast notifications
function showToast(message, type = 'info') {
    const toastContainer = document.getElementById('toast-container');
    if (!toastContainer) return;

    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.innerHTML = `
        <i class="fas fa-${type === 'success' ? 'check-circle' : type === 'error' ? 'exclamation-circle' : 'info-circle'}"></i>
        <span>${message}</span>
    `;

    toastContainer.appendChild(toast);

    // Auto remove after 3 seconds
    setTimeout(() => {
        toast.style.opacity = '0';
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

// Utility: Format file size
function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
}

// Utility: Format date
function formatDate(dateString) {
    const date = new Date(dateString);
    return date.toLocaleString();
}

// Check system health on load
document.addEventListener('DOMContentLoaded', function() {
    // Load system stats if on home page
    if (window.location.pathname === '/') {
        loadSystemStats();
    }
});

function loadSystemStats() {
    fetch('/api/health')
        .then(response => response.json())
        .then(data => {
            console.log('System health:', data);
            // Update stats if elements exist
            const docsStat = document.getElementById('stat-documents');
            const chunksStat = document.getElementById('stat-chunks');

            if (docsStat) docsStat.textContent = data.total_documents || 0;
            if (chunksStat) chunksStat.textContent = data.total_chunks || 0;
        })
        .catch(error => {
            console.error('Error loading stats:', error);
            // Set to 0 on error
            const docsStat = document.getElementById('stat-documents');
            const chunksStat = document.getElementById('stat-chunks');
            if (docsStat) docsStat.textContent = '0';
            if (chunksStat) chunksStat.textContent = '0';
        });
}
