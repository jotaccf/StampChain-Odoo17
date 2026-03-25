/** @odoo-module **/
import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

class StampDashboard extends Component {
    static template = "stamp_chain.StampDashboard";

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");

        // Bind methods for OWL template calls
        this.openZone = this.openZone.bind(this);
        this.openAction = this.openAction.bind(this);
        this.refreshData = this.refreshData.bind(this);

        this.state = useState({
            zones: [],
            recentMovements: [],
            loading: true,
            lastUpdate: '',
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
                "stock_theoretical", "stock_real",
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
        zones.sort((a, b) => {
            const urgA = a.discrepancy_active ? 2 : a.alert_active ? 1 : 0;
            const urgB = b.discrepancy_active ? 2 : b.alert_active ? 1 : 0;
            return urgB - urgA;
        });
        const now = new Date();
        const time = now.getHours().toString().padStart(2, '0')
            + ':' + now.getMinutes().toString().padStart(2, '0');
        Object.assign(this.state, {
            zones,
            recentMovements: movements,
            loading: false,
            lastUpdate: time,
        });
    }

    getZoneCardClass(zone) {
        if (zone.discrepancy_active) {
            return zone.discrepancy > 0 ? 'sc-zone-card disc-miss' : 'sc-zone-card disc-plus';
        }
        return zone.alert_active ? 'sc-zone-card warn' : 'sc-zone-card ok';
    }

    getBalanceClass(zone) {
        if (zone.discrepancy_active && zone.discrepancy > 0) return 'sc-zone-balance err';
        return zone.alert_active ? 'sc-zone-balance warn' : 'sc-zone-balance ok';
    }

    getDiscLabel(zone) {
        if (!zone.discrepancy_active) return '';
        const abs = Math.abs(zone.discrepancy);
        return zone.discrepancy > 0 ? `Faltam ${abs}` : `Sobram ${abs}`;
    }

    getDiscClass(zone) {
        if (!zone.discrepancy_active) return '';
        return zone.discrepancy > 0 ? 'sc-inline-alert disc-miss' : 'sc-inline-alert disc-plus';
    }

    getMovTypeClass(moveType) {
        const map = {
            in: 'sc-type-pill sc-type-in', out: 'sc-type-pill sc-type-out',
            breakdown: 'sc-type-pill sc-type-brk', recovery: 'sc-type-pill sc-type-rec',
            recovery_found: 'sc-type-pill sc-type-found', adjust: 'sc-type-pill sc-type-brk',
        };
        return map[moveType] || 'sc-type-pill';
    }

    getMovTypeLabel(moveType) {
        const map = {
            in: 'Entrada', out: 'Saida', breakdown: 'Quebra',
            recovery: 'Recuperacao', recovery_found: 'Encontrada', adjust: 'Ajuste',
        };
        return map[moveType] || moveType;
    }

    getQtyClass(moveType) {
        if (['in', 'recovery', 'recovery_found'].includes(moveType)) return 'sc-qty-pos';
        return moveType === 'breakdown' ? 'sc-qty-warn' : 'sc-qty-neg';
    }

    getQtyPrefix(moveType) {
        return ['in', 'recovery', 'recovery_found'].includes(moveType) ? '+' : '-';
    }

    getAlertZones() {
        return this.state.zones.filter(z => z.discrepancy_active);
    }

    getMinAlertZones() {
        return this.state.zones.filter(z => z.alert_active && !z.discrepancy_active);
    }

    async openZone(zoneId) {
        await this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "tobacco.stamp.zone",
            res_id: zoneId,
            views: [[false, "form"]],
        });
    }

    async openAction(actionXmlId) {
        await this.action.doAction(actionXmlId);
    }

    async refreshData() {
        this.state.loading = true;
        await this.loadData();
    }
}

registry.category("actions").add(
    "stamp_chain.stamp_dashboard",
    StampDashboard
);
