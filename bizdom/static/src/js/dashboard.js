/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, useState, onMounted } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

const DASHBOARD_API = '/api/dashboard';

class BizdomDashboard extends Component {
  static template = "bizdom.Dashboard";

  setup() {
    this.orm = useService("orm");
    this.action = useService("action");
    this.state = useState({
      pillars: [],
      loading: true,
      currentFilter: "MTD", // Default to MTD
      dateRangeLabel: "",
      customRange: {
        start: "",
        end: "",
      },
      activeRange: {
        start: "",
        end: "",
      },
    });

    onMounted(() => {
      this.loadPillars();
    });
  }

  onFilterChange(ev) {
    const nextFilter = ev.target.value;
    this.state.currentFilter = nextFilter;
    if (nextFilter !== "Custom") {
      this.state.customRange = { start: "", end: "" };
      this.loadPillars();
    } else {
      this.state.dateRangeLabel = "Select start and end dates";
      this.state.pillars = [];
    }
  }

  onFilterClick(filter) {
    this.state.currentFilter = filter;
    if (filter !== "Custom") {
      this.state.customRange = { start: "", end: "" };
      this.loadPillars();
    } else {
      this.state.dateRangeLabel = "Select start and end dates";
      this.state.pillars = [];
    }
  }

  onCustomDateChange(field, ev) {
    this.state.customRange = {
      ...this.state.customRange,
      [field]: ev.target.value,
    };

    const { start, end } = this.state.customRange;
    if (start && end) {
      if (new Date(start) > new Date(end)) {
        this.state.dateRangeLabel = "Start date cannot be after end date";
        this.state.pillars = [];
        return;
      }
      // Update dateRangeLabel for custom range
      const startDate = new Date(start);
      const endDate = new Date(end);
      this.state.dateRangeLabel = `Custom: ${this.formatRangeLabel(startDate, endDate)}`;
      this.loadPillars();
    } else {
      this.state.dateRangeLabel = "Select start and end dates";
      this.state.pillars = [];
    }
  }

  getDateRange(filter) {
    const today = new Date();
    let startDate, endDate;
    let label = "";

    switch (filter) {
      case "Today":
        startDate = new Date(today);
        startDate.setHours(0, 0, 0, 0);
        endDate = new Date(today);
        endDate.setHours(23, 59, 59, 999);
        label = `Today: ${this.formatRangeLabel(startDate, endDate)}`;
        break;
      case "WTD": // Week to Date
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
        endDate = new Date();
        endDate.setHours(23, 59, 59, 999);
        label = `Week to Date: ${this.formatRangeLabel(startDate, endDate)}`;
        break;
      case "YTD": // Year to Date
        startDate = new Date(today.getFullYear(), 0, 1);
        startDate.setHours(0, 0, 0, 0);
        endDate = new Date();
        endDate.setHours(23, 59, 59, 999);
        label = `Year to Date: ${this.formatRangeLabel(startDate, endDate)}`;
        break;
      case "MTD": // Month to Date (default)
        startDate = new Date(today.getFullYear(), today.getMonth(), 1);
        startDate.setHours(0, 0, 0, 0);
        endDate = new Date();
        endDate.setHours(23, 59, 59, 999);
        label = `Month to Date: ${this.formatRangeLabel(startDate, endDate)}`;
        break;
      case "Custom":
        const { start, end } = this.state.customRange;
        if (!start || !end) {
          return null;
        }
        startDate = new Date(start);
        endDate = new Date(end);
        if (startDate > endDate) {
          return null;
        }
        label = `Custom: ${this.formatRangeLabel(startDate, endDate)}`;
        break;
      default:
        startDate = new Date(today.getFullYear(), today.getMonth(), 1);
        startDate.setHours(0, 0, 0, 0);
        endDate = new Date();
        endDate.setHours(23, 59, 59, 999);
        label = this.formatRangeLabel(startDate, endDate);
        break;
    }

    // Format dates as YYYY-MM-DD for Odoo
    const formatDate = (date) => {
      const year = date.getFullYear();
      const month = String(date.getMonth() + 1).padStart(2, "0");
      const day = String(date.getDate()).padStart(2, "0");
      return `${year}-${month}-${day}`;
    };

    const range = {
      start_date: formatDate(startDate),
      end_date: formatDate(endDate),
      label,
    };

    return range;
  }

  formatRangeLabel(startDate, endDate) {
    return `${this.formatDisplayDate(startDate)} - ${this.formatDisplayDate(endDate)}`;
  }

  formatDisplayDate(date) {
    const options = { year: "numeric", month: "short", day: "2-digit" };
    return date.toLocaleDateString(undefined, options);
  }

  formatDateForAPI(date) {
    // Convert Date object or YYYY-MM-DD string to DD-MM-YYYY format for API
    if (!date) return '';
    
    let dateObj;
    if (date instanceof Date) {
      dateObj = date;
    } else if (typeof date === 'string') {
      // Handle YYYY-MM-DD format
      const parts = date.split('-');
      if (parts.length === 3) {
        dateObj = new Date(parts[0], parts[1] - 1, parts[2]);
      } else {
        return date; // Return as-is if format is unexpected
      }
    } else {
      return '';
    }
    
    const day = String(dateObj.getDate()).padStart(2, "0");
    const month = String(dateObj.getMonth() + 1).padStart(2, "0");
    const year = dateObj.getFullYear();
    return `${day}-${month}-${year}`;
  }



  async loadPillars() {
    try {
      this.state.loading = true;

      // Get date range based on current filter
      const dateRange = this.getDateRange(this.state.currentFilter);
      if (!dateRange) {
        this.state.pillars = [];
        this.state.loading = false;
        return;
      }
      this.state.dateRangeLabel = dateRange.label;
      this.state.activeRange = {
        start: dateRange.start_date,
        end: dateRange.end_date,
      };

      // Build API URL
      let url = `${DASHBOARD_API}?filterType=${this.state.currentFilter}&favoritesOnly=true`;
      
      // Add date parameters for Custom filter
      if (this.state.currentFilter === 'Custom' && dateRange.start_date && dateRange.end_date) {
        url += `&startDate=${this.formatDateForAPI(dateRange.start_date)}&endDate=${this.formatDateForAPI(dateRange.end_date)}`;
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
        console.error("Unauthorized access to dashboard API");
        this.state.pillars = [];
        return;
      }

      const responseText = await response.text();
      let dashboardData;
      try {
        dashboardData = JSON.parse(responseText);
      } catch (error) {
        console.error("Invalid dashboard response:", responseText);
        this.state.pillars = [];
        return;
      }

      if (dashboardData && dashboardData.statusCode === 200 && dashboardData.pillars) {
        // Transform API response to match expected format
        const pillars = dashboardData.pillars.map(pillar => ({
          id: pillar.pillar_id,
          name: pillar.pillar_name,
          scores: pillar.scores.map(score => ({
            id: score.score_id,
            score_name: score.score_name,
            type: score.type,
            total_score_value: score.total_score_value,
            context_total_score: score.total_score_value, // API returns total_score_value
            min_value: score.min_value,
            max_value: score.max_value,
          })),
        }));

        this.state.pillars = pillars;
        console.log('Dashboard data loaded:', pillars);
      } else {
        console.warn('No pillars data in dashboardData:', dashboardData);
        this.state.pillars = [];
      }
    } catch (error) {
      console.error("Error loading pillars and scores:", error);
      this.state.pillars = [];
    } finally {
      this.state.loading = false;
    }
  }

  openScoreDashboard(ev, score) {
    ev.preventDefault();
    // Store scoreId in sessionStorage for refresh recovery
    sessionStorage.setItem('bizdom_scoreId', String(score.id));
    sessionStorage.setItem('bizdom_scoreName', score.score_name);
    // Open score dashboard as client action to properly pass filter
    this.action.doAction({
      type: "ir.actions.client",
      tag: "score_dashboard",
      name: score.score_name + " Dashboard",
      context: {
        scoreId: score.id,
        scoreName: score.score_name,
        current_filter: this.state.currentFilter,
        date_range_start: this.state.activeRange.start,
        date_range_end: this.state.activeRange.end,
      },
    });
  }

  getPillarIcon(pillarName) {
    const iconMap = {
      'Operations': 'fa-cogs',
      'Sales and Marketing': 'fa-chart-line',
      'Finance': 'fa-dollar-sign',
      'Human Resources': 'fa-users',
      'Technology': 'fa-laptop-code',
      'Customer Service': 'fa-headset',
    };
    return iconMap[pillarName] || 'fa-layer-group';
  }

  getPillarColor(pillarName) {
    const colorMap = {
      'Operations': 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
      'Sales and Marketing': 'linear-gradient(135deg, #f093fb 0%, #f5576c 100%)',
      'Finance': 'linear-gradient(135deg, #4facfe 0%, #00f2fe 100%)',
      'Human Resources': 'linear-gradient(135deg, #43e97b 0%, #38f9d7 100%)',
      'Technology': 'linear-gradient(135deg, #fa709a 0%, #fee140 100%)',
      'Customer Service': 'linear-gradient(135deg, #30cfd0 0%, #330867 100%)',
    };
    return colorMap[pillarName] || 'linear-gradient(135deg, #a8edea 0%, #fed6e3 100%)';
  }

  getPillarOrbColor(pillarName, darker = false) {
    const colorMap = {
      'Operations': darker ? '#4a5fc7' : '#667eea',
      'Sales and Marketing': darker ? '#d17ae8' : '#f093fb',
      'Finance': darker ? '#3a8bfe' : '#4facfe',
      'Human Resources': darker ? '#2dd16b' : '#43e97b',
      'Technology': darker ? '#e85a8a' : '#fa709a',
      'Customer Service': darker ? '#26b5b5' : '#30cfd0',
      'Inventory': darker ? '#f59e0b' : '#fbbf24',
      'Services': darker ? '#10b981' : '#34d399',
      'Sales': darker ? '#10b981' : '#34d399',
    };
    return colorMap[pillarName] || (darker ? '#8b9dc3' : '#a8b5d1');
  }

  getScoreIcon(scoreName) {
    const iconMap = {
      'Labour': 'fa-hard-hat',
      'Customer Satisfaction': 'fa-smile',
      'TAT': 'fa-clock',
      'Leads': 'fa-bullseye',
      'Revenue': 'fa-money-bill-wave',
      'Productivity': 'fa-tachometer-alt',
      'Quality': 'fa-award',
      'Efficiency': 'fa-bolt',
    };
    return iconMap[scoreName] || 'fa-chart-bar';
  }

  getScoreColor(scoreName) {
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
    return colorMap[scoreName] || '#95a5a6';
  }
}

// Register the client action
registry.category("actions").add("bizdom_dashboard", BizdomDashboard);
