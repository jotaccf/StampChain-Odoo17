# -*- coding: utf-8 -*-
from odoo import models, fields


class WisedatInvoice(models.Model):
    _name = 'tobacco.wisedat.invoice'
    _description = 'Factura Wisedat (leitura)'
    _order = 'date desc'

    wisedat_id = fields.Char(
        string='ID Wisedat',
        required=True,
        index=True,
    )
    document_number = fields.Char(
        string='Numero Documento',
    )
    date = fields.Date(
        string='Data',
    )
    customer_id = fields.Many2one(
        'res.partner',
        string='Cliente',
    )
    total = fields.Float(
        string='Total',
    )
    merchandise = fields.Float(
        string='Mercadoria',
    )
    taxes = fields.Float(
        string='Impostos',
    )
    currency = fields.Char(
        string='Moeda',
    )
    wisedat_config_id = fields.Many2one(
        'tobacco.wisedat.config',
        string='Config Wisedat',
    )
    raw_data = fields.Text(
        string='Dados Brutos (JSON)',
        readonly=True,
    )
