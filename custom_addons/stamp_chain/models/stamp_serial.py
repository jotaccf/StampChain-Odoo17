# -*- coding: utf-8 -*-
from odoo import models, fields


class StampSerial(models.Model):
    _name = 'tobacco.stamp.serial'
    _description = 'Numero de Serie de Estampilha'
    _order = 'serial_number asc'

    serial_number = fields.Char(
        string='Numero de Serie',
        required=True,
        copy=False,
        index=True,
        help='Formato: PT_C-2026-INCM-REF-NNNNNN',
    )
    lot_id = fields.Many2one(
        'tobacco.stamp.lot',
        string='Lote INCM',
        required=True,
        ondelete='restrict',
        index=True,
    )
    zone_id = fields.Many2one(
        'tobacco.stamp.zone',
        string='Zona',
        related='lot_id.zone_id',
        store=True,
        index=True,
    )
    state = fields.Selection([
        ('available', 'Disponivel'),
        ('reserved', 'Reservado'),
        ('used', 'Utilizado'),
        ('broken', 'Quebrado'),
        ('quarantine', 'Quarentena'),
    ], string='Estado',
       default='available',
       required=True,
       index=True,
       tracking=True,
    )
    production_id = fields.Many2one(
        'mrp.production',
        string='Ordem de Producao',
        ondelete='set null',
    )
    sale_order_id = fields.Many2one(
        'sale.order',
        string='Encomenda de Venda',
        ondelete='set null',
    )
    picking_id = fields.Many2one(
        'stock.picking',
        string='Expedicao',
        ondelete='set null',
    )
    used_date = fields.Datetime(
        string='Data de Utilizacao',
        help='Preenchido automaticamente na expedicao',
    )
    breakdown_id = fields.Many2one(
        'tobacco.stamp.breakdown',
        string='Referencia de Quebra',
        ondelete='set null',
    )
    recovery_request_id = fields.Many2one(
        'tobacco.stamp.recovery',
        string='Pedido de Recuperacao',
        ondelete='set null',
    )
    recovery_date = fields.Datetime(
        string='Data de Recuperacao',
        readonly=True,
    )
    recovery_approved_by = fields.Many2one(
        'res.users',
        string='Aprovado por',
        readonly=True,
    )

    _sql_constraints = [
        (
            'serial_number_unique',
            'UNIQUE(serial_number)',
            'O numero de serie deve ser unico!'
        )
    ]
