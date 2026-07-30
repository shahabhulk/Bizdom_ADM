/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { useService } from "@web/core/utils/hooks";
import { AutoComplete } from "@web/core/autocomplete/autocomplete";
import { Component } from "@odoo/owl";

export class ItemCodeAutoCompleteField extends Component {
    static template = "car_repair_industry.ItemCodeAutoCompleteField";
    static components = { AutoComplete };
    static props = {
        ...standardFieldProps,
    };

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
    }

    get value() {
        const rawVal = this.props.record.data[this.props.name];
        if (typeof rawVal === "string") {
            return rawVal;
        }
        if (Array.isArray(rawVal) && rawVal.length > 1 && typeof rawVal[1] === "string") {
            return rawVal[1];
        }
        return "";
    }

    get sources() {
        return [
            {
                placeholder: _t("Loading..."),
                options: async (request) => {
                    return this.loadOptions(request);
                },
            },
        ];
    }

    async loadOptions(request) {
        const domain = [["type", "=", "consu"]];
        if (request && request.trim()) {
            const searchStr = request.trim();
            domain.push("|", "|", ["item_code", "ilike", searchStr], ["default_code", "ilike", searchStr], ["name", "ilike", searchStr]);
        }

        const products = await this.orm.searchRead(
            "product.product",
            domain,
            ["id", "display_name", "name", "item_code", "default_code"],
            { limit: 15 }
        );

        const options = products.map((p) => {
            const rawCode = (p.item_code || p.default_code || "").trim();
            const label = rawCode ? rawCode : "NIL";
            return {
                label: label,
                value: p.id,
                product: p,
                code: label,
                isCreate: false,
            };
        });

        if (request && request.trim()) {
            const reqCode = request.trim();
            const exactMatch = products.some(
                (p) => (p.item_code && p.item_code.toLowerCase() === reqCode.toLowerCase()) ||
                       (p.default_code && p.default_code.toLowerCase() === reqCode.toLowerCase())
            );
            if (!exactMatch) {
                options.push({
                    label: _t(`Create "${reqCode}"...`),
                    classList: "text-primary fw-bold",
                    code: reqCode,
                    isCreate: true,
                });
            }
        }

        return options;
    }

    async onSelectOption(option) {
        if (!option) return;
        if (option.isCreate) {
            await this.createProduct(option.code);
        } else if (option.product) {
            await this.selectProduct(option.product, option.code);
        }
    }

    async selectProduct(product, code) {
        const rawCode = (product.item_code || product.default_code || "").trim();
        const itemCode = rawCode ? rawCode : (code || "NIL");
        const changes = {
            item_code_display: itemCode,
            product_id: [product.id, product.name],
        };
        if ("item_code_id" in this.props.record.fields) {
            changes.item_code_id = [product.id, product.name];
        }
        await this.props.record.update(changes);
    }

    async createProduct(code) {
        try {
            const [newProductId] = await this.orm.create("product.product", [
                {
                    name: code,
                    item_code: code,
                    type: "consu",
                    is_storable: true,
                },
            ]);
            if (newProductId) {
                const changes = {
                    item_code_display: code,
                    product_id: [newProductId, code],
                };
                if ("item_code_id" in this.props.record.fields) {
                    changes.item_code_id = [newProductId, code];
                }
                await this.props.record.update(changes);
            }
        } catch (error) {
            this.notification.add(
                error.data?.message || _t("Failed to create new item code product."),
                { type: "danger" }
            );
        }
    }

    onInputChange(val) {
        if (val !== this.value) {
            this.props.record.update({ [this.props.name]: val });
        }
    }
}

export const itemCodeAutoCompleteField = {
    component: ItemCodeAutoCompleteField,
    supportedTypes: ["char"],
};

registry.category("fields").add("item_code_autocomplete", itemCodeAutoCompleteField);
