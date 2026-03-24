# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError
import logging

_logger = logging.getLogger(__name__)


class StampRecovery(models.Model):
    _name = 'tobacco.stamp.recovery'
    _description = 'Recuperacao de Estampilha Quebrada'
    _order = 'date desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(
        string='Referencia',
        required=True,
        copy=False,
        default=lambda self:
            self.env['ir.sequence'].next_by_code(
                'tobacco.stamp.recovery'
            ),
    )
    serial_ids = fields.Many2many(
        'tobacco.stamp.serial',
        'stamp_recovery_serial_rel',
        'recovery_id',
        'serial_id',
        string='Estampilhas a Recuperar',
    )
    qty_to_recover = fields.Integer(
        string='Quantidade a Recuperar',
        compute='_compute_qty_to_recover',
        store=True,
    )
    zone_id = fields.Many2one(
        'tobacco.stamp.zone',
        string='Zona',
        compute='_compute_zone',
        store=True,
    )
    breakdown_id = fields.Many2one(
        'tobacco.stamp.breakdown',
        string='Quebra de Origem',
        help='Registo de quebra original',
    )
    inspection_notes = fields.Text(
        string='Notas de Inspeccao',
        help='Descreve o processo de verificacao '
             'manual realizado',
    )
    inspection_photo = fields.Binary(
        string='Foto de Inspeccao',
        attachment=True,
    )
    inspection_photo_filename = fields.Char()
    inspected_by = fields.Many2one(
        'res.users',
        string='Inspeccionado por',
        default=lambda self: self.env.user,
        readonly=True,
    )
    inspection_date = fields.Datetime(
        string='Data de Inspeccao',
        default=fields.Datetime.now,
        readonly=True,
    )
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
        ('draft', 'Rascunho'),
        ('submitted', 'Submetido para Aprovacao'),
        ('approved', 'Aprovado — Em Quarentena'),
        ('released', 'Libertado para Uso'),
        ('rejected', 'Rejeitado'),
    ], string='Estado',
       default='draft',
       tracking=True,
    )
    movement_id = fields.Many2one(
        'tobacco.stamp.movement',
        string='Movimento de Recuperacao',
        readonly=True,
    )
    date = fields.Datetime(
        string='Data',
        default=fields.Datetime.now,
        readonly=True,
    )

    @api.depends('serial_ids')
    def _compute_qty_to_recover(self):
        for rec in self:
            rec.qty_to_recover = len(rec.serial_ids)

    @api.depends('serial_ids', 'serial_ids.zone_id')
    def _compute_zone(self):
        for rec in self:
            zones = rec.serial_ids.mapped('zone_id')
            if len(zones) == 1:
                rec.zone_id = zones[0]
            else:
                rec.zone_id = False

    @api.constrains('serial_ids')
    def _check_same_zone(self):
        for rec in self:
            if not rec.serial_ids:
                continue
            zones = rec.serial_ids.mapped('zone_id')
            if len(set(zones.ids)) > 1:
                raise ValidationError(
                    'Todas as estampilhas devem '
                    'pertencer a mesma zona fiscal.'
                )

    def action_submit(self):
        self.ensure_one()
        if self.state != 'draft':
            raise UserError(
                'Apenas registos em rascunho '
                'podem ser submetidos.'
            )
        if not self.inspection_notes:
            raise UserError(
                'As notas de inspeccao sao '
                'obrigatorias antes de submeter.'
            )
        if not self.serial_ids:
            raise UserError(
                'Seleccione pelo menos uma '
                'estampilha para recuperar.'
            )
        not_broken = self.serial_ids.filtered(
            lambda s: s.state != 'broken'
        )
        if not_broken:
            raise ValidationError(
                'Apenas estampilhas com estado '
                '"Quebrado" podem ser submetidas '
                'para recuperacao.'
            )
        self.serial_ids.write({
            'state': 'quarantine',
            'recovery_request_id': self.id,
        })
        self.state = 'submitted'
        self._notify_managers()
        self.message_post(
            body=(
                f'Pedido de recuperacao submetido '
                f'por {self.env.user.name}. '
                f'{self.qty_to_recover} estampilha(s) '
                f'em quarentena aguardam aprovacao.'
            ),
            message_type='notification',
        )

    def action_approve(self):
        self.ensure_one()
        if not self.env.user.has_group(
            'stamp_chain.group_stamp_manager'
        ):
            raise UserError(
                'Apenas o Gestor StampChain pode '
                'aprovar recuperacoes de estampilhas.'
            )
        if self.state != 'submitted':
            raise UserError(
                'Apenas pedidos submetidos '
                'podem ser aprovados.'
            )
        self.write({
            'state': 'approved',
            'approved_by': self.env.user.id,
            'approval_date': fields.Datetime.now(),
        })
        self.message_post(
            body=(
                f'Recuperacao aprovada por '
                f'{self.env.user.name}. '
                f'Estampilhas em quarentena — '
                f'usar "Libertar para Uso" '
                f'quando prontas.'
            ),
            message_type='notification',
        )

    def action_release(self):
        self.ensure_one()
        if not self.env.user.has_group(
            'stamp_chain.group_stamp_manager'
        ):
            raise UserError(
                'Apenas o Gestor pode libertar '
                'estampilhas da quarentena.'
            )
        if self.state != 'approved':
            raise UserError(
                'Apenas pedidos aprovados '
                'podem ser libertados.'
            )
        self.serial_ids.write({
            'state': 'available',
            'recovery_date': fields.Datetime.now(),
            'recovery_approved_by': self.env.user.id,
        })
        movement = self.env[
            'tobacco.stamp.movement'
        ].create({
            'zone_id': self.zone_id.id,
            'move_type': 'recovery',
            'qty': self.qty_to_recover,
            'reference': self.name,
            'notes': (
                f'Recuperacao aprovada: '
                f'{self.name} — '
                f'Aprovado por: '
                f'{self.approved_by.name} — '
                f'Quebra original: '
                f'{self.breakdown_id.name or "N/A"}'
            ),
        })
        self.write({
            'state': 'released',
            'movement_id': movement.id,
        })
        self.message_post(
            body=(
                f'{self.qty_to_recover} '
                f'estampilha(s) libertadas para '
                f'uso. Movimento: {movement.id}'
            ),
            message_type='notification',
        )

    def action_reject(self):
        self.ensure_one()
        if not self.env.user.has_group(
            'stamp_chain.group_stamp_manager'
        ):
            raise UserError(
                'Apenas o Gestor pode rejeitar '
                'pedidos de recuperacao.'
            )
        if self.state not in ('submitted', 'approved'):
            raise UserError(
                'Estado invalido para rejeicao.'
            )
        self.serial_ids.write({
            'state': 'broken',
            'recovery_request_id': False,
        })
        self.state = 'rejected'
        self.message_post(
            body=(
                f'Recuperacao rejeitada por '
                f'{self.env.user.name}. '
                f'Estampilhas mantem estado '
                f'"Quebrado".'
            ),
            message_type='notification',
        )

    def _notify_managers(self):
        managers = self.env['res.users'].search([
            ('groups_id', 'in', [
                self.env.ref(
                    'stamp_chain.group_stamp_manager'
                ).id
            ])
        ])
        for manager in managers:
            self.message_post(
                body=(
                    f'Novo pedido de recuperacao: '
                    f'{self.name}. '
                    f'Zona: {self.zone_id.name}. '
                    f'Quantidade: {self.qty_to_recover}. '
                    f'Aguarda aprovacao.'
                ),
                message_type='notification',
                partner_ids=[manager.partner_id.id],
            )
