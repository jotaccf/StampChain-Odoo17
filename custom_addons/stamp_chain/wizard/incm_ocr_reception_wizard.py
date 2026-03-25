# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import UserError
import re
import logging

_logger = logging.getLogger(__name__)

STAMP_REGEX = re.compile(r'^[A-Z]{5}\d{3}$')


class IncmOcrReceptionWizard(models.TransientModel):
    _name = 'tobacco.incm.ocr.reception.wizard'
    _description = 'Recepcao INCM com OCR'

    zone_id = fields.Many2one(
        'tobacco.stamp.zone',
        string='Zona Fiscal',
        required=True,
    )
    reception_date = fields.Date(
        string='Data de Recepcao',
        required=True,
        default=fields.Date.today,
    )
    incm_ref = fields.Char(
        string='Referencia INCM',
        required=True,
    )
    first_serial_ocr = fields.Char(
        string='Codigo da 1a Estampilha',
    )
    ocr_confirmed = fields.Boolean(
        string='Codigo confirmado',
        default=False,
    )

    # Previa (computed store=False)
    serial_prefix = fields.Char(
        compute='_compute_preview',
        store=False,
    )
    serial_suffix_start = fields.Integer(
        compute='_compute_preview',
        store=False,
    )
    serial_suffix_end_preview = fields.Integer(
        compute='_compute_preview',
        store=False,
    )
    last_serial_preview = fields.Char(
        compute='_compute_preview',
        store=False,
    )
    qty_total = fields.Integer(
        compute='_compute_preview',
        store=False,
    )
    # Boolean regular para invisible (R6)
    has_valid_code = fields.Boolean(
        string='Codigo valido',
        default=False,
    )

    @api.onchange('first_serial_ocr')
    def _onchange_check_valid_code(self):
        self.has_valid_code = bool(
            STAMP_REGEX.match(
                self.first_serial_ocr or ''
            )
        )

    @api.depends('first_serial_ocr')
    def _compute_preview(self):
        for wiz in self:
            code = wiz.first_serial_ocr or ''
            if STAMP_REGEX.match(code):
                prefix = code[:5]
                suffix = int(code[5:])
                wiz.serial_prefix = prefix
                wiz.serial_suffix_start = suffix
                wiz.serial_suffix_end_preview = (
                    suffix + 499
                )
                wiz.last_serial_preview = (
                    f'{prefix}{suffix + 499:03d}'
                )
                wiz.qty_total = 500
            else:
                wiz.serial_prefix = ''
                wiz.serial_suffix_start = 0
                wiz.serial_suffix_end_preview = 0
                wiz.last_serial_preview = ''
                wiz.qty_total = 0

    def _check_duplicate_in_confirm(self):
        code = self.first_serial_ocr or ''
        if not code:
            return
        existing = self.env[
            'tobacco.stamp.serial'
        ].search([
            ('serial_number', '=', code)
        ], limit=1)
        if existing:
            raise UserError(
                f'A estampilha {code} ja '
                f'existe no sistema.'
            )
        if STAMP_REGEX.match(code):
            prefix = code[:5]
            existing_lot = self.env[
                'tobacco.stamp.lot'
            ].search([
                ('serial_prefix', '=', prefix),
                ('zone_id', '=', self.zone_id.id),
            ], limit=1)
            if existing_lot:
                raise UserError(
                    f'Ja existe lote com prefixo '
                    f'{prefix} nesta zona: '
                    f'{existing_lot.incm_ref}.'
                )

    @api.onchange('first_serial_ocr')
    def _onchange_serial_warn_duplicate(self):
        code = self.first_serial_ocr or ''
        if not STAMP_REGEX.match(code):
            return
        existing = self.env[
            'tobacco.stamp.serial'
        ].search([
            ('serial_number', '=', code)
        ], limit=1)
        if existing:
            return {
                'warning': {
                    'title': 'Atencao',
                    'message': (
                        f'O codigo {code} ja '
                        f'existe no sistema.'
                    ),
                },
            }

    def action_confirm(self):
        self.ensure_one()
        if not self.first_serial_ocr:
            raise UserError(
                'Capture ou introduza o codigo.'
            )
        if not self.ocr_confirmed:
            raise UserError(
                'Confirme o codigo antes de avancar.'
            )
        if not STAMP_REGEX.match(
            self.first_serial_ocr
        ):
            raise UserError(
                'Formato invalido. Esperado: ZZAYC000'
            )
        self._check_duplicate_in_confirm()

        prefix = self.first_serial_ocr[:5]
        suffix_start = int(self.first_serial_ocr[5:])
        suffix_end = suffix_start + 499
        qty = 500

        fifo_seq = self.env[
            'tobacco.stamp.lot'
        ]._get_next_fifo_sequence(self.zone_id.id)

        lot = self.env['tobacco.stamp.lot'].create({
            'incm_ref': self.incm_ref,
            'zone_id': self.zone_id.id,
            'reception_date': self.reception_date,
            'qty_received': qty,
            'state': 'received',
            'fifo_sequence': fifo_seq,
            'first_serial_code': self.first_serial_ocr,
            'serial_prefix': prefix,
            'serial_suffix_start': suffix_start,
            'serial_suffix_end': suffix_end,
            'lot_status': 'reception',
        })

        ef_wh = self.env[
            'tobacco.warehouse.config'
        ].search([
            ('warehouse_type', '=', 'fiscal_warehouse')
        ], limit=1).warehouse_id

        serials = [
            {
                'serial_number': (
                    f'{prefix}{suffix_start + i:03d}'
                ),
                'lot_id': lot.id,
                'state': 'available',
                'current_warehouse_id': (
                    ef_wh.id if ef_wh else False
                ),
            }
            for i in range(qty)
        ]
        self.env['tobacco.stamp.serial'].create(serials)

        self.env['tobacco.stamp.movement'].create({
            'zone_id': self.zone_id.id,
            'move_type': 'in',
            'qty': qty,
            'lot_id': lot.id,
            'reference': lot.name,
            'notes': (
                f'Recepcao OCR: '
                f'{self.first_serial_ocr} -> '
                f'{prefix}{suffix_end:03d}. '
                f'INCM: {self.incm_ref}'
            ),
        })

        _logger.info(
            'StampChain: Lote %s criado. '
            '%d seriais: %s%03d-%s%03d',
            lot.name, qty,
            prefix, suffix_start,
            prefix, suffix_end
        )

        return {
            'type': 'ir.actions.act_window',
            'name': 'Lote INCM Criado',
            'res_model': 'tobacco.stamp.lot',
            'res_id': lot.id,
            'view_mode': 'form',
            'target': 'current',
        }
