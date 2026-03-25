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

    # — Layout fisico do armazem —
    num_corridors = fields.Integer(
        string='Corredores',
        default=2,
        help='Nomeados A, B, C... (max 26)',
    )
    num_shelves = fields.Integer(
        string='Estantes por Corredor',
        default=4,
    )
    num_levels = fields.Integer(
        string='Niveis por Estante',
        default=3,
        help='L1 (baixo) primeiro — FIFO',
    )
    num_positions = fields.Integer(
        string='Posicoes por Nivel',
        default=2,
    )
    last_layout_date = fields.Datetime(
        string='Ultima Geracao Layout',
        readonly=True,
    )
    last_layout_user = fields.Many2one(
        'res.users',
        string='Gerado por',
        readonly=True,
    )
    location_count = fields.Integer(
        string='Localizacoes Geradas',
        compute='_compute_location_count',
        store=False,
    )

    def _compute_location_count(self):
        for rec in self:
            if rec.warehouse_id:
                rec.location_count = self.env[
                    'stock.location'
                ].search_count([
                    ('location_id', '=',
                     rec.warehouse_id.lot_stock_id.id),
                    ('usage', '=', 'internal'),
                    ('barcode', '!=', False),
                ])
            else:
                rec.location_count = 0

    def action_open_layout_wizard(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Layout — {self.warehouse_id.code}',
            'res_model': (
                'tobacco.warehouse.layout.wizard'
            ),
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_warehouse_config_id': self.id,
                'default_warehouse_id':
                    self.warehouse_id.id,
                'default_num_corridors':
                    self.num_corridors,
                'default_num_shelves':
                    self.num_shelves,
                'default_num_levels':
                    self.num_levels,
                'default_num_positions':
                    self.num_positions,
            },
        }

    @api.depends('warehouse_type')
    def _compute_is_fiscal(self):
        for rec in self:
            rec.is_fiscal_warehouse = (
                rec.warehouse_type == 'fiscal_warehouse'
            )
