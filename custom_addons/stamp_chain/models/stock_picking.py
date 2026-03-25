# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import UserError
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
    wisedat_doc_id = fields.Char(
        string='ID Documento Wisedat',
        readonly=True,
    )
    is_ef_to_a1_transfer = fields.Boolean(
        string='Transferencia EF -> A1',
        compute='_compute_is_ef_transfer',
        store=True,
    )
    fiscal_document_id = fields.Many2one(
        'tobacco.fiscal.document',
        string='Documento Fiscal (eDIC/e-DA)',
        readonly=True,
    )

    @api.depends(
        'picking_type_id',
        'picking_type_id.code',
        'picking_type_id.warehouse_id')
    def _compute_is_ef_transfer(self):
        for picking in self:
            config = self.env[
                'tobacco.warehouse.config'
            ].search([
                ('warehouse_type', '=',
                 'fiscal_warehouse'),
            ], limit=1)
            picking.is_ef_to_a1_transfer = (
                picking.picking_type_id.code
                == 'internal'
                and bool(config)
                and picking.picking_type_id
                .warehouse_id.id
                == config.warehouse_id.id
            )

    def _check_ef_shipment_block(self):
        for picking in self:
            if picking.picking_type_id.code != 'outgoing':
                continue
            ef_config = self.env[
                'tobacco.warehouse.config'
            ].search([
                ('warehouse_type', '=',
                 'fiscal_warehouse'),
                ('warehouse_id', '=',
                 picking.picking_type_id
                 .warehouse_id.id),
            ], limit=1)
            if ef_config:
                raise UserError(
                    'Nao e possivel expedir '
                    'directamente do Entreposto '
                    'Fiscal (EF).\n'
                    'Realize a eDIC e transfira '
                    'para A1 primeiro.'
                )

    def button_validate(self):
        self._check_ef_shipment_block()
        res = super().button_validate()
        for picking in self:
            if (picking.picking_type_code == 'outgoing'
                    and picking.state == 'done'):
                picking._process_stamp_usage()
                config = self.env[
                    'tobacco.wisedat.config'
                ].search([], limit=1)
                if config and config.sync_invoices:
                    try:
                        config._create_wisedat_transport_guide(
                            picking.id
                        )
                    except Exception as e:
                        _logger.warning(
                            'Guia Wisedat falhou '
                            '(nao bloqueia): %s', e
                        )
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
