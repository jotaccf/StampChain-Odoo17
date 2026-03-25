# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import UserError
import re
import logging

_logger = logging.getLogger(__name__)
STAMP_REGEX = re.compile(r'^[A-Z]{5}\d{3}$')


class ProductionEndWizard(models.TransientModel):
    _name = 'tobacco.production.end.wizard'
    _description = 'Fim de Producao'

    production_id = fields.Many2one(
        'mrp.production',
        string='Ordem de Producao',
        required=True,
    )
    lot1_id = fields.Many2one(
        'tobacco.stamp.lot',
        string='Lote 1',
        required=True,
    )
    lot1_last_scan = fields.Char(
        string='Ultima Sobrante — Lote 1',
    )
    lot1_exhausted = fields.Boolean(
        string='Lote 1 esgotado',
        default=False,
    )
    lot1_scan_confirmed = fields.Boolean(
        string='Lote 1 confirmado',
        default=False,
    )
    lot1_consumed_stored = fields.Integer(
        string='Consumidas Lote 1',
        default=0,
    )
    lot1_remaining_stored = fields.Integer(
        string='Sobrantes Lote 1',
        default=0,
    )
    lot2_id = fields.Many2one(
        'tobacco.stamp.lot',
        string='Lote 2',
        required=True,
    )
    lot2_last_scan = fields.Char(
        string='Ultima Sobrante — Lote 2',
    )
    lot2_exhausted = fields.Boolean(
        string='Lote 2 esgotado',
        default=False,
    )
    lot2_scan_confirmed = fields.Boolean(
        string='Lote 2 confirmado',
        default=False,
    )
    lot2_consumed_stored = fields.Integer(
        string='Consumidas Lote 2',
        default=0,
    )
    lot2_remaining_stored = fields.Integer(
        string='Sobrantes Lote 2',
        default=0,
    )
    total_consumed_stored = fields.Integer(
        string='Total Consumidas',
        default=0,
    )

    def _parse_suffix(self, code):
        if code and STAMP_REGEX.match(code):
            return int(code[5:])
        return None

    def _calc_consumption(self, lot, last_scan,
                          exhausted):
        if exhausted or not last_scan:
            available_count = len(
                lot.serial_ids.filtered(
                    lambda s: s.state == 'available'
                )
            )
            return available_count, 0
        suffix_last = self._parse_suffix(last_scan)
        if suffix_last is None:
            return 0, 0
        remaining = lot.serial_ids.filtered(
            lambda s: (
                s.state == 'available'
                and len(s.serial_number) == 8
                and s.serial_number[5:].isdigit()
                and int(s.serial_number[5:])
                <= suffix_last
            )
        )
        consumed = lot.serial_ids.filtered(
            lambda s: (
                s.state == 'available'
                and len(s.serial_number) == 8
                and s.serial_number[5:].isdigit()
                and int(s.serial_number[5:])
                > suffix_last
            )
        )
        return len(consumed), len(remaining)

    @api.onchange('lot1_id', 'lot1_last_scan',
                  'lot1_exhausted')
    def _onchange_lot1_calc(self):
        if self.lot1_id:
            c, r = self._calc_consumption(
                self.lot1_id,
                self.lot1_last_scan,
                self.lot1_exhausted,
            )
            self.lot1_consumed_stored = c
            self.lot1_remaining_stored = r
            self._update_total()

    @api.onchange('lot2_id', 'lot2_last_scan',
                  'lot2_exhausted')
    def _onchange_lot2_calc(self):
        if self.lot2_id:
            c, r = self._calc_consumption(
                self.lot2_id,
                self.lot2_last_scan,
                self.lot2_exhausted,
            )
            self.lot2_consumed_stored = c
            self.lot2_remaining_stored = r
            self._update_total()

    def _update_total(self):
        self.total_consumed_stored = (
            self.lot1_consumed_stored
            + self.lot2_consumed_stored
        )

    def _validate_end_scan(self, lot, last_scan,
                           exhausted, lot_num):
        if exhausted:
            return True, ''
        if not last_scan:
            return (False,
                    f'Lote {lot_num}: scan obrigatorio '
                    f'ou marcar como esgotado.')
        if not STAMP_REGEX.match(last_scan):
            return (False,
                    f'Lote {lot_num}: formato invalido')
        if last_scan[:5] != lot.serial_prefix:
            return (False,
                    f'Lote {lot_num}: prefixo nao '
                    f'corresponde ao lote')
        serial = self.env[
            'tobacco.stamp.serial'
        ].search([
            ('serial_number', '=', last_scan),
            ('lot_id', '=', lot.id),
        ], limit=1)
        if not serial:
            return (False,
                    f'Lote {lot_num}: serial nao encontrado')
        if serial.state != 'available':
            return (False,
                    f'Lote {lot_num}: serial nao disponivel')
        suffix = int(last_scan[5:])
        if suffix > lot.current_suffix_end:
            return (False,
                    f'Lote {lot_num}: serial acima '
                    f'do disponivel (max: '
                    f'{lot.current_suffix_end})')
        return True, ''

    def action_confirm(self):
        self.ensure_one()
        ok1, w1 = self._validate_end_scan(
            self.lot1_id, self.lot1_last_scan,
            self.lot1_exhausted, 1)
        ok2, w2 = self._validate_end_scan(
            self.lot2_id, self.lot2_last_scan,
            self.lot2_exhausted, 2)
        if not ok1:
            raise UserError(w1)
        if not ok2:
            raise UserError(w2)
        if (not self.lot1_exhausted
                and not self.lot1_scan_confirmed):
            raise UserError(
                'Confirme o scan do Lote 1 '
                'ou marque como esgotado.')
        if (not self.lot2_exhausted
                and not self.lot2_scan_confirmed):
            raise UserError(
                'Confirme o scan do Lote 2 '
                'ou marque como esgotado.')

        zone = self.lot1_id.zone_id
        movements = []

        # R7: loop sem consumed/remaining
        for lot, last_scan, exhausted in [
            (self.lot1_id, self.lot1_last_scan,
             self.lot1_exhausted),
            (self.lot2_id, self.lot2_last_scan,
             self.lot2_exhausted),
        ]:
            self._process_lot_end(
                lot, last_scan,
                exhausted, movements
            )

        for mv in movements:
            self.env[
                'tobacco.stamp.movement'
            ].create(mv)

        zone._send_stock_alert()

        # Detecta discrepancia apos producao
        audit = self._check_and_create_audit(
            zone, self.production_id
        )

        self.production_id.message_post(
            body=(
                f'Producao concluida. '
                f'Total consumidas: '
                f'{self.total_consumed_stored}.'
            ),
        )
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'StampChain',
                'message': (
                    f'Producao registada. '
                    f'{self.total_consumed_stored}'
                    f' estampilhas consumidas.'
                ),
                'type': 'success',
            },
        }

    def _process_lot_end(self, lot, last_scan,
                         exhausted, movements):
        """R7: calcula actual_consumed internamente.
        R1: NUNCA modifica serial_suffix_end."""
        if exhausted:
            available = lot.serial_ids.filtered(
                lambda s: s.state == 'available'
            )
            actual_consumed = len(available)
            available.write({'state': 'used'})
            lot.write({
                'lot_status': 'exhausted',
                'qty_consumed': (
                    lot.qty_consumed + actual_consumed
                ),
            })
        else:
            suffix_last = self._parse_suffix(
                last_scan
            )
            consumed_serials = lot.serial_ids.filtered(
                lambda s: (
                    s.state == 'available'
                    and len(s.serial_number) == 8
                    and s.serial_number[5:].isdigit()
                    and int(s.serial_number[5:])
                    > suffix_last
                )
            )
            actual_consumed = len(consumed_serials)
            consumed_serials.write({'state': 'used'})
            new_status = (
                'exhausted'
                if not lot.serial_ids.filtered(
                    lambda s: s.state == 'available'
                )
                else 'partial'
            )
            lot.write({
                'lot_status': new_status,
                'qty_consumed': (
                    lot.qty_consumed + actual_consumed
                ),
            })

        if actual_consumed > 0:
            movements.append({
                'zone_id': lot.zone_id.id,
                'move_type': 'out',
                'qty': actual_consumed,
                'lot_id': lot.id,
                'reference': self.production_id.name,
                'notes': (
                    f'Producao: '
                    f'{self.production_id.name}. '
                    f'Lote {lot.incm_ref}: '
                    f'{actual_consumed} usadas'
                    + (f', sobrante: {last_scan}'
                       if not exhausted
                       else ' (esgotado)')
                ),
            })

    def _check_and_create_audit(
        self, zone, production
    ):
        """Detecta discrepancia apos producao
        e cria registo de auditoria se existir."""
        theoretical = zone.stock_theoretical
        real = zone.stock_real_auto
        disc = theoretical - real
        if disc == 0:
            return None
        audit = self.env[
            'tobacco.stamp.audit'
        ].create({
            'zone_id': zone.id,
            'stock_theoretical': theoretical,
            'stock_real': real,
            'stock_real_auto': real,
            'discrepancy': disc,
            'discrepancy_direction': (
                'missing' if disc > 0
                else 'surplus'
            ),
            'audit_type': 'production_end',
            'production_id': production.id,
        })
        production.message_post(
            body=(
                f'Discrepancia detectada: '
                f'{disc:+d} estampilhas. '
                f'Auditoria: {audit.name}'
            ),
        )
        return audit
