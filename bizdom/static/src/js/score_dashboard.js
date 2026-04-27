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
                q3: { title: "Level 2 Breakdown", data: [] },
                q4: { title: "Analysis", data: [] },
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
            chartTypeQ1: 'bar',
            chartTypeQ2: 'bar',
            chartTypeQ3: 'bar',
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
            
            // Update date range label - handle CUSTOM separately
            if (this.state.filterType === 'CUSTOM' && this.state.customRange?.start && this.state.customRange?.end) {
                const startDate = this.parseDateString(this.state.customRange.start);
                const endDate = this.parseDateString(this.state.customRange.end);
                if (startDate && endDate) {
                    this.state.dateRangeLabel = `Custom: ${this.formatRangeLabel(startDate, endDate)}`;
                }
            } else {
                const preset = this.getPresetRange(this.state.filterType);
                this.state.dateRangeLabel = preset.label;
            }
            
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
        
        let nextRange;
        if (normalizedFilter === 'CUSTOM') {
            // Allow switching to CUSTOM even if dates aren't set yet
            // User can then select dates, which will trigger loadScoreData
            if (this.state.customRange.start && this.state.customRange.end) {
                nextRange = { ...this.state.customRange };
                const start = this.parseDateString(nextRange.start);
                const end = this.parseDateString(nextRange.end);
                if (start && end) {
                    this.state.dateRangeLabel = `Custom: ${this.formatRangeLabel(start, end)}`;
                    this.state.activeRange = {
                        start: this.formatDateForServer(start),
                        end: this.formatDateForServer(end),
                    };
                } else {
                    this.state.dateRangeLabel = "Select start and end dates";
                    this.state.loading = false;
                    this.state.filterType = normalizedFilter;
                    return;
                }
            } else {
                // No dates selected yet, just switch to CUSTOM filter
                this.state.dateRangeLabel = "Select start and end dates";
                this.state.filterType = normalizedFilter;
                this.state.loading = false;
                return;
            }
        } else {
            const preset = this.getPresetRange(normalizedFilter);
            nextRange = { start: preset.start_date, end: preset.end_date };
            // Use the preset label directly (it's already correctly formatted with Date objects)
            this.state.dateRangeLabel = preset.label;
        }
        
        // Set loading state immediately for smooth transition
        this.state.loading = true;
        
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

    onChartTypeChange(quadrant, ev) {
        const value = ev.target.value;
        if (quadrant === 'q1') {
            this.state.chartTypeQ1 = value;
            this.renderChart();
        } else if (quadrant === 'q2') {
            this.state.chartTypeQ2 = value;
            this.renderDepartmentChart();
        } else if (quadrant === 'q3') {
            this.state.chartTypeQ3 = value;
            this.renderEmployeeChart();
        }
    }

    onCustomDateChange(field, ev) {
        this.state.customRange = {
            ...this.state.customRange,
            [field]: ev.target.value,
        };

        const { start, end } = this.state.customRange;
        if (start && end) {
            const startDate = this.parseDateString(start);
            const endDate = this.parseDateString(end);
            
            if (startDate && endDate && startDate > endDate) {
                console.warn("Start date cannot be after end date");
                this.state.dateRangeLabel = "Start date cannot be after end date";
                return;
            }
            
            // Update date range label and active range
            if (startDate && endDate) {
                this.state.dateRangeLabel = `Custom: ${this.formatRangeLabel(startDate, endDate)}`;
                this.state.activeRange = {
                    start: this.formatDateForServer(startDate),
                    end: this.formatDateForServer(endDate),
                };
                // Automatically load data when both dates are selected and filter is CUSTOM
                if (this.state.filterType === 'CUSTOM') {
                    this.loadScoreData();
                }
            }
        } else {
            this.state.dateRangeLabel = "Select start and end dates";
        }
    }

    getMaxValue(data) {
        if (!data || data.length === 0) return 100;
        return Math.max(...data.map(item => item.actual_value || 0), 100);
    }

    getPeriodLabel(item, filterType) {
        // Check if this is a custom period format (contains "to" separator)
        // API returns period as "DD-MM-YYYY to DD-MM-YYYY" for custom filters
        const normalizedFilterType = filterType ? String(filterType).toUpperCase().trim() : '';
        const isCustomFilter = normalizedFilterType === 'CUSTOM';
        const hasCustomPeriodFormat = item?.period && item.period.includes(' to ');
        
        // If it's a custom filter OR the period has the custom format, format it
        if (isCustomFilter || hasCustomPeriodFormat) {
            if (item?.period) {
                try {
                    // Parse the period string "DD-MM-YYYY to DD-MM-YYYY"
                    const periodParts = item.period.split(' to ');
                    if (periodParts.length === 2) {
                        const startStr = periodParts[0].trim();
                        const endStr = periodParts[1].trim();
                        
                        // Parse DD-MM-YYYY format
                        const startParts = startStr.split('-');
                        const endParts = endStr.split('-');
                        
                        if (startParts.length === 3 && endParts.length === 3) {
                            // Format as "DD MMM YYYY to DD MMM YYYY"
                            const startFormatted = `${parseInt(startParts[0])} ${this.getMonthName(parseInt(startParts[1]))} ${startParts[2]}`;
                            const endFormatted = `${parseInt(endParts[0])} ${this.getMonthName(parseInt(endParts[1]))} ${endParts[2]}`;
                            return `${startFormatted} to ${endFormatted}`;
                        }
                    }
                } catch (error) {
                    console.warn('Error formatting custom period:', error, item.period);
                }
                // Fallback to raw period string if formatting fails
                return item.period;
            }
            // If period is missing, try to construct from start_date and end_date
            if (item?.start_date && item?.end_date) {
                try {
                    const startParts = item.start_date.split('-');
                    const endParts = item.end_date.split('-');
                    if (startParts.length === 3 && endParts.length === 3) {
                        const startFormatted = `${parseInt(startParts[0])} ${this.getMonthName(parseInt(startParts[1]))} ${startParts[2]}`;
                        const endFormatted = `${parseInt(endParts[0])} ${this.getMonthName(parseInt(endParts[1]))} ${endParts[2]}`;
                        return `${startFormatted} to ${endFormatted}`;
                    }
                } catch (error) {
                    console.warn('Error constructing period from dates:', error);
                }
                return `${item.start_date} to ${item.end_date}`;
            }
            return '';
        }
        // For other filters, prioritize period field, then month/year
        // This ensures we use the period string from API when available
        return item?.period || item?.month || item?.year || '';
    }

    formatValue(value) {
        const numericValue = Number(value || 0);
        return numericValue.toFixed(1);
    }

    /**
     * Format a numeric value for display based on score type (percentage, currency_inr, value).
     */
    formatScoreValue(value) {
        const num = Number(value || 0);
        const scoreType = this.state.scoreType || 'value';
        if (scoreType === 'percentage') {
            return num.toFixed(2) + '%';
        }
        if (scoreType === 'currency_inr') {
            return '₹' + num.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
        }
        return num.toFixed(2);
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
        
        // For CUSTOM filter, try to use customRange from state
        if (this.state.filterType === 'CUSTOM' && this.state.customRange?.start && this.state.customRange?.end) {
            const startDate = this.parseDateString(this.state.customRange.start);
            const endDate = this.parseDateString(this.state.customRange.end);
            if (startDate && endDate) {
                this.state.activeRange = {
                    start: this.formatDateForServer(startDate),
                    end: this.formatDateForServer(endDate),
                };
                this.state.dateRangeLabel = `Custom: ${this.formatRangeLabel(startDate, endDate)}`;
                return this.state.activeRange;
            }
        }
        
        // Fallback to preset range
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
            case "CUSTOM": {
                // For custom, use the state's customRange if available
                if (this.state?.customRange?.start && this.state?.customRange?.end) {
                    const start = this.parseDateString(this.state.customRange.start);
                    const end = this.parseDateString(this.state.customRange.end);
                    if (start && end) {
                        startDate = start;
                        endDate = end;
                        label = `Custom: ${this.formatRangeLabel(startDate, endDate)}`;
                        break;
                    }
                }
                // Fall through to MTD if custom range not set
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
        // Only for Labour, Leads, Conversion, and Customer Retention scores (which have Q3 data)
        const scoreNameLower = (this.state.scoreName || '').toLowerCase();
        if (scoreNameLower === 'labour' || scoreNameLower === 'leads' || scoreNameLower === 'conversion' || scoreNameLower === 'customer retention'  || scoreNameLower === 'income'||scoreNameLower === 'expense'|| scoreNameLower === 'aov') {
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
            
            // Determine colors based on min/max values
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
            const hasValidMinMax =
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
            if (Array.isArray(this.state.departmentChartData.conversionValues) &&
                this.state.departmentChartData.conversionValues.length > 0) {
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

        const chartTypeQ2 = this.state.chartTypeQ2 || 'bar';
        this.departmentChart = new Chart(canvas, {
            type: chartTypeQ2,
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
                            title: () => {
                                const tooltipScoreName = this.state.scoreName || this.state.quadrants?.q1?.score_name;
                                return tooltipScoreName || 'Score';
                            },
                            label: (context) => {
                                // For both bar and line charts, x-axis has categories, y-axis has values
                                const value = context.parsed.y || 0;
                                const datasetLabel = context.datasetIndex === 0
                                    ? 'Actual'
                                    : (context.dataset.label || 'Value');
                                const formattedValue = this.formatScoreValue(value);
                                const tooltipLines = [`${datasetLabel}: ${formattedValue}`];
                                
                                // Add min/max values when available (first dataset only)
                                if (context.datasetIndex === 0 &&
                                    this.state.departmentChartData.minValues &&
                                    this.state.departmentChartData.maxValues) {
                                    const dataIndex = context.dataIndex;
                                    const minValue = this.state.departmentChartData.minValues[dataIndex];
                                    const maxValue = this.state.departmentChartData.maxValues[dataIndex];
                                    
                                    if (minValue !== null && maxValue !== null && 
                                        minValue !== undefined && maxValue !== undefined &&
                                        !isNaN(minValue) && !isNaN(maxValue) &&
                                        !(minValue === 0 && maxValue === 0)) {
                                        tooltipLines.push(`Min: ${this.formatScoreValue(minValue)}`);
                                        tooltipLines.push(`Max: ${this.formatScoreValue(maxValue)}`);
                                    }
                                }
                                
                                return tooltipLines;
                            }
                        }
                    }
                },
                scales: {
                    // For both bar and line charts, x-axis has categories, y-axis has values
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
                                if (this.state.scoreType === 'currency_inr' && value >= 1000) {
                                    return '₹' + (value / 1000).toFixed(2) + 'k';
                                }
                                if (value >= 1000 && this.state.scoreType !== 'currency_inr') {
                                    return (value / 1000).toFixed(2) + 'k' + (isPercentage ? '%' : '');
                                }
                                return this.formatScoreValue(value);
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
        
        // Extract min/max values for all scores when available
        let minValues = null;
        let maxValues = null;
        
        minValues = departments.map((dep, idx) => {
            const minVal = dep.min_value;
            const result = (minVal === '' || minVal === null || minVal === undefined) ? null : Number(minVal);
            if (isLabourScore) {
                console.log(`Department ${idx} (${dep.department_name}${dep.category_name ? ', category: ' + dep.category_name : ''}): min_value = ${minVal} -> ${result}, actual_value = ${dep.actual_value}`);
            }
            return Number.isFinite(result) ? result : null;
        });
        maxValues = departments.map((dep, idx) => {
            const maxVal = dep.max_value;
            const result = (maxVal === '' || maxVal === null || maxVal === undefined) ? null : Number(maxVal);
            if (isLabourScore) {
                console.log(`Department ${idx} (${dep.department_name}${dep.category_name ? ', category: ' + dep.category_name : ''}): max_value = ${maxVal} -> ${result}, actual_value = ${dep.actual_value}`);
            }
            return Number.isFinite(result) ? result : null;
        });
        if (isLabourScore) {
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
        
        // Handle for Labour, Leads, Conversion, Customer Retention, Income, and AOV scores
        if (scoreNameLower !== 'labour' && scoreNameLower !== 'leads' && scoreNameLower !== 'conversion' && scoreNameLower !== 'customer retention' && scoreNameLower !== 'income' && scoreNameLower !== 'expense' && scoreNameLower !== 'aov') {
            console.log('Employee/Source/Question/Category overview only available for Labour, Leads, Conversion, Customer Retention, Income, and AOV scores');
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
                    // Q3 now uses overview_category; keep fallback for older payloads.
                    this.state.employeeData = empData.overview_category || empData.overview_source || empData.overview_employee || [];
                    if (!this.state.employeeData.length) {
                        this.state.employeeError = 'No source data available for this medium.';
                    } else {
                        this.state.employeeError = null;
                        // Build leads chart data (same structure as employee chart data)
                        this.buildLeadsChartData();
                    }
                } else if (scoreNameLower === 'conversion') {
                    // Q3 now uses overview_category; keep fallback for older payloads.
                    this.state.employeeData = empData.overview_category || empData.overview_source || empData.overview_employee || [];
                    if (!this.state.employeeData.length) {
                        this.state.employeeError = 'No salesperson data available for this medium.';
                    } else {
                        this.state.employeeError = null;
                        // Build conversion chart data (similar to leads but for salespersons)
                        this.buildConversionChartData();
                    }
                } else if (scoreNameLower === 'customer retention') {
                    // Q3 now uses overview_category; keep fallback for older payloads.
                    this.state.employeeData = empData.overview_category || empData.overview_employee || [];
                    if (!this.state.employeeData.length) {
                        this.state.employeeError = 'No question data available for this department.';
                    } else {
                        this.state.employeeError = null;
                        // Build chart data from question data
                        this.buildCustomerRetentionChartData();
                    }
                } else if (scoreNameLower === 'income') {
                    // For Income score, use overview_category (contains product categories)
                    this.state.employeeData = empData.overview_category || empData.overview_product || [];
                    if (!this.state.employeeData.length) {
                        this.state.employeeError = 'No category data available for this department.';
                    } else {
                        this.state.employeeError = null;
                        // Build chart data from category data
                        this.buildIncomeChartData();
                    }
                }
                else if (scoreNameLower === 'expense') {
                    // For Income score, use overview_category (contains product categories)
                    this.state.employeeData = empData.overview_category || empData.overview_product || [];
                    if (!this.state.employeeData.length) {
                        this.state.employeeError = 'No category data available for this department.';
                    } else {
                        this.state.employeeError = null;
                        // Build chart data from category data
                        this.buildIncomeChartData();
                    }
                }


                else if (scoreNameLower === 'aov') {
                    // Q3 now uses overview_category; keep fallback for older payloads.
                    this.state.employeeData = empData.overview_category || empData.overview_employee || [];
                    if (!this.state.employeeData.length) {
                        this.state.employeeError = 'No car brand data available for this department.';
                    } else {
                        this.state.employeeError = null;
                        this.buildEmployeeChartData();
                    }
                } else {
                    // Q3 now uses overview_category; keep fallback for older payloads.
                    this.state.employeeData = empData.overview_category || empData.overview_employee || [];
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
        
        // Process categories/sources from the selected period
        const sources = [];
        const periodSources = selectedPeriodData.categories || selectedPeriodData.sources || [];

        if (Array.isArray(periodSources)) {
            periodSources.forEach(source => {
                sources.push({
                    source_id: source.source_id,
                    source_name: source.source_name || 'N/A',
                    lead_value: Number(source.lead_value || 0),
                    quality_lead_value: Number(source.quality_lead_value || 0),
                    min_value: source.min_value,
                    max_value: source.max_value
                });
            });
        }

        // Sort by lead_value descending
        sources.sort((a, b) => b.lead_value - a.lead_value);

        // Build chart data with both Leads and Quality Leads datasets (similar to Quadrant 1)
        const sharedMinRaw = selectedPeriodData.min_value;
        const sharedMaxRaw = selectedPeriodData.max_value;
        const sharedMin = (sharedMinRaw === '' || sharedMinRaw === null || sharedMinRaw === undefined)
            ? null
            : Number(sharedMinRaw);
        const sharedMax = (sharedMaxRaw === '' || sharedMaxRaw === null || sharedMaxRaw === undefined)
            ? null
            : Number(sharedMaxRaw);

        this.state.employeeChartData = {
            labels: sources.map(s => s.source_name),
            values: sources.map(s => s.lead_value),
            conversionValues: sources.map(s => s.quality_lead_value),
            minValues: sources.map(s => {
                const minVal = s.min_value;
                if (minVal === '' || minVal === null || minVal === undefined) return null;
                const parsed = Number(minVal);
                return Number.isFinite(parsed) ? parsed : null;
            }),
            maxValues: sources.map(s => {
                const maxVal = s.max_value;
                if (maxVal === '' || maxVal === null || maxVal === undefined) return null;
                const parsed = Number(maxVal);
                return Number.isFinite(parsed) ? parsed : null;
            }),
            sharedMin: Number.isFinite(sharedMin) ? sharedMin : null,
            sharedMax: Number.isFinite(sharedMax) ? sharedMax : null
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
        const salespersons = [];
        const periodSalespersons = selectedPeriodData.categories || selectedPeriodData.sources || [];

        if (Array.isArray(periodSalespersons)) {
            periodSalespersons.forEach(salesperson => {
                salespersons.push({
                    saleperson_id: salesperson.saleperson_id,
                    saleperson_name: salesperson.saleperson_name || 'N/A',
                    quality_lead_value: Number(salesperson.quality_lead_value || 0),
                    converted_value: Number(salesperson.converted_value || 0),
                    min_value: salesperson.min_value,
                    max_value: salesperson.max_value
                });
            });
        }

        // Sort by quality_lead_value descending
        salespersons.sort((a, b) => b.quality_lead_value - a.quality_lead_value);

        // Build chart data with both Quality Leads (total) and Converted datasets
        const sharedMinRaw = selectedPeriodData.min_value;
        const sharedMaxRaw = selectedPeriodData.max_value;
        const sharedMin = (sharedMinRaw === '' || sharedMinRaw === null || sharedMinRaw === undefined)
            ? null
            : Number(sharedMinRaw);
        const sharedMax = (sharedMaxRaw === '' || sharedMaxRaw === null || sharedMaxRaw === undefined)
            ? null
            : Number(sharedMaxRaw);

        this.state.employeeChartData = {
            labels: salespersons.map(s => s.saleperson_name),
            values: salespersons.map(s => s.quality_lead_value),
            conversionValues: salespersons.map(s => s.converted_value),
            minValues: salespersons.map(s => {
                const minVal = s.min_value;
                if (minVal === '' || minVal === null || minVal === undefined) return null;
                const parsed = Number(minVal);
                return Number.isFinite(parsed) ? parsed : null;
            }),
            maxValues: salespersons.map(s => {
                const maxVal = s.max_value;
                if (maxVal === '' || maxVal === null || maxVal === undefined) return null;
                const parsed = Number(maxVal);
                return Number.isFinite(parsed) ? parsed : null;
            }),
            sharedMin: Number.isFinite(sharedMin) ? sharedMin : null,
            sharedMax: Number.isFinite(sharedMax) ? sharedMax : null
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
                    employeeCount: (p.categories?.length || p.employees?.length || 0),
                    employees: (p.categories || p.employees || []).map(e => ({ name: e.employee_name, value: e.actual_value }))
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
                            employees: (period.categories || period.employees || []).map(e => ({ name: e.employee_name, value: e.actual_value }))
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
                            employees: (period.categories || period.employees || []).map(e => ({ name: e.employee_name, value: e.actual_value }))
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
                        employees: (selectedPeriodData.categories || selectedPeriodData.employees || []).map(e => ({ name: e.employee_name, value: e.actual_value }))
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
                values: [],
                sharedMin: null,
                sharedMax: null
            };
            return;
        }
        
        const periodsToProcess = [selectedPeriodData];
        
        console.log('Processing periods for employee chart:', {
            selectedPeriodData: {
                start_date: selectedPeriodData.start_date,
                end_date: selectedPeriodData.end_date,
                employeeCount: (selectedPeriodData.categories?.length || selectedPeriodData.employees?.length || 0),
                employees: (selectedPeriodData.categories || selectedPeriodData.employees || []).map(e => ({ name: e.employee_name, value: e.actual_value }))
            }
        });
        
        // Process employees from the selected period only - no aggregation needed
        const employees = [];
        
        const periodEmployees = selectedPeriodData.categories || selectedPeriodData.employees || [];
        if (Array.isArray(periodEmployees)) {
            periodEmployees.forEach(emp => {
                employees.push({
                    employee_id: emp.employee_id,
                    employee_name: emp.employee_name || 'N/A',
                    actual_value: Number(emp.actual_value || 0),
                    min_value: emp.min_value,
                    max_value: emp.max_value
                });
            });
        }

        // Sort by actual_value descending
        employees.sort((a, b) => b.actual_value - a.actual_value);

        console.log('Final employee chart data:', {
            employeeCount: employees.length,
            employees: employees.map(e => ({ name: e.employee_name, value: e.actual_value }))
        });

        const sharedMinRaw = selectedPeriodData.min_value;
        const sharedMaxRaw = selectedPeriodData.max_value;
        const sharedMin = (sharedMinRaw === '' || sharedMinRaw === null || sharedMinRaw === undefined)
            ? null
            : Number(sharedMinRaw);
        const sharedMax = (sharedMaxRaw === '' || sharedMaxRaw === null || sharedMaxRaw === undefined)
            ? null
            : Number(sharedMaxRaw);

        this.state.employeeChartData = {
            labels: employees.map(emp => emp.employee_name),
            values: employees.map(emp => emp.actual_value),
            minValues: employees.map(emp => {
                const minVal = emp.min_value;
                if (minVal === '' || minVal === null || minVal === undefined) return null;
                const parsed = Number(minVal);
                return Number.isFinite(parsed) ? parsed : null;
            }),
            maxValues: employees.map(emp => {
                const maxVal = emp.max_value;
                if (maxVal === '' || maxVal === null || maxVal === undefined) return null;
                const parsed = Number(maxVal);
                return Number.isFinite(parsed) ? parsed : null;
            }),
            sharedMin: Number.isFinite(sharedMin) ? sharedMin : null,
            sharedMax: Number.isFinite(sharedMax) ? sharedMax : null
        };
    }

    buildCustomerRetentionChartData() {
        if (!this.state.employeeData || this.state.employeeData.length === 0) {
            this.state.employeeChartData = null;
            return;
        }

        // Filter to show only questions from the selected period
        let selectedPeriodData = null;
        
        if (this.state.selectedPeriodInfo && (this.state.selectedPeriodInfo.startDate || this.state.selectedPeriodInfo.endDate)) {
            // Find the matching period in employee data
            const periodStart = String(this.state.selectedPeriodInfo.startDate || '').trim();
            const periodEnd = String(this.state.selectedPeriodInfo.endDate || '').trim();
            
            // Normalize dates for comparison - ensure both are strings in DD-MM-YYYY format
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
                values: []
            };
            return;
        }
        
        // Process questions/categories from the selected period
        const questions = [];
        const periodQuestions = selectedPeriodData.categories || selectedPeriodData.questions || [];

        if (Array.isArray(periodQuestions)) {
            periodQuestions.forEach(q => {
                // Only include questions with actual_value (not empty string)
                if (q.actual_value !== "" && q.actual_value !== null && q.actual_value !== undefined) {
                    questions.push({
                        question_id: q.question_id,
                        question: q.question || 'N/A',
                        actual_value: Number(q.actual_value || 0),
                        min_value: q.min_value,
                        max_value: q.max_value
                    });
                }
            });
        }

        // Sort by actual_value descending
        questions.sort((a, b) => b.actual_value - a.actual_value);

        const sharedMinRaw = selectedPeriodData.min_value;
        const sharedMaxRaw = selectedPeriodData.max_value;
        const sharedMin = (sharedMinRaw === '' || sharedMinRaw === null || sharedMinRaw === undefined)
            ? null
            : Number(sharedMinRaw);
        const sharedMax = (sharedMaxRaw === '' || sharedMaxRaw === null || sharedMaxRaw === undefined)
            ? null
            : Number(sharedMaxRaw);

        this.state.employeeChartData = {
            labels: questions.map(q => q.question),
            values: questions.map(q => q.actual_value),
            minValues: questions.map(q => {
                const minVal = q.min_value;
                if (minVal === '' || minVal === null || minVal === undefined) return null;
                const parsed = Number(minVal);
                return Number.isFinite(parsed) ? parsed : null;
            }),
            maxValues: questions.map(q => {
                const maxVal = q.max_value;
                if (maxVal === '' || maxVal === null || maxVal === undefined) return null;
                const parsed = Number(maxVal);
                return Number.isFinite(parsed) ? parsed : null;
            }),
            sharedMin: Number.isFinite(sharedMin) ? sharedMin : null,
            sharedMax: Number.isFinite(sharedMax) ? sharedMax : null
        };
    }

    buildIncomeChartData() {
        if (!this.state.employeeData || this.state.employeeData.length === 0) {
            this.state.employeeChartData = null;
            return;
        }

        // Filter to show only products from the selected period
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
            console.error('❌ No matching period found - showing empty chart');
            this.state.employeeChartData = {
                labels: [],
                values: []
            };
            return;
        }

        // Process categories (or products for backward compatibility) from the selected period
        const items = [];

        if (selectedPeriodData.categories && Array.isArray(selectedPeriodData.categories)) {
            selectedPeriodData.categories.forEach(cat => {
                items.push({
                    id: cat.category_id,
                    name: cat.category_name || 'N/A',
                    actual_value: Number(cat.actual_value || 0),
                    min_value: cat.min_value,
                    max_value: cat.max_value
                });
            });
        } else if (selectedPeriodData.products && Array.isArray(selectedPeriodData.products)) {
            selectedPeriodData.products.forEach(product => {
                items.push({
                    id: product.product_id || product.category_id,
                    name: product.product_name || product.category_name || 'N/A',
                    actual_value: Number(product.actual_value || 0),
                    min_value: product.min_value,
                    max_value: product.max_value
                });
            });
        } else if (selectedPeriodData.employees && Array.isArray(selectedPeriodData.employees)) {
            selectedPeriodData.employees.forEach(product => {
                items.push({
                    id: product.product_id || product.category_id || product.employee_id,
                    name: product.product_name || product.category_name || product.employee_name || 'N/A',
                    actual_value: Number(product.actual_value || 0),
                    min_value: product.min_value,
                    max_value: product.max_value
                });
            });
        }

        // Sort by actual_value descending
        items.sort((a, b) => b.actual_value - a.actual_value);

        const sharedMinRaw = selectedPeriodData.min_value;
        const sharedMaxRaw = selectedPeriodData.max_value;
        const sharedMin = (sharedMinRaw === '' || sharedMinRaw === null || sharedMinRaw === undefined)
            ? null
            : Number(sharedMinRaw);
        const sharedMax = (sharedMaxRaw === '' || sharedMaxRaw === null || sharedMaxRaw === undefined)
            ? null
            : Number(sharedMaxRaw);

        this.state.employeeChartData = {
            labels: items.map(p => p.name),
            values: items.map(p => p.actual_value),
            minValues: items.map(p => {
                const minVal = p.min_value;
                if (minVal === '' || minVal === null || minVal === undefined) return null;
                const parsed = Number(minVal);
                return Number.isFinite(parsed) ? parsed : null;
            }),
            maxValues: items.map(p => {
                const maxVal = p.max_value;
                if (maxVal === '' || maxVal === null || maxVal === undefined) return null;
                const parsed = Number(maxVal);
                return Number.isFinite(parsed) ? parsed : null;
            }),
            sharedMin: Number.isFinite(sharedMin) ? sharedMin : null,
            sharedMax: Number.isFinite(sharedMax) ? sharedMax : null
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
            const isCustomerRetentionScore = scoreNameLower === 'customer retention';
            const isIncomeScore = scoreNameLower === 'income';
            const isExpenseScore = scoreNameLower === 'expense';
            const isAOVScore = scoreNameLower === 'aov';


            // Build datasets based on score type
            const datasets = [];
            const sharedMin = this.state.employeeChartData.sharedMin;
            const sharedMax = this.state.employeeChartData.sharedMax;
            const thresholdMinValues = this.state.employeeChartData.minValues;
            const thresholdMaxValues = this.state.employeeChartData.maxValues;
            const hasPerItemThresholds = Array.isArray(thresholdMinValues) &&
                Array.isArray(thresholdMaxValues) &&
                thresholdMinValues.length === this.state.employeeChartData.values.length &&
                thresholdMaxValues.length === this.state.employeeChartData.values.length;
            const hasSharedThresholds = Number.isFinite(sharedMin) && Number.isFinite(sharedMax) && !(sharedMin === 0 && sharedMax === 0);
            const hasThresholds = hasPerItemThresholds || hasSharedThresholds;
            let primaryColors = '#0d6efd';
            let primaryBorderColors = '#0d6efd';
            if (hasThresholds) {
                const tolerance = 0.01;
                primaryColors = this.state.employeeChartData.values.map((actualValue, index) => {
                    const numericActual = Number(actualValue || 0);
                    const perItemMin = hasPerItemThresholds ? thresholdMinValues[index] : null;
                    const perItemMax = hasPerItemThresholds ? thresholdMaxValues[index] : null;
                    // If per-item arrays exist, use only per-item thresholds for that bar.
                    // Fall back to shared thresholds only when per-item thresholds are not present at all.
                    const minThreshold = hasPerItemThresholds
                        ? (Number.isFinite(perItemMin) ? perItemMin : null)
                        : (hasSharedThresholds ? sharedMin : null);
                    const maxThreshold = hasPerItemThresholds
                        ? (Number.isFinite(perItemMax) ? perItemMax : null)
                        : (hasSharedThresholds ? sharedMax : null);
                    if (!Number.isFinite(minThreshold) || !Number.isFinite(maxThreshold) || (minThreshold === 0 && maxThreshold === 0)) {
                        return '#0d6efd';
                    }
                    if (numericActual < minThreshold - tolerance) return '#dc3545';
                    if (numericActual >= maxThreshold - tolerance) return '#198754';
                    return '#ffc107';
                });
                primaryBorderColors = primaryColors;
            }
            
            if (isLeadsScore) {
                // For Leads score: show both Leads and Quality Leads as grouped bars
                datasets.push({
                    label: 'Leads',
                    data: this.state.employeeChartData.values,
                    backgroundColor: primaryColors,
                    borderColor: primaryBorderColors,
                    borderWidth: 1,
                    borderRadius: 4
                });
                
                // Add Quality Leads dataset if available
                if (Array.isArray(this.state.employeeChartData.conversionValues) &&
                    this.state.employeeChartData.conversionValues.length > 0) {
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
                    backgroundColor: primaryColors,
                    borderColor: primaryBorderColors,
                    borderWidth: 1,
                    borderRadius: 4
                });
                
                // Add Converted dataset if available
                if (Array.isArray(this.state.employeeChartData.conversionValues) &&
                    this.state.employeeChartData.conversionValues.length > 0) {
                    datasets.push({
                        label: 'Converted',
                        data: this.state.employeeChartData.conversionValues,
                        backgroundColor: '#198754',
                        borderColor: '#198754',
                        borderWidth: 1,
                        borderRadius: 4
                    });
                }
            } else if (isCustomerRetentionScore) {
                // For Customer Retention score: single dataset with Average Rating label
                datasets.push({
                    label: 'Average Rating',
                    data: this.state.employeeChartData.values,
                    backgroundColor: primaryColors,
                    borderColor: primaryBorderColors,
                    borderWidth: 1,
                    borderRadius: 4
                });
            } else if (isIncomeScore) {
                // For Income score: single dataset with Income label
                datasets.push({
                    label: 'Income',
                    data: this.state.employeeChartData.values,
                    backgroundColor: primaryColors,
                    borderColor: primaryBorderColors,
                    borderWidth: 1,
                    borderRadius: 4
                });
            }
            else if (isExpenseScore) {
                // For Expense score: single dataset with Expense label
                datasets.push({
                    label: 'Expense',
                    data: this.state.employeeChartData.values,
                    backgroundColor: primaryColors,
                    borderColor: primaryBorderColors,
                    borderWidth: 1,
                    borderRadius: 4
                });
            }
            else {
                // For Labour score: single dataset
                datasets.push({
                    label: 'Labour',
                    data: this.state.employeeChartData.values,
                    backgroundColor: primaryColors,
                    borderColor: primaryBorderColors,
                    borderWidth: 1,
                    borderRadius: 4
                });
            }

            // Calculate max value across all datasets
            const allValues = datasets.flatMap(dataset => (dataset.data || []));
            const maxValue = allValues.length > 0 ? Math.max(...allValues, 0) : 0;
            const suggestedMax = maxValue > 0 ? maxValue * 1.1 : 100;
            
            // Capture labels for tooltip callback
            const chartLabels = this.state.employeeChartData.labels || [];
            
            // Custom plugin to ensure minimum bar visibility - lightweight
            const minBarVisibilityPlugin = {
                id: 'minBarVisibilityPlugin',
                afterDatasetsDraw: (chart) => {
                    if (!chart.scales?.x) return;
                    
                    const ctx = chart.ctx;
                    const x0 = chart.scales.x.getPixelForValue(0);
                    const minBarWidth = 4;
                    
                    ctx.save();
                    
                    // Process datasets efficiently
                    const datasets = chart.data.datasets;
                    for (let d = 0; d < datasets.length; d++) {
                        const dataset = datasets[d];
                        const meta = chart.getDatasetMeta(d);
                        if (!meta?.data) continue;
                        
                        ctx.fillStyle = dataset.backgroundColor || '#0d6efd';
                        const bars = meta.data;
                        
                        for (let i = 0; i < bars.length; i++) {
                            const bar = bars[i];
                            if (bar && !bar.hidden && bar.width) {
                                const value = bar.parsed?.x || 0;
                                if (value > 0 && bar.width < minBarWidth) {
                                    ctx.fillRect(x0, bar.y - (bar.height / 2), minBarWidth, bar.height);
                                }
                            }
                        }
                    }
                    
                    ctx.restore();
                }
            };

            const chartTypeQ3 = this.state.chartTypeQ3 || 'bar';
            const optionsQ3 = {
                maintainAspectRatio: false,
                responsive: true,
                ...(chartTypeQ3 === 'bar' ? { indexAxis: 'y' } : {}), // Horizontal bars only
                animation: {
                    duration: 600,
                    easing: 'easeOutQuart'
                },
                interaction: {
                    intersect: false,
                    mode: 'nearest'
                },
                plugins: {
                    legend: {
                        display: isLeadsScore || isConversionScore,
                        position: 'top',
                        align: 'end',
                        labels: {
                            usePointStyle: true,
                            padding: 15,
                            font: { size: 12 }
                        }
                    },
                    tooltip: {
                        enabled: true,
                        intersect: false,
                        mode: 'nearest',
                        animation: { duration: 200 },
                        callbacks: {
                            title: () => {
                                const tooltipScoreName = this.state.scoreName || this.state.quadrants?.q1?.score_name;
                                return tooltipScoreName || 'Score';
                            },
                            label: (context) => {
                                const value = chartTypeQ3 === 'bar' ? (context.parsed?.x ?? 0) : (context.parsed?.y ?? 0);
                                const datasetLabel = context.datasetIndex === 0
                                    ? 'Actual'
                                    : (context.dataset.label || 'Value');
                                const decimals = (isCustomerRetentionScore || isLabourScore || isIncomeScore || isExpenseScore || isAOVScore) ? 2 : 0;
                                const tooltipLines = [`${datasetLabel}: ${value.toFixed(decimals)}`];
                                if (context.datasetIndex === 0) {
                                    const dataIndex = context.dataIndex;
                                    const perItemMin = Array.isArray(thresholdMinValues)
                                        ? thresholdMinValues[dataIndex]
                                        : (Number.isFinite(sharedMin) ? sharedMin : null);
                                    const perItemMax = Array.isArray(thresholdMaxValues)
                                        ? thresholdMaxValues[dataIndex]
                                        : (Number.isFinite(sharedMax) ? sharedMax : null);
                                    const minThreshold = Number.isFinite(perItemMin) ? perItemMin : null;
                                    const maxThreshold = Number.isFinite(perItemMax) ? perItemMax : null;
                                    if (Number.isFinite(minThreshold) && Number.isFinite(maxThreshold) &&
                                        !(minThreshold === 0 && maxThreshold === 0)) {
                                        tooltipLines.push(`Min: ${this.formatScoreValue(minThreshold)}`);
                                        tooltipLines.push(`Max: ${this.formatScoreValue(maxThreshold)}`);
                                    }
                                }
                                return tooltipLines;
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
                            stepSize: isCustomerRetentionScore ? 0.5 : 1,
                            maxTicksLimit: Math.ceil(suggestedMax) + 1,
                            callback: (value) => {
                                if (isCustomerRetentionScore) {
                                    return value.toFixed(1);
                                }
                                const useTwoDecimals = isLabourScore || isAOVScore;
                                const intValue = Math.round(value);
                                if (Math.abs(value - intValue) > 0.01) {
                                    return '';
                                }
                                if (intValue >= 1000) {
                                    return (intValue / 1000).toFixed(useTwoDecimals ? 2 : 1) + 'k';
                                }
                                return intValue.toFixed(useTwoDecimals ? 2 : 0);
                            },
                            afterBuildTicks: (axis) => {
                                const seen = new Set();
                                axis.ticks = axis.ticks.filter(tick => {
                                    const rounded = Math.round(tick.value);
                                    if (seen.has(rounded)) return false;
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
            };
            this.employeeChart = new Chart(canvas, {
                type: chartTypeQ3,
                data: {
                    labels: this.state.employeeChartData.labels,
                    datasets: datasets
                },
                plugins: chartTypeQ3 === 'bar' ? [minBarVisibilityPlugin] : [],
                options: optionsQ3
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
            if (scoreNameLower === 'aov') {
                return 'Select a department in the Department Breakdown to view AOV by car brand.';
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
        } else if (this.isIncomeScore()) {
            if (this.state.employeeData && this.state.employeeData.length > 0 && !this.state.employeeChartData) {
                return 'Select a department in the Department Breakdown to view income by category.';
            }
            return 'No category data available for this department.';
        } else if (scoreNameLower === 'aov') {
            if (this.state.employeeData && this.state.employeeData.length > 0 && !this.state.employeeChartData) {
                return 'Select a department in the Department Breakdown to view AOV by car brand.';
            }
            return 'No car brand data available for this department.';
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

    isCustomerRetentionScore() {
        const scoreNameLower = (this.state.scoreName || '').toLowerCase();
        return scoreNameLower === 'customer retention';
    }

    isIncomeScore() {
        const scoreNameLower = (this.state.scoreName || '').toLowerCase();
        return scoreNameLower === 'income';
    }

    isExpenseScore() {
        const scoreNameLower = (this.state.scoreName || '').toLowerCase();
        return scoreNameLower === 'expense';
    }

    isAOVScore() {
        const scoreNameLower = (this.state.scoreName || '').toLowerCase();
        return scoreNameLower === 'aov';
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
        const labels = data.map((item, index) => {
            // For custom filters, ensure we use the period field from API
            const filterType = this.state.quadrants.q1.filter_type || this.state.filterType || '';
            const periodLabel = this.getPeriodLabel(item, filterType);
            let dateRange = '';
            
            // Check if this is a custom date range filter
            const isCustomFilter = filterType && filterType.toUpperCase() === 'CUSTOM';
            
            if (isCustomFilter) {
                // For custom filters, use Period 1, Period 2, Period 3
                dateRange = `Period ${index + 1}`;
            } else {
                // Always try to create date range if we have dates from API response
                // API returns dates in DD-MM-YYYY format
                if (item.start_date && item.end_date) {
                    try {
                        // Parse DD-MM-YYYY format from API
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
                            // If formatting fails, try to parse DD-MM-YYYY manually
                            const startParts = item.start_date.split('-');
                            const endParts = item.end_date.split('-');
                            if (startParts.length === 3 && endParts.length === 3) {
                                // Assume DD-MM-YYYY format
                                const startFormatted = `${startParts[0]} ${this.getMonthName(parseInt(startParts[1]))} ${startParts[2]}`;
                                const endFormatted = `${endParts[0]} ${this.getMonthName(parseInt(endParts[1]))} ${endParts[2]}`;
                                dateRange = `${startFormatted} - ${endFormatted}`;
                            } else {
                                // Fallback to raw dates
                                dateRange = `${item.start_date} - ${item.end_date}`;
                            }
                        }
                    } catch (error) {
                        console.warn('Error formatting date range:', error, item.start_date, item.end_date);
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
                            // Try parsing DD-MM-YYYY manually
                            const parts = singleDate.split('-');
                            if (parts.length === 3) {
                                dateRange = `${parts[0]} ${this.getMonthName(parseInt(parts[1]))} ${parts[2]}`;
                            } else {
                                dateRange = singleDate;
                            }
                        }
                    } catch (error) {
                        dateRange = singleDate;
                    }
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
        const isIncomeScore = scoreNameToCheck && scoreNameToCheck.toLowerCase() === 'income';
        const isAOVScore = scoreNameToCheck && scoreNameToCheck.toLowerCase() === 'aov';
        const isCustomerRetentionScore = scoreNameToCheck && scoreNameToCheck.toLowerCase() === 'customer retention';
        const isTATScore = scoreNameToCheck && scoreNameToCheck.toLowerCase() === 'tat';
        const isCashflowScore = scoreNameToCheck && scoreNameToCheck.toLowerCase() === 'cashflow';

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
        
        if (isLabourScore  || isAOVScore|| isIncomeScore || isCustomerRetentionScore || isTATScore) {
            // Create array of colors for each bar based on comparison with min/max
            backgroundColor = data.map(item => {
                const actualVal = Number(item.actual_value || 0);
                const itemMinVal = Number(item.min_value || 0);
                const itemMaxVal = Number(item.max_value || 0);
                
                // Use tolerance for floating point comparison
                const tolerance = 0.01;
                
                // Compare actual value with this item's min/max values
                if (itemMinVal > 0 && itemMaxVal > 0) {
                    if (isTATScore) {
                        // TAT: lower is better → below min = green, above max = red, between = yellow
                        if (actualVal <= itemMinVal + tolerance) return '#198754';   // green
                        if (actualVal > itemMaxVal + tolerance) return '#dc3545';     // red
                        return '#ffc107';   // yellow (between)
                    }
                    // Labour/AOV/Income/Customer Retention: higher is better
                    if (actualVal < itemMinVal - tolerance) return '#dc3545';  // red
                    if (actualVal >= itemMaxVal - tolerance) return '#198754';  // green
                    return '#ffc107';   // yellow
                }
                return '#0d6efd';
            });
            
            // Set border colors to match background
            borderColor = backgroundColor;
        }
        
        let datasets;

        if (isCashflowScore) {
            const operatingValues = data.map(item => Number(item.operating_cash || 0));
            const financingValues = data.map(item => Number(item.financing_cash || 0));
            const investmentValues = data.map(item => Number(item.investment_cash || 0));

            datasets = [
                {
                    label: 'Operating',
                    data: operatingValues,
                    backgroundColor: '#0d6efd',
                    borderColor: '#0d6efd',
                    borderWidth: 1,
                    borderRadius: 4
                },
                {
                    label: 'Financing',
                    data: financingValues,
                    backgroundColor: '#198754',
                    borderColor: '#198754',
                    borderWidth: 1,
                    borderRadius: 4
                },
                {
                    label: 'Investment',
                    data: investmentValues,
                    backgroundColor: '#ffc107',
                    borderColor: '#ffc107',
                    borderWidth: 1,
                    borderRadius: 4
                }
            ];
        } else {
            datasets = [{
                label: isLeadsScore ? 'Leads' : (isConversionScore ? 'Conversions' : (scoreNameToCheck || 'Total')),
                data: values,
                backgroundColor: backgroundColor,
                borderColor: borderColor,
                borderWidth: 1,
                borderRadius: 4
            }];

            if (hasConversionValues) {
                const conversionValues = data.map(item => {
                    const convValue = item.quality_lead;
                    if (typeof convValue === 'string') {
                        return Number(convValue) || 0;
                    }
                    return Number(convValue || 0);
                });

                datasets.push({
                    label: 'Quality Leads',
                    data: conversionValues,
                    backgroundColor: '#198754',
                    borderColor: '#198754',
                    borderWidth: 1,
                    borderRadius: 4
                });
            }
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

    getMonthName(monthNumber) {
        // monthNumber is 1-based (1 = January, 12 = December)
        const monthNames = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", 
                           "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
        if (monthNumber >= 1 && monthNumber <= 12) {
            return monthNames[monthNumber - 1];
        }
        return String(monthNumber).padStart(2, '0');
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
        const capturedFilterType = this.state.quadrants.q1.filter_type || this.state.filterType || '';
        const capturedScoreType = this.state.scoreType || 'value';
        const formatLineLabel = (v) => {
            if (capturedScoreType === 'percentage') return (Number(v) || 0).toFixed(2) + '%';
            if (capturedScoreType === 'currency_inr') return '₹' + (Number(v) || 0).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
            return (Number(v) || 0).toFixed(2);
        };
        
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
                            ctx.fillText(formatLineLabel(capturedMaxValueLine), chartArea.right - 5, clampedY - 3);
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
                            ctx.fillText(formatLineLabel(capturedMinValueLine), chartArea.right - 5, clampedY - 3);
                        }
                    }
                    
                    // Reset line dash
                    ctx.setLineDash([]);
                }
                
                // Draw labels below x-axis
                ctx.font = '10px Arial';
                ctx.fillStyle = '#6c757d';
                ctx.textAlign = 'center';
                ctx.textBaseline = 'top';
                
                const filterType = capturedFilterType.toUpperCase();
                const isWtdMtdYtd = filterType === 'WTD' || filterType === 'MTD' || filterType === 'YTD';
                
                labels.forEach((label, index) => {
                    if (label && typeof label === 'object') {
                        try {
                            // Get the pixel position for this tick
                            const x = xAxis.getPixelForTick(index);
                            if (!isNaN(x)) {
                                const y = chartArea.bottom + 25; // Position below the axis
                                
                                if (isWtdMtdYtd) {
                                    // For WTD/MTD/YTD: draw period below (since dateRange is on x-axis)
                                    if (label.period && label.period.trim() !== '') {
                                        ctx.fillText(label.period, x, y);
                                    }
                                } else {
                                    // For Custom and others: draw dateRange below (since period is on x-axis)
                                    if (label.dateRange && label.dateRange.trim() !== '') {
                                        ctx.fillText(label.dateRange, x, y);
                                    }
                                }
                            }
                        } catch (error) {
                            console.warn('Error drawing label for bar', index, error);
                        }
                    }
                });
                
                ctx.restore();
            }
        };

        const chartTypeQ1 = this.state.chartTypeQ1 || 'bar';
        const config = {
            type: chartTypeQ1,
            data: chartData,
            plugins: [dateRangePlugin],
            options: {
                maintainAspectRatio: false,
                responsive: true,
                layout: {
                    padding: {
                        bottom: capturedFilterType && capturedFilterType.toUpperCase() === 'WTD' ? 60 : 40 // Extra padding for WTD to accommodate date ranges above x-axis
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
                        callbacks: {
                            title: () => {
                                const tooltipScoreName = this.state.scoreName || this.state.quadrants?.q1?.score_name;
                                return tooltipScoreName || 'Score';
                            },
                            label: (context) => {
                                const value = context.parsed.y || 0;
                                const datasetLabel = context.datasetIndex === 0
                                    ? 'Actual'
                                    : (context.dataset.label || 'Value');
                                const formattedValue = this.formatScoreValue(value);
                                const tooltipLines = [`${datasetLabel}: ${formattedValue}`];

                                if (context.datasetIndex === 0 && this.state.quadrants.q1.data) {
                                    const dataIndex = context.dataIndex;
                                    const periodData = this.state.quadrants.q1.data[dataIndex];
                                    const minValue = periodData ? Number(periodData.min_value) : null;
                                    const maxValue = periodData ? Number(periodData.max_value) : null;

                                    if (minValue !== null && maxValue !== null &&
                                        !isNaN(minValue) && !isNaN(maxValue) &&
                                        !(minValue === 0 && maxValue === 0)) {
                                        tooltipLines.push(`Min: ${this.formatScoreValue(minValue)}`);
                                        tooltipLines.push(`Max: ${this.formatScoreValue(maxValue)}`);
                                    }
                                }

                                return tooltipLines;
                            }
                        }
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
                                    // For WTD, MTD, YTD: show dateRange on x-axis, period below
                                    // For Custom and others: show period on x-axis, dateRange below
                                    const filterType = capturedFilterType.toUpperCase();
                                    if (filterType === 'WTD' || filterType === 'MTD' || filterType === 'YTD') {
                                        return label.dateRange || label.period || '';
                                    }
                                    return label.period || '';
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
                            callback: (value) => {
                                const scoreType = this.state.scoreType || 'value';
                                if (value >= 1000 && scoreType === 'currency_inr') {
                                    return '₹' + (value / 1000).toFixed(2) + 'k';
                                }
                                if (value >= 1000) {
                                    return (value / 1000).toFixed(2) + 'k' + (scoreType === 'percentage' ? '%' : '');
                                }
                                return this.formatScoreValue(value);
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