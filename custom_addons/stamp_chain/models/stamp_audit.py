# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import UserError


class StampAudit(models.Model):
    _name = 'tobacco.stamp.audit'
    _description = 'Registo de Auditoria de Discrepancia'
    _order = 'date desc'
    _inherit = ['mail.thread']

    name = fields.Char(
        string='Referencia',
        required=True,
        copy=False,
        default=lambda self:
            self.env['ir.sequence'].next_by_code(
                'tobacco.stamp.audit'
            ),
    )
    zone_id = fields.Many2one(
        'tobacco.stamp.zone',
        string='Zona IEC',
        required=True,
        ondelete='restrict',
    )
    date = fields.Datetime(
        string='Data',
        default=fields.Datetime.now,
        readonly=True,
    )
    stock_theoretical = fields.Integer(
        string='Stock Teorico',
        readonly=True,
    )
    stock_real = fields.Integer(
        string='Stock Real',
        readonly=True,
    )
    stock_real_auto = fields.Integer(
        string='Stock Real (automatico)',
        readonly=True,
    )
    stock_real_manual = fields.Integer(
        string='Stock Real (manual)',
        readonly=True,
        default=0,
    )
    discrepancy = fields.Integer(
        string='Discrepancia',
        readonly=True,
    )
    discrepancy_direction = fields.Selection([
        ('missing', 'Faltam Estampilhas'),
        ('surplus', 'Sobram Estampilhas'),
    ], string='Sentido',
       readonly=True,
    )
    audit_type = fields.Selection([
        ('production_end', 'Fim de Producao (automatico)'),
        ('physical_count', 'Contagem Fisica'),
        ('manual', 'Manual'),
    ], string='Tipo',
       required=True,
       default='manual',
    )
    production_id = fields.Many2one(
        'mrp.production',
        string='Ordem de Producao',
        readonly=True,
    )
    justification = fields.Text(
        string='Justificacao',
    )
    justified_by = fields.Many2one(
        'res.users',
        string='Justificado por',
        readonly=True,
    )
    justified_date = fields.Datetime(
        string='Data Justificacao',
        readonly=True,
    )
    is_justified = fields.Boolean(
        string='Justificado',
        default=False,
        readonly=True,
    )
    state = fields.Selection([
        ('open', 'Aberto'),
        ('justified', 'Justificado'),
    ], string='Estado',
       default='open',
       tracking=True,
    )
    found_ids = fields.One2many(
        'tobacco.stamp.found',
        'audit_id',
        string='Estampilhas Encontradas',
    )
    qty_found = fields.Integer(
        string='Encontradas',
        compute='_compute_qty_found',
        store=True,
    )
    net_discrepancy = fields.Integer(
        string='Discrepancia Liquida',
        compute='_compute_qty_found',
        store=True,
    )

    @api.depends('found_ids', 'found_ids.state')
    def _compute_qty_found(self):
        for audit in self:
            approved = len(
                audit.found_ids.filtered(
                    lambda r: r.state == 'approved'
                )
            )
            audit.qty_found = approved
            audit.net_discrepancy = (
                audit.discrepancy - approved
            )

    def action_justify(self):
        self.ensure_one()
        if not self.justification:
            raise UserError(
                'Introduza a justificacao '
                'antes de confirmar.'
            )
        self.write({
            'is_justified': True,
            'justified_by': self.env.user.id,
            'justified_date': fields.Datetime.now(),
            'state': 'justified',
        })
        self.message_post(
            body=(
                f'Discrepancia justificada '
                f'por {self.env.user.name}: '
                f'{self.justification}'
            ),
        )

    def action_add_found_stamp(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Registar Estampilha Encontrada',
            'res_model': 'tobacco.stamp.found',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_audit_id': self.id,
                'default_zone_id': self.zone_id.id,
            },
        }

    def unlink(self):
        raise UserError(
            'Os registos de auditoria sao '
            'imutaveis e nao podem ser '
            'eliminados. (R1)'
        )
