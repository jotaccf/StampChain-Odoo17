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
    # — Campos OCR (imutaveis apos recepcao R1) —
    first_serial_code = fields.Char(
        string='Codigo Inicial (scan)',
        readonly=True,
    )
    serial_prefix = fields.Char(
        string='Prefixo do Lote',
        readonly=True,
    )
    serial_suffix_start = fields.Integer(
        string='Sufixo Inicial (INCM)',
        readonly=True,
    )
    serial_suffix_end = fields.Integer(
        string='Sufixo Final (INCM)',
        readonly=True,
    )
    # — Campo computed (R2) —
    current_suffix_end = fields.Integer(
        string='Ultima Disponivel (sufixo)',
        compute='_compute_current_suffix_end',
        store=False,
    )
    # — Tracking producao —
    qty_consumed = fields.Integer(
        string='Consumidas em Producao',
        readonly=True,
        default=0,
    )
    lot_status = fields.Selection([
        ('reception', 'Em Armazem'),
        ('in_machine', 'Em Producao'),
        ('partial', 'Parcialmente Usado'),
        ('exhausted', 'Esgotado'),
    ], string='Estado Producao',
       default='reception',
       tracking=True,
    )
    production_lot_ids = fields.Many2many(
        'mrp.production',
        'stamp_lot_production_rel',
        'lot_id',
        'production_id',
        string='Ordens de Producao',
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

    @api.depends(
        'serial_ids',
        'serial_ids.state',
        'serial_ids.serial_number')
    def _compute_current_suffix_end(self):
        for lot in self:
            available = lot.serial_ids.filtered(
                lambda s: s.state == 'available'
            )
            if not available:
                lot.current_suffix_end = (
                    lot.serial_suffix_start - 1
                )
                continue
            suffixes = []
            for serial in available:
                code = serial.serial_number
                if (len(code) == 8
                        and code[:5].isalpha()
                        and code[5:].isdigit()):
                    suffixes.append(int(code[5:]))
            lot.current_suffix_end = (
                max(suffixes) if suffixes else 0
            )
