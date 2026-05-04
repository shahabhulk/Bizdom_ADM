/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, useState, onMounted } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

const DASHBOARD_API = '/api/dashboard';
const TODOS_API = '/api/todos';
const TODO_PILLAR_TABS = ["All", "Operations", "Sales and Marketing", "Finance"];

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
      todos: [],
      todosLoading: true,
      todosError: "",
      todoFilter: "open", // open | done | all
      todoPillarFilter: "All",
      showTodoForm: false,
      editingTodoId: null,
      savingTodo: false,
      deletingTodoId: null,
      pillarOptions: [],
      userOptions: [],
      todoFormError: "",
      todoForm: {
        name: "",
        description: "",
        date_deadline: "",
        priority: "low",
        pillar_id: "",
        assignee_id: "",
      },
    });

    onMounted(() => {
      this.loadPillars();
      this.loadTodos();
      this.loadTodoSupportData();
    });
  }

  async loadTodoSupportData() {
    try {
      const [pillars, users] = await Promise.all([
        this.orm.searchRead("bizdom.pillar", [], ["id", "name"], { order: "name asc" }),
        this.orm.searchRead(
          "res.users",
          [["active", "=", true], ["share", "=", false]],
          ["id", "name"],
          { order: "name asc", limit: 200 }
        ),
      ]);
      this.state.pillarOptions = pillars || [];
      this.state.userOptions = users || [];
    } catch (error) {
      console.warn("Could not load todo form options:", error);
      this.state.pillarOptions = [];
      this.state.userOptions = [];
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

  async loadTodos() {
    try {
      this.state.todosLoading = true;
      this.state.todosError = "";
      const response = await fetch(`${TODOS_API}?limit=100`, {
        method: "GET",
        headers: { "Content-Type": "application/json" },
        credentials: "same-origin",
      });
      const payload = await response.json().catch(() => null);
      if (response.status === 401) {
        this.state.todosError = "Please log in to see your todos";
        this.state.todos = [];
        return;
      }
      if (payload && payload.statusCode === 200 && Array.isArray(payload.data)) {
        this.state.todos = payload.data;
      } else {
        this.state.todos = [];
        this.state.todosError = (payload && payload.message) || "No todos available";
      }
    } catch (error) {
      console.error("Error loading todos:", error);
      this.state.todosError = "Could not load todos";
      this.state.todos = [];
    } finally {
      this.state.todosLoading = false;
    }
  }

  setTodoFilter(filter) {
    this.state.todoFilter = filter;
  }

  setTodoPillarFilter(pillarName) {
    this.state.todoPillarFilter = pillarName;
  }

  isTodoDone(todo) {
    return todo && (todo.state === "1_done" || todo.state === "1_canceled");
  }

  get filteredTodos() {
    let todos = this.state.todos || [];
    if (this.state.todoFilter === "done") {
      todos = todos.filter((t) => this.isTodoDone(t));
    }
    if (this.state.todoFilter === "open") {
      todos = todos.filter((t) => !this.isTodoDone(t));
    }
    if (this.state.todoPillarFilter !== "All") {
      todos = todos.filter((t) => (t.pillar_name || "") === this.state.todoPillarFilter);
    }
    return todos;
  }

  get todoCounts() {
    const todos = this.state.todos || [];
    const done = todos.filter((t) => this.isTodoDone(t)).length;
    return { total: todos.length, done, open: todos.length - done };
  }

  get todoPillarTabs() {
    const todos = this.state.todos || [];
    return TODO_PILLAR_TABS.map((name) => {
      if (name === "All") {
        return { name, count: todos.length };
      }
      return { name, count: todos.filter((t) => (t.pillar_name || "") === name).length };
    });
  }

  resetTodoForm() {
    this.state.todoForm = {
      name: "",
      description: "",
      date_deadline: "",
      priority: "low",
      pillar_id: "",
      assignee_id: "",
    };
    this.state.todoFormError = "";
  }

  openCreateTodoForm() {
    this.state.editingTodoId = null;
    this.resetTodoForm();
    this.state.showTodoForm = true;
  }

  openEditTodoForm(todo) {
    this.state.editingTodoId = todo.id;
    this.state.todoForm = {
      name: todo.name || "",
      description: todo.description || "",
      date_deadline: todo.date_deadline || "",
      priority: todo.priority || "low",
      pillar_id: todo.pillar_id || "",
      assignee_id: (todo.user_ids && todo.user_ids[0] && todo.user_ids[0].id) || "",
    };
    this.state.todoFormError = "";
    this.state.showTodoForm = true;
  }

  closeTodoForm() {
    this.state.showTodoForm = false;
    this.state.editingTodoId = null;
    this.state.todoFormError = "";
  }

  onTodoFormChange(field, ev) {
    this.state.todoForm = {
      ...this.state.todoForm,
      [field]: ev.target.value,
    };
  }

  setTodoPriority(priority) {
    this.state.todoForm = {
      ...this.state.todoForm,
      priority,
    };
  }

  async saveTodo(ev) {
    if (ev && ev.preventDefault) ev.preventDefault();
    if (this.state.savingTodo) return;

    const name = (this.state.todoForm.name || "").trim();
    if (!name) {
      this.state.todoFormError = "Title is required";
      return;
    }

    const payload = {
      name,
      description: this.state.todoForm.description || "",
      date_deadline: this.state.todoForm.date_deadline || false,
      priority: this.state.todoForm.priority || "low",
      pillar_id: this.state.todoForm.pillar_id ? Number(this.state.todoForm.pillar_id) : false,
    };
    if (this.state.todoForm.assignee_id) {
      payload.user_ids = [Number(this.state.todoForm.assignee_id)];
    }

    const isEdit = !!this.state.editingTodoId;
    const url = isEdit ? `${TODOS_API}/${this.state.editingTodoId}` : TODOS_API;
    const method = isEdit ? "PUT" : "POST";

    this.state.savingTodo = true;
    this.state.todoFormError = "";
    try {
      const response = await fetch(url, {
        method,
        headers: { "Content-Type": "application/json" },
        credentials: "same-origin",
        body: JSON.stringify(payload),
      });
      const data = await response.json().catch(() => null);
      if (!data || !(response.status === 200 || response.status === 201)) {
        this.state.todoFormError = (data && data.message) || "Could not save todo";
        return;
      }
      await this.loadTodos();
      this.closeTodoForm();
    } catch (error) {
      console.error("Error saving todo:", error);
      this.state.todoFormError = "Could not save todo";
    } finally {
      this.state.savingTodo = false;
    }
  }

  async deleteTodo(todoId) {
    const confirmed = window.confirm("Delete this todo?");
    if (!confirmed) return;
    this.state.deletingTodoId = todoId;
    try {
      const response = await fetch(`${TODOS_API}/${todoId}`, {
        method: "DELETE",
        headers: { "Content-Type": "application/json" },
        credentials: "same-origin",
      });
      const data = await response.json().catch(() => null);
      if (!data || response.status !== 200) {
        console.warn("Delete failed:", data);
        return;
      }
      this.state.todos = (this.state.todos || []).filter((t) => t.id !== todoId);
    } catch (error) {
      console.error("Error deleting todo:", error);
    } finally {
      this.state.deletingTodoId = null;
    }
  }

  getPriorityLabel(priority) {
    if (priority === "high") return "Urgent";
    if (priority === "medium") return "Medium";
    return "Low";
  }

  getPriorityClass(priority) {
    if (priority === "high") return "todo-priority-high";
    if (priority === "medium") return "todo-priority-medium";
    return "todo-priority-low";
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
    'Labour': 'fa-wrench',              // or 'fa-industry'
    'TAT': 'fa-clock-o',
    'AOV': 'fa-line-chart',
    'Leads': 'fa-bullseye',
    'Customer Retention': 'fa-users',
    'Conversion': 'fa-exchange',
    'Income': 'fa-money',
    'Expense': 'fa-credit-card',
    'Cashflow': 'fa-tint', 
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

  getScoreOverviewColor(score){
    const actual=Number(score.context_total_score ?? score.total_score_value ??0);
    const minVal = Number(score.min_value ?? 0);
    const maxVal = Number(score.max_value ?? 0);
    const tolerance = 0.01;
    const isTATScore = score.score_name.toLowerCase() === 'tat';
    if(minVal > 0 && maxVal > 0){
      if(isTATScore){
        if (actual <= minVal + tolerance) return '#198754';   // green
        if (actual > maxVal + tolerance) return '#dc3545';     // red
        return '#ffc107';   // yellow (between)
      }
      if(actual < minVal - tolerance){
        return '#dc3545';
      }
      if(actual >= maxVal - tolerance){
        return '#198754';
      }
      return '#ffc107';
    }
    return '#95a5a6';
  }
}

// Register the client action
registry.category("actions").add("bizdom_dashboard", BizdomDashboard);
