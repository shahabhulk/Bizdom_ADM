/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { Dialog } from "@web/core/dialog/dialog";
import { Many2OneField } from "@web/views/fields/many2one/many2one_field";
import { CharField } from "@web/views/fields/char/char_field";
import { useService } from "@web/core/utils/hooks";
import { Component } from "@odoo/owl";

class ClientNumberConflictDialog extends Component {
    static template = "car_repair_industry.ClientNumberConflictDialog";
    static components = { Dialog };
    static props = {
        close: Function,
        title: String,
        body: String,
        createLabel: { type: String, optional: true },
        cancelLabel: { type: String, optional: true },
        deleteLabel: { type: String, optional: true },
        onCreate: { type: Function, optional: true },
        onCancel: { type: Function, optional: true },
        onDelete: { type: Function, optional: true },
    };
    static defaultProps = {
        createLabel: _t("Create Anyway"),
        cancelLabel: _t("Cancel"),
        deleteLabel: _t("Delete"),
    };

    async _create() {
        if (this.props.onCreate) {
            await this.props.onCreate();
        }
        this.props.close();
    }

    async _cancel() {
        if (this.props.onCancel) {
            await this.props.onCancel();
        }
        this.props.close();
    }

    async _delete() {
        if (this.props.onDelete) {
            await this.props.onDelete();
        }
        this.props.close();
    }
}

patch(Many2OneField.prototype, {
    setup() {
        super.setup();

        const originalQuickCreate = this.quickCreate;
        if (!originalQuickCreate) {
            return;
        }

        this.quickCreate = async (name) => {
            const isTargetField =
                this.props.record?.resModel === "fleet.repair" &&
                this.props.name === "client_id" &&
                this.relation === "res.partner";

            if (!isTargetField) {
                return originalQuickCreate(name);
            }

            const existing = await this.orm.call(
                "res.partner",
                "get_existing_client_contacts",
                [name],
                { context: this.context }
            );

            if (!existing.length) {
                return originalQuickCreate(name);
            }

            const numberText = existing
                .flatMap((partner) => partner.numbers || [])
                .filter((number, index, arr) => number && arr.indexOf(number) === index)
                .join(", ");
            const hasAnyNumber = existing.some((partner) => partner.has_numbers);
            const displayNumberText = numberText || _t("No contact number");
            const warningMessage = hasAnyNumber
                ? _t(
                      'Client "%s" already exists with contact number(s): %s. Are you sure you want to create this customer?',
                      name,
                      displayNumberText
                  )
                : _t(
                      'Client "%s" already exists but no contact number is saved. Are you sure you want to create this customer?',
                      name
                  );

            const confirmCreate = await new Promise((resolve) => {
                this.dialog.add(ConfirmationDialog, {
                    title: _t("Existing Customer Found"),
                    body: warningMessage,
                    confirmLabel: _t("Create Anyway"),
                    cancelLabel: _t("Cancel"),
                    confirm: () => resolve(true),
                    cancel: () => resolve(false),
                    close: () => resolve(false),
                });
            });

            if (!confirmCreate) {
                return;
            }

            return originalQuickCreate(name);
        };
    },
});

patch(CharField.prototype, {
    setup() {
        super.setup();
        this.orm = useService("orm");
        this.dialog = useService("dialog");
        this._lastConfirmedValue = this.props.record.data[this.props.name] || "";
    },

    async onBlur() {
        super.onBlur();

        const isTargetField =
            this.props.record?.resModel === "fleet.repair" &&
            ["client_phone", "client_mobile"].includes(this.props.name);
        if (!isTargetField) {
            this._lastConfirmedValue = this.props.record.data[this.props.name] || "";
            return;
        }

        const currentValue = (this.props.record.data[this.props.name] || "").trim();
        if (!currentValue || currentValue === this._lastConfirmedValue) {
            this._lastConfirmedValue = currentValue;
            return;
        }

        const clientName = this.props.record.data.client_id?.[1] || "";
        const excludePartnerId = this.props.record.data.client_id?.[0] || false;
        const numbersToCheck = [
            this.props.record.data.client_phone || "",
            this.props.record.data.client_mobile || "",
        ];
        const conflicts = await this.orm.call(
            "res.partner",
            "get_conflicts_by_contact_number",
            [clientName, numbersToCheck, excludePartnerId],
            { context: this.props.record.context }
        );

        if (!conflicts.length) {
            this._lastConfirmedValue = currentValue;
            return;
        }

        const conflictNames = conflicts.map((c) => c.name).filter(Boolean).join(", ");
        const conflictNumbers = conflicts
            .flatMap((c) => c.numbers || [])
            .filter((num, index, arr) => num && arr.indexOf(num) === index)
            .join(", ");

        const userAction = await new Promise((resolve) => {
            this.dialog.add(ClientNumberConflictDialog, {
                title: _t("Existing Customer Found"),
                body: _t(
                    'Customer "%s" already exists with number(s): %s. Are you sure you want to create this customer?',
                    conflictNames || _t("Unknown"),
                    conflictNumbers || currentValue
                ),
                createLabel: _t("Create Anyway"),
                cancelLabel: _t("Cancel"),
                deleteLabel: _t("Delete"),
                onCreate: () => resolve("create"),
                onCancel: () => resolve("cancel"),
                onDelete: () => resolve("delete"),
            });
        });

        if (userAction === "cancel") {
            await this.props.record.update({ [this.props.name]: this._lastConfirmedValue || false });
            if (this.input?.el) {
                this.input.el.value = this._lastConfirmedValue || "";
            }
            return;
        }

        if (userAction === "delete") {
            if (excludePartnerId) {
                await this.orm.call("res.partner", "unlink", [[excludePartnerId]], {
                    context: this.props.record.context,
                });
            }
            await this.props.record.update({
                client_id: false,
                client_phone: false,
                client_mobile: false,
                client_email: false,
            });
            this._lastConfirmedValue = "";
            if (this.input?.el) {
                this.input.el.value = "";
            }
            return;
        }

        this._lastConfirmedValue = currentValue;
    },
});
