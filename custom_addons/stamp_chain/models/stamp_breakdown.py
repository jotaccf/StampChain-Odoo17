# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError


class StampBreakdown(models.Model):
    _name = 'tobacco.stamp.breakdown'
    _description = 'Registo de Quebra de Estampilha'
    _order = 'date desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(
        string='Referencia',
        required=True,
        copy=False,
        default=lambda self:
            self.env['ir.sequence'].next_by_code(
                'tobacco.stamp.breakdown'
            ),
    )
    production_id = fields.Many2one(
        'mrp.production',
        string='Ordem de Producao',
        required=True,
    )
    zone_id = fields.Many2one(
        'tobacco.stamp.zone',
        string='Zona',
        related='production_id.stamp_zone_id',
        store=True,
    )
    serial_ids = fields.Many2many(
        'tobacco.stamp.serial',
        string='Estampilhas Quebradas',
    )
    qty_broken = fields.Integer(
        string='Quantidade Quebrada',
        compute='_compute_qty_broken',
        store=True,
    )
    breakdown_reason = fields.Selection([
        ('broken_during_application',
         'Danificada durante colagem'),
        ('bad_incm_print',
         'Ma impressao INCM'),
        ('handling_error',
         'Erro de manuseamento'),
        ('other', 'Outro motivo'),
    ], string='Motivo da Quebra', required=True)
    description = fields.Text(
        string='Descricao Detalhada',
        help='Obrigatorio quando motivo = Outro',
    )
    photo = fields.Binary(
        string='Evidencia Fotografica',
        attachment=True,
    )
    photo_filename = fields.Char()
    date = fields.Datetime(
        string='Data',
        default=fields.Datetime.now,
        readonly=True,
    )
    user_id = fields.Many2one(
        'res.users',
        string='Operador',
        default=lambda self: self.env.user,
        readonly=True,
    )
    movement_id = fields.Many2one(
        'tobacco.stamp.movement',
        string='Movimento Conta Corrente',
        readonly=True,
    )

    @api.depends('serial_ids')
    def _compute_qty_broken(self):
        for rec in self:
            rec.qty_broken = len(rec.serial_ids)

    @api.constrains('description', 'breakdown_reason')
    def _check_description_required(self):
        for rec in self:
            if (rec.breakdown_reason == 'other'
                    and not rec.description):
                raise ValidationError(
                    'A descricao detalhada e '
                    'obrigatoria quando o motivo '
                    'e "Outro motivo".'
                )
