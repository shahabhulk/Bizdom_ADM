/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component } from "@odoo/owl";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

export class DeliveryStatusWidget extends Component {
    static template = "car_repair_industry.DeliveryStatusWidget";
    static props = {
        ...standardFieldProps,
    };

    get statusClass() {
        const value = this.props.record.data[this.props.name];
        if (!value) {
            return "";
        }
        const baseClass = "delivery-status-pulse";
        switch (value) {
            case 'green':
                return `o_status_green ${baseClass}`;
            case 'yellow':
                return `bg-warning ${baseClass}`;
            case 'red':
                return `bg-danger ${baseClass}`;
            default:
                return "";
        }
    }

    get statusTitle() {
        const value = this.props.record.data[this.props.name];
        if (!value) {
            return "";
        }
        switch (value) {
            case 'green':
                return "On Track";
            case 'yellow':
                return "Warning";
            case 'red':
                return "Delayed";
            default:
                return "";
        }
    }
}

export const deliveryStatusWidget = {
    component: DeliveryStatusWidget,
    fieldDependencies: [{ name: "delivery_status_color", type: "selection" }],
};

registry.category("fields").add("delivery_status", deliveryStatusWidget);

