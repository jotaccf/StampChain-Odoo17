/** @odoo-module **/
import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

class StampDashboard extends Component {
    static template = "stamp_chain.StampDashboard";

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");

        this.state = useState({
            zones: [],
            recentMovements: [],
            loading: true,
        });

        onWillStart(async () => {
            await this.loadData();
        });
    }

    async loadData() {
        const zones = await this.orm.searchRead(
            "tobacco.stamp.zone",
            [],
            [
                "id", "name", "code",
                "balance", "min_stock_alert",
                "alert_active", "color",
                "total_received", "total_used",
                "total_broken",
                "discrepancy", "discrepancy_active",
                "discrepancy_direction",
                "audit_open_count",
            ]
        );
        const movements = await this.orm.searchRead(
            "tobacco.stamp.movement",
            [],
            [
                "id", "date", "zone_id",
                "move_type", "qty",
                "balance_after", "reference",
            ],
            { limit: 10, order: "date desc" }
        );
        Object.assign(this.state, {
            zones,
            recentMovements: movements,
            loading: false,
        });
    }

    getZoneCardClass(zone) {
        if (zone.balance === 0) return "stamp-zone-card danger";
        if (zone.alert_active) return "stamp-zone-card warning";
        return "stamp-zone-card ok";
    }

    getMoveTypeLabel(moveType) {
        const labels = {
            in: "Entrada",
            out: "Saida",
            breakdown: "Quebra",
            recovery: "Recuperacao",
            adjust: "Ajuste",
        };
        return labels[moveType] || moveType;
    }

    getMoveTypeIcon(moveType) {
        const icons = {
            in: "fa-arrow-down",
            out: "fa-arrow-up",
            breakdown: "fa-times-circle",
            recovery: "fa-check-circle",
            adjust: "fa-sliders",
        };
        return icons[moveType] || "fa-circle";
    }

    getDiscrepancyClass(zone) {
        if (!zone.discrepancy_active) return "";
        return zone.discrepancy > 0
            ? "stamp-disc-missing"
            : "stamp-disc-surplus";
    }

    getDiscrepancyLabel(zone) {
        if (!zone.discrepancy_active) return "";
        const abs = Math.abs(zone.discrepancy);
        return zone.discrepancy > 0
            ? `Faltam ${abs}`
            : `Sobram ${abs}`;
    }

    async openZone(zoneId) {
        await this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "tobacco.stamp.zone",
            res_id: zoneId,
            views: [[false, "form"]],
        });
    }

    async openReception() {
        await this.action.doAction(
            "stamp_chain.action_incm_reception_wizard"
        );
    }

    async refresh() {
        this.state.loading = true;
        await this.loadData();
    }
}

registry.category("actions").add(
    "stamp_chain.stamp_dashboard",
    StampDashboard
);
