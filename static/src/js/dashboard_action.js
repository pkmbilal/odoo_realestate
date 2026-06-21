/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

class RealestateDashboardAction extends Component {
    setup() {
        this.orm = useService("orm");
        this.actionService = useService("action");
        this.notification = useService("notification");
        this.user = useService("user");
        this.state = useState({
            loading: true,
            error: "",
            dashboard: null,
            isAdmin: false,
        });

        onWillStart(async () => {
            const dashboardId = this.props.action?.params?.dashboard_id;
            if (!dashboardId) {
                const action = await this.orm.call("realestate.dashboard", "action_open_dashboard", []);
                await this.actionService.doAction(action);
                return;
            }

            await this._loadDashboard(dashboardId);
            try {
                this.state.isAdmin = await this.user.hasGroup("base.group_system");
            } catch {
                this.state.isAdmin = false;
            }
        });
    }

    get dashboard() {
        return this.state.dashboard || {};
    }

    get companyName() {
        const company = this.dashboard.company_id;
        return company ? company[1] : "";
    }

    async _loadDashboard(dashboardId) {
        try {
            const [dashboard] = await this.orm.read("realestate.dashboard", [dashboardId], [
                "company_id",
                "building_count",
                "floor_count",
                "unit_count",
                "available_unit_count",
                "occupied_unit_count",
                "maintenance_unit_count",
                "tenant_count",
                "active_contract_count",
                "invoice_due_count",
                "invoice_overdue_count",
            ]);
            this.state.dashboard = dashboard;
        } catch (error) {
            this.state.error = error?.message || "Unable to load the dashboard.";
            this.notification.add(this.state.error, { type: "danger" });
        } finally {
            this.state.loading = false;
        }
    }

    async _runDashboardAction(methodName) {
        if (!this.dashboard.id) {
            return;
        }
        try {
            const action = await this.orm.call("realestate.dashboard", methodName, [[this.dashboard.id]]);
            return this.actionService.doAction(action);
        } catch (error) {
            const message = error?.message || "Unable to open the requested view.";
            this.notification.add(message, { type: "danger" });
        }
    }

    openBuildings() {
        return this._runDashboardAction("action_open_buildings");
    }

    openFloors() {
        return this._runDashboardAction("action_open_floors");
    }

    openUnits() {
        return this._runDashboardAction("action_open_units");
    }

    openAvailableUnits() {
        return this._runDashboardAction("action_open_available_units");
    }

    openOccupiedUnits() {
        return this._runDashboardAction("action_open_occupied_units");
    }

    openTenants() {
        return this._runDashboardAction("action_open_tenants");
    }

    openContracts() {
        return this._runDashboardAction("action_open_contracts");
    }

    openActiveContracts() {
        return this._runDashboardAction("action_open_active_contracts");
    }

    openInvoices() {
        return this._runDashboardAction("action_open_invoices");
    }

    openDueInvoices() {
        return this._runDashboardAction("action_open_due_invoices");
    }

    openOverdueInvoices() {
        return this._runDashboardAction("action_open_overdue_invoices");
    }

    openSettings() {
        return this._runDashboardAction("action_open_settings");
    }
}

RealestateDashboardAction.template = "realestate.RealestateDashboardAction";

registry.category("actions").add("realestate_dashboard", RealestateDashboardAction);
