# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import (
    UserError, ValidationError
)
import re

STAMP_REGEX = re.compile(r'^[A-Z]{5}\d{3}$')


class ProductionStartWizard(models.TransientModel):
    _name = 'tobacco.production.start.wizard'
    _description = 'Inicio de Producao'

    production_id = fields.Many2one(
        'mrp.production',
        string='Ordem de Producao',
        required=True,
    )
    zone_id = fields.Many2one(
        'tobacco.stamp.zone',
        string='Zona',
        related='production_id.stamp_zone_id',
        readonly=True,
    )
    lot1_id = fields.Many2one(
        'tobacco.stamp.lot',
        string='Lote 1',
        required=True,
    )
    lot1_scan = fields.Char(
        string='Scan Inicio — Lote 1',
    )
    lot1_scan_confirmed = fields.Boolean(
        string='Lote 1 confirmado',
        default=False,
    )
    lot1_range = fields.Char(
        string='Range Lote 1',
        compute='_compute_lot1_info',
        store=False,
    )
    lot1_scan_warning = fields.Char(
        string='Aviso Lote 1',
        compute='_compute_lot1_scan_valid',
        store=False,
    )
    lot2_id = fields.Many2one(
        'tobacco.stamp.lot',
        string='Lote 2',
        required=True,
    )
    lot2_scan = fields.Char(
        string='Scan Inicio — Lote 2',
    )
    lot2_scan_confirmed = fields.Boolean(
        string='Lote 2 confirmado',
        default=False,
    )
    lot2_range = fields.Char(
        string='Range Lote 2',
        compute='_compute_lot2_info',
        store=False,
    )
    lot2_scan_warning = fields.Char(
        string='Aviso Lote 2',
        compute='_compute_lot2_scan_valid',
        store=False,
    )

    @api.depends('lot1_id')
    def _compute_lot1_info(self):
        for wiz in self:
            if not wiz.lot1_id:
                wiz.lot1_range = ''
                continue
            lot = wiz.lot1_id
            avail = lot.serial_ids.filtered(
                lambda s: s.state == 'available'
            )
            wiz.lot1_range = (
                f'{lot.serial_prefix}'
                f'{lot.serial_suffix_start:03d}'
                f' -> '
                f'{lot.serial_prefix}'
                f'{lot.current_suffix_end:03d}'
                f' ({len(avail)} disponiveis)'
                if avail else 'Sem disponiveis'
            )

    @api.depends('lot2_id')
    def _compute_lot2_info(self):
        for wiz in self:
            if not wiz.lot2_id:
                wiz.lot2_range = ''
                continue
            lot = wiz.lot2_id
            avail = lot.serial_ids.filtered(
                lambda s: s.state == 'available'
            )
            wiz.lot2_range = (
                f'{lot.serial_prefix}'
                f'{lot.serial_suffix_start:03d}'
                f' -> '
                f'{lot.serial_prefix}'
                f'{lot.current_suffix_end:03d}'
                f' ({len(avail)} disponiveis)'
                if avail else 'Sem disponiveis'
            )

    @api.depends('lot1_id', 'lot1_scan')
    def _compute_lot1_scan_valid(self):
        for wiz in self:
            _, wiz.lot1_scan_warning = (
                wiz._validate_start_scan(
                    wiz.lot1_id, wiz.lot1_scan, 1
                )
            )

    @api.depends('lot2_id', 'lot2_scan')
    def _compute_lot2_scan_valid(self):
        for wiz in self:
            _, wiz.lot2_scan_warning = (
                wiz._validate_start_scan(
                    wiz.lot2_id, wiz.lot2_scan, 2
                )
            )

    def _validate_start_scan(self, lot, scan_code,
                              lot_num):
        if not lot or not scan_code:
            return True, ''
        if not STAMP_REGEX.match(scan_code):
            return (False,
                    f'Lote {lot_num}: formato '
                    f'invalido — {scan_code}')
        if scan_code[:5] != lot.serial_prefix:
            return (False,
                    f'Lote {lot_num}: prefixo '
                    f'{scan_code[:5]} nao '
                    f'corresponde a {lot.serial_prefix}XXX')
        serial = self.env[
            'tobacco.stamp.serial'
        ].search([
            ('serial_number', '=', scan_code),
            ('lot_id', '=', lot.id),
        ], limit=1)
        if not serial:
            return (False,
                    f'Lote {lot_num}: serial '
                    f'{scan_code} nao encontrado')
        if serial.state != 'available':
            return (False,
                    f'Lote {lot_num}: serial '
                    f'{scan_code} nao disponivel '
                    f'(state: {serial.state})')
        suffix = int(scan_code[5:])
        if suffix > lot.current_suffix_end:
            return (False,
                    f'Lote {lot_num}: serial '
                    f'{scan_code} acima do disponivel '
                    f'(max: {lot.current_suffix_end})')
        return True, ''

    @api.constrains('lot1_id', 'lot2_id')
    def _check_lots_valid(self):
        for wiz in self:
            if (wiz.lot1_id and wiz.lot2_id
                    and wiz.lot1_id == wiz.lot2_id):
                raise ValidationError(
                    'Os dois lotes devem ser diferentes.'
                )
            if (wiz.lot1_id and wiz.lot2_id
                    and wiz.lot1_id.zone_id
                    != wiz.lot2_id.zone_id):
                raise ValidationError(
                    'Os dois lotes devem ser '
                    'da mesma zona fiscal.'
                )

    def action_confirm(self):
        self.ensure_one()
        ok1, w1 = self._validate_start_scan(
            self.lot1_id, self.lot1_scan, 1)
        ok2, w2 = self._validate_start_scan(
            self.lot2_id, self.lot2_scan, 2)
        if not ok1:
            raise UserError(w1)
        if not ok2:
            raise UserError(w2)
        if not self.lot1_scan_confirmed:
            raise UserError('Confirme o scan do Lote 1.')
        if not self.lot2_scan_confirmed:
            raise UserError('Confirme o scan do Lote 2.')

        for lot in [self.lot1_id, self.lot2_id]:
            lot.write({'lot_status': 'in_machine'})

        self.production_id.write({
            'stamp_lot_ids': [
                (4, self.lot1_id.id),
                (4, self.lot2_id.id),
            ],
        })
        self.production_id.message_post(
            body=(
                f'Producao iniciada. Lotes: '
                f'{self.lot1_id.incm_ref} '
                f'({self.lot1_scan}) + '
                f'{self.lot2_id.incm_ref} '
                f'({self.lot2_scan})'
            ),
        )
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'StampChain',
                'message': 'Producao iniciada. 2 lotes em maquina.',
                'type': 'success',
            },
        }
