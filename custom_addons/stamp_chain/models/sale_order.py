# -*- coding: utf-8 -*-
from odoo import models, fields, api


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    stamp_zone_id = fields.Many2one(
        'tobacco.stamp.zone',
        string='Zona Fiscal',
        related='partner_id.stamp_zone_id',
        store=True,
        help='Herdado do cliente — '
             'define estampilha a usar',
    )
    stamp_qty_required = fields.Integer(
        string='Estampilhas Necessarias',
        compute='_compute_stamp_qty',
        store=True,
        help='Total de macos = total de estampilhas',
    )

    @api.depends('order_line', 'order_line.product_uom_qty')
    def _compute_stamp_qty(self):
        for order in self:
            order.stamp_qty_required = int(
                sum(order.order_line.mapped(
                    'product_uom_qty'
                ))
            )
