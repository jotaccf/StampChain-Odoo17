/** @odoo-module **/
import { Component, useState, useRef,
         onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

class StampPickingHandheld extends Component {
    static template =
        "stamp_chain.StampPickingHandheld";

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.inputRef = useRef("scanInput");

        // C6: picking_id do context
        const ctx = this.props.action?.context || {};
        this.pickingId = ctx.picking_id;

        this.state = useState({
            step: 'location',
            currentLocation: '',
            currentProduct: '',
            currentQty: 0,
            moveLineId: 0,
            progress: '0/0',
            scanValue: '',
            errorMsg: '',
            successMsg: '',
            doneQty: 0,
            totalLines: 0,
            loading: true,
            pickingName: '',
        });

        // C3: onWillStart no setup
        onWillStart(async () => {
            await this.loadPickingInfo();
        });
    }

    async loadPickingInfo() {
        if (!this.pickingId) {
            this.state.loading = false;
            this.state.errorMsg =
                'Picking nao encontrado';
            return;
        }
        const picking = await this.orm.read(
            'stock.picking',
            [this.pickingId],
            ['name', 'current_move_line_id',
             'move_line_ids']
        );
        if (!picking.length) return;
        const p = picking[0];
        this.state.pickingName = p.name;
        const lines = await this.orm.searchRead(
            'stock.move.line',
            [['picking_id', '=', this.pickingId],
             ['state', 'not in',
              ['done', 'cancel']]],
            ['id', 'location_id', 'product_id',
             'quantity', 'qty_done'],
            { order: 'location_id asc' }
        );
        if (!lines.length) {
            this.state.step = 'done';
            this.state.loading = false;
            return;
        }
        const currentId =
            p.current_move_line_id?.[0]
            || lines[0].id;
        const currentIdx = lines.findIndex(
            l => l.id === currentId
        );
        const current = lines[
            Math.max(0, currentIdx)
        ];
        Object.assign(this.state, {
            loading: false,
            moveLineId: current.id,
            totalLines: lines.length,
            progress:
                `${Math.max(0, currentIdx) + 1}`
                + `/${lines.length}`,
            currentLocation:
                current.location_id[1] || '',
            currentProduct:
                current.product_id[1] || '',
            currentQty: current.quantity,
            step: 'location',
        });
        this._focusInput();
    }

    _focusInput() {
        setTimeout(() => {
            if (this.inputRef.el)
                this.inputRef.el.focus();
        }, 100);
    }

    _vibrate(pattern) {
        if (navigator.vibrate)
            navigator.vibrate(pattern);
    }

    onScanInput(ev) {
        this.state.scanValue =
            ev.target.value.trim();
    }

    onScanKeydown(ev) {
        if (ev.key === 'Enter')
            this.onScanSubmit();
    }

    async onScanSubmit() {
        const val = this.state.scanValue;
        if (!val) return;
        this.state.errorMsg = '';
        this.state.successMsg = '';
        if (this.state.step === 'location') {
            await this._validateLocation(val);
        } else if (
            this.state.step === 'product'
        ) {
            await this._validateProduct(val);
        }
        this.state.scanValue = '';
        if (this.inputRef.el) {
            this.inputRef.el.value = '';
            this.inputRef.el.focus();
        }
    }

    async _validateLocation(barcode) {
        const result = await this.orm.call(
            'stock.picking',
            'action_validate_location_scan',
            [[this.pickingId], barcode]
        );
        if (result.ok) {
            this._vibrate([100]);
            this.state.step = 'product';
            this.state.moveLineId =
                result.move_line_id;
            this.state.successMsg =
                'Localizacao OK: '
                + result.location;
        } else {
            this._vibrate([200, 100, 200]);
            this.state.errorMsg =
                result.message;
        }
    }

    async _validateProduct(barcode) {
        const result = await this.orm.call(
            'stock.picking',
            'action_validate_product_scan',
            [[this.pickingId], barcode]
        );
        if (result.ok) {
            this._vibrate([100]);
            this.state.step = 'qty';
            this.state.successMsg =
                'Produto OK: ' + result.product;
            this.state.doneQty =
                result.qty_todo;
        } else {
            this._vibrate([200, 100, 200]);
            this.state.errorMsg =
                result.message;
        }
    }

    async confirmQty() {
        // C5: move_line_id
        const result = await this.orm.call(
            'stock.picking',
            'action_confirm_qty',
            [[this.pickingId],
             this.state.doneQty,
             this.state.moveLineId]
        );
        if (!result.ok) {
            this.state.errorMsg =
                result.message;
            return;
        }
        if (result.done) {
            this.state.step = 'done';
            this.state.successMsg =
                result.message;
            this._vibrate(
                [100, 50, 100, 50, 200]
            );
            return;
        }
        Object.assign(this.state, {
            step: 'location',
            moveLineId:
                result.next_move_line_id,
            currentLocation:
                result.next_location,
            currentProduct:
                result.next_product,
            currentQty: result.next_qty,
            progress: result.progress,
            errorMsg: '',
            successMsg: '',
            doneQty: 0,
        });
        this._focusInput();
    }

    adjustQty(delta) {
        this.state.doneQty = Math.max(
            0, this.state.doneQty + delta
        );
    }

    async validatePicking() {
        try {
            await this.orm.call(
                'stock.picking',
                'button_validate',
                [[this.pickingId]]
            );
            this.notification.add(
                'Picking validado!',
                { type: 'success' }
            );
            await this.action.doAction({
                type: 'ir.actions.act_window',
                res_model: 'stock.picking',
                res_id: this.pickingId,
                views: [[false, 'form']],
            });
        } catch (e) {
            this.state.errorMsg =
                'Erro: ' + e.message;
        }
    }
}

registry.category("actions").add(
    "stamp_chain.picking_handheld",
    StampPickingHandheld
);
