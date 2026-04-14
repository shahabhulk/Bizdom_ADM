/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { ReferenceField } from "@web/views/fields/reference/reference_field";

// Keep a reference to the original getter so we can extend it safely.
const originalM2oPropsGetter = Object.getOwnPropertyDescriptor(
    ReferenceField.prototype,
    "m2oProps"
).get;

patch(ReferenceField.prototype, {
    get m2oProps() {
        const props = originalM2oPropsGetter.call(this);

        // Only target our Reference field on bizdom.category_lvl2.
        if (this.props?.name !== "category_lvl2_selection") {
            return props;
        }

        // Only apply when the selected model is product.product.
        if (this.relation !== "product.product" && this.relation !== "hr.employee") {
            return props;
        }
    

        // score_id is a many2one: [id, display_name]
        const scoreTuple = this.props?.record?.data?.score_id;
        console.log('scoreTuple', scoreTuple);
        const scoreName = scoreTuple?.[1];
        console.log('scoreName', scoreName);

        const deptId = this.props?.record?.data?.department_id?.[0];

        // When score is Expense, restrict the selectable products.
        if (scoreName === "Expense" && this.relation === "product.product") {
            props.domain = [["can_be_expensed", "=", true]];
        }

        if (this.relation === "hr.employee") {
            props.domain = [["department_id", "=", deptId]];
        }

        return props;
    },
});

