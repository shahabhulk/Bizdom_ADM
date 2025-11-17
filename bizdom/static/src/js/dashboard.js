/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, useState, onMounted } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

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

  onCustomDateChange(field, ev) {
    this.state.customRange = {
      ...this.state.customRange,
      [field]: ev.target.value,
    };

    const { start, end } = this.state.customRange;
    if (start && end) {
      if (new Date(start) > new Date(end)) {
        this.state.dateRangeLabel = "Start date cannot be after end date";
        return;
      }
      this.loadPillars();
    }
  }

  getDateRange(filter) {
    const today = new Date();
    let startDate, endDate;
    let label = "";

    switch (filter) {
      case "WTD": // Week to Date
        const dayOfWeek = today.getDay();
        startDate = new Date(today);
        startDate.setDate(today.getDate() - dayOfWeek + (dayOfWeek === 0 ? -6 : 1));
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

      // 1. Get the current user's company

      // 2. Fetch all pillars for the company
      const pillars = await this.orm.searchRead(
        "bizdom.pillar",
        [],
        ["id", "name"],
      );

      // 3. For each pillar, fetch its favorite scores with date filter
      for (let pillar of pillars) {
        const scores = await this.orm.searchRead(
          "bizdom.score",
          [
            ["pillar_id", "=", pillar.id],
            ["favorite", "=", true],
          ],
          ["id", "score_name", "total_score_value", "start_date", "end_date"],
        );

        // Compute context_total_score for each score with the date filter
        const scoresWithValues = [];
        for (let score of scores) {
          try {
            // Call the backend method to compute score with date filter
            const scoreData = await this.orm.call(
              "bizdom.score",
              "get_score_with_date_filter",
              [score.id, dateRange.start_date, dateRange.end_date],
            );
            scoresWithValues.push({
              ...score,
              context_total_score: scoreData.context_total_score || 0,
            });
          } catch (error) {
            console.error(`Error computing score ${score.id}:`, error);
            scoresWithValues.push({
              ...score,
              context_total_score: 0,
            });
          }
        }

        // Add scores to the pillar
        pillar.scores = scoresWithValues;
        console.log(`Pillar ${pillar.name} scores:`, pillar.scores);
      }

      // Update state with pillars and their scores
      this.state.pillars = pillars;
    } catch (error) {
      console.error("Error loading pillars and scores:", error);
    } finally {
      this.state.loading = false;
    }
  }

  openScoreDashboard(ev, score) {
    ev.preventDefault();
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
}

// Register the client action
registry.category("actions").add("bizdom_dashboard", BizdomDashboard);
