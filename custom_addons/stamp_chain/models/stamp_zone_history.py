# -*- coding: utf-8 -*-
from odoo import models, fields


class StampZoneHistory(models.Model):
    _name = 'tobacco.stamp.zone.history'
    _description = 'Historico Stock de Seguranca'
    _order = 'date desc'

    zone_id = fields.Many2one(
        'tobacco.stamp.zone',
        string='Zona',
        required=True,
        ondelete='cascade',
    )
    previous_value = fields.Integer(
        string='Valor Anterior',
        required=True,
    )
    new_value = fields.Integer(
        string='Novo Valor',
        required=True,
    )
    change_reason = fields.Text(
        string='Motivo da Alteracao',
        required=True,
    )
    changed_by = fields.Many2one(
        'res.users',
        string='Alterado por',
        default=lambda self: self.env.user,
        readonly=True,
    )
    date = fields.Datetime(
        string='Data',
        default=fields.Datetime.now,
        readonly=True,
    )
