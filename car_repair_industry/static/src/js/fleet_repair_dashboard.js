/** @odoo-module **/
import { registry } from "@web/core/registry";
import { rpc } from "@web/core/network/rpc";
import { _t } from "@web/core/l10n/translation";
import { Component } from "@odoo/owl";
import { onWillStart, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
const actionRegistry = registry.category("actions");
export class FleetRepairDasboard extends Component{
   
    static template = 'FleetRepairDashboard';
    static props = ["*"];
    
    setup() {
        this.action = useService("action");
        this.orm = useService("orm");
        this.state = useState({
            dashboards_templates: ['DashboardHeader', 'DashboardContent'],
            templates: [],
        })    

        onWillStart(async () => {
            var self = this;
            var def = rpc("/fleet_repair/dashboard_data").
            then(function (result) {
                self.fleet_repair_count = result.fleet_repair_count;
                self.fleet_diagnos_count = result.fleet_diagnos_count;
                self.fleet_diagnos_d_count = result.fleet_diagnos_d_count;
                self.fleet_repair_d_count = result.fleet_repair_d_count;
                self.fleet_workorder_count = result.fleet_workorder_count;
                self.fleet_service_type_count = result.fleet_service_type_count;
            });
            return Promise.all([def]);

        })
    }

    init (parent, action) {
        this._super.apply(this, arguments);
        this.dashboards_templates = ['DashboardHeader', 'DashboardContent'];
    }


    clickCarRepair (ev) {
        ev.preventDefault();
        var targetElement = ev.currentTarget.querySelector('.CarRepairList');
        var domain = targetElement.dataset.domain;
        this.action.doAction({
            name: 'Car Repair',
            res_model: 'fleet.repair',
            res_id: false,
            views: [[false, 'list'],[false, 'form']],
            type: 'ir.actions.act_window',
            domain: domain,
        }, {
            on_reverse_breadcrumb: this.on_reverse_breadcrumb
        });
    }

    clickAssignedtoTechnicians (ev) {
        ev.preventDefault();
        var targetElement = ev.currentTarget.querySelector('.AssignedtoTechnicians');
        var domain = targetElement.dataset.domain;
        this.action.doAction({
            name: 'Assigned to Technicians',
            res_model: 'fleet.diagnose',
            res_id: false,
            views: [[false, 'list'],[false, 'form']],
            type: 'ir.actions.act_window',
            domain: domain,
        }, {
            on_reverse_breadcrumb: this.on_reverse_breadcrumb
        });
    }

    clickCarDiagnosis (ev) {
        ev.preventDefault();
        this.action.doAction({
            name: 'Car Diagnosis',
            res_model: 'fleet.diagnose',
            res_id: false,
            views: [[false, 'list'],[false, 'form']],
            type: 'ir.actions.act_window',
        }, {
            on_reverse_breadcrumb: this.on_reverse_breadcrumb
        });
    }

    clickWorkOrders (ev) {
        ev.preventDefault();
        this.action.doAction({
            name: 'Work Orders',
            res_model: 'fleet.workorder',
            res_id: false,
            views: [[false, 'list'],[false, 'form']],
            type: 'ir.actions.act_window',
        }, {
            on_reverse_breadcrumb: this.on_reverse_breadcrumb
        });
    }

    clickServiceType (ev) {
        ev.preventDefault();
        this.action.doAction({
            name: 'Service Type',
            res_model: 'service.type',
            res_id: false,
            views: [[false, 'list'],[false, 'form']],
            type: 'ir.actions.act_window',
        },
        {
            on_reverse_breadcrumb: this.on_reverse_breadcrumb
        });
    
    }  

}

registry.category("actions").add("fleet_repair_dashboard", FleetRepairDasboard)

