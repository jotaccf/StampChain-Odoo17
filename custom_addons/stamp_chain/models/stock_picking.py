# -*- coding: utf-8 -*-
from odoo import models, fields
import logging

_logger = logging.getLogger(__name__)


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    stamp_movement_ids = fields.One2many(
        'tobacco.stamp.movement',
        'picking_id',
        string='Movimentos de Estampilhas',
    )
    stamp_validated_at = fields.Datetime(
        string='Estampilhas Baixadas Em',
        readonly=True,
    )
    stamp_validated_by = fields.Many2one(
        'res.users',
        string='Baixado Por',
        readonly=True,
    )

    def button_validate(self):
        res = super().button_validate()
        for picking in self:
            if (picking.picking_type_code == 'outgoing'
                    and picking.state == 'done'):
                picking._process_stamp_usage()
        return res

    def _process_stamp_usage(self):
        self.ensure_one()
        sale = self.env['sale.order'].search(
            [('name', '=', self.origin)],
            limit=1,
        )
        if not sale or not sale.stamp_zone_id:
            return

        with self.env.cr.savepoint():
            try:
                serials = self.env[
                    'tobacco.stamp.serial'
                ].search([
                    ('sale_order_id', '=', sale.id),
                    ('state', '=', 'reserved'),
                ])
                if not serials:
                    _logger.warning(
                        'StampChain: Sem seriais '
                        'reservados para %s', self.name
                    )
                    return

                serials.write({
                    'state': 'used',
                    'picking_id': self.id,
                    'used_date': fields.Datetime.now(),
                })

                self.env[
                    'tobacco.stamp.movement'
                ].create({
                    'zone_id': sale.stamp_zone_id.id,
                    'move_type': 'out',
                    'qty': len(serials),
                    'reference': self.name,
                    'picking_id': self.id,
                    'notes': (
                        f'Expedicao validada: '
                        f'{self.name} — '
                        f'Encomenda: {sale.name}'
                    ),
                })

                self.write({
                    'stamp_validated_at':
                        fields.Datetime.now(),
                    'stamp_validated_by':
                        self.env.user.id,
                })

                sale.stamp_zone_id._send_stock_alert()

            except Exception as e:
                _logger.error(
                    'StampChain erro na baixa '
                    'de estampilhas: %s', e
                )
