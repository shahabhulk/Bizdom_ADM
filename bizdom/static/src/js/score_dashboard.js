/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, useState, onMounted } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

class ScoreDashboard extends Component {
    static template = "bizdom.ScoreDashboard";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        
        // Get props from action context
        const action = this.props?.action || {};
        const context = action.context || {};
        const scoreId = context.scoreId || context.active_id || null;
        const scoreName = context.scoreName || action.name || '';
        const filterType = 'MTD'; // Currently we focus only on MTD overview
        
        this.state = useState({
            loading: true,
            score: null,
            scoreId: scoreId,
            scoreName: scoreName,
            filterType: filterType,
            quadrants: {
                q1: { title: "Score Overview", data: [], filter_type: filterType },
                q2: { title: "Trend Analysis", data: [] },
                q3: { title: "Department Breakdown", data: [] },
                q4: { title: "Time Period Analysis", data: [] },
            }
        });

        onMounted(() => {
            this.loadScoreData();
        });
    }

    async loadScoreData() {
        try {
            if (!this.state.scoreId) {
                console.warn("ScoreDashboard: Missing scoreId in context");
                this.state.loading = false;
                return;
            }
            this.state.loading = true;
            const scoreData = await this.orm.call(
                'bizdom.score',
                'get_score_dashboard_data',
                [this.state.scoreId, this.state.filterType],
            );

            if (scoreData && scoreData.overview) {
                this.state.score = scoreData;
                this.state.quadrants.q1 = {
                    title: scoreData.message || 'Score Overview',
                    data: scoreData.overview || [],
                    filter_type: 'MTD',
                    score_name: scoreData.score_name
                };
            }
        } catch (error) {
            console.error("Error loading score data:", error);
        } finally {
            this.state.loading = false;
        }
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

    navigateBack() {
        this.action.doAction('bizdom.dashboard_action');
    }
}

registry.category("actions").add("score_dashboard", ScoreDashboard);