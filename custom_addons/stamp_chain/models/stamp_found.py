# -*- coding: utf-8 -*-
import re
from odoo import models, fields, api
from odoo.exceptions import (
    UserError, ValidationError
)

STAMP_REGEX = re.compile(r'^[A-Z]{5}\d{3}$')


class StampFound(models.Model):
    _name = 'tobacco.stamp.found'
    _description = 'Estampilha Encontrada'
    _order = 'date desc'
    _inherit = ['mail.thread']

    name = fields.Char(
        string='Referencia',
        required=True,
        copy=False,
        default=lambda self:
            self.env['ir.sequence'].next_by_code(
                'tobacco.stamp.found'
            ),
    )
    audit_id = fields.Many2one(
        'tobacco.stamp.audit',
        string='Auditoria de Origem',
        required=True,
        ondelete='restrict',
    )
    zone_id = fields.Many2one(
        'tobacco.stamp.zone',
        string='Zona',
        related='audit_id.zone_id',
        store=True,
    )
    serial_code = fields.Char(
        string='Codigo da Estampilha',
        required=True,
    )
    lot_id = fields.Many2one(
        'tobacco.stamp.lot',
        string='Lote INCM',
        compute='_compute_lot',
        store=True,
        readonly=True,
    )
    found_location = fields.Text(
        string='Local onde foi encontrada',
        required=True,
    )
    found_by = fields.Many2one(
        'res.users',
        string='Encontrada por',
        default=lambda self: self.env.user,
        readonly=True,
    )
    date = fields.Datetime(
        string='Data',
        default=fields.Datetime.now,
        readonly=True,
    )
    photo = fields.Binary(
        string='Foto',
        attachment=True,
    )
    photo_filename = fields.Char()
    approval_notes = fields.Text(
        string='Notas de Aprovacao',
    )
    approved_by = fields.Many2one(
        'res.users',
        string='Aprovado por',
        readonly=True,
    )
    approval_date = fields.Datetime(
        string='Data de Aprovacao',
        readonly=True,
    )
    state = fields.Selection([
        ('pending', 'Aguarda Aprovacao'),
        ('approved', 'Aprovado'),
        ('rejected', 'Rejeitado'),
    ], string='Estado',
       default='pending',
       tracking=True,
    )
    serial_id = fields.Many2one(
        'tobacco.stamp.serial',
        string='Serial Criado',
        readonly=True,
    )

    @api.depends('serial_code')
    def _compute_lot(self):
        for rec in self:
            code = rec.serial_code or ''
            if STAMP_REGEX.match(code):
                prefix = code[:5]
                lot = self.env[
                    'tobacco.stamp.lot'
                ].search([
                    ('serial_prefix', '=', prefix)
                ], limit=1)
                rec.lot_id = lot or False
            else:
                rec.lot_id = False

    @api.constrains('serial_code')
    def _check_format(self):
        for rec in self:
            if not STAMP_REGEX.match(
                rec.serial_code or ''
            ):
                raise ValidationError(
                    f'Codigo invalido: '
                    f'"{rec.serial_code}". '
                    f'Formato: ZZAYC000'
                )

    def action_approve(self):
        self.ensure_one()
        if not self.env.user.has_group(
            'stamp_chain.group_stamp_manager'
        ):
            raise UserError(
                'Apenas o Gestor pode aprovar '
                'estampilhas encontradas.'
            )
        if self.state != 'pending':
            raise UserError(
                'Estado invalido para aprovacao.'
            )
        existing = self.env[
            'tobacco.stamp.serial'
        ].search([
            ('serial_number', '=', self.serial_code)
        ], limit=1)
        if existing:
            raise UserError(
                f'Serial {self.serial_code} '
                f'ja existe com estado: '
                f'{existing.state}.'
            )
        if not self.lot_id:
            raise UserError(
                f'Nao foi possivel identificar '
                f'o lote INCM para o codigo '
                f'{self.serial_code}. '
                f'O prefixo nao corresponde a '
                f'nenhum lote registado.'
            )
        serial = self.env[
            'tobacco.stamp.serial'
        ].create({
            'serial_number': self.serial_code,
            'lot_id': self.lot_id.id,
            'state': 'available',
        })
        self.env[
            'tobacco.stamp.movement'
        ].create({
            'zone_id': self.zone_id.id,
            'move_type': 'recovery_found',
            'qty': 1,
            'reference': self.name,
            'notes': (
                f'Estampilha encontrada: '
                f'{self.serial_code}. '
                f'Auditoria: {self.audit_id.name}. '
                f'Local: {self.found_location}'
            ),
        })
        self.write({
            'state': 'approved',
            'approved_by': self.env.user.id,
            'approval_date': fields.Datetime.now(),
            'serial_id': serial.id,
        })
        self.message_post(
            body=(
                f'Estampilha {self.serial_code} '
                f'aprovada por {self.env.user.name}.'
            ),
        )

    def action_reject(self):
        self.ensure_one()
        if not self.env.user.has_group(
            'stamp_chain.group_stamp_manager'
        ):
            raise UserError(
                'Apenas o Gestor pode rejeitar.'
            )
        if self.state != 'pending':
            raise UserError(
                'Estado invalido para rejeicao.'
            )
        self.write({'state': 'rejected'})
        self.message_post(
            body=(
                f'Rejeitado por '
                f'{self.env.user.name}.'
            ),
        )
