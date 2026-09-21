/** @odoo-module **/
import { registry } from "@web/core/registry";
import { rpc } from "@web/core/network/rpc";
import { _t } from "@web/core/l10n/translation";
import { Component } from "@odoo/owl";
import { onWillStart, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

const actionRegistry = registry.category("actions");

export class FleetRepairDasboard extends Component {
    static template = 'FleetRepairDashboard';
    static props = ["*"];

    setup() {
        this.action = useService("action");
        this.orm = useService("orm");

        const initialDept = this.props.action?.params?.department ||
                            this.props.action?.context?.department ||
                            this.props.action?.context?.default_department ||
                            null;

        this.state = useState({
            dashboards_templates: ['DashboardHeader', 'DashboardContent'],
            templates: [],
            currentDepartment: initialDept,
            departmentName: initialDept ? (initialDept.charAt(0).toUpperCase() + initialDept.slice(1)) : 'Car Repair',
            user_department: false,
            fleet_repair_count: 0,
            bodyshop_repair_count: 0,
            workshop_repair_count: 0,
            fleet_diagnos_count: 0,
            fleet_diagnos_d_count: 0,
            fleet_repair_d_count: 0,
            fleet_workorder_count: 0,
            fleet_service_type_count: 0,
            feedback_count: 0,
            lead_count: 0,
            parts_purchase_count: 0,
            company_expense_count: 0,
        });

        onWillStart(async () => {
            await this.loadDashboardData(initialDept);
        });
    }

    get fleet_repair_count() { return this.state.fleet_repair_count; }
    get bodyshop_repair_count() { return this.state.bodyshop_repair_count; }
    get workshop_repair_count() { return this.state.workshop_repair_count; }
    get user_department() { return this.state.user_department; }
    get fleet_diagnos_count() { return this.state.fleet_diagnos_count; }
    get fleet_diagnos_d_count() { return this.state.fleet_diagnos_d_count; }
    get fleet_repair_d_count() { return this.state.fleet_repair_d_count; }
    get fleet_workorder_count() { return this.state.fleet_workorder_count; }
    get fleet_service_type_count() { return this.state.fleet_service_type_count; }
    get feedback_count() { return this.state.feedback_count; }
    get lead_count() { return this.state.lead_count; }
    get parts_purchase_count() { return this.state.parts_purchase_count; }
    get company_expense_count() { return this.state.company_expense_count; }

    async loadDashboardData(department) {
        const result = await rpc("/fleet_repair/dashboard_data", { department: department || null });
        this.state.fleet_repair_count = result.fleet_repair_count;
        this.state.bodyshop_repair_count = result.bodyshop_repair_count || 0;
        this.state.workshop_repair_count = result.workshop_repair_count || 0;
        this.state.user_department = result.user_department || false;
        this.state.fleet_diagnos_count = result.fleet_diagnos_count;
        this.state.fleet_diagnos_d_count = result.fleet_diagnos_d_count;
        this.state.fleet_repair_d_count = result.fleet_repair_d_count;
        this.state.fleet_workorder_count = result.fleet_workorder_count;
        this.state.fleet_service_type_count = result.fleet_service_type_count;
        this.state.feedback_count = result.feedback_count;
        this.state.lead_count = result.lead_count || 0;
        this.state.parts_purchase_count = result.parts_purchase_count || 0;
        this.state.company_expense_count = result.company_expense_count || 0;

        const activeDept = result.department || department || null;
        this.state.currentDepartment = activeDept;
        this.state.departmentName = activeDept ? (activeDept.charAt(0).toUpperCase() + activeDept.slice(1)) : 'Car Repair';
    }

    async switchDepartment(department) {
        await this.loadDashboardData(department);
    }

    setBodyshop() {
        this.switchDepartment('bodyshop');
    }

    setWorkshop() {
        this.switchDepartment('workshop');
    }

    setAllDepartments() {
        this.switchDepartment(null);
    }

    init(parent, action) {
        this._super.apply(this, arguments);
        this.dashboards_templates = ['DashboardHeader', 'DashboardContent'];
    }

    clickBodyshop(ev) {
        ev.preventDefault();
        this.action.doAction({
            name: 'Bodyshop Job Cards',
            res_model: 'fleet.repair',
            res_id: false,
            views: [[false, 'list'], [false, 'form']],
            type: 'ir.actions.act_window',
            domain: [['department_id.name', 'ilike', 'bodyshop'], ['state', 'not in', ['done', 'invoiced', 'cancel']]],
            context: { 'search_default_filter_bodyshop': 1, 'search_default_not_done': 1 },
        }, {
            on_reverse_breadcrumb: this.on_reverse_breadcrumb
        });
    }

    clickWorkshop(ev) {
        ev.preventDefault();
        this.action.doAction({
            name: 'Workshop Job Cards',
            res_model: 'fleet.repair',
            res_id: false,
            views: [[false, 'list'], [false, 'form']],
            type: 'ir.actions.act_window',
            domain: [['department_id.name', 'ilike', 'workshop'], ['state', 'not in', ['done', 'invoiced', 'cancel']]],
            context: { 'search_default_filter_workshop': 1, 'search_default_not_done': 1 },
        }, {
            on_reverse_breadcrumb: this.on_reverse_breadcrumb
        });
    }

    clickCarRepair(ev) {
        ev.preventDefault();
        var targetElement = ev.currentTarget.querySelector('.CarRepairList');
        var isDoneCard = targetElement && (
            targetElement.dataset.activity_type === 'Fleet Repair Done' ||
            (targetElement.dataset.domain && targetElement.dataset.domain.includes("'='") && targetElement.dataset.domain.includes('done'))
        );
        var domain = [];
        if (isDoneCard) {
            domain = [['state', '=', 'done']];
        } else {
            domain = [['state', 'not in', ['done', 'invoiced', 'cancel']]];
        }
        if (this.state.currentDepartment) {
            domain.push(['department_id.name', 'ilike', this.state.currentDepartment]);
        }
        this.action.doAction({
            name: isDoneCard ? `${this.state.departmentName} - Done` : `${this.state.departmentName} - Requests`,
            res_model: 'fleet.repair',
            res_id: false,
            views: [[false, 'list'], [false, 'form']],
            type: 'ir.actions.act_window',
            domain: domain,
            context: this.state.currentDepartment ? { [`search_default_filter_${this.state.currentDepartment}`]: 1 } : {},
        }, {
            on_reverse_breadcrumb: this.on_reverse_breadcrumb
        });
    }

    clickAssignedtoTechnicians(ev) {
        ev.preventDefault();
        var domain = [['state', '=', 'in_progress']];
        if (this.state.currentDepartment) {
            domain.push(['fleet_repair_id.department_id.name', 'ilike', this.state.currentDepartment]);
        }
        this.action.doAction({
            name: `${this.state.departmentName} - Assigned to Technicians`,
            res_model: 'fleet.diagnose',
            res_id: false,
            views: [[false, 'list'], [false, 'form']],
            type: 'ir.actions.act_window',
            domain: domain,
        }, {
            on_reverse_breadcrumb: this.on_reverse_breadcrumb
        });
    }

    clickCarDiagnosis(ev) {
        ev.preventDefault();
        var domain = [];
        if (this.state.currentDepartment) {
            domain.push(['fleet_repair_id.department_id.name', 'ilike', this.state.currentDepartment]);
        }
        this.action.doAction({
            name: `${this.state.departmentName} - Car Diagnosis`,
            res_model: 'fleet.diagnose',
            res_id: false,
            views: [[false, 'list'], [false, 'form']],
            type: 'ir.actions.act_window',
            domain: domain,
        }, {
            on_reverse_breadcrumb: this.on_reverse_breadcrumb
        });
    }

    clickWorkOrders(ev) {
        ev.preventDefault();
        var domain = [];
        if (this.state.currentDepartment) {
            domain.push(['fleet_repair_id.department_id.name', 'ilike', this.state.currentDepartment]);
        }
        this.action.doAction({
            name: `${this.state.departmentName} - Work Orders`,
            res_model: 'fleet.workorder',
            res_id: false,
            views: [[false, 'list'], [false, 'form']],
            type: 'ir.actions.act_window',
            domain: domain,
        }, {
            on_reverse_breadcrumb: this.on_reverse_breadcrumb
        });
    }

    clickServiceType(ev) {
        ev.preventDefault();
        var domain = [];
        if (this.state.currentDepartment) {
            domain.push(['department_id.name', 'ilike', this.state.currentDepartment]);
        }
        this.action.doAction({
            name: `${this.state.departmentName} - Service Type`,
            res_model: 'service.type',
            res_id: false,
            views: [[false, 'list'], [false, 'form']],
            type: 'ir.actions.act_window',
            domain: domain,
        }, {
            on_reverse_breadcrumb: this.on_reverse_breadcrumb
        });
    }

    clickServiceFeedback(ev) {
        ev.preventDefault();
        var domain = [];
        if (this.state.currentDepartment) {
            domain.push(['department_ids.name', 'ilike', this.state.currentDepartment]);
        }
        this.action.doAction({
            name: `${this.state.departmentName} - Service Feedbacks`,
            res_model: 'fleet.repair.feedback',
            res_id: false,
            views: [[false, 'list'], [false, 'form']],
            type: 'ir.actions.act_window',
            domain: domain,
        }, {
            on_reverse_breadcrumb: this.on_reverse_breadcrumb
        });
    }

    clickFleetLeads(ev) {
        ev.preventDefault();
        this.action.doAction({
            name: 'Fleet Leads',
            res_model: 'crm.lead',
            res_id: false,
            views: [[false, 'list'], [false, 'form']],
            type: 'ir.actions.act_window',
            context: {
                'default_state': 'new'
            },
            domain: []
        }, {
            on_reverse_breadcrumb: this.on_reverse_breadcrumb
        });
    }

    clickPartsPurchase(ev) {
        ev.preventDefault();
        this.action.doAction({
            name: 'Purchase Orders',
            res_model: 'purchase.order',
            res_id: false,
            views: [[false, 'list'], [false, 'form']],
            type: 'ir.actions.act_window',
        }, {
            on_reverse_breadcrumb: this.on_reverse_breadcrumb
        });
    }

    clickCompanyExpense(ev) {
        ev.preventDefault();
        this.action.doAction({
            name: 'Company Expenses',
            res_model: 'hr.expense',
            res_id: false,
            views: [[false, 'list'], [false, 'form']],
            type: 'ir.actions.act_window',
            domain: [],
        }, {
            on_reverse_breadcrumb: this.on_reverse_breadcrumb
        });
    }
}

registry.category("actions").add("fleet_repair_dashboard", FleetRepairDasboard);
