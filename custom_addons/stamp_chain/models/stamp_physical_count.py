# -*- coding: utf-8 -*-
from odoo import models, fields


class StampPhysicalCount(models.Model):
    _name = 'tobacco.stamp.physical.count'
    _description = 'Contagem Fisica'
    _order = 'date desc'

    zone_id = fields.Many2one(
        'tobacco.stamp.zone',
        string='Zona',
        required=True,
        ondelete='restrict',
    )
    date = fields.Datetime(
        string='Data',
        default=fields.Datetime.now,
        readonly=True,
    )
    counted_by = fields.Many2one(
        'res.users',
        string='Contado por',
        default=lambda self: self.env.user,
        readonly=True,
    )
    qty_counted = fields.Integer(
        string='Total Contado Fisicamente',
        required=True,
    )
    stock_theoretical_snapshot = fields.Integer(
        string='Stock Teorico no Momento',
        readonly=True,
    )
    stock_real_auto_snapshot = fields.Integer(
        string='Stock Real Auto no Momento',
        readonly=True,
    )
    discrepancy_snapshot = fields.Integer(
        string='Discrepancia no Momento',
        readonly=True,
    )
    notes = fields.Text(string='Observacoes')
    audit_id = fields.Many2one(
        'tobacco.stamp.audit',
        string='Auditoria Gerada',
        readonly=True,
    )
