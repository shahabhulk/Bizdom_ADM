/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";
import {
    AlertDialog,
    ConfirmationDialog,
} from "@web/core/confirmation_dialog/confirmation_dialog";
import { Many2OneField } from "@web/views/fields/many2one/many2one_field";

function showAlert(dialog, title, body) {
    return new Promise((resolve) => {
        dialog.add(AlertDialog, {
            title,
            body,
            confirm: () => resolve(),
        });
    });
}

async function confirmEnableInventoryTracking(dialog, productName) {
    return new Promise((resolve) => {
        dialog.add(ConfirmationDialog, {
            title: _t("Track Inventory"),
            body: _t(
                'Product "%s" is not set to track inventory. Would you like to enable inventory tracking?',
                productName
            ),
            confirmLabel: _t("Yes"),
            cancelLabel: _t("No"),
            confirm: () => resolve(true),
            cancel: () => resolve(false),
            close: () => resolve(false),
        });
    });
}

patch(Many2OneField.prototype, {
    _clearProductLineSelection() {
        const { record } = this.props;
        const changes = { [this.props.name]: false };
        const linkedField = this.props.name === "product_id" ? "item_code_id" : "product_id";
        if (linkedField in record.fields) {
            changes[linkedField] = false;
        }
        if (Object.keys(changes).length === 1) {
            return super.updateRecord([false, ""]);
        }
        return record.update(changes);
    },

    async updateRecord(value) {
        const isProductLineField =
            this.props.record?.resModel === "fleet.repair.product.line" &&
            ["product_id", "item_code_id"].includes(this.props.name) &&
            this.relation === "product.product";

        if (!isProductLineField || !value?.[0]) {
            return super.updateRecord(...arguments);
        }

        const productId = value[0];
        const [product] = await this.orm.read(
            "product.product",
            [productId],
            ["is_storable", "type", "display_name"],
            { context: this.context }
        );

        if (!product) {
            return super.updateRecord(...arguments);
        }

        if (product.type === "service") {
            await showAlert(
                this.dialog,
                _t("Invalid Product"),
                _t("You cannot add a service product here.")
            );
            return this._clearProductLineSelection();
        }

        if (product.type === "consu" && !product.is_storable) {
            const enableTracking = await confirmEnableInventoryTracking(
                this.dialog,
                product.display_name
            );
            if (!enableTracking) {
                return this._clearProductLineSelection();
            }
            try {
                await this.orm.call(
                    "fleet.repair.product.line",
                    "action_enable_inventory_tracking",
                    [productId],
                    { context: this.context }
                );
            } catch (error) {
                this.notification.add(
                    error.data?.message ||
                        _t("Could not enable inventory tracking for this product."),
                    { type: "danger" }
                );
                return this._clearProductLineSelection();
            }
        }

        return super.updateRecord(...arguments);
    },
});
