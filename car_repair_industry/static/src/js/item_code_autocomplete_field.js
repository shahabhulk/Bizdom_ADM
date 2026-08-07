/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { useService } from "@web/core/utils/hooks";
import { AutoComplete } from "@web/core/autocomplete/autocomplete";
import { FormViewDialog } from "@web/views/view_dialogs/form_view_dialog";
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
        this.dialog = useService("dialog");
    }

    get value() {
        const rawVal = this.props.record.data[this.props.name];
        if (!rawVal || rawVal === "false" || rawVal === false) {
            return "";
        }
        if (typeof rawVal === "string") {
            return rawVal;
        }
        if (Array.isArray(rawVal) && rawVal.length > 1 && typeof rawVal[1] === "string") {
            return rawVal[1] === "false" ? "" : rawVal[1];
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
        const domain = [
            ["type", "=", "consu"],
            ["item_code", "!=", false],
            ["item_code", "!=", ""]
        ];
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

        const options = products
            .filter((p) => p.item_code && typeof p.item_code === "string" && p.item_code.trim() !== "" && p.item_code !== "false")
            .map((p) => {
                const rawCode = p.item_code.trim();
                return {
                    label: rawCode,
                    value: p.id,
                    product: p,
                    code: rawCode,
                    isCreate: false,
                };
            });

        const reqCode = request ? request.trim() : "";
        options.push({
            label: reqCode ? _t(`Create and Edit "${reqCode}"...`) : _t("Create and Edit..."),
            classList: "text-primary fw-bold",
            code: reqCode,
            isCreateEdit: true,
        });

        return options;
    }

    async onSelectOption(option) {
        if (!option) return;
        if (option.isCreateEdit) {
            await this.createAndEditProduct(option.code);
        } else if (option.product) {
            await this.selectProduct(option.product, option.code);
        }
    }

    async selectProduct(product, code) {
        if (product && product.type === "consu" && !product.is_storable) {
            await this.orm.call("fleet.repair.product.line", "action_enable_inventory_tracking", [product.id]);
        }
        const rawCode = (product.item_code || product.default_code || "").trim();
        const itemCode = rawCode ? rawCode : (code || "");
        const changes = {
            item_code_display: itemCode,
            product_id: [product.id, product.name],
        };
        if ("item_code_id" in this.props.record.fields) {
            changes.item_code_id = [product.id, product.name];
        }
        await this.props.record.update(changes);
    }

    async createAndEditProduct(code = "") {
        const context = {
            default_name: code,
            default_item_code: code,
            default_type: "consu",
            default_is_storable: true,
            default_categ_id: false,
        };
        this.dialog.add(FormViewDialog, {
            resModel: "product.product",
            context: context,
            title: _t("Create Item"),
            onRecordSaved: async (record) => {
                if (record && record.resId) {
                    const [product] = await this.orm.read(
                        "product.product",
                        [record.resId],
                        ["id", "display_name", "name", "item_code", "default_code", "type", "is_storable"]
                    );
                    if (product) {
                        if (product.type === "consu" && !product.is_storable) {
                            await this.orm.call("fleet.repair.product.line", "action_enable_inventory_tracking", [product.id]);
                        }
                        const rawCode = (product.item_code || product.default_code || code || "").trim();
                        const changes = {
                            item_code_display: rawCode,
                            product_id: [product.id, product.name],
                        };
                        if ("item_code_id" in this.props.record.fields) {
                            changes.item_code_id = [product.id, product.name];
                        }
                        await this.props.record.update(changes);
                    }
                }
            },
        });
    }

    async onKeyDown(ev) {
        if (ev.key === "Tab" || ev.keyCode === 9) {
            const inputValue = (ev.target?.value || this.value || "").trim();
            if (!inputValue) {
                return;
            }

            const domain = [
                ["type", "=", "consu"],
                ["item_code", "!=", false],
                ["item_code", "!=", ""],
                ["item_code", "=ilike", inputValue],
            ];

            const products = await this.orm.searchRead(
                "product.product",
                domain,
                ["id", "display_name", "name", "item_code", "default_code", "type", "is_storable"],
                { limit: 1 }
            );

            if (products && products.length > 0) {
                const product = products[0];
                const rawCode = (product.item_code || product.default_code || inputValue).trim();
                await this.selectProduct(product, rawCode);
            } else {
                ev.preventDefault();
                ev.stopPropagation();
                await this.createAndEditProduct(inputValue);
            }
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
