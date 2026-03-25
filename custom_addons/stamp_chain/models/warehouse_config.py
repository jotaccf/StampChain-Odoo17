# -*- coding: utf-8 -*-
from odoo import models, fields, api


class StampWarehouseConfig(models.Model):
    _name = 'tobacco.warehouse.config'
    _description = 'Mapeamento Armazem Odoo-Wisedat'
    _inherit = ['mail.thread']

    name = fields.Char(
        string='Nome',
        required=True,
    )
    warehouse_id = fields.Many2one(
        'stock.warehouse',
        string='Armazem Odoo',
        required=True,
        ondelete='restrict',
    )
    wisedat_warehouse_code = fields.Char(
        string='Codigo Wisedat',
        required=True,
        help='Codigo do armazem no Wisedat (EF, A1)',
    )
    warehouse_type = fields.Selection([
        ('fiscal_warehouse',
         'Entreposto Fiscal (EF)'),
        ('main_warehouse',
         'Armazem Principal (A1)'),
        ('other', 'Outro'),
    ], string='Tipo',
       required=True,
       tracking=True,
    )
    is_fiscal_warehouse = fields.Boolean(
        string='E Entreposto Fiscal',
        compute='_compute_is_fiscal',
        store=True,
    )
    requires_edic = fields.Boolean(
        string='Requer eDIC para saida',
        default=False,
    )
    destination_warehouse_id = fields.Many2one(
        'stock.warehouse',
        string='Armazem Destino apos eDIC',
    )
    wisedat_config_id = fields.Many2one(
        'tobacco.wisedat.config',
        string='Configuracao Wisedat',
        required=True,
    )
    active = fields.Boolean(default=True)

    @api.depends('warehouse_type')
    def _compute_is_fiscal(self):
        for rec in self:
            rec.is_fiscal_warehouse = (
                rec.warehouse_type == 'fiscal_warehouse'
            )
