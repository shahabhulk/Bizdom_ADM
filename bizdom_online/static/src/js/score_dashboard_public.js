// Score Dashboard - Public version (vanilla JS)

// Global scrolling fix function for public score dashboard
function fixPublicScoreDashboardScrolling() {
    // More aggressive approach to fix scrolling
    const applyScrollingFix = () => {
        // Find all relevant containers for public score dashboard
        const scoreDashboardContent = document.getElementById('score-dashboard-content');
        const container = document.querySelector('.container');
        const body = document.body;
        const html = document.documentElement;
        
        if (scoreDashboardContent) {
            // Force scrolling on score dashboard content
            scoreDashboardContent.style.setProperty('overflow-y', 'auto', 'important');
            scoreDashboardContent.style.setProperty('height', 'auto', 'important');
            scoreDashboardContent.style.setProperty('min-height', '100%', 'important');
            scoreDashboardContent.style.setProperty('max-height', 'none', 'important');
            scoreDashboardContent.classList.add('public_score_dashboard_scrollable');
        }
        
        if (container) {
            // Allow container to expand
            container.style.setProperty('overflow-y', 'auto', 'important');
            container.style.setProperty('height', 'auto', 'important');
            container.style.setProperty('min-height', '100vh', 'important');
            container.style.setProperty('max-height', 'none', 'important');
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
    
    // Observe the score dashboard content container
    const scoreDashboardContent = document.getElementById('score-dashboard-content');
    if (scoreDashboardContent) {
        observer.observe(scoreDashboardContent, {
            attributes: true,
            attributeFilter: ['style', 'class']
        });
    }
    
    // Also observe container
    const container = document.querySelector('.container');
    if (container) {
        observer.observe(container, {
            attributes: true,
            attributeFilter: ['style', 'class']
        });
    }
    
    return observer;
}

// Global observer instance
let globalPublicScoreDashboardObserver = null;

(function() {
    'use strict';
    
    const API_BASE = '/api/score/overview';
    const DEPARTMENT_API = '/api/score/overview/department';
    const EMPLOYEE_OVERVIEW_API = '/api/score/overview/employee';
    let jwtToken = null;
    let chart = null;
    let departmentChart = null;
    let employeeChart = null;
    let originalChartData = [];
    let isRenderingChart = false; // Flag to prevent duplicate renders
    
    // Get token from localStorage
    function getStoredToken() {
        const token = localStorage.getItem('jwt_token');
        if (token && typeof token === 'string' && token.trim() !== '' && token !== 'null' && token !== 'undefined') {
            return token;
        }
        if (token) {
            localStorage.removeItem('jwt_token');
        }
        return null;
    }
    
    // Set initial token state
    jwtToken = getStoredToken();
    
    // Get URL parameters
    function getUrlParams() {
        const params = new URLSearchParams(window.location.search);
        return {
            scoreId: params.get('scoreId'),
            scoreName: params.get('scoreName') || 'Score',
            filterType: (params.get('filterType') || 'MTD').toUpperCase()
        };
    }
    
    // State management
    let state = {
        loading: true,
        score: null,
        scoreId: null,
        scoreName: 'Score',
        scoreType: 'value',
        filterType: 'MTD',
        dateRangeLabel: '',
        activeRange: null,
        quadrants: {
            q1: { title: "Score Overview", data: [], filter_type: 'MTD' },
            q2: { title: "Department Breakdown", data: [] },
            q3: { title: "Trend Analysis", data: [] },
            q4: { title: "Time Period Analysis", data: [] },
        },
        departmentData: [],
        departmentDataLoaded: false,
        departmentDataLoading: false,
        departmentChartData: null,
        departmentChartLabel: '',
        departmentError: null,
        employeeData: [],
        employeeDataLoading: false,
        employeeChartData: null,
        employeeChartLabel: '',
        employeeError: null,
        selectedDepartmentId: null,
        selectedDepartmentName: null,
        selectedPeriodInfo: null,
        currentSelectedPeriodItem: null // Store the period item selected in q1
    };
    
    // Date utility functions
    function parseDateString(value) {
        if (!value) return null;
        if (value instanceof Date) {
            return value;
        }
        if (typeof value === 'string' && value.match(/^\d{4}-\d{2}-\d{2}$/)) {
            const parts = value.split('-');
            return new Date(parseInt(parts[0]), parseInt(parts[1]) - 1, parseInt(parts[2]));
        }
        const date = new Date(value);
        if (isNaN(date.getTime())) {
            return null;
        }
        return date;
    }
    
    function formatDateForServer(date) {
        const year = date.getFullYear();
        const month = String(date.getMonth() + 1).padStart(2, "0");
        const day = String(date.getDate()).padStart(2, "0");
        return `${year}-${month}-${day}`;
    }
    
    function formatDateForQuadrantAPI(dateStr) {
        if (!dateStr) return '';
        const parts = dateStr.split('-');
        if (parts.length === 3) {
            return `${parts[2]}-${parts[1]}-${parts[0]}`;
        }
        return dateStr;
    }
    
    function formatDisplayDate(date) {
        if (!date) return "";
        if (isNaN(date.getTime())) return "";
        const day = date.getDate();
        const monthNames = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", 
                           "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
        const month = monthNames[date.getMonth()];
        const year = date.getFullYear();
        return `${day} ${month} ${year}`;
    }
    
    function formatRangeLabel(startDate, endDate) {
        if (!startDate || !endDate) return "";
        return `${formatDisplayDate(startDate)} - ${formatDisplayDate(endDate)}`;
    }
    
    function formatDateForTooltip(dateString) {
        if (!dateString) return '';
        try {
            let date;
            if (dateString instanceof Date) {
                date = dateString;
            } else if (typeof dateString === 'string') {
                // Backend sends dates as DD-MM-YYYY (e.g., "26-09-2025")
                // Use local timezone to avoid date shifts
                if (dateString.match(/^\d{2}-\d{2}-\d{4}$/)) {
                    // Format: DD-MM-YYYY
                    const parts = dateString.split('-');
                    const day = parseInt(parts[0], 10);
                    const month = parseInt(parts[1], 10) - 1; // Month is 0-indexed
                    const year = parseInt(parts[2], 10);
                    // Use Date constructor with local time to avoid timezone issues
                    date = new Date(year, month, day, 12, 0, 0); // Use noon to avoid DST issues
                } else if (dateString.match(/^\d{4}-\d{2}-\d{2}$/)) {
                    // Format: YYYY-MM-DD
                    const parts = dateString.split('-');
                    const year = parseInt(parts[0], 10);
                    const month = parseInt(parts[1], 10) - 1; // Month is 0-indexed
                    const day = parseInt(parts[2], 10);
                    date = new Date(year, month, day, 12, 0, 0); // Use noon to avoid DST issues
                } else if (dateString.match(/^\d{1,2}-\d{1,2}-\d{4}$/)) {
                    // Handle single-digit days/months (e.g., "9-1-2025")
                    const parts = dateString.split('-');
                    const day = parseInt(parts[0], 10);
                    const month = parseInt(parts[1], 10) - 1;
                    const year = parseInt(parts[2], 10);
                    date = new Date(year, month, day, 12, 0, 0);
                } else {
                    // Try parsing as-is (handles ISO format, etc.)
                    date = new Date(dateString);
                }
            } else {
                return String(dateString);
            }
            
            // Validate the date
            if (!date || isNaN(date.getTime())) {
                console.warn('Invalid date:', dateString);
                return String(dateString);
            }
            
            return formatDisplayDate(date);
        } catch (error) {
            console.warn('Error formatting date:', dateString, error);
            return String(dateString);
        }
    }
    
    function getPresetRange(filter) {
        const today = new Date();
        let startDate, endDate, label;
        switch (filter) {
            case "WTD": {
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
                label = `Week to Date: ${formatRangeLabel(startDate, endDate)}`;
                break;
            }
            case "YTD": {
                startDate = new Date(today.getFullYear(), 0, 1);
                startDate.setHours(0, 0, 0, 0);
                endDate = new Date(today);
                endDate.setHours(23, 59, 59, 999);
                label = `Year to Date: ${formatRangeLabel(startDate, endDate)}`;
                break;
            }
            default: { // MTD
                startDate = new Date(today.getFullYear(), today.getMonth(), 1);
                startDate.setHours(0, 0, 0, 0);
                endDate = new Date(today);
                endDate.setHours(23, 59, 59, 999);
                label = `Month to Date: ${formatRangeLabel(startDate, endDate)}`;
                break;
            }
        }
        return {
            start_date: formatDateForServer(startDate),
            end_date: formatDateForServer(endDate),
            label: label
        };
    }
    
    function ensureActiveRange() {
        if (state.activeRange?.start && state.activeRange?.end) {
            return state.activeRange;
        }
        const preset = getPresetRange(state.filterType);
        state.activeRange = { start: preset.start_date, end: preset.end_date };
        state.dateRangeLabel = preset.label;
        return state.activeRange;
    }
    
    function resetDepartmentState(options = { keepChart: false }) {
        state.departmentData = [];
        state.departmentDataLoaded = false;
        state.departmentDataLoading = false;
        state.departmentChartData = null;
        state.departmentChartLabel = '';
        state.departmentError = null;
        
        if (departmentChart && !options.keepChart) {
            departmentChart.destroy();
            departmentChart = null;
        }
        
        renderDepartmentChart();
    }
    
    function resetEmployeeState(options = { keepChart: false }) {
        state.employeeData = [];
        state.employeeDataLoading = false;
        state.employeeChartData = null;
        state.employeeChartLabel = '';
        state.employeeError = null;
        state.selectedDepartmentId = null;
        state.selectedDepartmentName = null;
        state.selectedPeriodInfo = null;
        
        if (employeeChart && !options.keepChart) {
            employeeChart.destroy();
            employeeChart = null;
        }
        
        renderEmployeeChart();
    }
    
    function getPeriodLabel(item, filterType) {
        return item?.month || item?.period || item?.year || '';
    }
    
    function formatDepartmentPeriodLabel(entry) {
        if (!entry) return '';
        if (entry.period) {
            return entry.period;
        }
        if (entry.start_date && entry.end_date) {
            return `${entry.start_date} to ${entry.end_date}`;
        }
        return '';
    }
    
    function findMatchingDepartmentEntry(periodItem) {
        if (!periodItem || !state.departmentData || state.departmentData.length === 0) {
            return null;
        }
        
        const possibleLabels = [];
        const periodLabel = getPeriodLabel(periodItem, state.filterType);
        if (periodLabel) {
            possibleLabels.push(periodLabel.trim());
        }
        if (periodItem.period) {
            possibleLabels.push(String(periodItem.period).trim());
        }
        if (periodItem.start_date && periodItem.end_date) {
            possibleLabels.push(`${periodItem.start_date.trim()}|${periodItem.end_date.trim()}`);
        }
        
        for (const entry of state.departmentData) {
            const entryPeriod = (entry.period || '').trim();
            if (entryPeriod && possibleLabels.includes(entryPeriod)) {
                return entry;
            }
            if (entry.start_date && entry.end_date) {
                const entryRange = `${entry.start_date.trim()}|${entry.end_date.trim()}`;
                if (possibleLabels.includes(entryRange)) {
                    return entry;
                }
            }
        }
        
        const index = state.quadrants.q1.data.indexOf(periodItem);
        if (index > -1 && state.departmentData[index]) {
            return state.departmentData[index];
        }
        return null;
    }
    
    function buildDepartmentChartPayload(entry) {
        const departments = entry?.department || [];
        const scoreNameLower = (state.scoreName || '').toLowerCase();
        const isLeadsScore = scoreNameLower.includes('lead') && !scoreNameLower.includes('conversion');
        const isConversionScore = scoreNameLower.includes('conversion');
        // Check for quality_lead field - for Leads and Conversion scores, show it even if values are 0
        const hasConversionValues = (isLeadsScore || isConversionScore) && departments.some(dep => {
            const convValue = dep.quality_lead;
            // Field exists (even if 0) - we want to show it for Leads and Conversion
            return convValue !== undefined && convValue !== null;
        });
        
        return {
            labels: departments.map(dep => dep.department_name || dep.department_id || 'Department'),
            values: departments.map(dep => Number(dep.actual_value || 0)),
            conversionValues: (isLeadsScore || isConversionScore) && hasConversionValues ? departments.map(dep => {
                const convValue = dep.quality_lead;
                if (typeof convValue === 'string') {
                    return Number(convValue) || 0;
                }
                return Number(convValue || 0);
            }) : null,
            departmentIds: departments.map(dep => dep.department_id || dep.department_name),
            departments: departments,
            periodStartDate: entry?.start_date,
            periodEndDate: entry?.end_date,
            period: entry?.period
        };
    }
    
    function updateDepartmentChartState(entry, fallbackPeriod) {
        if (!entry || !entry.department || entry.department.length === 0) {
            state.departmentChartData = null;
            state.departmentChartLabel = fallbackPeriod || '';
            state.departmentError = 'No department data available for the selected period.';
            return;
        }
        state.departmentError = null;
        state.departmentChartLabel = formatDepartmentPeriodLabel(entry) || fallbackPeriod || '';
        state.departmentChartData = buildDepartmentChartPayload(entry);
    }
    
    function getDepartmentPlaceholderMessage() {
        if (state.departmentDataLoading) {
            return 'Loading department data...';
        }
        if (state.departmentError) {
            return state.departmentError;
        }
        if (!state.departmentDataLoaded) {
            return 'Select a bar in the Score Overview to view department breakdown.';
        }
        if (state.departmentData && state.departmentData.length > 0) {
            return 'Select a bar in the Score Overview to view department breakdown.';
        }
        return 'No department data available for this filter.';
    }
    
    function renderDepartmentChart() {
        try {
            const placeholder = document.getElementById('department-chart-placeholder');
            const container = document.getElementById('department-chart-container');
            const canvas = document.getElementById('departmentChartCanvas');
            const periodLabelEl = document.getElementById('department-chart-period');
            
            if (periodLabelEl) {
                periodLabelEl.textContent = state.departmentChartLabel || '';
            }
            
            if (!placeholder || !container) {
                return;
            }
            
            if (state.departmentDataLoading || state.departmentError || !state.departmentChartData || !state.departmentChartData.labels || state.departmentChartData.labels.length === 0) {
                placeholder.style.display = 'block';
                placeholder.textContent = getDepartmentPlaceholderMessage();
                container.style.display = 'none';
                if (departmentChart) {
                    departmentChart.destroy();
                    departmentChart = null;
                }
                return;
            }
            
            placeholder.style.display = 'none';
            container.style.display = 'block';
            
            if (!canvas) {
                return;
            }
            
            if (departmentChart) {
                departmentChart.destroy();
                departmentChart = null;
            }
            
            // Validate department chart data
            if (!state.departmentChartData || !state.departmentChartData.values || !Array.isArray(state.departmentChartData.values)) {
                return;
            }
        
        // Build datasets
        const scoreNameLower = (state.scoreName || '').toLowerCase();
        const isLeadsScore = scoreNameLower.includes('lead') && !scoreNameLower.includes('conversion');
        const isConversionScore = scoreNameLower.includes('conversion');
        
        const datasets = [{
            label: isLeadsScore ? 'Leads' : (isConversionScore ? 'Conversions' : 'Actual'),
            data: state.departmentChartData.values,
            backgroundColor: '#0d6efd',
            borderColor: '#0d6efd',
            borderWidth: 1,
            borderRadius: 4
        }];
        
        // Add quality leads dataset if available (for Leads and Conversion scores)
        if (state.departmentChartData.conversionValues && Array.isArray(state.departmentChartData.conversionValues)) {
            datasets.push({
                label: 'Quality Leads',
                data: state.departmentChartData.conversionValues,
                backgroundColor: '#198754',
                borderColor: '#198754',
                borderWidth: 1,
                borderRadius: 4
            });
        }
        
        // Calculate max value across all datasets
        const allValues = datasets.flatMap(dataset => (dataset.data || []));
        const maxValue = allValues.length > 0 ? Math.max(...allValues, 0) : 0;
        const suggestedMax = maxValue > 0 ? maxValue * 1.1 : 100;
        const hasConversionValues = datasets.length > 1;
        
        departmentChart = new Chart(canvas, {
            type: 'bar',
            data: {
                labels: state.departmentChartData.labels,
                datasets: datasets
            },
            options: {
                maintainAspectRatio: false,
                responsive: true,
                plugins: {
                    legend: {
                        display: true,
                        position: 'top',
                        align: 'end',
                        labels: {
                            usePointStyle: true,
                            padding: 15,
                            font: {
                                size: 12
                            }
                        }
                    },
                    tooltip: {
                        callbacks: {
                            label: (context) => {
                                const value = context.parsed.y || 0;
                                const datasetLabel = context.dataset.label || 'Value';
                                const suffix = state.scoreType === 'percentage' ? '%' : '';
                                return `${datasetLabel}: ${value.toFixed(2)}${suffix}`;
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        grid: {
                            display: false
                        },
                        ticks: {
                            color: '#111827',
                            font: {
                                size: 11
                            }
                        }
                    },
                    y: {
                        beginAtZero: true,
                        suggestedMax: suggestedMax,
                        grid: {
                            color: 'rgba(0, 0, 0, 0.1)'
                        },
                        ticks: {
                            color: '#111827',
                            font: {
                                size: 11
                            },
                            callback: function(value) {
                                const suffix = state.scoreType === 'percentage' ? '%' : '';
                                if (value >= 1000) {
                                    return (value / 1000).toFixed(2) + 'k' + suffix;
                                }
                                return value.toFixed(2) + suffix;
                            }
                        }
                    }
                },
                onClick: async (event, elements) => {
                    if (elements && elements.length > 0) {
                        const element = elements[0];
                        const dataIndex = element.index;
                        const departmentName = state.departmentChartData.labels[dataIndex];
                        
                        // Get period information from the currently selected period item in q1
                        // This ensures we use the correct period (e.g., "Week 3") that was clicked
                        const periodItem = state.currentSelectedPeriodItem;
                        
                        const periodInfo = {
                            startDate: periodItem?.start_date || state.departmentChartData.periodStartDate,
                            endDate: periodItem?.end_date || state.departmentChartData.periodEndDate,
                            period: getPeriodLabel(periodItem, state.filterType) || periodItem?.period || state.departmentChartData.period
                        };
                        
                        console.log('Department clicked - periodInfo:', periodInfo, 'periodItem:', periodItem, 'departmentChartData:', {
                            periodStartDate: state.departmentChartData.periodStartDate,
                            periodEndDate: state.departmentChartData.periodEndDate,
                            period: state.departmentChartData.period
                        });
                        
                        // Get department ID from chart data
                        let departmentId = null;
                        if (state.departmentChartData.departmentIds && state.departmentChartData.departmentIds[dataIndex]) {
                            departmentId = state.departmentChartData.departmentIds[dataIndex];
                        } else if (state.departmentChartData.departments && state.departmentChartData.departments[dataIndex]) {
                            const dept = state.departmentChartData.departments[dataIndex];
                            departmentId = dept.department_id;
                        }
                        
                        if (departmentId) {
                            await handleDepartmentClick(departmentId, departmentName, periodInfo);
                        }
                    }
                }
            }
        });
        } catch (error) {
            console.error('Error rendering department chart:', error);
            const placeholder = document.getElementById('department-chart-placeholder');
            const container = document.getElementById('department-chart-container');
            if (placeholder) {
                placeholder.style.display = 'block';
                placeholder.textContent = 'Error rendering chart. Please try again.';
            }
            if (container) {
                container.style.display = 'none';
            }
            if (departmentChart) {
                departmentChart.destroy();
                departmentChart = null;
            }
        }
    }
    
    async function loadDepartmentData() {
        if (!state.scoreId) {
            return [];
        }
        
        if (!jwtToken) {
            jwtToken = getStoredToken();
            if (!jwtToken) {
                window.location.href = '/bizdom/dashboard/public';
                return [];
            }
        }
        
        try {
            state.departmentDataLoading = true;
            state.departmentError = null;
            renderDepartmentChart();
            
            const activeRange = ensureActiveRange();
            let url = `${DEPARTMENT_API}?scoreId=${state.scoreId}&filterType=${state.filterType}`;
            if (state.filterType === 'Custom' && activeRange.start && activeRange.end) {
                url += `&startDate=${formatDateForQuadrantAPI(activeRange.start)}&endDate=${formatDateForQuadrantAPI(activeRange.end)}`;
            }
            
            const response = await fetch(url, {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${jwtToken}`
                }
            });
            
            if (response.status === 401) {
                localStorage.removeItem('jwt_token');
                window.location.href = '/bizdom/dashboard/public';
                return [];
            }
            
            const responseText = await response.text();
            let deptData;
            try {
                deptData = JSON.parse(responseText);
            } catch (error) {
                console.error("Invalid department response:", responseText);
                state.departmentError = 'Unable to load department data.';
                state.departmentData = [];
                state.departmentDataLoaded = false;
                return [];
            }
            
            if (deptData && deptData.statusCode === 200) {
                state.departmentData = deptData.overview_department || [];
                state.departmentDataLoaded = true;
                if (!state.departmentData.length) {
                    state.departmentError = 'No department data available for this filter.';
                } else {
                    state.departmentError = null;
                }
            } else {
                state.departmentData = [];
                state.departmentDataLoaded = false;
                state.departmentError = deptData?.message || 'Unable to load department data.';
            }
        } catch (error) {
            console.error("Error loading department data:", error);
            state.departmentData = [];
            state.departmentDataLoaded = false;
            state.departmentError = 'Unable to load department data.';
        } finally {
            state.departmentDataLoading = false;
            renderDepartmentChart();
        }
        
        return state.departmentData;
    }
    
    async function handleOverviewBarClick(periodItem) {
        if (!periodItem) {
            return;
        }
        
        // Store the currently selected period item for use when clicking departments
        state.currentSelectedPeriodItem = periodItem;
        
        const fallbackPeriod = getPeriodLabel(periodItem, state.filterType);
        state.departmentChartLabel = fallbackPeriod || '';
        state.departmentChartData = null;
        state.departmentError = null;
        renderDepartmentChart();
        
        if (!state.departmentDataLoaded && !state.departmentDataLoading) {
            await loadDepartmentData();
        }
        
        if (state.departmentDataLoading) {
            return;
        }
        
        if (!state.departmentData || state.departmentData.length === 0) {
            state.departmentChartData = null;
            state.departmentChartLabel = fallbackPeriod || '';
            renderDepartmentChart();
            return;
        }
        
        const matchingEntry = findMatchingDepartmentEntry(periodItem);
        if (!matchingEntry) {
            state.departmentChartData = null;
            state.departmentChartLabel = fallbackPeriod || '';
            state.departmentError = 'No department data available for the selected period.';
            renderDepartmentChart();
            return;
        }
        
        updateDepartmentChartState(matchingEntry, fallbackPeriod);
        renderDepartmentChart();
    }
    
    async function handleDepartmentClick(departmentId, departmentName, periodInfo = null) {
        const scoreNameLower = (state.scoreName || '').toLowerCase();
        
        // Handle for Labour and Leads scores
        if (scoreNameLower !== 'labour' && scoreNameLower !== 'leads') {
            console.log('Employee/Source overview only available for Labour and Leads scores');
            return;
        }

        if (!departmentId) {
            console.warn('Department/Medium ID is required');
            return;
        }

        state.selectedDepartmentId = departmentId;
        state.selectedDepartmentName = departmentName;
        state.selectedPeriodInfo = periodInfo;
        state.employeeChartData = null;
        state.employeeError = null;
        state.employeeChartLabel = departmentName || '';

        await loadEmployeeData(departmentId);
    }
    
    async function loadEmployeeData(departmentId) {
        if (!state.scoreId || !departmentId) {
            return;
        }

        try {
            state.employeeDataLoading = true;
            state.employeeError = null;
            renderEmployeeChart();

            const activeRange = ensureActiveRange();
            let url = `${EMPLOYEE_OVERVIEW_API}?scoreId=${state.scoreId}&departmentId=${departmentId}&filterType=${state.filterType}`;
            if (state.filterType === 'Custom' && activeRange.start && activeRange.end) {
                url += `&startDate=${formatDateForQuadrantAPI(activeRange.start)}&endDate=${formatDateForQuadrantAPI(activeRange.end)}`;
            }

            const response = await fetch(url, {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${jwtToken}`
                }
            });

            if (response.status === 401) {
                localStorage.removeItem('jwt_token');
                window.location.href = '/bizdom/dashboard/public';
                return;
            }

            const responseText = await response.text();
            let empData;
            try {
                empData = JSON.parse(responseText);
            } catch (error) {
                console.error("Invalid employee response:", responseText);
                state.employeeError = 'Unable to load employee data.';
                state.employeeData = [];
                return;
            }

            if (empData && empData.statusCode === 200) {
                const scoreNameLower = (state.scoreName || '').toLowerCase();
                
                if (scoreNameLower === 'leads') {
                    state.employeeData = empData.overview_source || [];
                    if (!state.employeeData.length) {
                        state.employeeError = 'No source data available for this medium.';
                    } else {
                        state.employeeError = null;
                        buildLeadsChartData();
                    }
                } else {
                    state.employeeData = empData.overview_employee || [];
                    if (!state.employeeData.length) {
                        state.employeeError = 'No employee data available for this department.';
                    } else {
                        state.employeeError = null;
                        buildEmployeeChartData();
                    }
                }
            } else {
                state.employeeData = [];
                state.employeeError = empData?.message || 'Unable to load employee/source data.';
            }
        } catch (error) {
            console.error("Error loading employee data:", error);
            state.employeeData = [];
            state.employeeError = 'Unable to load employee data.';
        } finally {
            state.employeeDataLoading = false;
            renderEmployeeChart();
        }
    }
    
    function buildEmployeeChartData() {
        if (!state.employeeData || state.employeeData.length === 0) {
            state.employeeChartData = null;
            return;
        }

        let selectedPeriodData = null;
        
        if (state.selectedPeriodInfo && (state.selectedPeriodInfo.startDate || state.selectedPeriodInfo.endDate || state.selectedPeriodInfo.period)) {
            const periodStart = String(state.selectedPeriodInfo.startDate || '').trim();
            const periodEnd = String(state.selectedPeriodInfo.endDate || '').trim();
            const periodLabel = String(state.selectedPeriodInfo.period || '').trim();
            
            console.log('Building employee chart data:', {
                selectedPeriodInfo: state.selectedPeriodInfo,
                periodStart,
                periodEnd,
                periodLabel,
                employeeDataPeriods: state.employeeData.map(p => ({
                    start_date: p.start_date,
                    end_date: p.end_date,
                    period: p.period,
                    employeeCount: p.employees?.length || 0
                }))
            });
            
            const normalizeDate = (dateStr) => {
                if (!dateStr) return null;
                const str = String(dateStr).trim();
                if (str.match(/^\d{2}-\d{2}-\d{4}$/)) {
                    return str;
                }
                return str;
            };
            
            const normalizedStart = normalizeDate(periodStart);
            const normalizedEnd = normalizeDate(periodEnd);
            
            // Try exact match first - both start and end dates must match
            selectedPeriodData = state.employeeData.find(period => {
                const periodStartNorm = normalizeDate(period.start_date);
                const periodEndNorm = normalizeDate(period.end_date);
                
                if (normalizedStart && normalizedEnd && periodStartNorm && periodEndNorm) {
                    const startMatch = periodStartNorm === normalizedStart;
                    const endMatch = periodEndNorm === normalizedEnd;
                    const match = startMatch && endMatch;
                    
                    if (match) {
                        console.log('✓ Found exact period match:', {
                            selected: { start: normalizedStart, end: normalizedEnd },
                            found: { start: periodStartNorm, end: periodEndNorm }
                        });
                    }
                    return match;
                }
                return false;
            });
            
            // If exact match not found, try matching by start date only (for current week scenarios)
            if (!selectedPeriodData && normalizedStart) {
                console.log('Trying to match by start date only:', normalizedStart);
                selectedPeriodData = state.employeeData.find(period => {
                    const periodStartNorm = normalizeDate(period.start_date);
                    const match = periodStartNorm === normalizedStart;
                    if (match) {
                        console.log('✓ Found period match by start date:', {
                            start: normalizedStart,
                            period: { start: periodStartNorm, end: normalizeDate(period.end_date), period: period.period }
                        });
                    }
                    return match;
                });
            }
            
            // Final fallback: match by period label if available (e.g., "Week 3", "Week 2", "Week 1")
            if (!selectedPeriodData && periodLabel) {
                console.log('Trying to match by period label:', periodLabel);
                selectedPeriodData = state.employeeData.find(period => {
                    const match = period.period && period.period === periodLabel;
                    if (match) {
                        console.log('✓ Found period match by label:', {
                            period: periodLabel,
                            found: { start: period.start_date, end: period.end_date, period: period.period }
                        });
                    }
                    return match;
                });
            }
            
            if (!selectedPeriodData) {
                console.error('❌ No matching period found for:', {
                    startDate: normalizedStart,
                    endDate: normalizedEnd,
                    period: periodLabel,
                    availablePeriods: state.employeeData.map(p => ({
                        start: p.start_date,
                        end: p.end_date,
                        period: p.period
                    }))
                });
            }
        }
        
        if (!selectedPeriodData) {
            state.employeeChartData = { labels: [], values: [] };
            return;
        }
        
        const employees = [];
        
        if (selectedPeriodData.employees && Array.isArray(selectedPeriodData.employees)) {
            selectedPeriodData.employees.forEach(emp => {
                employees.push({
                    employee_id: emp.employee_id,
                    employee_name: emp.employee_name || 'N/A',
                    actual_value: Number(emp.actual_value || 0)
                });
            });
        }

        employees.sort((a, b) => b.actual_value - a.actual_value);

        state.employeeChartData = {
            labels: employees.map(emp => emp.employee_name),
            values: employees.map(emp => emp.actual_value)
        };
    }
    
    function buildLeadsChartData() {
        if (!state.employeeData || state.employeeData.length === 0) {
            state.employeeChartData = null;
            return;
        }

        let selectedPeriodData = null;
        
        if (state.selectedPeriodInfo && (state.selectedPeriodInfo.startDate || state.selectedPeriodInfo.endDate)) {
            const periodStart = String(state.selectedPeriodInfo.startDate || '').trim();
            const periodEnd = String(state.selectedPeriodInfo.endDate || '').trim();
            
            const normalizeDate = (dateStr) => {
                if (!dateStr) return null;
                const str = String(dateStr).trim();
                if (str.match(/^\d{2}-\d{2}-\d{4}$/)) {
                    return str;
                }
                return str;
            };
            
            const normalizedStart = normalizeDate(periodStart);
            const normalizedEnd = normalizeDate(periodEnd);
            
            selectedPeriodData = state.employeeData.find(period => {
                const periodStartNorm = normalizeDate(period.start_date);
                const periodEndNorm = normalizeDate(period.end_date);
                
                if (normalizedStart && normalizedEnd && periodStartNorm && periodEndNorm) {
                    return periodStartNorm === normalizedStart && periodEndNorm === normalizedEnd;
                }
                return false;
            });
            
            if (!selectedPeriodData && normalizedStart) {
                selectedPeriodData = state.employeeData.find(period => {
                    const periodStartNorm = normalizeDate(period.start_date);
                    return periodStartNorm === normalizedStart;
                });
            }
            
            if (!selectedPeriodData && state.selectedPeriodInfo.period) {
                selectedPeriodData = state.employeeData.find(period => {
                    return period.period && period.period === state.selectedPeriodInfo.period;
                });
            }
        }
        
        if (!selectedPeriodData) {
            state.employeeChartData = { labels: [], values: [], conversionValues: [] };
            return;
        }
        
        const sources = [];
        
        if (selectedPeriodData.sources && Array.isArray(selectedPeriodData.sources)) {
            selectedPeriodData.sources.forEach(source => {
                sources.push({
                    source_id: source.source_id,
                    source_name: source.source_name || 'N/A',
                    lead_value: Number(source.lead_value || 0),
                    quality_lead_value: Number(source.quality_lead_value || 0)
                });
            });
        }

        sources.sort((a, b) => b.lead_value - a.lead_value);

        state.employeeChartData = {
            labels: sources.map(s => s.source_name),
            values: sources.map(s => s.lead_value),
            conversionValues: sources.map(s => s.quality_lead_value)
        };
    }
    
    function renderEmployeeChart() {
        try {
            const canvas = document.getElementById('employeeChartCanvas');
            const placeholder = document.getElementById('employee-chart-placeholder');
            const container = document.getElementById('employee-chart-container');
            
            if (!canvas || !placeholder || !container) {
                return;
            }
            
            if (state.employeeDataLoading || state.employeeError || !state.employeeChartData || !state.employeeChartData.labels || state.employeeChartData.labels.length === 0) {
                placeholder.style.display = 'block';
                placeholder.textContent = getEmployeePlaceholderMessage();
                container.style.display = 'none';
                if (employeeChart) {
                    employeeChart.destroy();
                    employeeChart = null;
                }
                return;
            }
            
            placeholder.style.display = 'none';
            container.style.display = 'block';
            
            if (employeeChart) {
                employeeChart.destroy();
                employeeChart = null;
            }
            
            if (!state.employeeChartData.values || !Array.isArray(state.employeeChartData.values)) {
                return;
            }

            const scoreNameLower = (state.scoreName || '').toLowerCase();
            const isLeadsScore = scoreNameLower === 'leads';
            const isLabourScore = scoreNameLower === 'labour';

            const datasets = [];
            
            if (isLeadsScore) {
                datasets.push({
                    label: 'Leads',
                    data: state.employeeChartData.values,
                    backgroundColor: '#0d6efd',
                    borderColor: '#0d6efd',
                    borderWidth: 1,
                    borderRadius: 4
                });
                
                if (state.employeeChartData.conversionValues && Array.isArray(state.employeeChartData.conversionValues)) {
                    datasets.push({
                        label: 'Quality Leads',
                        data: state.employeeChartData.conversionValues,
                        backgroundColor: '#198754',
                        borderColor: '#198754',
                        borderWidth: 1,
                        borderRadius: 4
                    });
                }
            } else {
                datasets.push({
                    label: 'Labour',
                    data: state.employeeChartData.values,
                    backgroundColor: '#0d6efd',
                    borderColor: '#0d6efd',
                    borderWidth: 1,
                    borderRadius: 4
                });
            }

            const allValues = datasets.flatMap(dataset => (dataset.data || []));
            const maxValue = allValues.length > 0 ? Math.max(...allValues, 0) : 0;
            const suggestedMax = maxValue > 0 ? maxValue * 1.1 : 100;

            employeeChart = new Chart(canvas, {
                type: 'bar',
                data: {
                    labels: state.employeeChartData.labels,
                    datasets: datasets
                },
                options: {
                    indexAxis: 'y',
                    maintainAspectRatio: false,
                    responsive: true,
                    plugins: {
                        legend: {
                            display: isLeadsScore,
                            position: 'top',
                            align: 'end',
                            labels: {
                                usePointStyle: true,
                                padding: 15,
                                font: { size: 12 }
                            }
                        },
                        tooltip: {
                            callbacks: {
                                label: (context) => {
                                    const value = context.parsed.x || 0;
                                    const datasetLabel = context.dataset.label || 'Value';
                                    return `${datasetLabel}: ${value.toFixed(isLabourScore ? 2 : 0)}`;
                                }
                            }
                        }
                    },
                    scales: {
                        x: {
                            beginAtZero: true,
                            suggestedMax: suggestedMax,
                            grid: { color: 'rgba(0, 0, 0, 0.1)' },
                            ticks: {
                                color: '#111827',
                                font: { size: 11 },
                                stepSize: isLabourScore ? undefined : 1, // Allow decimal steps for Labour
                                maxTicksLimit: isLabourScore ? 10 : Math.ceil(suggestedMax) + 1,
                                callback: (value) => {
                                    if (isLabourScore) {
                                        // For Labour scores, show decimal values
                                        if (value >= 1000) {
                                            return (value / 1000).toFixed(2) + 'k';
                                        }
                                        return value.toFixed(2);
                                    } else {
                                        // For other scores (Leads), show integer values
                                        const intValue = Math.round(value);
                                        if (Math.abs(value - intValue) > 0.01) {
                                            return '';
                                        }
                                        if (intValue >= 1000) {
                                            return (intValue / 1000).toFixed(1) + 'k';
                                        }
                                        return intValue.toFixed(0);
                                    }
                                },
                                afterBuildTicks: (axis) => {
                                    if (!isLabourScore) {
                                        // Only filter duplicates for non-Labour scores
                                        const seen = new Set();
                                        axis.ticks = axis.ticks.filter(tick => {
                                            const rounded = Math.round(tick.value);
                                            if (seen.has(rounded)) {
                                                return false;
                                            }
                                            seen.add(rounded);
                                            return true;
                                        });
                                    }
                                }
                            }
                        },
                        y: {
                            grid: { display: false },
                            ticks: {
                                color: '#111827',
                                font: { size: 11 }
                            }
                        }
                    }
                }
            });
        } catch (error) {
            console.error('Error rendering employee chart:', error);
            const placeholder = document.getElementById('employee-chart-placeholder');
            const container = document.getElementById('employee-chart-container');
            if (placeholder) {
                placeholder.style.display = 'block';
                placeholder.textContent = 'Error rendering chart. Please try again.';
            }
            if (container) {
                container.style.display = 'none';
            }
            if (employeeChart) {
                employeeChart.destroy();
                employeeChart = null;
            }
        }
    }
    
    function getEmployeePlaceholderMessage() {
        if (state.employeeDataLoading) {
            return 'Loading employee/source data...';
        }
        if (state.employeeError) {
            return state.employeeError;
        }
        const scoreNameLower = (state.scoreName || '').toLowerCase();
        if (scoreNameLower === 'labour') {
            return 'Select a department in the Department Breakdown to view employee labour.';
        } else if (scoreNameLower === 'leads') {
            return 'Select a medium in the Department Breakdown to view leads by source.';
        }
        return 'Select a department/medium in the Department Breakdown to view details.';
    }
    
    // Load score data
    async function loadScoreData() {
        try {
            if (!state.scoreId) {
                console.warn("ScoreDashboard: Missing scoreId");
                state.loading = false;
                renderDashboard();
                return;
            }
            
            if (!jwtToken) {
                jwtToken = getStoredToken();
                if (!jwtToken) {
                    window.location.href = '/bizdom/dashboard/public';
                    return;
                }
            }
            
            state.loading = true;
            // Chart should already be destroyed in switchFilter, but ensure it's destroyed
            if (chart) {
                chart.destroy();
                chart = null;
            }
            isRenderingChart = false; // Reset flag when loading starts
            // Only render if not already showing loading (to avoid flicker)
            if (!document.querySelector('.chart-loading-overlay')) {
                renderDashboard();
            } else {
                // Just ensure loading overlay is visible
                updateLoadingOverlay(true);
            }
            
            const activeRange = ensureActiveRange();
            const preset = getPresetRange(state.filterType);
            state.dateRangeLabel = preset.label;
            
            // Build URL - quadrant_api.py only needs dates for Custom filter
            let url = `${API_BASE}?scoreId=${state.scoreId}&filterType=${state.filterType}`;
            if (state.filterType === 'Custom' && activeRange.start && activeRange.end) {
                url += `&startDate=${formatDateForQuadrantAPI(activeRange.start)}&endDate=${formatDateForQuadrantAPI(activeRange.end)}`;
            }
            
            const response = await fetch(url, {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${jwtToken}`
                }
            });
            
            if (response.status === 401) {
                localStorage.removeItem('jwt_token');
                window.location.href = '/bizdom/dashboard/public';
                return;
            }
            
            // Handle response - quadrant_api.py may return string JSON
            let responseText = await response.text();
            console.log('Raw response text:', responseText.substring(0, 200)); // Log first 200 chars
            
            let scoreData;
            try {
                // Try parsing as JSON (handles both string and object responses)
                scoreData = JSON.parse(responseText);
                console.log('Parsed score data:', scoreData);
            } catch (e) {
                console.error("Error parsing JSON response:", e, "Response text:", responseText);
                // If already parsed or invalid, try as is
                try {
                    scoreData = JSON.parse(responseText);
                } catch (e2) {
                    console.error("Invalid response format from server:", e2);
                    throw new Error('Invalid response format from server');
                }
            }
            
            if (scoreData && scoreData.statusCode === 200) {
                state.score = scoreData;
                if (scoreData.score_name) {
                    state.scoreName = scoreData.score_name;
                }
                // Store score type for formatting
                state.scoreType = scoreData.score_type || 'value';
                // quadrant_api.py returns 'overview', not 'overview_list'
                const overviewData = scoreData.overview || scoreData.overview_list || [];
                console.log('Score data received:', {
                    statusCode: scoreData.statusCode,
                    score_name: scoreData.score_name,
                    score_type: state.scoreType,
                    overview_length: overviewData.length,
                    overview: overviewData
                });
                
                state.quadrants.q1 = {
                    title: scoreData.message || 'Score Overview',
                    data: overviewData,
                    filter_type: state.filterType,
                    score_name: scoreData.score_name
                };
            } else {
                console.error('Invalid response from API:', scoreData);
            }
        } catch (error) {
            console.error("Error loading score data:", error);
            state.quadrants.q1 = {
                title: 'Score Overview',
                data: [],
                filter_type: state.filterType,
                score_name: state.scoreName
            };
        } finally {
            state.loading = false;
            // Render dashboard first to update content
            renderDashboard();
            // Apply scrolling fix after data loads
            setTimeout(() => fixPublicScoreDashboardScrolling(), 100);
            // Hide loading overlay smoothly after a brief delay to ensure smooth transition
            setTimeout(() => {
                updateLoadingOverlay(false);
                disableFilterButtons(false);
            }, 50);
            // Always try to render chart, even if data is empty (will show "No data available")
            // Use a single timeout to prevent double rendering
            setTimeout(() => {
                try {
                    if (state.quadrants.q1.data && state.quadrants.q1.data.length > 0 && !isRenderingChart) {
                        renderChart();
                    } else if (!state.quadrants.q1.data || state.quadrants.q1.data.length === 0) {
                        console.warn('No data available for chart. Quadrant data:', state.quadrants.q1);
                    }
                } catch (error) {
                    console.error('Error in chart rendering timeout:', error);
                    isRenderingChart = false;
                }
            }, 250);
        }
    }
    
    // Get chart data
    function getChartData() {
        try {
            const data = state.quadrants.q1.data;
            if (!data || data.length === 0) {
                originalChartData = [];
                return { labels: [], datasets: [] };
            }
            
            originalChartData = data;
        
        const labels = data.map(item => {
            const periodLabel = getPeriodLabel(item, state.quadrants.q1.filter_type);
            let dateRange = '';
            
            // Always try to create date range if we have dates
            if (item.start_date && item.end_date) {
                try {
                    const startDate = formatDateForTooltip(item.start_date);
                    const endDate = formatDateForTooltip(item.end_date);
                    
                    // Use formatted dates if they're valid
                    if (startDate && endDate && 
                        !startDate.includes('Invalid') && 
                        !endDate.includes('Invalid') &&
                        startDate !== '' && 
                        endDate !== '') {
                        dateRange = `${startDate} - ${endDate}`;
                    } else {
                        // If formatting fails, try to use the raw dates
                        dateRange = `${item.start_date} - ${item.end_date}`;
                    }
                } catch (error) {
                    // Fallback to raw dates if formatting fails
                    dateRange = `${item.start_date} - ${item.end_date}`;
                }
            } else if (item.start_date || item.end_date) {
                // If only one date is available, use it
                const singleDate = item.start_date || item.end_date;
                try {
                    const formattedDate = formatDateForTooltip(singleDate);
                    if (formattedDate && !formattedDate.includes('Invalid') && formattedDate !== '') {
                        dateRange = formattedDate;
                    } else {
                        dateRange = singleDate;
                    }
                } catch (error) {
                    dateRange = singleDate;
                }
            }
            
            return {
                period: periodLabel,
                dateRange: dateRange
            };
        });
        
        const values = data.map(item => Number(item.actual_value || 0));
        
        // Check if this is Leads or Conversion score - check both state and quadrant data
        const scoreNameToCheck = state.scoreName || state.quadrants.q1.score_name || '';
        const isLeadsScore = scoreNameToCheck && scoreNameToCheck.toLowerCase().includes('lead') && !scoreNameToCheck.toLowerCase().includes('conversion');
        const isConversionScore = scoreNameToCheck && scoreNameToCheck.toLowerCase().includes('conversion');
        
        // Check for quality_lead field - for Leads and Conversion scores, show it even if values are 0
        const hasConversionValues = (isLeadsScore || isConversionScore) && data.some(item => {
            const convValue = item.quality_lead;
            // Field exists (even if 0) - we want to show it for Leads and Conversion
            return convValue !== undefined && convValue !== null;
        });
        
        console.log('Chart data check:', {
            scoreName: state.scoreName,
            quadrantScoreName: state.quadrants.q1.score_name,
            scoreNameToCheck: scoreNameToCheck,
            isLeadsScore: isLeadsScore,
            isConversionScore: isConversionScore,
            hasConversionValues: hasConversionValues,
            sampleItem: data[0],
            conversionValueInFirstItem: data[0]?.quality_lead,
            allConversionValues: data.map(item => item.quality_lead)
        });
        
        const datasets = [{
            label: isLeadsScore ? 'Leads' : (isConversionScore ? 'Conversions' : (scoreNameToCheck || 'Total')),
            data: values,
            backgroundColor: '#0d6efd',
            borderColor: '#0d6efd',
            borderWidth: 1,
            borderRadius: 4
        }];
        
        // Add quality leads dataset if this is Leads or Conversion score and has conversion values
        // hasConversionValues already checks for isLeadsScore or isConversionScore
        if (hasConversionValues) {
            const conversionValues = data.map(item => {
                const convValue = item.quality_lead;
                // Handle both string and number conversion values
                if (typeof convValue === 'string') {
                    return Number(convValue) || 0;
                }
                return Number(convValue || 0);
            });
            
            console.log('Adding quality leads dataset:', {
                conversionValues: conversionValues,
                length: conversionValues.length,
                isLeadsScore: isLeadsScore,
                isConversionScore: isConversionScore
            });
            
            datasets.push({
                label: 'Quality Leads',
                data: conversionValues,
                backgroundColor: '#198754',
                borderColor: '#198754',
                borderWidth: 1,
                borderRadius: 4
            });
        } else {
            console.log('Not adding quality leads dataset:', {
                isLeadsScore: isLeadsScore,
                isConversionScore: isConversionScore,
                hasConversionValues: hasConversionValues
            });
        }
        
            return {
                labels: labels,
                datasets: datasets
            };
        } catch (error) {
            console.error('Error in getChartData:', error);
            originalChartData = [];
            return { labels: [], datasets: [] };
        }
    }
    
    // Render chart
    function renderChart() {
        // Prevent duplicate renders
        if (isRenderingChart && chart) {
            console.log('Skipping duplicate chart render');
            return;
        }
        
        try {
            isRenderingChart = true;
            
            if (chart) {
                chart.destroy();
                chart = null;
            }
            
            const canvas = document.getElementById('chartCanvas');
            if (!canvas) {
                isRenderingChart = false;
                return;
            }
            
            const chartData = getChartData();
            if (!chartData || !chartData.labels || chartData.labels.length === 0) {
                return;
            }
            
            if (!chartData.datasets || chartData.datasets.length === 0) {
                return;
            }
        
        // Calculate max value across all datasets
        const allValues = chartData.datasets.flatMap(dataset => (dataset.data || []));
        const maxValue = allValues.length > 0 ? Math.max(...allValues, 0) : 0;
        const suggestedMax = maxValue > 0 ? maxValue * 1.1 : 100;
        const isPercentage = state.scoreType === 'percentage';
        
        // Check if we have conversion values (Leads score)
        const hasConversionValues = chartData.datasets.length > 1;
        
        // Detect mobile device
        const isMobile = window.innerWidth < 768;
        const isSmallMobile = window.innerWidth < 480;
        
        // Helper function to format date range for mobile
        function formatDateRangeForMobile(dateRange) {
            if (!dateRange) return '';
            if (isSmallMobile) {
                // For very small screens, use a compact format
                // "01 Jan 2025 - 15 Jan 2025" -> "01-15 Jan"
                const parts = dateRange.split(' - ');
                if (parts.length === 2) {
                    const start = parts[0].trim();
                    const end = parts[1].trim();
                    // Extract day and month from start, day from end
                    const startMatch = start.match(/(\d{1,2})\s+(\w{3})/);
                    const endMatch = end.match(/(\d{1,2})/);
                    if (startMatch && endMatch) {
                        return `${startMatch[1]}-${endMatch[1]} ${startMatch[2]}`;
                    }
                }
            } else if (isMobile) {
                // For mobile, use shorter format
                // "01 Jan 2025 - 15 Jan 2025" -> "01-15 Jan 2025"
                const parts = dateRange.split(' - ');
                if (parts.length === 2) {
                    const start = parts[0].trim();
                    const end = parts[1].trim();
                    const startMatch = start.match(/(\d{1,2})\s+(\w{3})\s+(\d{4})/);
                    const endMatch = end.match(/(\d{1,2})/);
                    if (startMatch && endMatch) {
                        return `${startMatch[1]}-${endMatch[1]} ${startMatch[2]} ${startMatch[3]}`;
                    }
                }
            }
            return dateRange;
        }
        
        // Custom plugin to draw date ranges below x-axis labels
        // On very small screens, hide date ranges to prevent clustering
        const dateRangePlugin = {
            id: 'dateRangePlugin',
            afterDraw: (chart) => {
                // Don't draw date ranges on very small screens - show in tooltip instead
                if (isSmallMobile) {
                    return;
                }
                
                const ctx = chart.ctx;
                const xAxis = chart.scales.x;
                const chartArea = chart.chartArea;
                const labels = chartData.labels;
                
                ctx.save();
                
                // Responsive font size
                const fontSize = isMobile ? 8 : 10;
                ctx.font = `${fontSize}px Arial`;
                ctx.fillStyle = '#6c757d';
                ctx.textAlign = 'center';
                ctx.textBaseline = 'top';
                
                // Calculate spacing to prevent overlap
                const barWidth = xAxis.width / labels.length;
                
                labels.forEach((label, index) => {
                    if (label && typeof label === 'object' && label.dateRange && label.dateRange.trim() !== '') {
                        try {
                            const x = xAxis.getPixelForTick(index);
                            if (!isNaN(x)) {
                                // Check if there's enough space
                                const nextX = index < labels.length - 1 ? xAxis.getPixelForTick(index + 1) : x + barWidth;
                                const availableWidth = nextX - x;
                                
                                // Format date range for mobile
                                const displayText = formatDateRangeForMobile(label.dateRange);
                                
                                // Measure text width
                                const textMetrics = ctx.measureText(displayText);
                                const textWidth = textMetrics.width;
                                
                                // Only draw if there's enough space (at least 80% of available width)
                                if (textWidth <= availableWidth * 0.8) {
                                    const y = chartArea.bottom + (isMobile ? 15 : 25);
                                    ctx.fillText(displayText, x, y);
                                }
                                // If not enough space, skip drawing this date range to prevent overlap
                            }
                        } catch (error) {
                            console.warn('Error drawing date range:', error);
                        }
                    }
                });
                
                ctx.restore();
            }
        };
        
        const config = {
            type: 'bar',
            data: chartData,
            plugins: [dateRangePlugin],
            options: {
                maintainAspectRatio: false,
                responsive: true,
                layout: {
                    padding: {
                        // Reduce padding on small screens since date ranges are hidden
                        bottom: isSmallMobile ? 10 : isMobile ? 50 : 40
                    }
                },
                plugins: {
                    title: {
                        display: false
                    },
                    legend: {
                        display: true,
                        position: 'top',
                        align: 'end',
                        labels: {
                            usePointStyle: true,
                            padding: 15,
                            font: {
                                size: 12
                            }
                        }
                    },
                    tooltip: {
                        enabled: true,
                        backgroundColor: 'rgba(0, 0, 0, 0.8)',
                        padding: 10,
                        titleFont: {
                            size: isMobile ? 12 : 13
                        },
                        bodyFont: {
                            size: isMobile ? 14 : 16,
                            weight: 'bold'
                        },
                        callbacks: {
                            title: () => {
                                // Hide title, we'll show it in afterLabel instead
                                return '';
                            },
                            label: (context) => {
                                const value = context.parsed.y;
                                const datasetLabel = context.dataset.label || 'Value';
                                // Show exact value with 2 decimal places
                                const formattedValue = value.toFixed(2);
                                const suffix = isPercentage ? '%' : '';
                                return `${datasetLabel}: ${formattedValue}${suffix}`;
                            },
                            afterLabel: (context) => {
                                // Show period/title after the value
                                // Only show once per tooltip (for the first dataset)
                                if (context.datasetIndex === 0) {
                                    const dataIndex = context.dataIndex;
                                    const label = chartData.labels[dataIndex];
                                    if (label && typeof label === 'object' && label.period) {
                                        return label.period;
                                    }
                                }
                                return '';
                            },
                            afterBody: (tooltipItems) => {
                                // Show date range only on mobile devices
                                const currentIsMobile = window.innerWidth < 768;
                                if (!currentIsMobile) {
                                    return '';
                                }
                                // Show date range at the bottom (e.g., "01 Jan 2025 - 31 Jan 2025")
                                if (!tooltipItems || tooltipItems.length === 0) {
                                    return '';
                                }
                                const tooltipItem = tooltipItems[0];
                                if (!tooltipItem || tooltipItem.dataIndex === undefined) {
                                    return '';
                                }
                                const dataIndex = tooltipItem.dataIndex;
                                const label = chartData.labels[dataIndex];
                                
                                // Try to get dateRange from label
                                if (label && typeof label === 'object' && label.dateRange && label.dateRange.trim() !== '') {
                                    return label.dateRange;
                                }
                                
                                // Fallback: get dates from original data
                                const originalData = originalChartData[dataIndex];
                                if (originalData && originalData.start_date && originalData.end_date) {
                                    try {
                                        const startDate = formatDateForTooltip(originalData.start_date);
                                        const endDate = formatDateForTooltip(originalData.end_date);
                                        if (startDate && endDate && 
                                            !startDate.includes('Invalid') && 
                                            !endDate.includes('Invalid') &&
                                            startDate !== '' && 
                                            endDate !== '') {
                                            return `${startDate} - ${endDate}`;
                                        }
                                    } catch (error) {
                                        // If formatting fails, use raw dates
                                        return `${originalData.start_date} - ${originalData.end_date}`;
                                    }
                                }
                                
                                return '';
                            }
                        },
                        displayColors: false
                    }
                },
                scales: {
                    x: {
                        grid: {
                            display: false,
                            color: 'transparent'
                        },
                        border: {
                            display: false
                        },
                        ticks: {
                            color: '#111827',
                            font: {
                                size: isMobile ? 10 : 11
                            },
                            maxRotation: isMobile ? 45 : 0,
                            minRotation: isMobile ? 45 : 0,
                            autoSkip: isMobile,
                            maxTicksLimit: isSmallMobile ? 3 : isMobile ? 5 : undefined,
                            callback: (value, index) => {
                                const label = chartData.labels[index];
                                if (label && typeof label === 'object') {
                                    // Truncate period label on small screens
                                    const period = label.period || '';
                                    if (isSmallMobile && period.length > 8) {
                                        return period.substring(0, 6) + '...';
                                    }
                                    return period;
                                }
                                return label || '';
                            }
                        }
                    },
                    y: {
                        beginAtZero: true,
                        grid: {
                            color: 'rgba(0, 0, 0, 0.1)',
                            drawBorder: false
                        },
                        border: {
                            display: false
                        },
                        ticks: {
                            color: '#111827',
                            font: {
                                size: 11
                            },
                            callback: function(value) {
                                const suffix = state.scoreType === 'percentage' ? '%' : '';
                                if (value >= 1000) {
                                    return (value / 1000).toFixed(2) + 'k' + suffix;
                                }
                                return value.toFixed(2) + suffix;
                            }
                        },
                        suggestedMax: suggestedMax
                    }
                },
                animation: {
                    duration: 600,
                    delay: (context) => {
                        let delay = 0;
                        if (context.type === 'data' && context.mode === 'default') {
                            delay = context.dataIndex * 50;
                        }
                        return delay;
                    }
                }
            }
        };
        
        chart = new Chart(canvas, config);
        
        // Reset rendering flag after chart is successfully created
        isRenderingChart = false;
        
            canvas.onclick = async (event) => {
                if (!chart) {
                    return;
                }
                try {
                    const points = chart.getElementsAtEventForMode(event, 'nearest', { intersect: true }, true);
                    if (!points || points.length === 0) {
                        return;
                    }
                    const firstPoint = points[0];
                    const dataIndex = firstPoint.index;
                    // Only trigger on click of the first dataset (Leads) to avoid duplicate clicks
                    if (firstPoint.datasetIndex === 0) {
                        const selectedData = (state.quadrants.q1.data || [])[dataIndex];
                        if (selectedData) {
                            await handleOverviewBarClick(selectedData);
                        }
                    }
                } catch (error) {
                    console.error('Error handling chart click:', error);
                }
            };
        } catch (error) {
            console.error('Error rendering chart:', error);
            isRenderingChart = false; // Reset flag on error
        }
    }
    
    // Switch filter
    function switchFilter(filterType) {
        if (state.filterType === filterType.toUpperCase()) {
            return;
        }
        
        // Destroy chart immediately before changing state for smooth transition
        if (chart) {
            chart.destroy();
            chart = null;
        }
        isRenderingChart = false; // Reset flag when changing filters
        
        // Set loading state immediately for smooth transition
        state.loading = true;
        state.filterType = filterType.toUpperCase();
        
        // Update loading overlay immediately without full re-render
        updateLoadingOverlay(true);
        disableFilterButtons(true);
        
        resetDepartmentState();
        resetEmployeeState();
        loadScoreData();
        // Apply scrolling fix after filter switch
        setTimeout(() => fixPublicScoreDashboardScrolling(), 100);
    }
    
    // Update loading overlay smoothly
    function updateLoadingOverlay(show) {
        const cardBody = document.querySelector('.card-body.position-relative');
        if (!cardBody) {
            // If card body doesn't exist yet, do full render
            renderDashboard();
            return;
        }
        
        let overlay = cardBody.querySelector('.chart-loading-overlay');
        const chartContainer = cardBody.querySelector('.chart-container');
        
        if (show) {
            if (!overlay) {
                overlay = document.createElement('div');
                overlay.className = 'chart-loading-overlay';
                overlay.innerHTML = `
                    <div class="spinner-container">
                        <div class="spinner-border text-primary" role="status">
                            <span class="visually-hidden">Loading...</span>
                        </div>
                        <p class="mt-3 text-muted">Loading chart data...</p>
                    </div>
                `;
                cardBody.appendChild(overlay);
            }
            overlay.style.display = 'flex';
            
            if (chartContainer) {
                chartContainer.classList.add('chart-loading');
            }
        } else {
            if (overlay) {
                overlay.style.display = 'none';
            }
            if (chartContainer) {
                chartContainer.classList.remove('chart-loading');
            }
        }
    }
    
    // Disable/enable filter buttons
    function disableFilterButtons(disable) {
        const buttons = document.querySelectorAll('.filter-group .btn');
        buttons.forEach(btn => {
            if (disable) {
                btn.disabled = true;
                btn.style.opacity = '0.6';
                btn.style.cursor = 'not-allowed';
            } else {
                btn.disabled = false;
                btn.style.opacity = '1';
                btn.style.cursor = 'pointer';
            }
        });
    }
    
    // Navigate back
    function navigateBack() {
        window.location.href = '/bizdom/dashboard/public';
    }
    
    // Render dashboard
    function renderDashboard() {
        const container = document.getElementById('score-dashboard-content');
        const loadingEl = document.getElementById('loading-indicator');
        
        if (!container) {
            console.error('Score dashboard container not found!');
            return;
        }
        
        if (state.loading) {
            loadingEl.style.display = 'flex';
            container.style.display = 'none';
            return;
        }
        
        loadingEl.style.display = 'none';
        container.style.display = 'block';
        
        const departmentPlaceholderText = getDepartmentPlaceholderMessage();
        
        const html = `
            <div class="container" style="padding: 2rem; background: #f5f7fa; min-height: 100vh;">
                <div class="d-flex justify-content-between align-items-center mb-4 flex-wrap gap-3">
                    <div class="d-flex align-items-center">
                        <button class="btn btn-link me-3" onclick="window.navigateBack()" style="text-decoration: none;">
                            <i class="fa fa-arrow-left me-1"></i> Back to Dashboard
                        </button>
                        <h2 class="mb-0">${state.scoreName} Dashboard</h2>
                    </div>
                    <div class="btn-group filter-group ms-auto">
                        <button type="button" 
                                class="btn btn-sm ${state.filterType === 'WTD' ? 'btn-primary text-white' : 'btn-outline-primary'}"
                                ${state.loading ? 'disabled' : ''}
                                onclick="window.switchFilter('WTD')">
                            WTD
                        </button>
                        <button type="button" 
                                class="btn btn-sm ${state.filterType === 'MTD' ? 'btn-primary text-white' : 'btn-outline-primary'}"
                                ${state.loading ? 'disabled' : ''}
                                onclick="window.switchFilter('MTD')">
                            MTD
                        </button>
                        <button type="button" 
                                class="btn btn-sm ${state.filterType === 'YTD' ? 'btn-primary text-white' : 'btn-outline-primary'}"
                                ${state.loading ? 'disabled' : ''}
                                onclick="window.switchFilter('YTD')">
                            YTD
                        </button>
                    </div>
                </div>
                
                <div class="row mb-4">
                    <div class="col-md-6">
                        <div class="card h-100">
                            <div class="card-header bg-primary text-white">
                                <h5 class="card-title mb-0">${state.quadrants.q1.title}</h5>
                            </div>
                            <div class="card-body position-relative">
                                ${state.loading ? `
                                    <div class="chart-loading-overlay">
                                        <div class="spinner-container">
                                            <div class="spinner-border text-primary" role="status">
                                                <span class="visually-hidden">Loading...</span>
                                            </div>
                                            <p class="mt-3 text-muted">Loading chart data...</p>
                                        </div>
                                    </div>
                                ` : ''}
                                ${state.quadrants.q1.data.length > 0 ? `
                                    <div class="chart-container ${state.loading ? 'chart-loading' : ''}" style="position: relative; height: ${window.innerWidth < 480 ? '250px' : window.innerWidth < 768 ? '280px' : '300px'}; width: 100%; padding: 10px; overflow-x: auto;">
                                        <canvas id="chartCanvas"></canvas>
                                    </div>
                                ` : !state.loading ? `
                                    <div class="text-muted text-center p-4">
                                        <i class="fa fa-info-circle mb-2" style="font-size: 2rem; opacity: 0.5;"></i>
                                        <p class="mb-0">No data available for ${state.scoreName || 'this score'}</p>
                                        <small>Try selecting a different filter or check if the score has data for this period.</small>
                                    </div>
                                ` : ''}
                            </div>
                        </div>
                    </div>
                    <div class="col-md-6">
                        <div class="card h-100">
                            <div class="card-header bg-success text-white">
                                <div class="d-flex justify-content-between align-items-center">
                                    <h5 class="card-title mb-0">${state.quadrants.q2.title}</h5>
                                    <small id="department-chart-period" class="text-white-50">${state.departmentChartLabel || ''}</small>
                                </div>
                            </div>
                            <div class="card-body">
                                <div id="department-chart-placeholder" class="text-muted text-center p-4">
                                    ${departmentPlaceholderText}
                                </div>
                                <div id="department-chart-container" style="position: relative; height: ${window.innerWidth < 480 ? '250px' : window.innerWidth < 768 ? '280px' : '300px'}; width: 100%; padding: 10px; display: none; overflow-x: auto;">
                                    <canvas id="departmentChartCanvas"></canvas>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
                
                <div class="row">
                    <div class="col-md-6">
                        <div class="card h-100">
                            <div class="card-header bg-warning text-dark">
                                <div class="d-flex justify-content-between align-items-center">
                                    <h5 class="card-title mb-0">
                                        ${(() => {
                                            const scoreNameLower = (state.scoreName || '').toLowerCase();
                                            if (scoreNameLower === 'labour') return 'Employee Labour';
                                            if (scoreNameLower === 'leads') return 'Leads by Source';
                                            return state.quadrants.q3.title;
                                        })()}
                                    </h5>
                                    ${(() => {
                                        const scoreNameLower = (state.scoreName || '').toLowerCase();
                                        if (scoreNameLower === 'labour' || scoreNameLower === 'leads') {
                                            return `<small class="text-dark-50">${state.employeeChartLabel || ''}</small>`;
                                        }
                                        return '';
                                    })()}
                                </div>
                            </div>
                            <div class="card-body">
                                ${(() => {
                                    const scoreNameLower = (state.scoreName || '').toLowerCase();
                                    if (scoreNameLower === 'labour' || scoreNameLower === 'leads') {
                                        return `
                                            <div id="employee-chart-placeholder" class="text-muted text-center p-4">
                                                ${getEmployeePlaceholderMessage()}
                                            </div>
                                            <div id="employee-chart-container" style="position: relative; height: ${window.innerWidth < 480 ? '250px' : window.innerWidth < 768 ? '280px' : '300px'}; width: 100%; padding: 10px; display: none; overflow-x: auto;">
                                                <canvas id="employeeChartCanvas"></canvas>
                                            </div>
                                        `;
                                    } else {
                                        return state.quadrants.q3.data.length > 0 ? 
                                            state.quadrants.q3.data.map(item => `
                                                <div class="mb-2">
                                                    <span>${item.label || ''}</span>: <span>${item.value || ''}</span>
                                                </div>
                                            `).join('') : 
                                            '<div class="text-muted">No data available</div>';
                                    }
                                })()}
                            </div>
                        </div>
                    </div>
                    <div class="col-md-6">
                        <div class="card h-100">
                            <div class="card-header bg-danger text-white">
                                <h5 class="card-title mb-0">${state.quadrants.q4.title}</h5>
                            </div>
                            <div class="card-body">
                                ${state.quadrants.q4.data.length > 0 ? 
                                    state.quadrants.q4.data.map(item => `
                                        <div class="mb-2">
                                            <span>${item.label || ''}</span>: <span>${item.value || ''}</span>
                                        </div>
                                    `).join('') : 
                                    '<div class="text-muted">No data available</div>'
                                }
                            </div>
                        </div>
                    </div>
                </div>
            </div>
            <style>
                .filter-group .btn {
                    min-width: 70px;
                    text-transform: uppercase;
                    transition: all 0.2s ease;
                }
                .filter-group .btn:disabled {
                    opacity: 0.6;
                    cursor: not-allowed;
                }
                .chart-container {
                    overflow-x: auto;
                    overflow-y: hidden;
                    -webkit-overflow-scrolling: touch;
                    transition: opacity 0.3s ease, filter 0.3s ease;
                }
                .chart-container.chart-loading {
                    opacity: 0.5;
                    filter: blur(2px);
                    pointer-events: none;
                }
                .chart-loading-overlay {
                    position: absolute;
                    top: 0;
                    left: 0;
                    right: 0;
                    bottom: 0;
                    background-color: rgba(255, 255, 255, 0.9);
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    z-index: 10;
                    border-radius: 0.375rem;
                    animation: fadeIn 0.3s ease-in;
                }
                .spinner-container {
                    display: flex;
                    flex-direction: column;
                    align-items: center;
                    justify-content: center;
                }
                .spinner-container .spinner-border {
                    width: 3rem;
                    height: 3rem;
                    border-width: 0.3rem;
                }
                @keyframes fadeIn {
                    from {
                        opacity: 0;
                    }
                    to {
                        opacity: 1;
                    }
                }
                @media (max-width: 768px) {
                    .chart-container {
                        padding: 5px !important;
                        min-height: 250px;
                    }
                }
                @media (max-width: 480px) {
                    .chart-container {
                        padding: 5px !important;
                        min-height: 220px;
                    }
                }
            </style>
        `;
        
        container.innerHTML = html;
        
        // Apply scrolling fix after rendering
        if (!globalPublicScoreDashboardObserver) {
            globalPublicScoreDashboardObserver = fixPublicScoreDashboardScrolling();
        } else {
            fixPublicScoreDashboardScrolling();
        }
        
        // Don't render chart here - let loadScoreData handle it to avoid double rendering
        // Chart will be rendered in loadScoreData's finally block
        setTimeout(() => {
            try {
                renderDepartmentChart();
                renderEmployeeChart();
            } catch (error) {
                console.error('Error rendering charts in renderDashboard:', error);
            }
        }, 120);
    }
    
    // Make functions global
    window.switchFilter = switchFilter;
    window.navigateBack = navigateBack;
    window.updateLoadingOverlay = updateLoadingOverlay;
    window.disableFilterButtons = disableFilterButtons;
    
    // Initialize
    function initializeScoreDashboard() {
        jwtToken = getStoredToken();
        
        // Apply scrolling fix on initialization
        if (!globalPublicScoreDashboardObserver) {
            globalPublicScoreDashboardObserver = fixPublicScoreDashboardScrolling();
        }
        
        if (!jwtToken) {
            window.location.href = '/bizdom/dashboard/public';
            return;
        }
        
        const params = getUrlParams();
        state.scoreId = params.scoreId;
        state.scoreName = params.scoreName;
        state.filterType = params.filterType;
        
        if (!state.scoreId) {
            console.error('Score ID is required');
            window.location.href = '/bizdom/dashboard/public';
            return;
        }
        
        resetDepartmentState();
        loadScoreData();
    }
    
    // Wait for DOM and Chart.js to be ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => {
            // Apply scrolling fix after DOM is loaded
            setTimeout(() => fixPublicScoreDashboardScrolling(), 100);
            
            if (typeof Chart !== 'undefined') {
                initializeScoreDashboard();
            } else {
                window.addEventListener('load', initializeScoreDashboard);
            }
        });
    } else {
        // Apply scrolling fix immediately
        setTimeout(() => fixPublicScoreDashboardScrolling(), 100);
        
        if (typeof Chart !== 'undefined') {
            initializeScoreDashboard();
        } else {
            window.addEventListener('load', initializeScoreDashboard);
        }
    }
    
    // Global initialization: Apply scrolling fix when score dashboard is loaded
    // This ensures scrolling works for all score dashboard views
    if (typeof window !== 'undefined') {
        // Apply immediately if DOM is ready
        if (document.readyState === 'complete' || document.readyState === 'interactive') {
            setTimeout(() => fixPublicScoreDashboardScrolling(), 100);
        } else {
            window.addEventListener('load', () => {
                setTimeout(() => fixPublicScoreDashboardScrolling(), 100);
            });
        }
        
        // Also apply on DOMContentLoaded as backup
        document.addEventListener('DOMContentLoaded', () => {
            setTimeout(() => fixPublicScoreDashboardScrolling(), 100);
        });
        
        // Apply after a short delay to catch any late renders
        setTimeout(() => fixPublicScoreDashboardScrolling(), 100);
    }
})();

