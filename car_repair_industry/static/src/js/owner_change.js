/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { Many2OneField } from "@web/views/fields/many2one/many2one_field";
import { useService } from "@web/core/utils/hooks";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";

console.log("Owner Change JS Loaded");

patch(Many2OneField.prototype, {

    setup() {
        super.setup();
        this.orm = useService("orm");
        this.dialog = useService("dialog");

    },

    async updateRecord(value) {

        await super.updateRecord(value);

        if (
            this.props.record.resModel !== "fleet.repair" ||
            this.props.name !== "client_id"
        ) {
            return;
        }

        const record = this.props.record;

        if (!record.data.license_plate || !record.data.client_id) {
            return;
        }

        console.log("Checking ownership...");

        const result = await this.orm.call(
            "fleet.repair",
            "check_owner_change",
            [
                record.data.license_plate,
                record.data.client_id[0],
            ]
        );

       if (!result.changed) {
    return;
}

this.dialog.add(ConfirmationDialog, {
    title: "Ownership Changed",

    body:
        `Current Owner : ${result.current_owner}

The selected client is different.

Do you want to create a new ownership record?`,

    confirmLabel: "Yes",

    cancelLabel: "No",

    confirm: async () => {
           const newVehicle = await this.orm.call(
        "fleet.repair",
        "create_new_owner",
        [
            result.vehicle_id,
            record.data.client_id[0],
        ]
    );

    console.log("Created vehicle:", newVehicle);
    },

    cancel: () => {
        console.log("NO CLICKED");
    },
});
    },

});