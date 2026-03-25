# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import UserError


class MrpProduction(models.Model):
    _inherit = 'mrp.production'

    stamp_zone_id = fields.Many2one(
        'tobacco.stamp.zone',
        string='Zona de Estampilha',
        compute='_compute_stamp_zone',
        store=True,
        help='Herdado da encomenda do cliente',
    )
    stamp_serial_ids = fields.Many2many(
        'tobacco.stamp.serial',
        string='Estampilhas Reservadas',
    )
    # M2M inverso em stamp_lot (lot_id, production_id)
    stamp_lot_ids = fields.Many2many(
        'tobacco.stamp.lot',
        'stamp_lot_production_rel',
        'production_id',
        'lot_id',
        string='Lotes INCM em Producao',
    )
    stamp_qty_planned = fields.Integer(
        string='Estampilhas Planeadas',
        compute='_compute_stamp_qty_planned',
        store=True,
    )
    stamp_qty_used = fields.Integer(
        string='Estampilhas Utilizadas',
        compute='_compute_stamp_qty_used',
        store=True,
    )
    stamp_qty_broken = fields.Integer(
        string='Estampilhas Quebradas',
        compute='_compute_stamp_qty_broken',
        store=True,
    )
    stamp_status = fields.Selection([
        ('pending', 'Pendente'),
        ('reserved', 'Reservado'),
        ('in_progress', 'Em Producao'),
        ('completed', 'Concluido'),
    ], string='Estado Estampilhas',
       default='pending',
    )

    @api.depends('origin')
    def _compute_stamp_zone(self):
        for prod in self:
            zone = False
            if prod.origin:
                sale = self.env['sale.order'].search(
                    [('name', '=', prod.origin)],
                    limit=1,
                )
                if sale and sale.partner_id.stamp_zone_id:
                    zone = sale.partner_id.stamp_zone_id.id
            prod.stamp_zone_id = zone

    @api.depends('product_qty')
    def _compute_stamp_qty_planned(self):
        for prod in self:
            prod.stamp_qty_planned = int(
                prod.product_qty
            )

    @api.depends('stamp_serial_ids',
                 'stamp_serial_ids.state')
    def _compute_stamp_qty_used(self):
        for prod in self:
            prod.stamp_qty_used = len(
                prod.stamp_serial_ids.filtered(
                    lambda s: s.state == 'used'
                )
            )

    @api.depends('stamp_serial_ids',
                 'stamp_serial_ids.state')
    def _compute_stamp_qty_broken(self):
        for prod in self:
            prod.stamp_qty_broken = len(
                prod.stamp_serial_ids.filtered(
                    lambda s: s.state == 'broken'
                )
            )

    def _reserve_stamps_fifo(self):
        self.ensure_one()
        if not self.stamp_zone_id:
            raise UserError(
                'Nao foi possivel determinar a zona '
                'de estampilha. Verifique se a '
                'encomenda de origem tem um cliente '
                'com zona fiscal definida.'
            )
        StampSerial = self.env['tobacco.stamp.serial']
        StampLot = self.env['tobacco.stamp.lot']

        lots = StampLot.search([
            ('zone_id', '=', self.stamp_zone_id.id),
            ('state', 'in', ('received', 'in_use')),
            ('qty_available', '>', 0),
        ], order='fifo_sequence asc')

        qty_needed = self.stamp_qty_planned
        serials_to_reserve = self.env[
            'tobacco.stamp.serial'
        ]

        for lot in lots:
            if qty_needed <= 0:
                break
            available = StampSerial.search([
                ('lot_id', '=', lot.id),
                ('state', '=', 'available'),
            ], order='serial_number asc',
               limit=qty_needed)
            serials_to_reserve |= available
            qty_needed -= len(available)

        if qty_needed > 0:
            raise UserError(
                f'Estampilhas insuficientes na zona '
                f'{self.stamp_zone_id.name}. '
                f'Faltam {qty_needed} estampilhas. '
                f'Efectue novo pedido INCM.'
            )

        serials_to_reserve.write({
            'state': 'reserved',
            'production_id': self.id,
        })
        self.stamp_serial_ids = serials_to_reserve
        self.stamp_status = 'reserved'

    def action_confirm(self):
        res = super().action_confirm()
        for prod in self:
            if prod.stamp_zone_id:
                prod._reserve_stamps_fifo()
        return res
