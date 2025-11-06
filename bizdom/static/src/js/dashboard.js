/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, useState, onMounted } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

class BizdomDashboard extends Component {
    static template = "bizdom.Dashboard";

    setup() {
        this.orm = useService("orm");
        this.state = useState({
            pillars: [],
            loading: true
        });

        onMounted(() => {
            this.loadPillars();
        });
    }

    async loadPillars() {
        try {
            this.state.loading = true;
            this.state.pillars = await this.orm.searchRead(
                "bizdom.pillar",
                [],
                ["id", "name"]
            );
        } catch (error) {
            console.error("Error loading pillars:", error);
        } finally {
            this.state.loading = false;
        }
    }
}

// Register the client action
registry.category("actions").add("bizdom_dashboard", BizdomDashboard);