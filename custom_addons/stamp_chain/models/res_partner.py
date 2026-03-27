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
    wisedat_entity_type = fields.Selection([
        ('0001', 'Cliente Final'),
        ('0002', 'Revendedor'),
        ('0003', 'Grossista'),
        ('0004', 'Distribuicao'),
    ], string='Tipo Entidade Wisedat',
       readonly=True,
       index=True,
       help='Tipo de entidade no Wisedat. '
            'Obtido via GET /customers?id=X.',
    )
    wisedat_entity_type_checked = fields.Boolean(
        string='Tipo Entidade Verificado',
        default=False,
        readonly=True,
        help='True apos verificacao do entity_type '
             'via API (mesmo que vazio).',
    )
