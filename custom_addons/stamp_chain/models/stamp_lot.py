# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError


class StampLot(models.Model):
    _name = 'tobacco.stamp.lot'
    _description = 'Lote INCM de Estampilhas'
    _order = 'fifo_sequence asc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(
        string='Referencia Interna',
        required=True,
        copy=False,
        default=lambda self:
            self.env['ir.sequence'].next_by_code(
                'tobacco.stamp.lot'
            ),
    )
    incm_ref = fields.Char(
        string='Referencia INCM',
        required=True,
        tracking=True,
        help='Numero de referencia/guia da INCM',
    )
    zone_id = fields.Many2one(
        'tobacco.stamp.zone',
        string='Zona Fiscal',
        required=True,
        ondelete='restrict',
        tracking=True,
    )
    reception_date = fields.Date(
        string='Data de Recepcao',
        required=True,
        default=fields.Date.today,
    )
    qty_received = fields.Integer(
        string='Quantidade Recebida',
        required=True,
        help='Deve ser multiplo de 500',
    )
    qty_available = fields.Integer(
        string='Disponivel',
        compute='_compute_qty_available',
        store=True,
    )
    qty_used = fields.Integer(
        string='Utilizados',
        compute='_compute_qty_used',
        store=True,
    )
    qty_broken = fields.Integer(
        string='Quebras',
        compute='_compute_qty_broken',
        store=True,
    )
    serial_ids = fields.One2many(
        'tobacco.stamp.serial',
        'lot_id',
        string='Numeros de Serie',
    )
    edic_ref = fields.Char(
        string='Referencia eDIC (Codigo AT)',
        tracking=True,
    )
    eda_ref = fields.Char(
        string='Referencia e-DA (Codigo AT)',
        tracking=True,
    )
    # Many2many inverso definido em fiscal_document.py
    # Tabela: fiscal_doc_lot_rel
    # Esta coluna: lot_id — outra: doc_id
    fiscal_document_ids = fields.Many2many(
        'tobacco.fiscal.document',
        'fiscal_doc_lot_rel',
        'lot_id', 'doc_id',
        string='Documentos Fiscais',
    )
    warehouse_id = fields.Many2one(
        'stock.warehouse',
        string='Armazem Actual',
    )
    state = fields.Selection([
        ('draft', 'Rascunho'),
        ('received', 'Recebido'),
        ('in_use', 'Em Uso'),
        ('exhausted', 'Esgotado'),
    ], string='Estado',
       default='draft',
       tracking=True,
    )
    fifo_sequence = fields.Integer(
        string='Sequencia FIFO',
        help='Menor numero = lote mais antigo',
    )
    notes = fields.Text(string='Notas')

    @api.depends('serial_ids', 'serial_ids.state')
    def _compute_qty_available(self):
        for lot in self:
            lot.qty_available = len(
                lot.serial_ids.filtered(
                    lambda s: s.state == 'available'
                )
            )

    @api.depends('serial_ids', 'serial_ids.state')
    def _compute_qty_used(self):
        for lot in self:
            lot.qty_used = len(
                lot.serial_ids.filtered(
                    lambda s: s.state == 'used'
                )
            )

    @api.depends('serial_ids', 'serial_ids.state')
    def _compute_qty_broken(self):
        for lot in self:
            lot.qty_broken = len(
                lot.serial_ids.filtered(
                    lambda s: s.state == 'broken'
                )
            )

    @api.constrains('qty_received')
    def _check_qty_multiple_500(self):
        for lot in self:
            if lot.qty_received % 500 != 0:
                raise ValidationError(
                    'A quantidade recebida deve ser '
                    'multiplo de 500 '
                    '(1 lote = 500 estampilhas).'
                )

    @api.model
    def _get_next_fifo_sequence(self, zone_id):
        last = self.search(
            [('zone_id', '=', zone_id)],
            order='fifo_sequence desc',
            limit=1,
        )
        return (last.fifo_sequence + 1) if last else 1
