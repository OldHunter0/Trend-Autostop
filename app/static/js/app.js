/**
 * Trend-Autostop Frontend JavaScript
 */

// Toast Notifications
function showToast(message, type = 'success') {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;
    container.appendChild(toast);
    
    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateX(100%)';
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

// API Helper
async function apiCall(url, method = 'GET', data = null) {
    const options = {
        method,
        headers: {
            'Content-Type': 'application/json',
        },
    };
    
    if (data) {
        options.body = JSON.stringify(data);
    }
    
    const response = await fetch(url, options);
    
    if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: 'Request failed' }));
        throw new Error(error.detail || 'Request failed');
    }
    
    return response.json();
}

// Format number with precision
function formatNumber(num, precision = 4) {
    if (num === null || num === undefined) return '--';
    return Number(num).toFixed(precision);
}

// Format date
function formatDate(dateStr) {
    const date = new Date(dateStr);
    return date.toLocaleString('zh-CN', {
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit'
    });
}

// Auto refresh dashboard (every 30 seconds)
function setupAutoRefresh(interval = 30000) {
    if (window.location.pathname === '/') {
        setInterval(() => {
            fetch('/api/dashboard/stats')
                .then(res => res.json())
                .then(stats => {
                    // Update stats if elements exist
                    const elements = document.querySelectorAll('.stat-value');
                    // Could update specific elements here
                })
                .catch(console.error);
        }, interval);
    }
}

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    // Setup auto refresh on dashboard
    setupAutoRefresh();
    
    // Add loading states to forms
    document.querySelectorAll('form').forEach(form => {
        form.addEventListener('submit', function() {
            const btn = this.querySelector('button[type="submit"]');
            if (btn) {
                btn.disabled = true;
                const originalText = btn.innerHTML;
                btn.innerHTML = '<span class="loading">处理中...</span>';
                setTimeout(() => {
                    btn.disabled = false;
                    btn.innerHTML = originalText;
                }, 5000);
            }
        });
    });
});

// Export for global access
window.showToast = showToast;
window.apiCall = apiCall;
window.formatNumber = formatNumber;
window.formatDate = formatDate;

