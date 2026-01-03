// Public Dashboard - Standalone version

// Global scrolling fix function for public dashboard
function fixPublicDashboardScrolling() {
    // More aggressive approach to fix scrolling
    const applyScrollingFix = () => {
        // Find all relevant containers for public dashboard
        const dashboardContent = document.querySelector('.dashboard-content');
        const dashboardContainer = document.getElementById('dashboard-content');
        const verticalsDashboard = document.querySelector('.verticals-dashboard');
        const body = document.body;
        const html = document.documentElement;
        
        if (dashboardContent) {
            // Force scrolling on dashboard content
            dashboardContent.style.setProperty('overflow-y', 'auto', 'important');
            dashboardContent.style.setProperty('height', 'auto', 'important');
            dashboardContent.style.setProperty('min-height', '100%', 'important');
            dashboardContent.style.setProperty('max-height', 'none', 'important');
            dashboardContent.classList.add('public_dashboard_scrollable');
        }
        
        if (dashboardContainer) {
            // Allow dashboard container to expand
            dashboardContainer.style.setProperty('overflow-y', 'auto', 'important');
            dashboardContainer.style.setProperty('height', 'auto', 'important');
            dashboardContainer.style.setProperty('max-height', 'none', 'important');
        }
        
        if (verticalsDashboard) {
            // Ensure verticals dashboard allows scrolling
            verticalsDashboard.style.setProperty('overflow-y', 'auto', 'important');
            verticalsDashboard.style.setProperty('height', 'auto', 'important');
            verticalsDashboard.style.setProperty('min-height', '100vh', 'important');
        }
        
        // Ensure body and html allow scrolling
        if (body) {
            body.style.setProperty('overflow-y', 'auto', 'important');
            body.style.setProperty('height', 'auto', 'important');
        }
        
        if (html) {
            html.style.setProperty('overflow-y', 'auto', 'important');
            html.style.setProperty('height', 'auto', 'important');
        }
    };
    
    // Apply immediately
    applyScrollingFix();
    
    // Apply after delays to catch different render phases
    setTimeout(applyScrollingFix, 100);
    setTimeout(applyScrollingFix, 500);
    setTimeout(applyScrollingFix, 1000);
    
    // Use MutationObserver to watch for style changes and reapply
    const observer = new MutationObserver((mutations) => {
        let shouldReapply = false;
        mutations.forEach((mutation) => {
            if (mutation.type === 'attributes' && mutation.attributeName === 'style') {
                shouldReapply = true;
            }
        });
        if (shouldReapply) {
            setTimeout(applyScrollingFix, 50);
        }
    });
    
    // Observe the dashboard content container
    const dashboardContent = document.querySelector('.dashboard-content');
    if (dashboardContent) {
        observer.observe(dashboardContent, {
            attributes: true,
            attributeFilter: ['style', 'class']
        });
    }
    
    // Also observe dashboard container
    const dashboardContainer = document.getElementById('dashboard-content');
    if (dashboardContainer) {
        observer.observe(dashboardContainer, {
            attributes: true,
            attributeFilter: ['style', 'class']
        });
    }
    
    return observer;
}

// Global observer instance
let globalPublicDashboardObserver = null;

// Define global functions OUTSIDE IIFE so they're available immediately
window.openScoreClickHandler = function(scoreId, scoreName) {
    console.log('=== openScoreClickHandler CALLED ===', scoreId, scoreName);
    try {
        if (!scoreId) {
            console.error('Score ID is missing');
            alert('Error: Score ID is missing');
            return;
        }
        
        // Get current filter (will be set by the dashboard script)
        const filterType = window.currentFilter || 'MTD';
        
        // Build URL using URL constructor for proper URL handling
        const params = new URLSearchParams({
            scoreId: scoreId,
            scoreName: scoreName || 'Score',
            filterType: filterType
        });
        
        // Build absolute URL and attach query string
        const url = new URL('/bizdom/score/dashboard', window.location.origin);
        url.search = params.toString();
        
        // Navigate
        console.log('Navigating to:', url.toString());
        window.location.href = url.toString();
    } catch (error) {
        console.error('Error in openScoreClickHandler:', error);
        alert('Error opening score dashboard: ' + error.message);
    }
};

window.testKpiClick = function() {
    console.log('testKpiClick is available!');
    alert('KPI click function is available!');
};

// Test function to manually trigger navigation
window.testNavigation = function(scoreId, scoreName) {
    console.log('Testing navigation with:', scoreId, scoreName);
    if (window.openScoreClickHandler) {
        window.openScoreClickHandler(scoreId || 1, scoreName || 'Test Score');
    } else {
        alert('openScoreClickHandler not available!');
    }
};

// Debug function to check if event listener is attached
window.checkEventListeners = function() {
    const dashboardContent = document.querySelector('.dashboard-content');
    if (dashboardContent) {
        console.log('dashboard-content element found:', dashboardContent);
        const kpiCircles = dashboardContent.querySelectorAll('.kpi-circle');
        console.log('Number of KPI circles found:', kpiCircles.length);
        kpiCircles.forEach((circle, index) => {
            console.log(`KPI ${index + 1}:`, {
                scoreId: circle.dataset.scoreId,
                scoreName: circle.dataset.scoreName,
                element: circle
            });
        });
    } else {
        console.error('dashboard-content element NOT found!');
    }
};

(function() {
    'use strict';
    
    const API_BASE = '/api/dashboard';
    let currentFilter = 'MTD';
    let dashboardData = null;
    let jwtToken = null;
    // Store custom date range in YYYY-MM-DD (input[type="date"]) format
    let customRange = { start: '', end: '' };
    
    // Expose currentFilter to window so openScoreClickHandler can access it
    window.currentFilter = currentFilter;
    
    // Immediately check for token on script load (before DOM ready)
    // This prevents any accidental API calls
    function getStoredToken() {
        const token = localStorage.getItem('jwt_token');
        // Only return valid non-empty strings
        if (token && typeof token === 'string' && token.trim() !== '' && token !== 'null' && token !== 'undefined') {
            return token;
        }
        // Clean up invalid token
        if (token) {
            localStorage.removeItem('jwt_token');
        }
        return null;
    }
    
    // Set initial token state
    jwtToken = getStoredToken();

    // Login function
    async function login(username, password) {
        try{
            console.log('Attempting login...');
            const response = await fetch('/api/login', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ username, password }),
            });
            
            // Check if response is ok
            if (!response.ok) {
                const errorText = await response.text();
                console.error('Login response error:', response.status, errorText);
                let errorData;
                try {
                    errorData = JSON.parse(errorText);
                } catch {
                    errorData = { message: `Server error: ${response.status}` };
                }
                return { success: false, message: errorData.message || 'Login failed' };
            }
            
            const data = await response.json();
            console.log('Login response:', data);
            
            if(data.statusCode === 200 && data.token){
                jwtToken = data.token;
                localStorage.setItem('jwt_token', data.token);
                localStorage.setItem('uid', data.uid);
                console.log('Login successful, token stored');
                return { success: true, message: 'Login successful' };
            }else{
                return { success: false, message: data.message || 'Failed to login' }; 
            }
        }
        catch(error){
            console.error('Login network error:', error);
            // Check if it's a network error
            if (error.message && error.message.includes('NetworkError') || error.message.includes('Failed to fetch')) {
                return { success: false, message: 'Cannot connect to server. Please check if the server is running and try again.' };
            }
            return { success: false, message: error.message || 'Login failed. Please try again.' };
        }
    }

    //Check if user is logged in
    function isLoggedIn(){
        const token = getStoredToken();
        if(token){
            jwtToken = token;
            return true;
        }
        return false;
    }

    //Logout function
    function logout(){
        jwtToken = null;
        localStorage.removeItem('jwt_token');
        localStorage.removeItem('uid');
        showLoginPage();
    }
    
    // Utility functions
    function getDateRange(filter) {
        const today = new Date();
        let startDate, endDate, label;
        
        switch(filter) {
            case 'Today':
                startDate = new Date(today);
                startDate.setHours(0, 0, 0, 0);
                endDate = new Date(today);
                endDate.setHours(23, 59, 59, 999);
                label = `Today: ${formatDate(startDate)} - ${formatDate(endDate)}`;
                break;
            case 'WTD':
                // JavaScript getDay(): 0=Sunday, 1=Monday, ..., 6=Saturday
                // Python weekday(): 0=Monday, 1=Tuesday, ..., 6=Sunday
                // To convert JS getDay() to Python weekday():
                //   Sunday (0) -> 6, Monday (1) -> 0, Tuesday (2) -> 1, etc.
                // Formula: python_weekday = (js_getDay + 6) % 7
                const dayOfWeek = today.getDay();
                const pythonWeekday = (dayOfWeek + 6) % 7; // Convert JS day to Python weekday
                
                // Backend uses: week_start = today - timedelta(days=today.weekday())
                // So we subtract pythonWeekday days
                startDate = new Date(today);
                startDate.setDate(today.getDate() - pythonWeekday);
                startDate.setHours(0, 0, 0, 0);
                endDate = new Date(today);
                endDate.setHours(23, 59, 59, 999);
                label = `Week to Date: ${formatDate(startDate)} - ${formatDate(endDate)}`;
                break;
            case 'YTD':
                startDate = new Date(today.getFullYear(), 0, 1);
                startDate.setHours(0, 0, 0, 0);
                endDate = new Date(today);
                endDate.setHours(23, 59, 59, 999);
                label = `Year to Date: ${formatDate(startDate)} - ${formatDate(endDate)}`;
                break;
            case 'Custom': {
                // Custom range relies on customRange (YYYY-MM-DD)
                if (!customRange.start || !customRange.end) {
                    return null;
                }
                startDate = new Date(customRange.start);
                endDate = new Date(customRange.end);
                if (!startDate || isNaN(startDate.getTime()) || !endDate || isNaN(endDate.getTime())) {
                    return null;
                }
                if (startDate > endDate) {
                    return null;
                }
                label = `Custom: ${formatDate(startDate)} - ${formatDate(endDate)}`;
                break;
            }
            case 'MTD':
            default:
                startDate = new Date(today.getFullYear(), today.getMonth(), 1);
                startDate.setHours(0, 0, 0, 0);
                endDate = new Date(today);
                endDate.setHours(23, 59, 59, 999);
                label = `Month to Date: ${formatDate(startDate)} - ${formatDate(endDate)}`;
                break;
        }
        
        return {
            startDate: formatDateForAPI(startDate),
            endDate: formatDateForAPI(endDate),
            label: label
        };
    }
    
    function formatDate(date) {
        // Format as D M Y (Day Month Year)
        if (!date || isNaN(date.getTime())) {
            return "";
        }
        const day = date.getDate();
        const monthNames = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", 
                           "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
        const month = monthNames[date.getMonth()];
        const year = date.getFullYear();
        return `${day} ${month} ${year}`;
    }
    
    function formatDateForAPI(date) {
        const day = String(date.getDate()).padStart(2, '0');
        const month = String(date.getMonth() + 1).padStart(2, '0');
        const year = date.getFullYear();
        return `${day}-${month}-${year}`;
    }
    
    function getPillarColor(pillarName) {
        const colorMap = {
            'Operations': '#667eea',
            'Sales and Marketing': '#f093fb',
            'Finance': '#4facfe',
            'Human Resources': '#43e97b',
            'Technology': '#fa709a',
            'Customer Service': '#30cfd0',
        };
        return colorMap[pillarName] || '#a8b5d1';
    }
    
    function getScoreIcon(scoreName) {
        // Normalize score name: trim whitespace and handle case-insensitive matching
        const normalizedName = (scoreName || '').trim();
        
        // Map of score names to icon classes - includes variations
        // Using Font Awesome 6 syntax: fas = solid, far = regular, fal = light
        const iconMap = {
            'Labour': 'fas fa-hard-hat',
            'Customer Satisfaction': 'fas fa-thumbs-up',  // Thumbs up for satisfaction
            'TAT': 'fas fa-clock',
             'Leads': 'fas fa-handshake',
            'Revenue': 'fas fa-money-bill-wave',
            'Productivity': 'fas fa-tachometer-alt',
            'Quality': 'fas fa-award',
            'Efficiency': 'fas fa-bolt',
        };
        
        // Try exact match first
        if (iconMap[normalizedName]) {
            console.log(`Icon match (exact): "${scoreName}" -> "${normalizedName}" -> "${iconMap[normalizedName]}"`);
            return iconMap[normalizedName];
        }
        
        // Try case-insensitive match
        const lowerName = normalizedName.toLowerCase();
        for (const [key, value] of Object.entries(iconMap)) {
            if (key.toLowerCase() === lowerName) {
                console.log(`Icon match (case-insensitive): "${scoreName}" -> "${key}" -> "${value}"`);
                return value;
            }
        }
        
        // Try partial match (e.g., "Leads" matches "Lead")
        for (const [key, value] of Object.entries(iconMap)) {
            if (lowerName.includes(key.toLowerCase()) || key.toLowerCase().includes(lowerName)) {
                console.log(`Icon match (partial): "${scoreName}" -> "${key}" -> "${value}"`);
                return value;
            }
        }
        
        // Debug: log if no match found - show all available keys for comparison
        console.warn(`No icon found for score name: "${scoreName}" (normalized: "${normalizedName}")`);
        console.log('Available icon keys:', Object.keys(iconMap));
        console.log('Normalized name char codes:', normalizedName.split('').map(c => `${c}(${c.charCodeAt(0)})`).join(' '));
        
        // Always return a valid icon class - never return empty string
        // Using Font Awesome 6 syntax
        return 'fas fa-chart-bar';
    }
    
    // Function to get icon-specific styles (sharpness, contrast, etc.)
    function getIconStyle(scoreName) {
        // Normalize score name: trim whitespace and handle case-insensitive matching
        const normalizedName = (scoreName || '').trim();
        
        const styleMap = {
            'Labour': {
                filter: 'contrast(1.2) brightness(1.1) saturate(1.2)',
                textShadow: '0 1px 3px rgba(0,0,0,0.3)',
                fontWeight: '600'
            },
            'Customer Satisfaction': {
                filter: 'contrast(1.15) brightness(1.05)',
                textShadow: '0 1px 2px rgba(0,0,0,0.2)',
                fontWeight: '500'
            },
            'TAT': {
                filter: 'contrast(1.3) brightness(1.15) saturate(1.3)',
                textShadow: '0 0 2px rgba(255,255,255,0.5), 0 1px 3px rgba(0,0,0,0.3)',
                fontWeight: '600'
            },
            'Leads': {
                filter: 'contrast(1.1) brightness(1.08)',
                textShadow: '0 1px 2px rgba(0,0,0,0.25)',
                fontWeight: '500'
            },
            'Revenue': {
                filter: 'contrast(1.25) brightness(1.12) saturate(1.25)',
                textShadow: '0 1px 3px rgba(0,0,0,0.3)',
                fontWeight: '600'
            },
            'Productivity': {
                filter: 'contrast(1.2) brightness(1.1)',
                textShadow: '0 1px 2px rgba(0,0,0,0.2)',
                fontWeight: '500'
            },
            'Quality': {
                filter: 'contrast(1.3) brightness(1.2) saturate(1.4)',
                textShadow: '0 0 3px rgba(255,255,255,0.6), 0 2px 4px rgba(0,0,0,0.4)',
                fontWeight: '700'
            },
            'Efficiency': {
                filter: 'contrast(1.25) brightness(1.15) saturate(1.3)',
                textShadow: '0 1px 3px rgba(0,0,0,0.3)',
                fontWeight: '600'
            }
        };
        
        // Try exact match first
        let style = styleMap[normalizedName];
        
        // Try case-insensitive match if exact match failed
        if (!style) {
            const lowerName = normalizedName.toLowerCase();
            for (const [key, value] of Object.entries(styleMap)) {
                if (key.toLowerCase() === lowerName) {
                    style = value;
                    break;
                }
            }
        }
        
        // Default style if no match
        if (!style) {
            style = {
                filter: 'contrast(1.1) brightness(1.05)',
                textShadow: '0 1px 2px rgba(0,0,0,0.2)',
                fontWeight: '500'
            };
        }
        
        // Convert object to CSS string
        return `filter: ${style.filter}; text-shadow: ${style.textShadow}; font-weight: ${style.fontWeight};`;
    }
    
    function getScoreColor(scoreName) {
        // Normalize score name: trim whitespace and handle case-insensitive matching
        const normalizedName = (scoreName || '').trim();
        
        const colorMap = {
            'Labour': '#ff6b6b',
            'Customer Satisfaction': '#4ecdc4',
            'TAT': '#ffe66d',
            'Leads': '#95e1d3',
            'Revenue': '#f38181',
            'Productivity': '#a8e6cf',
            'Quality': '#ffd93d',
            'Efficiency': '#6bcf7f',
        };
        
        // Try exact match first
        if (colorMap[normalizedName]) {
            return colorMap[normalizedName];
        }
        
        // Try case-insensitive match
        const lowerName = normalizedName.toLowerCase();
        for (const [key, value] of Object.entries(colorMap)) {
            if (key.toLowerCase() === lowerName) {
                return value;
            }
        }
        
        return '#95a5a6';
    }

    // Show login page
    function showLoginPage() {
        console.log('Showing login page...');
        const container = document.getElementById('dashboard-content');
        const loadingEl = document.getElementById('loading-indicator');
        
        if (loadingEl) {
            loadingEl.style.display = 'none';
        }
        
        if (!container) {
            console.error('Dashboard content container not found!');
            return;
        }
        
        container.style.display = 'block';
        container.innerHTML = `
        <div style="min-height: 100vh; display: flex; justify-content: center; align-items: center; background: #f5f7fa;">
            <div style="background: white; padding: 2rem; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.1); max-width: 400px; width: 100%;">
                <h2 style="text-align: center; margin-bottom: 1.5rem; color: #212529;">BIZDOM Login</h2>
                <form id="login-form" onsubmit="handleLogin(event)">
                    <div style="margin-bottom: 1rem;">
                        <label style="display: block; margin-bottom: 0.5rem; color: #495057; font-weight: 500;">Username</label>
                        <input type="text" id="username" required 
                               style="width: 100%; padding: 0.75rem; border: 1px solid #e9ecef; border-radius: 6px; font-size: 1rem;">
                    </div>
                    <div style="margin-bottom: 1.5rem;">
                        <label style="display: block; margin-bottom: 0.5rem; color: #495057; font-weight: 500;">Password</label>
                        <input type="password" id="password" required 
                               style="width: 100%; padding: 0.75rem; border: 1px solid #e9ecef; border-radius: 6px; font-size: 1rem;">
                    </div>
                    <div id="login-error" style="color: #dc3545; margin-bottom: 1rem; display: none;"></div>
                    <button type="submit" 
                            style="width: 100%; padding: 0.75rem; background: #667eea; color: white; border: none; border-radius: 6px; font-size: 1rem; font-weight: 600; cursor: pointer;">
                        Login
                    </button>
                </form>
            </div>
        </div>
    `;
}


// Handle login form submission
async function handleLogin(event) {
    event.preventDefault();
    
    const username = document.getElementById('username').value;
    const password = document.getElementById('password').value;
    const errorDiv = document.getElementById('login-error');
    
    errorDiv.style.display = 'none';
    
    const result = await login(username, password);
    
    if (result.success) {
        // Login successful, load dashboard
        loadDashboard(currentFilter);
    } else {
        // Show error
        errorDiv.textContent = result.message || 'Login failed';
        errorDiv.style.display = 'block';
    }
}

// Make handleLogin global so it can be called from onclick
window.handleLogin = handleLogin;

    // Open score dashboard - Similar structure to dashboard.js but using window.location for vanilla JS
    function openScoreDashboard(ev, score) {
        console.log('openScoreDashboard called with:', ev, score);
        
        if (ev) {
            ev.preventDefault();
            ev.stopPropagation();
        }
        
        // Handle both object and individual parameters
        let scoreId, scoreName;
        if (score && typeof score === 'object') {
            scoreId = score.score_id || score.id;
            scoreName = score.score_name || 'Score';
        } else {
            // If called with individual parameters
            scoreId = score; // first param is scoreId
            scoreName = arguments[2] || 'Score'; // second param is scoreName
        }
        
        if (!scoreId) {
            console.warn('Score ID is required. Received:', score);
            alert('Error: Score ID is missing');
            return;
        }
        
        console.log('Opening score dashboard - ID:', scoreId, 'Name:', scoreName);
        
        // Get current filter and date range
        const filterType = currentFilter || 'MTD';
        const dateRange = getDateRange(filterType);
        
        // Build URL with parameters - similar to dashboard.js context
        const params = new URLSearchParams({
            scoreId: scoreId,
            scoreName: scoreName || 'Score',
            filterType: filterType
        });
        
        // Add date range if available (similar to date_range_start/end in dashboard.js)
        if (dateRange && dateRange.startDate && dateRange.endDate) {
            params.append('startDate', dateRange.startDate);
            params.append('endDate', dateRange.endDate);
        }
        
        // Navigate to score dashboard (equivalent to doAction in Odoo)
        const url = `/bizdom/score/dashboard?${params.toString()}`;
        console.log('Navigating to:', url);
        window.location.href = url;
    }
    
    // Make it available globally (backup, but already defined outside IIFE)
    window.openScoreDashboard = openScoreDashboard;
    
    // Fetch dashboard data
    async function loadDashboard(filterType) {
        const loadingEl = document.getElementById('loading-indicator');
        const contentEl = document.getElementById('dashboard-content');
        
        // CRITICAL: Check for token BEFORE doing anything
        if (!jwtToken) {
            jwtToken = getStoredToken();
        }
        
        // If still no token, show login page immediately
        if (!jwtToken) {
            console.log('No token available, showing login page');
            showLoginPage();
            return;
        }
        
        try {
            loadingEl.style.display = 'flex';
            contentEl.style.display = 'none';
            
            // Compute date range (used for label and for Custom/Today)
            const dateRange = getDateRange(filterType);

            // Determine effective filter and URL parameters
            let effectiveFilter = filterType;
            let url = `${API_BASE}?favoritesOnly=true`;
            // Today and Custom both use the backend "Custom" branch with explicit dates
            if ((filterType === 'Today' || filterType === 'Custom') && dateRange) {
                effectiveFilter = 'Custom';
                url += `&filterType=Custom&startDate=${encodeURIComponent(dateRange.startDate)}&endDate=${encodeURIComponent(dateRange.endDate)}`;
            } else {
                // Fallback to standard filters (MTD/WTD/YTD)
                url += `&filterType=${encodeURIComponent(effectiveFilter)}`;
            }

            //Build headers with JWT token
            const headers = {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${jwtToken}`
            };

            // Debug: Log token (remove in production)
            console.log('Making request with token:', jwtToken ? 'Token present' : 'No token');
            
            // Double check - should never happen but safety check
            if (!jwtToken) {
                console.error('Token missing right before API call!');
                showLoginPage();
                return;
            }

            //Make request with headers
            const response = await fetch(url, {
                method: 'GET',
                headers: headers
            });

            if (response.status === 401) {
                logout();
                return; // logout() already shows login page
            }
            
            // Handle response - dashboard.py may return string JSON
            const responseText = await response.text();
            let data;
            try {
                data = JSON.parse(responseText);
            } catch (e) {
                console.error('Non-JSON response from /api/dashboard:', responseText);
                // Gracefully handle invalid JSON by surfacing raw text
                data = {
                    statusCode: response.status || 500,
                    message: responseText || 'Invalid response format from server'
                };
            }
            
            if (data.statusCode === 200) {
                dashboardData = data;
                const labelToUse = dateRange ? dateRange.label : '';
                renderDashboard(data, labelToUse);
                // Apply scrolling fix after dashboard loads
                setTimeout(() => fixPublicDashboardScrolling(), 100);
                loadingEl.style.display = 'none';
                contentEl.style.display = 'block';
            } else {
                // Check if it's an authentication error
                if (data.statusCode === 401 || (data.message && data.message.includes('Authentication'))) {
                    logout();
                    return; // logout() already shows login page
                }
                throw new Error(data.message || 'Failed to load dashboard');
            }
        } catch (error) {
            console.error('Error loading dashboard:', error);
            
            // Check if it's an authentication error
            if (error.message && (error.message.includes('Authentication') || error.message.includes('401'))) {
                logout();
                return; // logout() already shows login page
            }
            
            // For other errors, show error message
            loadingEl.innerHTML = `
                <div class="alert alert-danger" style="max-width: 600px; margin: 0 auto;">
                    <h4>Error Loading Dashboard</h4>
                    <p>${error.message}</p>
                    <button onclick="location.reload()" class="btn btn-primary mt-2">Retry</button>
                </div>
            `;
        }
    }
    
    // Render dashboard
    function renderDashboard(data, dateLabel) {
        const container = document.getElementById('dashboard-content');
        
        const html = `
            <div class="verticals-dashboard" style="min-height: 100vh; background: #f5f7fa; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;">
                <div class="dashboard-header" style="background: white; padding: 1.5rem 2rem; display: flex; justify-content: space-between; align-items: center; box-shadow: 0 2px 4px rgba(0,0,0,0.1); border-bottom: 1px solid #e9ecef; flex-wrap: wrap; gap: 1rem;">
                    <div class="header-left" style="display: flex; flex-direction: column; gap: 0.5rem;">
                        <h1 class="company-name" style="font-size: 1.5rem; font-weight: 700; color: #212529; margin: 0;">BIZDOM</h1>
                        <div class="verticals-label" style="font-size: 0.9rem; color: #6c757d; font-weight: 600; text-transform: uppercase; letter-spacing: 1px;">YOUR BUSINESS AT A GLANCE</div>
                    </div>
                    <div class="header-right" style="display: flex; align-items: center; gap: 1.5rem; flex-wrap: wrap;">
                        ${dateLabel ? `
                            <div class="date-range-banner" style="background: #f0f4ff; color: #495057; padding: 0.5rem 1rem; border-radius: 6px; border: 1px solid #e0e7ff; display: flex; align-items: center; gap: 0.5rem; font-size: 0.9rem;">
                                <i class="fa fa-calendar-alt" style="font-size: 0.85rem; color: #667eea;"></i>
                                <span>${dateLabel}</span>
                            </div>
                        ` : ''}
                        <div class="filter-buttons" style="display: flex; gap: 0.5rem; align-items: center; flex-wrap: wrap;">
                            <button type="button" class="filter-btn ${currentFilter === 'Today' ? 'active' : ''}" 
                                    onclick="window.switchFilter('Today')" 
                                    style="padding: 0.5rem 1.25rem; border: 2px solid #e9ecef; background: white; border-radius: 8px; cursor: pointer; font-size: 0.9rem; font-weight: 500; transition: all 0.2s ease;">Today</button>
                            <button type="button" class="filter-btn ${currentFilter === 'MTD' ? 'active' : ''}" 
                                    onclick="window.switchFilter('MTD')" 
                                    style="padding: 0.5rem 1.25rem; border: 2px solid #e9ecef; background: white; border-radius: 8px; cursor: pointer; font-size: 0.9rem; font-weight: 500; transition: all 0.2s ease;">MTD</button>
                            <button type="button" class="filter-btn ${currentFilter === 'WTD' ? 'active' : ''}" 
                                    onclick="window.switchFilter('WTD')" 
                                    style="padding: 0.5rem 1.25rem; border: 2px solid #e9ecef; background: white; border-radius: 8px; cursor: pointer; font-size: 0.9rem; font-weight: 500; transition: all 0.2s ease;">WTD</button>
                            <button type="button" class="filter-btn ${currentFilter === 'YTD' ? 'active' : ''}" 
                                    onclick="window.switchFilter('YTD')" 
                                    style="padding: 0.5rem 1.25rem; border: 2px solid #e9ecef; background: white; border-radius: 8px; cursor: pointer; font-size: 0.9rem; font-weight: 500; transition: all 0.2s ease;">YTD</button>
                            <button type="button" class="filter-btn ${currentFilter === 'Custom' ? 'active' : ''}" 
                                    onclick="window.switchFilter('Custom')" 
                                    style="padding: 0.5rem 1.25rem; border: 2px solid #e9ecef; background: white; border-radius: 8px; cursor: pointer; font-size: 0.9rem; font-weight: 500; transition: all 0.2s ease;">Custom</button>
                            <div class="custom-range-container" style="display: ${currentFilter === 'Custom' ? 'flex' : 'none'}; align-items: center; gap: 0.5rem; margin-left: 0.5rem;">
                                <input type="date" id="custom-start-date" 
                                       style="padding: 0.25rem 0.5rem; border: 1px solid #ced4da; border-radius: 6px; font-size: 0.85rem;">
                                <span style="font-size: 0.85rem; color: #6c757d;">to</span>
                                <input type="date" id="custom-end-date" 
                                       style="padding: 0.25rem 0.5rem; border: 1px solid #ced4da; border-radius: 6px; font-size: 0.85rem;">
                            </div>
                            <button type="button" onclick="logout()" 
                                    style="padding: 0.5rem 1rem; background: #dc3545; color: white; border: none; border-radius: 6px; cursor: pointer; font-size: 0.9rem; font-weight: 500; transition: all 0.2s ease;">
                                Logout
                            </button>
                        </div>
                    </div>
                </div>
                
                <div class="dashboard-content" style="padding: 2rem; background: #f5f7fa; overflow-y: auto; min-height: calc(100vh - 120px);">
                    ${data.pillars && data.pillars.length > 0 ? 
                        data.pillars.map(pillar => renderPillar(pillar)).join('') 
                        : '<div class="alert alert-info" style="text-align: center; padding: 2rem;">No data available</div>'
                    }
                </div>
            </div>
            <style>
                .filter-btn:hover {
                    background: #f8f9fa !important;
                    border-color: #667eea !important;
                }
                .filter-btn.active {
                    background: #667eea !important;
                    color: white !important;
                    border-color: #667eea !important;
                }
            </style>
        `;
        
        container.innerHTML = html;
        
        // Apply scrolling fix after rendering
        if (!globalPublicDashboardObserver) {
            globalPublicDashboardObserver = fixPublicDashboardScrolling();
        } else {
            fixPublicDashboardScrolling();
        }
        
        // Post-render: Check all icon elements to see what's actually rendered
        setTimeout(() => {
            const allIcons = container.querySelectorAll('.kpi-icon-wrapper i');
            console.log('=== POST-RENDER ICON CHECK ===');
            allIcons.forEach((iconEl, index) => {
                const scoreName = iconEl.getAttribute('data-icon-name') || 'unknown';
                const iconClass = iconEl.getAttribute('data-icon-class') || 'unknown';
                const actualClasses = iconEl.className;
                const computedStyle = window.getComputedStyle(iconEl);
                const fontFamily = computedStyle.fontFamily;
                
                console.log(`Icon ${index + 1} (${scoreName}):`, {
                    expectedClass: iconClass,
                    actualClasses: actualClasses,
                    fontFamily: fontFamily,
                    element: iconEl,
                    innerHTML: iconEl.innerHTML,
                    textContent: iconEl.textContent
                });
                
                // If we see "FB 01" or unexpected text, log it
                if (iconEl.textContent && iconEl.textContent.trim() !== '' && !iconEl.textContent.match(/^\s*$/)) {
                    console.error(`UNEXPECTED TEXT IN ICON for "${scoreName}": "${iconEl.textContent}"`);
                }
            });
        }, 100);
        
        // Initialize custom range inputs when Custom filter is active
        if (currentFilter === 'Custom') {
            const startInput = container.querySelector('#custom-start-date');
            const endInput = container.querySelector('#custom-end-date');
            
            if (startInput && endInput) {
                // Restore previous values if available
                startInput.value = customRange.start || '';
                endInput.value = customRange.end || '';

                const handleCustomChange = () => {
                    const startVal = startInput.value;
                    const endVal = endInput.value;

                    customRange = { start: startVal, end: endVal };

                    // Only load when both dates are present
                    if (!startVal || !endVal) {
                        return;
                    }

                    const startDate = new Date(startVal);
                    const endDate = new Date(endVal);
                    if (!startDate || isNaN(startDate.getTime()) || !endDate || isNaN(endDate.getTime())) {
                        alert('Invalid date selection.');
                        return;
                    }
                    if (startDate > endDate) {
                        alert('Start date cannot be after end date.');
                        return;
                    }

                    // Valid range: load dashboard with Custom filter
                    loadDashboard('Custom');
                };

                startInput.addEventListener('change', handleCustomChange);
                endInput.addEventListener('change', handleCustomChange);
            }
        }
        
        // Use event delegation - this is the PRIMARY method now
        // Attach to the dashboard-content div which contains all KPIs
        const dashboardContent = container.querySelector('.dashboard-content');
        if (dashboardContent) {
            // Remove any existing listener first
            const clickHandler = function(e) {
                console.log('=== CLICK EVENT DETECTED ===', e.target);
                
                // Find the closest .kpi-circle parent
                const kpiCircle = e.target.closest('.kpi-circle');
                console.log('Closest KPI circle:', kpiCircle);
                
                if (kpiCircle) {
                    const scoreId = kpiCircle.dataset.scoreId;
                    const scoreName = kpiCircle.dataset.scoreName || 'Score';
                    
                    console.log('KPI circle clicked - Score ID:', scoreId, 'Score Name:', scoreName);
                    
                    if (scoreId) {
                        e.preventDefault();
                        e.stopPropagation();
                        
                        console.log('Calling openScoreClickHandler...');
                        if (window.openScoreClickHandler) {
                            window.openScoreClickHandler(parseInt(scoreId), scoreName);
                        } else {
                            console.error('ERROR: openScoreClickHandler is NOT available on window object!');
                            alert('Error: Click handler function not loaded. Please refresh the page.');
                        }
                    } else {
                        console.warn('No scoreId found in dataset');
                    }
                }
            };
            
            // Remove old listener if exists, then add new one
            dashboardContent.removeEventListener('click', clickHandler);
            dashboardContent.addEventListener('click', clickHandler);
            
            console.log('Event listener attached to dashboard-content');
        } else {
            console.error('ERROR: dashboard-content element not found!');
        }
    }
    
    function renderPillar(pillar) {
        const color = getPillarColor(pillar.pillar_name);
        const darkerColor = color;
        
        return `
            <div class="pillar-row" style="display: flex; align-items: center; margin-bottom: 2rem; background: white; border-radius: 12px; padding: 1.5rem; box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);">
                <div class="pillar-section" style="width: 280px; flex-shrink: 0;">
                    <div class="vertical-item" style="display: flex; align-items: center; gap: 1rem; padding: 1rem; background: #1e3a5f; border-radius: 12px; transition: all 0.2s ease;">
                        <div class="vertical-orb" style="width: 16px; height: 16px; border-radius: 50%; flex-shrink: 0; background: radial-gradient(circle, ${color} 0%, ${darkerColor} 100%); box-shadow: 0 0 20px ${color};"></div>
                        <div class="vertical-name" style="color: white; font-weight: 600; font-size: 1rem;">${pillar.pillar_name}</div>
                    </div>
                </div>
                <div class="kpi-flow" style="flex: 1; padding-left: 2rem; display: flex; gap: 2rem; flex-wrap: wrap; align-items: center; min-height: 80px; border-left: 4px solid ${color};">
                    ${pillar.scores && pillar.scores.length > 0 ? 
                        pillar.scores.map(score => renderScore(score)).join('') 
                        : '<div class="no-scores" style="color: #6c757d; font-style: italic; padding: 1rem;">No scores available</div>'
                    }
                </div>
            </div>
        `;
    }
    
    function renderScore(score) {
        // Debug: Log the exact score data received
        console.log('renderScore called with:', {
            score_name: score.score_name,
            score_name_type: typeof score.score_name,
            score_name_length: score.score_name ? score.score_name.length : 0,
            score_name_chars: score.score_name ? score.score_name.split('').map(c => c.charCodeAt(0)) : [],
            full_score: score
        });
        
        let icon = getScoreIcon(score.score_name);
        console.log(`Icon for "${score.score_name}": "${icon}"`);
        
        // Ensure icon is always a valid string - never empty or undefined
        if (!icon || typeof icon !== 'string' || icon.trim() === '') {
            console.error(`Invalid icon returned for "${score.score_name}": "${icon}". Using fallback.`);
            icon = 'fas fa-chart-bar';
        }
        
        // In Font Awesome 6, icons already include the style prefix (fas, far, etc.)
        // So we don't need to add 'fa' prefix - the icon class is complete
        
        const color = getScoreColor(score.score_name);
        const iconStyle = getIconStyle(score.score_name); // Get custom styles for this icon
        const value = (score.total_score_value || 0).toFixed(1);
        const suffix = (score.type === 'percentage') ? '%' : '';
        const scoreId = score.score_id || score.id;
        
        // Ensure scoreId exists
        if (!scoreId) {
            console.warn('Score ID missing for score:', score);
            return `<div class="kpi-circle" style="display: flex; flex-direction: column; align-items: center; gap: 0.5rem; min-width: 100px; opacity: 0.5;">
                <div class="kpi-icon-wrapper" style="width: 60px; height: 60px; border-radius: 50%; display: flex; align-items: center; justify-content: center; color: white; font-size: 1.5rem; box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15); background-color: ${color};">
                    <i class="${icon}" style="${iconStyle}"></i>
                </div>
                <div class="kpi-label" style="font-size: 0.85rem; color: #495057; text-align: center; font-weight: 500; max-width: 100px;">${score.score_name}</div>
                <div class="kpi-value" style="font-size: 0.9rem; color: #212529; font-weight: 600;">${value}${suffix}</div>
            </div>`;
        }
        
        // Escape the score name for use in onclick attribute
        const escapedScoreName = (score.score_name || 'Score').replace(/'/g, "\\'").replace(/"/g, '&quot;');
        
        // Debug: Log the final icon class that will be rendered
        // In Font Awesome 6, icon already includes the style prefix (fas, far, etc.)
        console.log(`Rendering icon for "${score.score_name}": class="${icon}", score_name="${score.score_name}"`);
        
        // Double-check icon is valid before rendering
        if (!icon || icon.trim() === '') {
            console.error(`CRITICAL: Icon is empty for "${score.score_name}"! Using fallback.`);
            icon = 'fa-chart-bar';
        }
        
        return `
            <div class="kpi-circle" 
                 data-score-id="${scoreId}"
                 data-score-name="${escapedScoreName}"
                 style="display: flex; flex-direction: column; align-items: center; gap: 0.5rem; cursor: pointer; transition: transform 0.2s ease; min-width: 100px;"
                 onmouseover="this.style.transform='scale(1.05)'"
                 onmouseout="this.style.transform='scale(1)'">
                <div class="kpi-icon-wrapper" style="width: 60px; height: 60px; border-radius: 50%; display: flex; align-items: center; justify-content: center; color: white; font-size: 1.5rem; box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15); background-color: ${color};">
                    <i class="${icon}" style="${iconStyle}" data-icon-name="${score.score_name}" data-icon-class="${icon}"></i>
                </div>
                <div class="kpi-label" style="font-size: 0.85rem; color: #495057; text-align: center; font-weight: 500; max-width: 100px;">${score.score_name}</div>
                <div class="kpi-value" style="font-size: 0.9rem; color: #212529; font-weight: 600;">${value}${suffix}</div>
            </div>
        `;
    }
    
    // Global function for filter switching
    window.switchFilter = function(filter) {
        // Check if still logged in
        if (!isLoggedIn()) {
            showLoginPage();
            return;
        }
        
        currentFilter = filter;
        window.currentFilter = filter; // Update global reference
        if (filter === 'Custom') {
            // Don't load data immediately; wait for valid dates
            // Re-render header with custom date inputs (keep existing data if any)
            renderDashboard(dashboardData || { pillars: [] }, '');
            return;
        } else {
            // When switching away from Custom, reset custom range so we don't reuse stale dates
            customRange = { start: '', end: '' };
        }
        loadDashboard(filter);
    };
    
    // Make logout function global
    window.logout = logout;
    
    // Initialize on page load
    function initializeDashboard() {
        // Load token from localStorage first
        jwtToken = getStoredToken();
        
        // Apply scrolling fix on initialization
        if (!globalPublicDashboardObserver) {
            globalPublicDashboardObserver = fixPublicDashboardScrolling();
        }
        
        if (jwtToken) {
            console.log('Token found, loading dashboard...');
            loadDashboard(currentFilter);
        } else {
            console.log('No token found, showing login page...');
            showLoginPage();
        }
    }
    
    // Wait for DOM to be ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => {
            initializeDashboard();
            // Apply scrolling fix after DOM is loaded
            setTimeout(() => fixPublicDashboardScrolling(), 100);
        });
    } else {
        // DOM already loaded, initialize immediately
        initializeDashboard();
        // Apply scrolling fix immediately
        setTimeout(() => fixPublicDashboardScrolling(), 100);
    }
    
    // Global initialization: Apply scrolling fix when dashboard is loaded
    // This ensures scrolling works for all dashboard views
    if (typeof window !== 'undefined') {
        // Apply immediately if DOM is ready
        if (document.readyState === 'complete' || document.readyState === 'interactive') {
            setTimeout(() => fixPublicDashboardScrolling(), 100);
        } else {
            window.addEventListener('load', () => {
                setTimeout(() => fixPublicDashboardScrolling(), 100);
            });
        }
        
        // Also apply on DOMContentLoaded as backup
        document.addEventListener('DOMContentLoaded', () => {
            setTimeout(() => fixPublicDashboardScrolling(), 100);
        });
        
        // Apply after a short delay to catch any late renders
        setTimeout(() => fixPublicDashboardScrolling(), 100);
    }
    
    // Verify functions are available
    console.log('Dashboard script loaded. Functions available:', {
        openScoreDashboard: typeof window.openScoreDashboard,
        openScoreClickHandler: typeof window.openScoreClickHandler,
        testKpiClick: typeof window.testKpiClick
    });
})();


