# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError


class IncmReceptionWizard(models.TransientModel):
    _name = 'tobacco.incm.reception.wizard'
    _description = 'Wizard Recepcao Lote INCM'

    incm_ref = fields.Char(
        string='Referencia INCM',
        required=True,
    )
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
    qty_lots = fields.Integer(
        string='Numero de Lotes',
        required=True,
        default=1,
        help='1 lote = 500 estampilhas',
    )
    qty_total = fields.Integer(
        string='Total de Estampilhas',
        compute='_compute_qty_total',
        store=False,
    )
    notes = fields.Text(string='Observacoes')

    @api.depends('qty_lots')
    def _compute_qty_total(self):
        for wiz in self:
            wiz.qty_total = wiz.qty_lots * 500

    @api.constrains('qty_lots')
    def _check_qty_lots(self):
        for wiz in self:
            if wiz.qty_lots < 1:
                raise ValidationError(
                    'O numero de lotes deve '
                    'ser pelo menos 1.'
                )

    def action_confirm(self):
        self.ensure_one()
        StampLot = self.env['tobacco.stamp.lot']
        StampSerial = self.env['tobacco.stamp.serial']
        StampMovement = self.env[
            'tobacco.stamp.movement'
        ]

        fifo_seq = StampLot._get_next_fifo_sequence(
            self.zone_id.id
        )

        lot = StampLot.create({
            'incm_ref': self.incm_ref,
            'zone_id': self.zone_id.id,
            'reception_date': self.reception_date,
            'qty_received': self.qty_total,
            'state': 'received',
            'fifo_sequence': fifo_seq,
            'notes': self.notes,
        })

        zone_code = self.zone_id.code
        year = self.reception_date.year
        incm_clean = self.incm_ref.replace(' ', '-')
        serials = [
            {
                'serial_number': (
                    f"{zone_code}-{year}-"
                    f"{incm_clean}-{i:06d}"
                ),
                'lot_id': lot.id,
                'state': 'available',
            }
            for i in range(1, self.qty_total + 1)
        ]
        StampSerial.create(serials)

        StampMovement.create({
            'zone_id': self.zone_id.id,
            'move_type': 'in',
            'qty': self.qty_total,
            'lot_id': lot.id,
            'reference': lot.name,
            'notes': (
                f'Recepcao INCM: {self.incm_ref}'
            ),
        })

        return {
            'type': 'ir.actions.act_window',
            'name': 'Lote INCM Criado',
            'res_model': 'tobacco.stamp.lot',
            'res_id': lot.id,
            'view_mode': 'form',
            'target': 'current',
        }
