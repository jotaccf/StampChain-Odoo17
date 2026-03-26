# -*- coding: utf-8 -*-
from odoo import models, fields


class ProductProduct(models.Model):
    _inherit = 'product.product'

    wisedat_id = fields.Integer(
        string='ID Wisedat',
        readonly=True,
        index=True,
        copy=False,
    )
    wisedat_parent_id = fields.Integer(
        string='ID Artigo Pai Wisedat',
        readonly=True,
        help='Referencia ao artigo pai no Wisedat '
             '(variantes cor/tamanho)',
    )
    wisedat_synced = fields.Boolean(
        string='Sincronizado Wisedat',
        default=False,
        readonly=True,
    )
    wisedat_sync_date = fields.Datetime(
        string='Data Sync Wisedat',
        readonly=True,
    )
    wisedat_variant_info = fields.Char(
        string='Variante (cor/tamanho)',
        readonly=True,
    )
    is_iec_product = fields.Boolean(
        string='Produto IEC (estampilhas)',
        default=False,
        help='Produto sujeito a IEC. Stock '
             'controlado por seriais no Odoo. '
             'Wisedat qty apenas comparativa.',
    )


class ProductCategory(models.Model):
    _inherit = 'product.category'

    wisedat_id = fields.Integer(
        string='ID Wisedat',
        readonly=True,
        index=True,
        copy=False,
    )
