/** @odoo-module **/

import { registry } from "@web/core/registry";
import { listView } from "@web/views/list/list_view";
import { ListController } from "@web/views/list/list_controller";
import { SearchBar } from "@web/search/search_bar/search_bar";
import { SearchModel } from "@web/search/search_model";
import { Domain } from "@web/core/domain";
import { debounce } from "@web/core/utils/timing";

export class FleetRepairSearchModel extends SearchModel {
    setup(services) {
        super.setup(services);
        this.quickSearchTerm = "";
    }

    setQuickSearch(term) {
        const trimmed = (term || "").trim();
        if (this.quickSearchTerm === trimmed) {
            return;
        }
        this.quickSearchTerm = trimmed;
        this._notify();
    }

    _getDomain(params = {}) {
        const domain = super._getDomain(params);
        if (!this.quickSearchTerm) {
            return domain;
        }
        const term = this.quickSearchTerm;
        const quickDomain = [
            "|", "|", "|", "|", "|", "|", "|", "|",
            ["sequence", "ilike", term],
            ["name", "ilike", term],
            ["client_id", "ilike", term],
            ["client_phone", "ilike", term],
            ["client_mobile", "ilike", term],
            ["fleet_id", "ilike", term],
            ["license_plate", "ilike", term],
            ["user_id", "ilike", term],
            ["vin_sn", "ilike", term],
        ];
        try {
            const combined = Domain.and([domain, quickDomain]);
            return params.raw ? combined : combined.toList(this.domainEvalContext || {});
        } catch (_err) {
            return domain;
        }
    }
}

export class FleetRepairSearchBar extends SearchBar {
    setup() {
        super.setup();
        this.debouncedLiveSearch = debounce(this._applyLiveSearch.bind(this), 350);
    }

    _applyLiveSearch(val) {
        if (this.env.searchModel?.setQuickSearch) {
            this.env.searchModel.setQuickSearch(val);
        }
    }

    onSearchInput(ev) {
        super.onSearchInput(ev);
        const query = ev.target.value;
        this.debouncedLiveSearch(query);
    }

    selectItem(item) {
        if (this.env.searchModel?.setQuickSearch) {
            this.env.searchModel.quickSearchTerm = "";
        }
        super.selectItem(item);
    }

    resetState(options = { focus: true }) {
        super.resetState(options);
        if (this.env.searchModel?.setQuickSearch && this.env.searchModel.quickSearchTerm) {
            this.env.searchModel.setQuickSearch("");
        }
    }
}

export class FleetRepairListController extends ListController {
    static components = {
        ...ListController.components,
        SearchBar: FleetRepairSearchBar,
    };
}

export const FleetRepairListView = {
    ...listView,
    Controller: FleetRepairListController,
    SearchModel: FleetRepairSearchModel,
};

registry.category("views").add("fleet_repair_list", FleetRepairListView);
