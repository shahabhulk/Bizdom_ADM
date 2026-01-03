/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, useState, onMounted, useRef, useEffect, onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { loadBundle } from "@web/core/assets";

const DEPARTMENT_API = '/api/score/overview/department';
const SCORE_OVERVIEW_API = '/api/score/overview';
const EMPLOYEE_OVERVIEW_API = '/api/score/overview/employee';

// Global scrolling fix function for all score dashboards
function fixScoreDashboardScrolling() {
    // More aggressive approach to fix scrolling
    const applyScrollingFix = () => {
        // Find all relevant containers
        const contentContainer = document.querySelector('.o_action_manager .o_action .o_content');
        const actionContainer = document.querySelector('.o_action_manager .o_action');
        const actionManager = document.querySelector('.o_action_manager');
        
        if (contentContainer) {
            // Force scrolling on content container
            contentContainer.style.setProperty('overflow-y', 'auto', 'important');
            contentContainer.style.setProperty('height', 'auto', 'important');
            contentContainer.style.setProperty('min-height', '100%', 'important');
            contentContainer.style.setProperty('max-height', 'none', 'important');
            contentContainer.classList.add('o_score_dashboard_scrollable');
        }
        
        if (actionContainer) {
            // Allow action container to expand
            actionContainer.style.setProperty('overflow-y', 'auto', 'important');
            actionContainer.style.setProperty('height', 'auto', 'important');
            actionContainer.style.setProperty('max-height', 'none', 'important');
        }
        
        if (actionManager) {
            // Ensure action manager allows scrolling
            actionManager.style.setProperty('overflow-y', 'auto', 'important');
            actionManager.style.setProperty('height', 'auto', 'important');
        }
        
        // Also fix the renderer/wrapper if it exists
        const renderer = document.querySelector('.o_action_manager .o_action .o_content > div');
        if (renderer) {
            renderer.style.setProperty('min-height', '100%', 'important');
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
    
    // Observe the content container
    const contentContainer = document.querySelector('.o_action_manager .o_action .o_content');
    if (contentContainer) {
        observer.observe(contentContainer, {
            attributes: true,
            attributeFilter: ['style', 'class']
        });
    }
    
    // Also observe action container
    const actionContainer = document.querySelector('.o_action_manager .o_action');
    if (actionContainer) {
        observer.observe(actionContainer, {
            attributes: true,
            attributeFilter: ['style', 'class']
        });
    }
    
    return observer;
}

// Global observer instance
let globalScrollingObserver = null;

class ScoreDashboard extends Component {
    static template = "bizdom.ScoreDashboard";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        
        // Chart references
        this.chartRef = useRef("chartCanvas");
        this.chart = null;
        this.departmentChartRef = useRef("departmentChartCanvas");
        this.departmentChart = null;
        this.employeeChartRef = useRef("employeeChartCanvas");
        this.employeeChart = null;
        this.originalChartData = []; // Store original data for tooltip
        this.isRenderingChart = false; // Flag to prevent duplicate renders
        this.isRenderingChart = false; // Flag to prevent duplicate renders
        
        // Get props from action context
        const action = this.props?.action || {};
        const context = action.context || {};
        
        // Try to get scoreId from multiple sources (context, URL params, sessionStorage)
        let scoreId = context.scoreId || context.active_id || null;
        let scoreName = context.scoreName || action.name || 'Score';
        
        // If scoreId is not in context (e.g., on page refresh), try to get from URL or sessionStorage
        if (!scoreId) {
            // Try to get from URL parameters
            const urlParams = new URLSearchParams(window.location.search);
            const urlScoreId = urlParams.get('scoreId');
            if (urlScoreId) {
                scoreId = parseInt(urlScoreId);
                scoreName = urlParams.get('scoreName') || scoreName;
            } else {
                // Try to get from sessionStorage (stored when opening dashboard)
                const storedScoreId = sessionStorage.getItem('bizdom_scoreId');
                const storedScoreName = sessionStorage.getItem('bizdom_scoreName');
                if (storedScoreId) {
                    scoreId = parseInt(storedScoreId);
                    scoreName = storedScoreName || scoreName;
                }
            }
        } else {
            // Store in sessionStorage for refresh recovery
            sessionStorage.setItem('bizdom_scoreId', String(scoreId));
            if (scoreName) {
                sessionStorage.setItem('bizdom_scoreName', scoreName);
            }
        }
        
        const filterType = (context.current_filter || 'MTD').toUpperCase();
        const initialRange = this.computeInitialRange(filterType, context);
        const hasCustomRange = (context.current_filter || '').toUpperCase() === 'CUSTOM'
            && Boolean(context.date_range_start && context.date_range_end);
        
        this.state = useState({
            loading: true,
            score: null,
            scoreId: scoreId,
            scoreName: scoreName,
            scoreType: 'value',
            filterType: filterType,
            dateRangeLabel: initialRange.label,
            activeRange: initialRange.range,
            customRange: hasCustomRange ? { ...initialRange.range } : { start: "", end: "" },
            hasCustomRange: hasCustomRange,
            availableFilters: this.getAvailableFilters(filterType, hasCustomRange),
            quadrants: {
                q1: { title: "Score Overview", data: [], filter_type: filterType },
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
            selectedPeriodInfo: null, // Store period info (startDate, endDate, period) for filtering employees
        });

        onWillStart(async () => {
            await loadBundle("web.chartjs_lib");
        });

        onMounted(() => {
            this.loadScoreData();
            // Ensure scrolling works by fixing Odoo's height restrictions
            // Use global function for consistency across all score dashboards
            if (!globalScrollingObserver) {
                globalScrollingObserver = fixScoreDashboardScrolling();
            } else {
                // Reapply fix if observer already exists
                fixScoreDashboardScrolling();
            }
        });

        useEffect(() => {
            // Only render if we have data and are not loading, and not already rendering
            if (this.state.quadrants.q1.data && this.state.quadrants.q1.data.length > 0 && !this.state.loading && !this.isRenderingChart) {
                // Add a delay to ensure DOM is ready after template re-render
                setTimeout(() => {
                    try {
                        // Check if canvas exists before rendering and not already rendering
                        if (this.chartRef && this.chartRef.el && !this.isRenderingChart) {
                            this.isRenderingChart = true;
                            this.renderChart();
                            // Flag will be reset in renderChart after chart is created
                        } else if (!this.chartRef || !this.chartRef.el) {
                            // Retry if canvas is not ready yet
                            console.log('Canvas not ready, retrying in 200ms...');
                            setTimeout(() => {
                                if (this.chartRef && this.chartRef.el && this.state.quadrants.q1.data && this.state.quadrants.q1.data.length > 0 && !this.state.loading && !this.isRenderingChart) {
                                    this.isRenderingChart = true;
                                    this.renderChart();
                                }
                            }, 200);
                        }
                    } catch (error) {
                        console.error('Error in useEffect renderChart:', error);
                        this.isRenderingChart = false;
                    }
                }, 150);
            } else if (this.state.loading) {
                // If loading, destroy chart to prevent showing stale data
                if (this.chart) {
                    this.chart.destroy();
                    this.chart = null;
                    this.isRenderingChart = false;
                }
            } else if (!this.state.quadrants.q1.data || this.state.quadrants.q1.data.length === 0) {
                // If no data, destroy chart
                if (this.chart) {
                    this.chart.destroy();
                    this.chart = null;
                    this.isRenderingChart = false;
                }
            }
        }, () => [this.state.quadrants.q1.data, this.state.filterType, this.state.dateRangeLabel, this.state.loading]);

        useEffect(() => {
            try {
                this.renderDepartmentChart();
            } catch (error) {
                console.error('Error in useEffect renderDepartmentChart:', error);
            }
        }, () => [
            this.state.departmentChartData,
            this.state.departmentDataLoading,
            this.state.departmentError,
            this.state.departmentChartLabel,
            this.state.loading
        ]);

        useEffect(() => {
            try {
                this.renderEmployeeChart();
            } catch (error) {
                console.error('Error in useEffect renderEmployeeChart:', error);
            }
        }, () => [
            this.state.employeeChartData,
            this.state.employeeDataLoading,
            this.state.employeeError,
            this.state.employeeChartLabel,
            this.state.loading,
            this.state.scoreName
        ]);

        // Re-apply scrolling fix whenever state changes
        useEffect(() => {
            // Use global function for consistency
            fixScoreDashboardScrolling();
        }, () => [
            this.state.loading,
            this.state.quadrants.q1.data,
            this.state.departmentChartData,
            this.state.employeeChartData
        ]);
    }

    async loadScoreData() {
        try {
            // If scoreId is still missing, try to get it again from sessionStorage
            if (!this.state.scoreId) {
                const storedScoreId = sessionStorage.getItem('bizdom_scoreId');
                const storedScoreName = sessionStorage.getItem('bizdom_scoreName');
                if (storedScoreId) {
                    this.state.scoreId = parseInt(storedScoreId);
                    if (storedScoreName) {
                        this.state.scoreName = storedScoreName;
                    }
                    console.log('Recovered scoreId from sessionStorage:', this.state.scoreId);
                } else {
                    console.warn("ScoreDashboard: Missing scoreId in context and sessionStorage");
                    this.state.loading = false;
                    return;
                }
            }
            this.state.loading = true;
            const activeRange = this.ensureActiveRange();
            
            // Update date range label using preset (which creates it correctly with Date objects)
            const preset = this.getPresetRange(this.state.filterType);
            this.state.dateRangeLabel = preset.label;
            
            // Build API URL
            let url = `${SCORE_OVERVIEW_API}?scoreId=${this.state.scoreId}&filterType=${this.state.filterType}`;
            if (this.state.filterType === 'CUSTOM' && activeRange?.start && activeRange?.end) {
                // Format dates: convert Date objects to strings if needed, then format for API (DD-MM-YYYY)
                const startDateStr = activeRange.start instanceof Date ? this.formatDateForServer(activeRange.start) : activeRange.start;
                const endDateStr = activeRange.end instanceof Date ? this.formatDateForServer(activeRange.end) : activeRange.end;
                url += `&startDate=${this.formatDateForQuadrantAPI(startDateStr)}&endDate=${this.formatDateForQuadrantAPI(endDateStr)}`;
            }

            // Fetch from API endpoint
            const response = await fetch(url, {
                method: 'GET',
                headers: { 
                    'Content-Type': 'application/json',
                },
                credentials: 'same-origin', // This includes session cookies
            });

            if (response.status === 401) {
                console.error("Unauthorized access to score overview API");
                this.state.quadrants.q1.title = 'Score Overview';
                this.state.quadrants.q1.data = [];
                this.state.quadrants.q1.filter_type = this.state.filterType;
                this.state.quadrants.q1.score_name = this.state.scoreName;
                this.state.quadrants.q1.min_score = null;
                this.state.quadrants.q1.max_score = null;
                return;
            }

            const responseText = await response.text();
            let scoreData;
            try {
                scoreData = JSON.parse(responseText);
            } catch (error) {
                console.error("Invalid score overview response:", responseText);
                this.state.quadrants.q1.title = 'Score Overview';
                this.state.quadrants.q1.data = [];
                this.state.quadrants.q1.filter_type = this.state.filterType;
                this.state.quadrants.q1.score_name = this.state.scoreName;
                this.state.quadrants.q1.min_score = null;
                this.state.quadrants.q1.max_score = null;
                return;
            }

            console.log('Score data received:', scoreData);
            
            if (scoreData && scoreData.statusCode === 200 && scoreData.overview) {
                this.state.score = scoreData;
                // Update scoreName if available from the data
                if (scoreData.score_name) {
                    this.state.scoreName = scoreData.score_name;
                }
                // Store score type for formatting
                this.state.scoreType = scoreData.score_type || 'value';
                // Store actual min/max score values for reference lines
                this.state.quadrants.q1.min_score = scoreData.min_score !== undefined ? scoreData.min_score : null;
                this.state.quadrants.q1.max_score = scoreData.max_score !== undefined ? scoreData.max_score : null;
                // Update quadrant data - update properties individually to ensure reactivity
                this.state.quadrants.q1.title = scoreData.message || 'Score Overview';
                this.state.quadrants.q1.data = scoreData.overview || [];
                this.state.quadrants.q1.filter_type = this.state.filterType;
                this.state.quadrants.q1.score_name = scoreData.score_name;
                console.log('Quadrant data set:', {
                    title: this.state.quadrants.q1.title,
                    dataLength: this.state.quadrants.q1.data.length,
                    firstItem: this.state.quadrants.q1.data[0]
                });
                this.resetDepartmentState();
            } else {
                console.warn('No overview data in scoreData:', scoreData);
                // Ensure we have empty data structure if no data
                this.state.quadrants.q1.title = 'Score Overview';
                this.state.quadrants.q1.data = [];
                this.state.quadrants.q1.filter_type = this.state.filterType;
                this.state.quadrants.q1.score_name = this.state.scoreName;
                this.state.quadrants.q1.min_score = null;
                this.state.quadrants.q1.max_score = null;
            }
        } catch (error) {
            console.error("Error loading score data:", error);
            // Update properties individually to ensure reactivity
            this.state.quadrants.q1.title = 'Score Overview';
            this.state.quadrants.q1.data = [];
            this.state.quadrants.q1.filter_type = this.state.filterType;
            this.state.quadrants.q1.score_name = this.state.scoreName;
            this.state.quadrants.q1.min_score = null;
            this.state.quadrants.q1.max_score = null;
        } finally {
            this.state.loading = false;
            console.log('loadScoreData completed, loading:', this.state.loading, 'data length:', this.state.quadrants.q1.data?.length);
            // Don't render chart here - let useEffect handle it to avoid double rendering
            // The useEffect will trigger when loading becomes false and data is available
        }
    }

    async onFilterSelect(filterType) {
        const normalizedFilter = filterType.toUpperCase();
        if (this.state.filterType === normalizedFilter) {
            return;
        }
        // Set loading state immediately for smooth transition
        this.state.loading = true;
        
        let nextRange;
        if (normalizedFilter === 'CUSTOM') {
            if (!(this.state.customRange.start && this.state.customRange.end)) {
                console.warn("Custom range not available for this score dashboard");
                this.state.loading = false;
                return;
            }
            nextRange = { ...this.state.customRange };
            const start = this.parseDateString(nextRange.start);
            const end = this.parseDateString(nextRange.end);
            if (start && end) {
                this.state.dateRangeLabel = this.formatRangeLabel(start, end);
            }
        } else {
            const preset = this.getPresetRange(normalizedFilter);
            nextRange = { start: preset.start_date, end: preset.end_date };
            // Use the preset label directly (it's already correctly formatted with Date objects)
            this.state.dateRangeLabel = preset.label;
        }
        // Destroy chart before changing filter to prevent rendering issues
        if (this.chart) {
            this.chart.destroy();
            this.chart = null;
        }
        this.isRenderingChart = false;
        this.state.filterType = normalizedFilter;
        this.state.activeRange = nextRange;
        this.resetDepartmentState();
        await this.loadScoreData();
    }

    switchFilter(filterType) {
        return this.onFilterSelect(filterType);
    }

    getMaxValue(data) {
        if (!data || data.length === 0) return 100;
        return Math.max(...data.map(item => item.actual_value || 0), 100);
    }

    getPeriodLabel(item, filterType) {
        return item?.month || item?.period || item?.year || '';
    }

    formatValue(value) {
        const numericValue = Number(value || 0);
        return numericValue.toFixed(1);
    }

    hasPositiveValue(item) {
        return Number(item?.actual_value || 0) > 0;
    }

    getBarHeight(value, data) {
        const maxValue = this.getMaxValue(data);
        const numericValue = Number(value || 0);
        if (maxValue <= 0) {
            return '5%';
        }
        const percentage = Math.min((numericValue / maxValue) * 100, 100);
        const minPercentage = 8; // ensure small values are still visible
        return `${Math.max(percentage, minPercentage)}%`;
    }

    ensureActiveRange() {
        if (this.state.activeRange?.start && this.state.activeRange?.end) {
            return this.state.activeRange;
        }
        const fallback = this.getPresetRange(this.state.filterType === 'CUSTOM' ? 'MTD' : this.state.filterType);
        this.state.activeRange = { start: fallback.start_date, end: fallback.end_date };
        this.state.dateRangeLabel = fallback.label;
        return this.state.activeRange;
    }

    computeInitialRange(filterType, context) {
        const start = context.date_range_start;
        const end = context.date_range_end;
        if (start && end) {
            const startDate = this.parseDateString(start);
            const endDate = this.parseDateString(end);
            return {
                range: { start, end },
                label: this.formatRangeLabel(startDate, endDate),
            };
        }
        const fallbackFilter = filterType === 'CUSTOM' ? 'MTD' : filterType;
        const fallback = this.getPresetRange(fallbackFilter);
        return {
            range: { start: fallback.start_date, end: fallback.end_date },
            label: fallback.label,
        };
    }

    getPresetRange(filter) {
        const today = new Date();
        let startDate;
        let endDate;
        let label = "";
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
                label = `Week to Date: ${this.formatRangeLabel(startDate, endDate)}`;
                break;
            }
            case "YTD": {
                startDate = new Date(today.getFullYear(), 0, 1);
                startDate.setHours(0, 0, 0, 0);
                endDate = new Date(today);
                endDate.setHours(23, 59, 59, 999);
                label = `Year to Date: ${this.formatRangeLabel(startDate, endDate)}`;
                break;
            }
            default: { // MTD fallback
                startDate = new Date(today.getFullYear(), today.getMonth(), 1);
                startDate.setHours(0, 0, 0, 0);
                endDate = new Date(today);
                endDate.setHours(23, 59, 59, 999);
                label = `Month to Date: ${this.formatRangeLabel(startDate, endDate)}`;
                break;
            }
        }
        return {
            start_date: this.formatDateForServer(startDate),
            end_date: this.formatDateForServer(endDate),
            label,
        };
    }

    getAvailableFilters(currentFilter, includeCustom = false) {
        const filters = ["WTD", "MTD", "YTD"];
        if (includeCustom || currentFilter === 'CUSTOM') {
            filters.push("CUSTOM");
        }
        if (!filters.includes(currentFilter)) {
            filters.push(currentFilter);
        }
        return [...new Set(filters)];
    }

    parseDateString(value) {
        if (!value) return null;
        
        // If it's already a Date object, return it
        if (value instanceof Date) {
            return value;
        }
        
        // Handle YYYY-MM-DD format
        if (typeof value === 'string' && value.match(/^\d{4}-\d{2}-\d{2}$/)) {
            const parts = value.split('-');
            // Create date in local timezone (month is 0-indexed)
            return new Date(parseInt(parts[0]), parseInt(parts[1]) - 1, parseInt(parts[2]));
        }
        
        // Try parsing as is
        const date = new Date(value);
        if (isNaN(date.getTime())) {
            return null;
        }
        return date;
    }

    formatDateForServer(date) {
        const year = date.getFullYear();
        const month = String(date.getMonth() + 1).padStart(2, "0");
        const day = String(date.getDate()).padStart(2, "0");
        return `${year}-${month}-${day}`;
    }

    formatRangeLabel(startDate, endDate) {
        if (!startDate || !endDate) {
            return "";
        }
        return `${this.formatDisplayDate(startDate)} - ${this.formatDisplayDate(endDate)}`;
    }

    formatDisplayDate(date) {
        if (!date) {
            return "";
        }
        // Validate date
        if (isNaN(date.getTime())) {
            return "";
        }
        // Format as D M Y (Day Month Year)
        const day = date.getDate();
        const monthNames = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", 
                           "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
        const month = monthNames[date.getMonth()];
        const year = date.getFullYear();
        return `${day} ${month} ${year}`;
    }

    navigateBack() {
        this.action.doAction('bizdom.dashboard_action');
    }

    async loadDepartmentData() {
        if (!this.state.scoreId) {
            return [];
        }

        try {
            this.state.departmentDataLoading = true;
            this.state.departmentError = null;

            const activeRange = this.ensureActiveRange();
            let url = `${DEPARTMENT_API}?scoreId=${this.state.scoreId}&filterType=${this.state.filterType}`;
            if (this.state.filterType === 'CUSTOM' && activeRange?.start && activeRange?.end) {
                url += `&startDate=${this.formatDateForQuadrantAPI(activeRange.start)}&endDate=${this.formatDateForQuadrantAPI(activeRange.end)}`;
            }

            const response = await fetch(url, {
                method: 'GET',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'same-origin',
            });

            if (response.status === 401) {
                this.state.departmentError = 'You are not authorized to view department data.';
                this.state.departmentData = [];
                this.state.departmentDataLoaded = false;
                return [];
            }

            const responseText = await response.text();
            let deptData;
            try {
                deptData = JSON.parse(responseText);
            } catch (error) {
                console.error("Invalid department response:", responseText);
                this.state.departmentError = 'Unable to load department data.';
                this.state.departmentData = [];
                this.state.departmentDataLoaded = false;
                return [];
            }

            if (deptData && deptData.statusCode === 200) {
                this.state.departmentData = deptData.overview_department || [];
                this.state.departmentDataLoaded = true;
                if (!this.state.departmentData.length) {
                    this.state.departmentError = 'No department data available for this filter.';
                } else {
                    this.state.departmentError = null;
                }
            } else {
                this.state.departmentData = [];
                this.state.departmentDataLoaded = false;
                this.state.departmentError = deptData?.message || 'Unable to load department data.';
            }
        } catch (error) {
            console.error("Error loading department data:", error);
            this.state.departmentData = [];
            this.state.departmentDataLoaded = false;
            this.state.departmentError = 'Unable to load department data.';
        } finally {
            this.state.departmentDataLoading = false;
        }

        return this.state.departmentData;
    }

    async handleOverviewBarClick(periodItem) {
        if (!periodItem) {
            return;
        }

        const fallbackPeriod = this.getPeriodLabel(periodItem, this.state.filterType);
        this.state.departmentChartLabel = fallbackPeriod || '';
        this.state.departmentChartData = null;
        this.state.departmentError = null;

        if (!this.state.departmentDataLoaded && !this.state.departmentDataLoading) {
            await this.loadDepartmentData();
        }

        if (this.state.departmentDataLoading) {
            return;
        }

        if (!this.state.departmentData || this.state.departmentData.length === 0) {
            this.state.departmentChartData = null;
            this.state.departmentChartLabel = fallbackPeriod || '';
            this.state.departmentError = 'No department data available for this filter.';
            return;
        }

        const matchingEntry = this.findMatchingDepartmentEntry(periodItem);
        if (!matchingEntry) {
            this.state.departmentChartData = null;
            this.state.departmentChartLabel = fallbackPeriod || '';
            this.state.departmentError = 'No department data available for the selected period.';
            return;
        }

        // Pass periodItem to ensure we use the correct period dates
        this.updateDepartmentChartState(matchingEntry, fallbackPeriod, periodItem);
        
        // Auto-update Q3 (employee chart) by selecting the first department from Q2
        // Only for Labour, Leads, and Conversion scores (which have Q3 data)
        const scoreNameLower = (this.state.scoreName || '').toLowerCase();
        if (scoreNameLower === 'labour' || scoreNameLower === 'leads' || scoreNameLower === 'conversion') {
            // Wait for department chart data to be set, then auto-select first department
            setTimeout(async () => {
                if (this.state.departmentChartData && 
                    this.state.departmentChartData.departments && 
                    this.state.departmentChartData.departments.length > 0) {
                    const firstDept = this.state.departmentChartData.departments[0];
                    const departmentId = firstDept.department_id;
                    const departmentName = firstDept.department_name || this.state.departmentChartData.labels[0];
                    
                    // Create period info from the selected Q1 period
                    const periodInfo = {
                        startDate: periodItem.start_date || matchingEntry.start_date,
                        endDate: periodItem.end_date || matchingEntry.end_date,
                        period: periodItem.period || matchingEntry.period
                    };
                    
                    await this.handleDepartmentClick(departmentId, departmentName, periodInfo);
                }
            }, 150); // Small delay to ensure Q2 chart state is updated
        } else {
            // For other scores, reset Q3 when Q1 is clicked
            this.resetEmployeeState();
        }
    }

    renderDepartmentChart() {
        try {
            const canvas = this.departmentChartRef.el;

            if (!canvas || !this.state.departmentChartData || !this.state.departmentChartData.labels || !this.state.departmentChartData.labels.length) {
                if (this.departmentChart) {
                    this.departmentChart.destroy();
                    this.departmentChart = null;
                }
                return;
            }

            if (this.departmentChart) {
                this.departmentChart.destroy();
                this.departmentChart = null;
            }

            // Validate department chart data
            if (!this.state.departmentChartData.values || !Array.isArray(this.state.departmentChartData.values)) {
                return;
            }

            // Build datasets
            const scoreNameLower = (this.state.scoreName || '').toLowerCase();
            const isLeadsScore = scoreNameLower.includes('lead') && !scoreNameLower.includes('conversion');
            const isConversionScore = scoreNameLower.includes('conversion');
            const isLabourScore = scoreNameLower === 'labour';
            
            // Determine colors for Labour scores based on min/max values
            let backgroundColor = '#0d6efd'; // Default blue
            let borderColor = '#0d6efd';
            
            console.log('renderDepartmentChart - Labour check:', {
                scoreName: this.state.scoreName,
                scoreNameLower: scoreNameLower,
                isLabourScore: isLabourScore,
                hasMinValues: !!this.state.departmentChartData.minValues,
                hasMaxValues: !!this.state.departmentChartData.maxValues,
                minValues: this.state.departmentChartData.minValues,
                maxValues: this.state.departmentChartData.maxValues,
                values: this.state.departmentChartData.values,
                minValuesLength: this.state.departmentChartData.minValues?.length,
                maxValuesLength: this.state.departmentChartData.maxValues?.length,
                valuesLength: this.state.departmentChartData.values?.length
            });
            
            // Check if we have valid min/max arrays with at least one non-null value
            const hasValidMinMax = isLabourScore && 
                this.state.departmentChartData.minValues && 
                this.state.departmentChartData.maxValues &&
                Array.isArray(this.state.departmentChartData.minValues) &&
                Array.isArray(this.state.departmentChartData.maxValues) &&
                this.state.departmentChartData.minValues.length > 0 &&
                this.state.departmentChartData.maxValues.length > 0 &&
                this.state.departmentChartData.minValues.some(v => v !== null && v !== undefined && v !== '') &&
                this.state.departmentChartData.maxValues.some(v => v !== null && v !== undefined && v !== '');
            
            console.log('hasValidMinMax:', hasValidMinMax);
            
            if (hasValidMinMax) {
                // Ensure arrays have the same length
                const valuesLength = this.state.departmentChartData.values.length;
                const minLength = this.state.departmentChartData.minValues.length;
                const maxLength = this.state.departmentChartData.maxValues.length;
                
                if (valuesLength !== minLength || valuesLength !== maxLength) {
                    console.warn('Array length mismatch:', {
                        valuesLength,
                        minLength,
                        maxLength
                    });
                }
                
                // Create color arrays based on min/max comparison
                backgroundColor = this.state.departmentChartData.values.map((actualValue, index) => {
                    const minValue = index < this.state.departmentChartData.minValues.length 
                        ? this.state.departmentChartData.minValues[index] 
                        : null;
                    const maxValue = index < this.state.departmentChartData.maxValues.length 
                        ? this.state.departmentChartData.maxValues[index] 
                        : null;
                    
                    console.log(`Department ${index}:`, {
                        actualValue: actualValue,
                        minValue: minValue,
                        maxValue: maxValue,
                        minType: typeof minValue,
                        maxType: typeof maxValue
                    });
                    
                    // Skip if min/max values are not available (null, undefined, empty string, or 0)
                    if (minValue === null || maxValue === null || 
                        minValue === undefined || maxValue === undefined ||
                        minValue === '' || maxValue === '' ||
                        isNaN(minValue) || isNaN(maxValue)) {
                        console.log(`Department ${index}: Using default blue (min/max not available)`);
                        return '#0d6efd'; // Default blue
                    }
                    
                    const numMinValue = Number(minValue);
                    const numMaxValue = Number(maxValue);
                    
                    // Skip if min/max are both 0 or invalid (means no threshold set)
                    if (numMinValue === 0 && numMaxValue === 0) {
                        console.log(`Department ${index} (${this.state.departmentChartData.labels[index]}): Using default blue (min/max both 0) - no threshold set`);
                        return '#0d6efd'; // Default blue
                    }
                    
                    // Apply color logic:
                    // >= max: green (if max > 0)
                    // >= min and < max (or equal to min): yellow (if min >= 0)
                    // < min: red
                    let color;
                    if (numMaxValue > 0 && actualValue >= numMaxValue) {
                        color = '#198754'; // Green
                    } else if (actualValue >= numMinValue) {
                        // This covers: actualValue >= minValue (including when minValue is 0)
                        // and actualValue < maxValue (if maxValue > 0)
                        color = '#ffc107'; // Yellow
                    } else {
                        color = '#dc3545'; // Red
                    }
                    
                    console.log(`Department ${index} (${this.state.departmentChartData.labels[index]}): ${actualValue} vs [min:${numMinValue}, max:${numMaxValue}] = ${color}`);
                    return color;
                });
                borderColor = backgroundColor;
                console.log('Final backgroundColor array:', backgroundColor);
            }
            
            const datasets = [{
                label: isLeadsScore ? 'Leads' : (isConversionScore ? 'Conversions' : 'Actual'),
                data: this.state.departmentChartData.values,
                backgroundColor: backgroundColor,
                borderColor: borderColor,
                borderWidth: 1,
                borderRadius: 4
            }];
            
            // Add quality leads dataset if available (for Leads and Conversion scores)
            if (this.state.departmentChartData.conversionValues && Array.isArray(this.state.departmentChartData.conversionValues)) {
                datasets.push({
                    label: 'Quality Leads',
                    data: this.state.departmentChartData.conversionValues,
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
            const scoreType = this.state.scoreType || 'value';
            const isPercentage = scoreType === 'percentage';
            const hasConversionValues = datasets.length > 1;

        this.departmentChart = new Chart(canvas, {
            type: 'bar',
            data: {
                labels: this.state.departmentChartData.labels,
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
                                const suffix = isPercentage ? '%' : '';
                                const tooltipLines = [`${datasetLabel}: ${value.toFixed(2)}${suffix}`];
                                
                                // Add min/max values for Labour scores on separate lines
                                if (isLabourScore && this.state.departmentChartData.minValues && this.state.departmentChartData.maxValues) {
                                    const dataIndex = context.dataIndex;
                                    const minValue = this.state.departmentChartData.minValues[dataIndex];
                                    const maxValue = this.state.departmentChartData.maxValues[dataIndex];
                                    
                                    if (minValue !== null && maxValue !== null && 
                                        minValue !== undefined && maxValue !== undefined &&
                                        !isNaN(minValue) && !isNaN(maxValue) &&
                                        !(minValue === 0 && maxValue === 0)) {
                                        tooltipLines.push(`Min: ${minValue.toFixed(2)}${suffix}`);
                                        tooltipLines.push(`Max: ${maxValue.toFixed(2)}${suffix}`);
                                    }
                                }
                                
                                return tooltipLines;
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        grid: { display: false },
                        ticks: {
                            color: '#111827',
                            font: { size: 11 }
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
                            font: { size: 11 },
                            callback: (value) => {
                                const suffix = isPercentage ? '%' : '';
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
                        const departmentName = this.state.departmentChartData.labels[dataIndex];
                        
                        // Get period information from department chart data
                        // This should match the period that was selected in the score overview
                        const periodInfo = {
                            startDate: this.state.departmentChartData.periodStartDate,
                            endDate: this.state.departmentChartData.periodEndDate,
                            period: this.state.departmentChartData.period
                        };
                        
                        console.log('Department clicked:', {
                            departmentName,
                            dataIndex,
                            periodInfo,
                            departmentChartData: {
                                periodStartDate: this.state.departmentChartData.periodStartDate,
                                periodEndDate: this.state.departmentChartData.periodEndDate,
                                period: this.state.departmentChartData.period
                            }
                        });
                        
                        // Get department ID from chart data
                        if (this.state.departmentChartData.departmentIds && this.state.departmentChartData.departmentIds[dataIndex]) {
                            const departmentId = this.state.departmentChartData.departmentIds[dataIndex];
                            await this.handleDepartmentClick(departmentId, departmentName, periodInfo);
                        } else if (this.state.departmentChartData.departments && this.state.departmentChartData.departments[dataIndex]) {
                            const dept = this.state.departmentChartData.departments[dataIndex];
                            await this.handleDepartmentClick(dept.department_id, departmentName, periodInfo);
                        }
                    }
                }
            }
        });
        } catch (error) {
            console.error('Error rendering department chart:', error);
            if (this.departmentChart) {
                this.departmentChart.destroy();
                this.departmentChart = null;
            }
        }
    }

    /**
     * Gets the formatted date range label for the current filter
     */
    getDateRangeLabel() {
        // Use the stored label if available and valid
        if (this.state.dateRangeLabel) {
            return this.state.dateRangeLabel;
        }
        
        // Otherwise, get from preset (which creates the label correctly with Date objects)
        const preset = this.getPresetRange(this.state.filterType);
        return preset.label || '';
    }

    formatDateForQuadrantAPI(dateStr) {
        if (!dateStr) {
            return '';
        }
        const parts = dateStr.split('-');
        if (parts.length === 3) {
            return `${parts[2]}-${parts[1]}-${parts[0]}`;
        }
        return dateStr;
    }

    resetDepartmentState(options = {}) {
        this.state.departmentData = [];
        this.state.departmentDataLoaded = false;
        this.state.departmentDataLoading = false;
        this.state.departmentChartData = null;
        this.state.departmentChartLabel = '';
        this.state.departmentError = null;
        if (this.departmentChart && !options.keepChart) {
            this.departmentChart.destroy();
            this.departmentChart = null;
        }
        // Also reset employee state when department state is reset
        this.resetEmployeeState(options);
    }

    resetEmployeeState(options = {}) {
        this.state.employeeData = [];
        this.state.employeeDataLoading = false;
        this.state.employeeChartData = null;
        this.state.employeeChartLabel = '';
        this.state.employeeError = null;
        this.state.selectedDepartmentId = null;
        this.state.selectedDepartmentName = null;
        this.state.selectedPeriodInfo = null;
        if (this.employeeChart && !options.keepChart) {
            this.employeeChart.destroy();
            this.employeeChart = null;
        }
    }

    formatDepartmentPeriodLabel(entry) {
        if (!entry) {
            return '';
        }
        if (entry.period) {
            return entry.period;
        }
        if (entry.start_date && entry.end_date) {
            return `${entry.start_date} to ${entry.end_date}`;
        }
        return '';
    }

    findMatchingDepartmentEntry(periodItem) {
        if (!periodItem || !this.state.departmentData || !this.state.departmentData.length) {
            return null;
        }

        const possibleLabels = [];
        const periodLabel = this.getPeriodLabel(periodItem, this.state.filterType);
        if (periodLabel) {
            possibleLabels.push(periodLabel.trim());
        }
        if (periodItem.period) {
            possibleLabels.push(String(periodItem.period).trim());
        }
        if (periodItem.start_date && periodItem.end_date) {
            possibleLabels.push(`${periodItem.start_date.trim()}|${periodItem.end_date.trim()}`);
        }

        for (const entry of this.state.departmentData) {
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

        const index = this.state.quadrants.q1.data.indexOf(periodItem);
        if (index > -1 && this.state.departmentData[index]) {
            return this.state.departmentData[index];
        }
        return null;
    }

    buildDepartmentChartPayload(entry) {
        const departments = entry?.department || [];
        const scoreNameLower = (this.state.scoreName || '').toLowerCase();
        const isLeadsScore = scoreNameLower.includes('lead') && !scoreNameLower.includes('conversion');
        const isConversionScore = scoreNameLower.includes('conversion');
        const isLabourScore = scoreNameLower === 'labour';
        const hasConversionValues = (isLeadsScore || isConversionScore) && departments.some(dep => dep.quality_lead !== undefined && dep.quality_lead !== null);
        
        // Extract period dates - prefer entry dates if available
        const periodStartDate = entry?.start_date || null;
        const periodEndDate = entry?.end_date || null;
        const period = entry?.period || null;
        
        console.log('Building department chart payload:', {
            periodStartDate,
            periodEndDate,
            period,
            departmentCount: departments.length,
            isLabourScore: isLabourScore,
            scoreName: this.state.scoreName,
            sampleDepartment: departments.length > 0 ? departments[0] : null
        });
        
        // Extract min/max values for Labour scores
        let minValues = null;
        let maxValues = null;
        
        if (isLabourScore) {
            minValues = departments.map((dep, idx) => {
                const minVal = dep.min_value;
                const result = (minVal === '' || minVal === null || minVal === undefined) ? null : Number(minVal);
                console.log(`Department ${idx} (${dep.department_name}${dep.category_name ? ', category: ' + dep.category_name : ''}): min_value = ${minVal} -> ${result}, actual_value = ${dep.actual_value}`);
                return result;
            });
            maxValues = departments.map((dep, idx) => {
                const maxVal = dep.max_value;
                const result = (maxVal === '' || maxVal === null || maxVal === undefined) ? null : Number(maxVal);
                console.log(`Department ${idx} (${dep.department_name}${dep.category_name ? ', category: ' + dep.category_name : ''}): max_value = ${maxVal} -> ${result}, actual_value = ${dep.actual_value}`);
                return result;
            });
            console.log('Labour minValues:', minValues);
            console.log('Labour maxValues:', maxValues);
            console.log('Full department data:', departments);
        }
        
        return {
            labels: departments.map(dep => dep.department_name || dep.department_id || 'Department'),
            values: departments.map(dep => Number(dep.actual_value || 0)),
            departmentIds: departments.map(dep => dep.department_id),
            departments: departments, // Store full department objects for click handler
            // Store period information for filtering employee data
            periodStartDate: periodStartDate,
            periodEndDate: periodEndDate,
            period: period,
            // Include min/max values for Labour scores
            minValues: minValues,
            maxValues: maxValues,
            conversionValues: (isLeadsScore || isConversionScore) && hasConversionValues ? departments.map(dep => {
                const convValue = dep.quality_lead;
                if (typeof convValue === 'string') {
                    return Number(convValue) || 0;
                }
                return Number(convValue || 0);
            }) : null
        };
    }

    updateDepartmentChartState(entry, fallbackPeriod, periodItem = null) {
        if (!entry || !entry.department || !entry.department.length) {
            this.state.departmentChartData = null;
            this.state.departmentChartLabel = fallbackPeriod || '';
            this.state.departmentError = 'No department data available for the selected period.';
            return;
        }
        this.state.departmentError = null;
        this.state.departmentChartLabel = this.formatDepartmentPeriodLabel(entry) || fallbackPeriod || '';
        
        // Use periodItem dates if available (more reliable than entry dates)
        // This ensures we use the exact period that was clicked in the score overview
        // But keep the entry's department data
        let finalEntry = entry;
        
        if (periodItem && (periodItem.start_date || periodItem.end_date)) {
            // Create a new object with updated dates but keep all other entry properties
            finalEntry = {
                ...entry,
                start_date: periodItem.start_date || entry.start_date,
                end_date: periodItem.end_date || entry.end_date,
                period: periodItem.period || entry.period
            };
        }
        
        console.log('updateDepartmentChartState:', {
            hasEntry: !!entry,
            hasPeriodItem: !!periodItem,
            entryDates: entry ? { start: entry.start_date, end: entry.end_date, period: entry.period } : null,
            periodItemDates: periodItem ? { start: periodItem.start_date, end: periodItem.end_date, period: periodItem.period } : null,
            finalDates: finalEntry ? { start: finalEntry.start_date, end: finalEntry.end_date, period: finalEntry.period } : null,
            departmentCount: entry && entry.department ? entry.department.length : 0,
            finalEntryHasDepartment: finalEntry && finalEntry.department ? finalEntry.department.length : 0
        });
        
        this.state.departmentChartData = this.buildDepartmentChartPayload(finalEntry);
    }

    getDepartmentPlaceholderMessage() {
        if (this.state.departmentDataLoading) {
            return 'Loading department data...';
        }
        if (this.state.departmentError) {
            return this.state.departmentError;
        }
        if (!this.state.departmentDataLoaded) {
            return 'Select a bar in the Score Overview to view department breakdown.';
        }
        if (this.state.departmentData && this.state.departmentData.length > 0 && !this.state.departmentChartData) {
            return 'Select a bar in the Score Overview to view department breakdown.';
        }
        return 'No department data available for this filter.';
    }

    async handleDepartmentClick(departmentId, departmentName, periodInfo = null) {
        const scoreNameLower = (this.state.scoreName || '').toLowerCase();
        
        // Handle for Labour, Leads, and Conversion scores
        if (scoreNameLower !== 'labour' && scoreNameLower !== 'leads' && scoreNameLower !== 'conversion') {
            console.log('Employee/Source overview only available for Labour, Leads, and Conversion scores');
            return;
        }

        if (!departmentId) {
            console.warn('Department/Medium ID is required');
            return;
        }

        this.state.selectedDepartmentId = departmentId;
        this.state.selectedDepartmentName = departmentName;
        this.state.selectedPeriodInfo = periodInfo; // Store period info for filtering
        this.state.employeeChartData = null;
        this.state.employeeError = null;
        this.state.employeeChartLabel = departmentName || '';

        await this.loadEmployeeData(departmentId);
    }

    async loadEmployeeData(departmentId) {
        if (!this.state.scoreId || !departmentId) {
            return;
        }

        try {
            this.state.employeeDataLoading = true;
            this.state.employeeError = null;

            const activeRange = this.ensureActiveRange();
            let url = `${EMPLOYEE_OVERVIEW_API}?scoreId=${this.state.scoreId}&departmentId=${departmentId}&filterType=${this.state.filterType}`;
            if (this.state.filterType === 'CUSTOM' && activeRange?.start && activeRange?.end) {
                url += `&startDate=${this.formatDateForQuadrantAPI(activeRange.start)}&endDate=${this.formatDateForQuadrantAPI(activeRange.end)}`;
            }

            // Use same-origin credentials for session-based auth
            const response = await fetch(url, {
                method: 'GET',
                headers: { 
                    'Content-Type': 'application/json'
                },
                credentials: 'same-origin',
            });

            if (response.status === 401) {
                this.state.employeeError = 'You are not authorized to view employee data.';
                this.state.employeeData = [];
                return;
            }

            const responseText = await response.text();
            let empData;
            try {
                empData = JSON.parse(responseText);
            } catch (error) {
                console.error("Invalid employee response:", responseText);
                this.state.employeeError = 'Unable to load employee data.';
                this.state.employeeData = [];
                return;
            }

            if (empData && empData.statusCode === 200) {
                const scoreNameLower = (this.state.scoreName || '').toLowerCase();
                
                if (scoreNameLower === 'leads') {
                    // For Leads score, the response uses overview_source instead of overview_employee
                    this.state.employeeData = empData.overview_source || [];
                    if (!this.state.employeeData.length) {
                        this.state.employeeError = 'No source data available for this medium.';
                    } else {
                        this.state.employeeError = null;
                        // Build leads chart data (same structure as employee chart data)
                        this.buildLeadsChartData();
                    }
                } else if (scoreNameLower === 'conversion') {
                    // For Conversion score, the response uses overview_source (contains salespersons)
                    this.state.employeeData = empData.overview_source || [];
                    if (!this.state.employeeData.length) {
                        this.state.employeeError = 'No salesperson data available for this medium.';
                    } else {
                        this.state.employeeError = null;
                        // Build conversion chart data (similar to leads but for salespersons)
                        this.buildConversionChartData();
                    }
                } else {
                    // For Labour score, use overview_employee
                    this.state.employeeData = empData.overview_employee || [];
                    if (!this.state.employeeData.length) {
                        this.state.employeeError = 'No employee data available for this department.';
                    } else {
                        this.state.employeeError = null;
                        // Build chart data from employee data
                        this.buildEmployeeChartData();
                    }
                }
            } else {
                this.state.employeeData = [];
                this.state.employeeError = empData?.message || 'Unable to load employee/source data.';
            }
        } catch (error) {
            console.error("Error loading employee data:", error);
            this.state.employeeData = [];
            this.state.employeeError = 'Unable to load employee data.';
        } finally {
            this.state.employeeDataLoading = false;
        }
    }

    buildLeadsChartData() {
        if (!this.state.employeeData || this.state.employeeData.length === 0) {
            this.state.leadsChart1Data = null;
            this.state.leadsChart2Data = null;
            return;
        }

        // Filter to show only sources from the selected period
        let selectedPeriodData = null;
        
        if (this.state.selectedPeriodInfo && (this.state.selectedPeriodInfo.startDate || this.state.selectedPeriodInfo.endDate)) {
            const periodStart = String(this.state.selectedPeriodInfo.startDate || '').trim();
            const periodEnd = String(this.state.selectedPeriodInfo.endDate || '').trim();
            
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
            
            // Try exact match first
            selectedPeriodData = this.state.employeeData.find(period => {
                const periodStartNorm = normalizeDate(period.start_date);
                const periodEndNorm = normalizeDate(period.end_date);
                
                if (normalizedStart && normalizedEnd && periodStartNorm && periodEndNorm) {
                    return periodStartNorm === normalizedStart && periodEndNorm === normalizedEnd;
                }
                return false;
            });
            
            // If exact match not found, try matching by start date only
            if (!selectedPeriodData && normalizedStart) {
                selectedPeriodData = this.state.employeeData.find(period => {
                    const periodStartNorm = normalizeDate(period.start_date);
                    return periodStartNorm === normalizedStart;
                });
            }
            
            // Final fallback: match by period label if available
            if (!selectedPeriodData && this.state.selectedPeriodInfo.period) {
                selectedPeriodData = this.state.employeeData.find(period => {
                    return period.period && period.period === this.state.selectedPeriodInfo.period;
                });
            }
        }
        
        // If no specific period selected or not found, show empty
        if (!selectedPeriodData) {
            this.state.employeeChartData = {
                labels: [],
                values: [],
                conversionValues: []
            };
            return;
        }
        
        // Process sources from the selected period
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

        // Sort by lead_value descending
        sources.sort((a, b) => b.lead_value - a.lead_value);

        // Build chart data with both Leads and Quality Leads datasets (similar to Quadrant 1)
        this.state.employeeChartData = {
            labels: sources.map(s => s.source_name),
            values: sources.map(s => s.lead_value),
            conversionValues: sources.map(s => s.quality_lead_value)
        };
    }

    buildConversionChartData() {
        if (!this.state.employeeData || this.state.employeeData.length === 0) {
            this.state.employeeChartData = {
                labels: [],
                values: [],
                conversionValues: []
            };
            return;
        }

        // Filter to show only salespersons from the selected period
        let selectedPeriodData = null;
        
        if (this.state.selectedPeriodInfo && (this.state.selectedPeriodInfo.startDate || this.state.selectedPeriodInfo.endDate)) {
            const periodStart = String(this.state.selectedPeriodInfo.startDate || '').trim();
            const periodEnd = String(this.state.selectedPeriodInfo.endDate || '').trim();
            
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
            
            // Try exact match first
            selectedPeriodData = this.state.employeeData.find(period => {
                const periodStartNorm = normalizeDate(period.start_date);
                const periodEndNorm = normalizeDate(period.end_date);
                
                if (normalizedStart && normalizedEnd && periodStartNorm && periodEndNorm) {
                    return periodStartNorm === normalizedStart && periodEndNorm === normalizedEnd;
                }
                return false;
            });
            
            // If exact match not found, try matching by start date only
            if (!selectedPeriodData && normalizedStart) {
                selectedPeriodData = this.state.employeeData.find(period => {
                    const periodStartNorm = normalizeDate(period.start_date);
                    return periodStartNorm === normalizedStart;
                });
            }
            
            // Final fallback: match by period label if available
            if (!selectedPeriodData && this.state.selectedPeriodInfo.period) {
                selectedPeriodData = this.state.employeeData.find(period => {
                    return period.period && period.period === this.state.selectedPeriodInfo.period;
                });
            }
        }
        
        // If no specific period selected or not found, show empty
        if (!selectedPeriodData) {
            this.state.employeeChartData = {
                labels: [],
                values: [],
                conversionValues: []
            };
            return;
        }
        
        // Process salespersons from the selected period
        // Note: Conversion API uses "sources" key but contains salesperson data
        const salespersons = [];
        
        if (selectedPeriodData.sources && Array.isArray(selectedPeriodData.sources)) {
            selectedPeriodData.sources.forEach(salesperson => {
                salespersons.push({
                    saleperson_id: salesperson.saleperson_id,
                    saleperson_name: salesperson.saleperson_name || 'N/A',
                    quality_lead_value: Number(salesperson.quality_lead_value || 0),
                    converted_value: Number(salesperson.converted_value || 0)
                });
            });
        }

        // Sort by quality_lead_value descending
        salespersons.sort((a, b) => b.quality_lead_value - a.quality_lead_value);

        // Build chart data with both Quality Leads (total) and Converted datasets
        this.state.employeeChartData = {
            labels: salespersons.map(s => s.saleperson_name),
            values: salespersons.map(s => s.quality_lead_value),
            conversionValues: salespersons.map(s => s.converted_value)
        };
    }

    buildEmployeeChartData() {
        if (!this.state.employeeData || this.state.employeeData.length === 0) {
            this.state.employeeChartData = null;
            return;
        }

        // Filter to show only employees from the selected period
        let selectedPeriodData = null;
        
        if (this.state.selectedPeriodInfo && (this.state.selectedPeriodInfo.startDate || this.state.selectedPeriodInfo.endDate)) {
            // Find the matching period in employee data
            const periodStart = String(this.state.selectedPeriodInfo.startDate || '').trim();
            const periodEnd = String(this.state.selectedPeriodInfo.endDate || '').trim();
            
            console.log('Building employee chart data:', {
                selectedPeriodInfo: this.state.selectedPeriodInfo,
                periodStart,
                periodEnd,
                employeeDataPeriods: this.state.employeeData.map(p => ({
                    start_date: p.start_date,
                    end_date: p.end_date,
                    period: p.period,
                    employeeCount: p.employees?.length || 0,
                    employees: p.employees?.map(e => ({ name: e.employee_name, value: e.actual_value }))
                }))
            });
            
            // Normalize dates for comparison - ensure both are strings in DD-MM-YYYY format
            const normalizeDate = (dateStr) => {
                if (!dateStr) return null;
                // Convert to string and trim
                const str = String(dateStr).trim();
                // If already in DD-MM-YYYY format, return as is
                if (str.match(/^\d{2}-\d{2}-\d{4}$/)) {
                    return str;
                }
                return str;
            };
            
            const normalizedStart = normalizeDate(periodStart);
            const normalizedEnd = normalizeDate(periodEnd);
            
            // Try exact match first - both start and end dates must match
            selectedPeriodData = this.state.employeeData.find(period => {
                const periodStartNorm = normalizeDate(period.start_date);
                const periodEndNorm = normalizeDate(period.end_date);
                
                // Exact match on both dates
                if (normalizedStart && normalizedEnd && periodStartNorm && periodEndNorm) {
                    const startMatch = periodStartNorm === normalizedStart;
                    const endMatch = periodEndNorm === normalizedEnd;
                    const match = startMatch && endMatch;
                    
                    if (match) {
                        console.log('✓ Found exact period match:', {
                            selected: { start: normalizedStart, end: normalizedEnd },
                            found: { start: periodStartNorm, end: periodEndNorm },
                            employees: period.employees?.map(e => ({ name: e.employee_name, value: e.actual_value }))
                        });
                    } else {
                        console.log('✗ Period mismatch:', {
                            selected: { start: normalizedStart, end: normalizedEnd },
                            checking: { start: periodStartNorm, end: periodEndNorm },
                            startMatch,
                            endMatch
                        });
                    }
                    return match;
                }
                return false;
            });
            
            // If exact match not found, try matching by start date only (for current week scenarios)
            if (!selectedPeriodData && normalizedStart) {
                console.log('Trying to match by start date only:', normalizedStart);
                selectedPeriodData = this.state.employeeData.find(period => {
                    const periodStartNorm = normalizeDate(period.start_date);
                    const match = periodStartNorm === normalizedStart;
                    if (match) {
                        console.log('✓ Found period match by start date:', {
                            start: normalizedStart,
                            period: { start: periodStartNorm, end: normalizeDate(period.end_date) },
                            employees: period.employees?.map(e => ({ name: e.employee_name, value: e.actual_value }))
                        });
                    }
                    return match;
                });
            }
            
            // Final fallback: match by period label if available
            if (!selectedPeriodData && this.state.selectedPeriodInfo.period) {
                console.log('Trying to match by period label:', this.state.selectedPeriodInfo.period);
                selectedPeriodData = this.state.employeeData.find(period => {
                    return period.period && period.period === this.state.selectedPeriodInfo.period;
                });
                if (selectedPeriodData) {
                    console.log('✓ Found period match by label:', {
                        period: this.state.selectedPeriodInfo.period,
                        employees: selectedPeriodData.employees?.map(e => ({ name: e.employee_name, value: e.actual_value }))
                    });
                }
            }
            
            if (!selectedPeriodData) {
                console.error('❌ No matching period found for:', {
                    startDate: normalizedStart,
                    endDate: normalizedEnd,
                    period: this.state.selectedPeriodInfo.period,
                    availablePeriods: this.state.employeeData.map(p => ({
                        start: p.start_date,
                        end: p.end_date,
                        period: p.period
                    }))
                });
            }
        }
        
        // CRITICAL: If no specific period selected or not found, show EMPTY instead of all periods
        // This prevents showing wrong data
        if (!selectedPeriodData) {
            console.error('❌ No matching period found - showing empty chart');
            this.state.employeeChartData = {
                labels: [],
                values: []
            };
            return;
        }
        
        const periodsToProcess = [selectedPeriodData];
        
        console.log('Processing periods for employee chart:', {
            selectedPeriodData: {
                start_date: selectedPeriodData.start_date,
                end_date: selectedPeriodData.end_date,
                employeeCount: selectedPeriodData.employees?.length || 0,
                employees: selectedPeriodData.employees?.map(e => ({ name: e.employee_name, value: e.actual_value }))
            }
        });
        
        // Process employees from the selected period only - no aggregation needed
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

        // Sort by actual_value descending
        employees.sort((a, b) => b.actual_value - a.actual_value);

        console.log('Final employee chart data:', {
            employeeCount: employees.length,
            employees: employees.map(e => ({ name: e.employee_name, value: e.actual_value }))
        });

        this.state.employeeChartData = {
            labels: employees.map(emp => emp.employee_name),
            values: employees.map(emp => emp.actual_value)
        };
    }

    renderEmployeeChart() {
        try {
            const canvas = this.employeeChartRef.el;

            if (!canvas || !this.state.employeeChartData || !this.state.employeeChartData.labels || !this.state.employeeChartData.labels.length) {
                if (this.employeeChart) {
                    this.employeeChart.destroy();
                    this.employeeChart = null;
                }
                return;
            }

            if (this.employeeChart) {
                this.employeeChart.destroy();
                this.employeeChart = null;
            }

            // Validate employee chart data
            if (!this.state.employeeChartData.values || !Array.isArray(this.state.employeeChartData.values)) {
                return;
            }

            const scoreNameLower = (this.state.scoreName || '').toLowerCase();
            const isLeadsScore = scoreNameLower === 'leads';
            const isConversionScore = scoreNameLower === 'conversion';
            const isLabourScore = scoreNameLower === 'labour';

            // Build datasets based on score type
            const datasets = [];
            
            if (isLeadsScore) {
                // For Leads score: show both Leads and Quality Leads as grouped bars
                datasets.push({
                    label: 'Leads',
                    data: this.state.employeeChartData.values,
                    backgroundColor: '#0d6efd',
                    borderColor: '#0d6efd',
                    borderWidth: 1,
                    borderRadius: 4
                });
                
                // Add Quality Leads dataset if available
                if (this.state.employeeChartData.conversionValues && Array.isArray(this.state.employeeChartData.conversionValues)) {
                    datasets.push({
                        label: 'Quality Leads',
                        data: this.state.employeeChartData.conversionValues,
                        backgroundColor: '#198754',
                        borderColor: '#198754',
                        borderWidth: 1,
                        borderRadius: 4
                    });
                }
            } else if (isConversionScore) {
                // For Conversion score: show both Quality Leads (total) and Converted as grouped bars
                datasets.push({
                    label: 'Quality Leads',
                    data: this.state.employeeChartData.values,
                    backgroundColor: '#0d6efd',
                    borderColor: '#0d6efd',
                    borderWidth: 1,
                    borderRadius: 4
                });
                
                // Add Converted dataset if available
                if (this.state.employeeChartData.conversionValues && Array.isArray(this.state.employeeChartData.conversionValues)) {
                    datasets.push({
                        label: 'Converted',
                        data: this.state.employeeChartData.conversionValues,
                        backgroundColor: '#198754',
                        borderColor: '#198754',
                        borderWidth: 1,
                        borderRadius: 4
                    });
                }
            } else {
                // For Labour score: single dataset
                datasets.push({
                    label: 'Labour',
                    data: this.state.employeeChartData.values,
                    backgroundColor: '#0d6efd',
                    borderColor: '#0d6efd',
                    borderWidth: 1,
                    borderRadius: 4
                });
            }

            // Calculate max value across all datasets
            const allValues = datasets.flatMap(dataset => (dataset.data || []));
            const maxValue = allValues.length > 0 ? Math.max(...allValues, 0) : 0;
            const suggestedMax = maxValue > 0 ? maxValue * 1.1 : 100;

            this.employeeChart = new Chart(canvas, {
                type: 'bar',
                data: {
                    labels: this.state.employeeChartData.labels,
                    datasets: datasets
                },
                options: {
                    indexAxis: 'y', // Horizontal bar chart
                    maintainAspectRatio: false,
                    responsive: true,
                    plugins: {
                        legend: {
                            display: isLeadsScore || isConversionScore, // Show legend for Leads and Conversion scores (multiple datasets)
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
                            grid: {
                                color: 'rgba(0, 0, 0, 0.1)'
                            },
                            ticks: {
                                color: '#111827',
                                font: { size: 11 },
                                stepSize: 1, // Ensure ticks increment by 1
                                maxTicksLimit: Math.ceil(suggestedMax) + 1, // Limit based on max value
                                callback: (value) => {
                                    // Only show integer values to avoid duplicates
                                    const intValue = Math.round(value);
                                    if (Math.abs(value - intValue) > 0.01) {
                                        return '';
                                    }
                                    if (intValue >= 1000) {
                                        return (intValue / 1000).toFixed(isLabourScore ? 2 : 1) + 'k';
                                    }
                                    return intValue.toFixed(isLabourScore ? 2 : 0);
                                },
                                afterBuildTicks: (axis) => {
                                    // Filter out duplicate ticks
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
            if (this.employeeChart) {
                this.employeeChart.destroy();
                this.employeeChart = null;
            }
        }
    }

    getEmployeePlaceholderMessage() {
        const scoreNameLower = (this.state.scoreName || '').toLowerCase();
        
        if (this.state.employeeDataLoading) {
            if (scoreNameLower === 'leads') {
                return 'Loading source data...';
            }
            return 'Loading employee data...';
        }
        if (this.state.employeeError) {
            return this.state.employeeError;
        }
        if (!this.state.selectedDepartmentId) {
            if (scoreNameLower === 'leads') {
                return 'Select a medium in the Department Breakdown to view leads by source.';
            }
            if (scoreNameLower === 'conversion') {
                return 'Select a medium in the Department Breakdown to view conversions by salesperson.';
            }
            return 'Select a department in the Department Breakdown to view employee labour.';
        }
        if (scoreNameLower === 'leads') {
            if (this.state.employeeData && this.state.employeeData.length > 0 && !this.state.employeeChartData) {
                return 'Select a medium in the Department Breakdown to view leads by source.';
            }
            return 'No source data available for this medium.';
        } else if (this.isConversionScore()) {
            if (this.state.employeeData && this.state.employeeData.length > 0 && !this.state.employeeChartData) {
                return 'Select a medium in the Department Breakdown to view conversions by salesperson.';
            }
            return 'No salesperson data available for this medium.';
        } else {
            if (this.state.employeeData && this.state.employeeData.length > 0 && !this.state.employeeChartData) {
                return 'Select a department in the Department Breakdown to view employee labour.';
            }
            return 'No employee data available for this department.';
        }
    }

    isLeadsScore() {
        const scoreNameLower = (this.state.scoreName || '').toLowerCase();
        return scoreNameLower === 'leads';
    }

    isConversionScore() {
        const scoreNameLower = (this.state.scoreName || '').toLowerCase();
        return scoreNameLower === 'conversion';
    }

    isLabourScore() {
        const scoreNameLower = (this.state.scoreName || '').toLowerCase();
        return scoreNameLower === 'labour';
    }

    /**
     * Transforms the quadrant data into Chart.js format
     */
    getChartData() {
        try {
            const data = this.state.quadrants.q1.data;
            if (!data || data.length === 0) {
                this.originalChartData = [];
                return { labels: [], datasets: [] };
            }

            // Store original data for tooltip access
            this.originalChartData = data;

        // Create labels with period and date range
        const labels = data.map(item => {
            const periodLabel = this.getPeriodLabel(item, this.state.quadrants.q1.filter_type);
            let dateRange = '';
            
            // Always try to create date range if we have dates
            if (item.start_date && item.end_date) {
                try {
                    const startDate = this.formatDateForTooltip(item.start_date);
                    const endDate = this.formatDateForTooltip(item.end_date);
                    
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
                    const formattedDate = this.formatDateForTooltip(singleDate);
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
        const scoreNameToCheck = this.state.scoreName || this.state.quadrants.q1.score_name || '';
        const isLeadsScore = scoreNameToCheck && scoreNameToCheck.toLowerCase().includes('lead') && !scoreNameToCheck.toLowerCase().includes('conversion');
        const isConversionScore = scoreNameToCheck && scoreNameToCheck.toLowerCase().includes('conversion');
        const isLabourScore = scoreNameToCheck && scoreNameToCheck.toLowerCase() === 'labour';
        
        // Check for quality_lead field - for Leads and Conversion scores, show it even if values are 0
        const hasConversionValues = (isLeadsScore || isConversionScore) && data.some(item => {
            const convValue = item.quality_lead;
            // Field exists (even if 0) - we want to show it for Leads and Conversion
            return convValue !== undefined && convValue !== null;
        });
        
        console.log('Chart data check:', {
            scoreName: this.state.scoreName,
            quadrantScoreName: this.state.quadrants.q1.score_name,
            scoreNameToCheck: scoreNameToCheck,
            isLeadsScore: isLeadsScore,
            isConversionScore: isConversionScore,
            isLabourScore: isLabourScore,
            hasConversionValues: hasConversionValues,
            sampleItem: data[0],
            conversionValueInFirstItem: data[0]?.quality_lead,
            allConversionValues: data.map(item => item.quality_lead)
        });
        
        // For Labour score, determine bar colors based on actual_value vs min_value/max_value
        let backgroundColor = '#0d6efd'; // Default blue
        let borderColor = '#0d6efd';
        
        if (isLabourScore) {
            // Create array of colors for each bar based on comparison with min/max
            backgroundColor = data.map(item => {
                const actualVal = Number(item.actual_value || 0);
                const itemMinVal = Number(item.min_value || 0);
                const itemMaxVal = Number(item.max_value || 0);
                
                // Use tolerance for floating point comparison
                const tolerance = 0.01;
                
                // Compare actual value with this item's min/max values
                if (itemMinVal > 0 && itemMaxVal > 0) {
                    // Below min → Red
                    if (actualVal < itemMinVal - tolerance) {
                        return '#dc3545'; // Red
                    }
                    // At or above max → Green
                    if (actualVal >= itemMaxVal - tolerance) {
                        return '#198754'; // Green
                    }
                    // Between min and max → Yellow
                    if (actualVal >= itemMinVal - tolerance && actualVal < itemMaxVal - tolerance) {
                        return '#ffc107'; // Yellow
                    }
                }
                
                // Fallback: use default blue if we can't determine
                return '#0d6efd';
            });
            
            // Set border colors to match background
            borderColor = backgroundColor;
        }
        
        const datasets = [{
            label: isLeadsScore ? 'Leads' : (isConversionScore ? 'Conversions' : (scoreNameToCheck || 'Total')),
            data: values,
            backgroundColor: backgroundColor,
            borderColor: borderColor,
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
            this.originalChartData = [];
            return { labels: [], datasets: [] };
        }
    }

    /**
     * Formats date for display in tooltip
     */
    formatDateForTooltip(dateString) {
        if (!dateString) return '';
        
        try {
            let date;
            
            // If it's already a Date object
            if (dateString instanceof Date) {
                date = dateString;
            } else if (typeof dateString === 'string') {
                // Handle YYYY-MM-DD format (most common from Odoo)
                if (dateString.match(/^\d{4}-\d{2}-\d{2}$/)) {
                    // Parse in local timezone to avoid day shifts
                    const parts = dateString.split('-');
                    const year = parseInt(parts[0], 10);
                    const month = parseInt(parts[1], 10) - 1; // Month is 0-indexed
                    const day = parseInt(parts[2], 10);
                    date = new Date(year, month, day);
                } else if (dateString.match(/^\d{4}-\d{2}-\d{2}/)) {
                    // Has time component - extract just the date part
                    const datePart = dateString.split(' ')[0].split('T')[0];
                    const parts = datePart.split('-');
                    if (parts.length === 3) {
                        const year = parseInt(parts[0], 10);
                        const month = parseInt(parts[1], 10) - 1;
                        const day = parseInt(parts[2], 10);
                        date = new Date(year, month, day);
                    } else {
                        date = new Date(dateString);
                    }
                } else if (dateString.match(/^\d{2}-\d{2}-\d{4}$/)) {
                    // Handle DD-MM-YYYY format
                    const parts = dateString.split('-');
                    const day = parseInt(parts[0], 10);
                    const month = parseInt(parts[1], 10) - 1;
                    const year = parseInt(parts[2], 10);
                    date = new Date(year, month, day);
                } else {
                    // Try parsing as is
                    date = new Date(dateString);
                }
            } else {
                return String(dateString);
            }
            
            // Validate the date
            if (!date || isNaN(date.getTime())) {
                console.warn('Invalid date:', dateString);
                return String(dateString); // Return original if invalid
            }
            
            // Format using the existing method
            const formatted = this.formatDisplayDate(date);
            if (!formatted || formatted.includes('Invalid')) {
                console.warn('Date formatting failed for:', dateString);
                return String(dateString);
            }
            return formatted;
        } catch (error) {
            console.warn('Error formatting date for tooltip:', dateString, error);
            return String(dateString); // Return original string on error
        }
    }

    /**
     * Renders the Chart.js bar chart
     */
    renderChart() {
        // Prevent duplicate renders
        if (this.isRenderingChart && this.chart) {
            console.log('Skipping render - already rendering');
            return;
        }
        
        try {
            // Check if we have data before proceeding
            if (!this.state.quadrants.q1.data || this.state.quadrants.q1.data.length === 0) {
                console.warn('No data available for chart rendering');
                if (this.chart) {
                    this.chart.destroy();
                    this.chart = null;
                }
                this.isRenderingChart = false;
                return;
            }

            if (this.chart) {
                this.chart.destroy();
                this.chart = null;
            }

            // Wait for DOM to be ready
            if (!this.chartRef || !this.chartRef.el) {
                console.warn('Chart canvas not available yet, retrying...');
                this.isRenderingChart = false;
                setTimeout(() => {
                    if (this.state.quadrants.q1.data && this.state.quadrants.q1.data.length > 0 && !this.state.loading) {
                        this.renderChart();
                    }
                }, 100);
                return;
            }

            const chartData = this.getChartData();
            if (!chartData || !chartData.labels || chartData.labels.length === 0) {
                console.warn('No chart data available:', chartData);
                this.isRenderingChart = false;
                return;
            }

            if (!chartData.datasets || chartData.datasets.length === 0) {
                console.warn('No datasets available:', chartData);
                this.isRenderingChart = false;
                return;
            }
            
            console.log('Rendering chart with data:', {
                labelsCount: chartData.labels.length,
                datasetsCount: chartData.datasets.length,
                firstDatasetLabel: chartData.datasets[0]?.label,
                firstDatasetData: chartData.datasets[0]?.data,
                secondDatasetLabel: chartData.datasets[1]?.label,
                secondDatasetData: chartData.datasets[1]?.data
            });

            // Calculate max value across all datasets
            const allValues = chartData.datasets.flatMap(dataset => (dataset.data || []));
            const maxValue = allValues.length > 0 ? Math.max(...allValues, 0) : 0;
            const scoreType = this.state.scoreType || 'value';
            const isPercentage = scoreType === 'percentage';
            
            // Check if we have quality leads values (Leads or Conversion score)
            const hasConversionValues = chartData.datasets.length > 1;
        // Detect mobile device
        const isMobile = window.innerWidth < 768;

        // Check if this is Labour score or RCR and extract max/min values
        const scoreNameToCheck = (this.state.scoreName || this.state.quadrants.q1.score_name || '').toLowerCase();
        const isLabourScore = scoreNameToCheck === 'labour';
        const isRcrScore = scoreNameToCheck === 'rcr';
        let maxValueLine = null;
        let minValueLine = null;
        
        if (isLabourScore && this.state.quadrants.q1.data && this.state.quadrants.q1.data.length > 0) {
            // Extract max and min values from the data (calculated period values)
            // Get all max_value and min_value from all periods
            console.log('Labour score - Raw data items:', this.state.quadrants.q1.data.map(item => ({
                period: item.period,
                max_value: item.max_value,
                min_value: item.min_value,
                actual_value: item.actual_value
            })));
            
            const maxValues = this.state.quadrants.q1.data
                .map(item => {
                    const val = Number(item.max_value);
                    return !isNaN(val) ? val : null;
                })
                .filter(val => val !== null && val !== undefined);
            const minValues = this.state.quadrants.q1.data
                .map(item => {
                    const val = Number(item.min_value);
                    return !isNaN(val) ? val : null;
                })
                .filter(val => val !== null && val !== undefined);
            
            // For Labour score, we want to show the calculated period values, not the configured values
            // Filter out values that are too large (likely the configured values like 2000/1000)
            // and use the calculated period values instead
            // The calculated values should be much smaller (e.g., 129.03, 64.52)
            const configuredMaxScore = this.state.quadrants.q1.max_score || 2000;
            const configuredMinScore = this.state.quadrants.q1.min_score || 1000;
            
            // Filter out values that are close to configured values (within 10% tolerance)
            const filteredMaxValues = maxValues.filter(val => {
                const isConfiguredValue = Math.abs(val - configuredMaxScore) < (configuredMaxScore * 0.1);
                return !isConfiguredValue;
            });
            const filteredMinValues = minValues.filter(val => {
                const isConfiguredValue = Math.abs(val - configuredMinScore) < (configuredMinScore * 0.1);
                return !isConfiguredValue;
            });
            
            // Use filtered calculated values, or fall back to all values if no filtered values exist
            const finalMaxValues = filteredMaxValues.length > 0 ? filteredMaxValues : maxValues;
            const finalMinValues = filteredMinValues.length > 0 ? filteredMinValues : minValues;
            
            // Use the maximum of calculated max_values and minimum of calculated min_values
            if (finalMaxValues.length > 0) {
                maxValueLine = Math.max(...finalMaxValues);
                console.log('Labour score - Max values found:', maxValues, 'Filtered max values:', filteredMaxValues, 'Selected max:', maxValueLine);
            } else {
                console.warn('Labour score - No max values found in data!');
            }
            if (finalMinValues.length > 0) {
                minValueLine = Math.min(...finalMinValues);
                console.log('Labour score - Min values found:', minValues, 'Filtered min values:', filteredMinValues, 'Selected min:', minValueLine);
            } else {
                console.warn('Labour score - No min values found in data!');
            }
        } else if (isRcrScore && this.state.quadrants.q1.data && this.state.quadrants.q1.data.length > 0) {
            // For RCR, min/max values are the same across all periods (raw values)
            // Get from first data item
            const firstItem = this.state.quadrants.q1.data[0];
            if (firstItem) {
                const maxVal = Number(firstItem.max_value);
                const minVal = Number(firstItem.min_value);
                
                if (!isNaN(maxVal) && maxVal > 0) {
                    maxValueLine = maxVal;
                    console.log('RCR - Max value:', maxValueLine);
                }
                if (!isNaN(minVal) && minVal > 0) {
                    minValueLine = minVal;
                    console.log('RCR - Min value:', minValueLine);
                }
            }
        }

        // Calculate suggestedMax to ensure both min/max lines are visible
        // Include maxValueLine and minValueLine in the calculation if they exist
        let suggestedMax = maxValue > 0 ? maxValue * 1.1 : 100;
        if (isLabourScore || isRcrScore) {
            const valuesToConsider = [maxValue];
            if (maxValueLine !== null && maxValueLine !== undefined) {
                valuesToConsider.push(maxValueLine);
            }
            if (minValueLine !== null && minValueLine !== undefined) {
                valuesToConsider.push(minValueLine);
            }
            const maxOfAll = Math.max(...valuesToConsider);
            // Add extra padding (20%) to ensure max line is well within visible range
            suggestedMax = maxOfAll > 0 ? maxOfAll * 1.2 : 100;
            console.log(`${isLabourScore ? 'Labour' : 'RCR'} score - suggestedMax calculation:`, {
                maxValue: maxValue,
                maxValueLine: maxValueLine,
                minValueLine: minValueLine,
                maxOfAll: maxOfAll,
                suggestedMax: suggestedMax
            });
        }

        // Removed date range label from top - dates now show below each bar

        // Custom plugin to draw date ranges below x-axis labels and max/min lines for Labour and RCR scores
        // Capture maxValueLine and minValueLine in closure to ensure they're accessible
        const capturedMaxValueLine = maxValueLine;
        const capturedMinValueLine = minValueLine;
        const capturedIsLabourScore = isLabourScore;
        const capturedisRcrScore = isRcrScore;
        
        const dateRangePlugin = {
            id: 'dateRangePlugin',
            afterDraw: (chart) => {
                const ctx = chart.ctx;
                const xAxis = chart.scales.x;
                const yAxis = chart.scales.y;
                const chartArea = chart.chartArea;
                const labels = chartData.labels;
                
                ctx.save();
                
                // Draw max and min value lines for Labour and RCR scores
                // Use captured values from closure
                if ((capturedIsLabourScore || capturedisRcrScore) && (capturedMaxValueLine !== null || capturedMinValueLine !== null)) {
                    console.log('Plugin - Drawing lines with values:', {
                        maxValueLine: capturedMaxValueLine,
                        minValueLine: capturedMinValueLine
                    });
                    ctx.lineWidth = 1.5;
                    ctx.setLineDash([5, 5]); // Dotted line pattern
                    
                    // Draw max value line
                    if (capturedMaxValueLine !== null && capturedMaxValueLine !== undefined) {
                        const maxY = yAxis.getPixelForValue(capturedMaxValueLine);
                        // Check if the value is within the y-axis range
                        const yAxisMin = yAxis.min;
                        const yAxisMax = yAxis.max;
                        
                        console.log('Drawing max line:', {
                            maxValueLine: capturedMaxValueLine,
                            maxY: maxY,
                            yAxisMin: yAxisMin,
                            yAxisMax: yAxisMax,
                            chartAreaTop: chartArea.top,
                            chartAreaBottom: chartArea.bottom,
                            isValid: !isNaN(maxY) && capturedMaxValueLine >= yAxisMin && capturedMaxValueLine <= yAxisMax
                        });
                        
                        // Allow slight tolerance for floating point comparison
                        const tolerance = 0.01;
                        if (!isNaN(maxY) && capturedMaxValueLine >= (yAxisMin - tolerance) && capturedMaxValueLine <= (yAxisMax + tolerance)) {
                            // Clamp the Y position to chart area bounds to ensure visibility
                            const clampedY = Math.max(chartArea.top, Math.min(chartArea.bottom, maxY));
                            
                            // Draw black dotted line
                            ctx.strokeStyle = '#000000'; // Black color
                            ctx.beginPath();
                            ctx.moveTo(chartArea.left, clampedY);
                            ctx.lineTo(chartArea.right, clampedY);
                            ctx.stroke();
                            
                            // Add label at the top of the line, at the end (right side)
                            ctx.fillStyle = '#000000'; // Black text
                            ctx.font = '11px Arial';
                            ctx.textAlign = 'right';
                            ctx.textBaseline = 'bottom'; // Position text above the line
                            ctx.fillText(`${capturedMaxValueLine.toFixed(2)}`, chartArea.right - 5, clampedY - 3);
                        } else {
                            console.warn('Max line not drawn - value outside y-axis range:', {
                                maxValueLine: capturedMaxValueLine,
                                yAxisMin: yAxisMin,
                                yAxisMax: yAxisMax
                            });
                        }
                    }
                    
                    // Draw min value line
                    if (capturedMinValueLine !== null && capturedMinValueLine !== undefined) {
                        const minY = yAxis.getPixelForValue(capturedMinValueLine);
                        // Check if the value is within the y-axis range
                        const yAxisMin = yAxis.min;
                        const yAxisMax = yAxis.max;
                        
                        if (!isNaN(minY) && capturedMinValueLine >= yAxisMin && capturedMinValueLine <= yAxisMax) {
                            // Clamp the Y position to chart area bounds to ensure visibility
                            const clampedY = Math.max(chartArea.top, Math.min(chartArea.bottom, minY));
                            
                            // Draw black dotted line
                            ctx.strokeStyle = '#000000'; // Black color
                            ctx.beginPath();
                            ctx.moveTo(chartArea.left, clampedY);
                            ctx.lineTo(chartArea.right, clampedY);
                            ctx.stroke();
                            
                            // Add label at the top of the line, at the end (right side)
                            ctx.fillStyle = '#000000'; // Black text
                            ctx.font = '11px Arial';
                            ctx.textAlign = 'right';
                            ctx.textBaseline = 'bottom'; // Position text above the line
                            ctx.fillText(`${capturedMinValueLine.toFixed(2)}`, chartArea.right - 5, clampedY - 3);
                        }
                    }
                    
                    // Reset line dash
                    ctx.setLineDash([]);
                }
                
                // Draw date ranges below x-axis labels
                ctx.font = '10px Arial';
                ctx.fillStyle = '#6c757d';
                ctx.textAlign = 'center';
                ctx.textBaseline = 'top';
                
                labels.forEach((label, index) => {
                    if (label && typeof label === 'object' && label.dateRange && label.dateRange.trim() !== '') {
                        try {
                            // Get the pixel position for this tick
                            const x = xAxis.getPixelForTick(index);
                            if (!isNaN(x)) {
                                const y = chartArea.bottom + 25; // Position below the axis
                                ctx.fillText(label.dateRange, x, y);
                            }
                        } catch (error) {
                            console.warn('Error drawing date range for bar', index, error);
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
                        bottom: 40 // Add padding at bottom for date ranges
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
                            size: 13
                        },
                        bodyFont: {
                            size: 16,
                            weight: 'bold'
                        },
                        callbacks: {
                            title: () => {
                                // Hide title, we'll show it in label instead
                                return '';
                            },
                            label: (context) => {
                                const value = context.parsed.y;
                                const datasetLabel = context.dataset.label || 'Value';
                                // Show exact value with 2 decimal places
                                const formattedValue = value.toFixed(2);
                                const suffix = this.state.scoreType === 'percentage' ? '%' : '';
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
                                const originalData = this.originalChartData[dataIndex];
                                if (originalData && originalData.start_date && originalData.end_date) {
                                    try {
                                        const startDate = this.formatDateForTooltip(originalData.start_date);
                                        const endDate = this.formatDateForTooltip(originalData.end_date);
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
                                size: 11
                            },
                            callback: (value, index) => {
                                const label = chartData.labels[index];
                                if (label && typeof label === 'object') {
                                    return label.period;
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
                                if (value >= 1000) {
                                    return (value / 1000).toFixed(2) + 'k';
                                }
                                return value.toFixed(2);
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

        this.chart = new Chart(this.chartRef.el, config);
        
        // Reset rendering flag after chart is successfully created
        this.isRenderingChart = false;

            const canvas = this.chartRef.el;
            if (canvas) {
                canvas.onclick = async (event) => {
                    if (!this.chart) {
                        return;
                    }
                    try {
                        const points = this.chart.getElementsAtEventForMode(event, 'nearest', { intersect: true }, true);
                        if (!points || !points.length) {
                            return;
                        }
                        const firstPoint = points[0];
                        const dataIndex = firstPoint.index;
                        // Only trigger on click of the first dataset (Leads) to avoid duplicate clicks
                        if (firstPoint.datasetIndex === 0) {
                            const selectedData = (this.state.quadrants.q1.data || [])[dataIndex];
                            if (selectedData) {
                                await this.handleOverviewBarClick(selectedData);
                            }
                        }
                    } catch (error) {
                        console.error('Error handling chart click:', error);
                    }
                };
            }
        } catch (error) {
            console.error('Error rendering chart:', error);
            this.isRenderingChart = false; // Reset flag on error
        }
    }
}

registry.category("actions").add("score_dashboard", ScoreDashboard);

// Global initialization: Apply scrolling fix when score dashboard action is loaded
// This ensures scrolling works for all score dashboards
document.addEventListener('DOMContentLoaded', () => {
    // Initial fix
    fixScoreDashboardScrolling();
    
    // Also watch for navigation/action changes
    const actionManager = document.querySelector('.o_action_manager');
    if (actionManager) {
        const navObserver = new MutationObserver(() => {
            // Check if score dashboard is active
            const scoreDashboard = document.querySelector('.o_score_dashboard_container, [data-action-id*="score"]');
            if (scoreDashboard) {
                setTimeout(() => fixScoreDashboardScrolling(), 100);
            }
        });
        
        navObserver.observe(actionManager, {
            childList: true,
            subtree: true
        });
    }
});

// Also apply fix immediately if DOM is already loaded
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', fixScoreDashboardScrolling);
} else {
    // DOM is already loaded
    setTimeout(fixScoreDashboardScrolling, 100);
}