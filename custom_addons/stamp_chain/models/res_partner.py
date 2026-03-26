# -*- coding: utf-8 -*-
from odoo import models, fields


class ResPartner(models.Model):
    _inherit = 'res.partner'

    stamp_zone_id = fields.Many2one(
        'tobacco.stamp.zone',
        string='Zona Fiscal de Estampilhas',
        help='Zona IEC do cliente — define que '
             'estampilha usar nas encomendas',
    )
    wisedat_id = fields.Integer(
        string='ID Wisedat',
        readonly=True,
        index=True,
        help='ID do cliente no sistema Wisedat',
    )
    wisedat_synced = fields.Boolean(
        string='Sincronizado Wisedat',
        default=False,
        readonly=True,
    )
    wisedat_sync_date = fields.Datetime(
        string='Data Ultima Sincronizacao',
        readonly=True,
    )
