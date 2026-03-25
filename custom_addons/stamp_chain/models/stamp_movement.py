# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import UserError


class StampMovement(models.Model):
    _name = 'tobacco.stamp.movement'
    _description = 'Conta Corrente de Estampilhas'
    _order = 'date desc, id desc'

    zone_id = fields.Many2one(
        'tobacco.stamp.zone',
        string='Zona',
        required=True,
        ondelete='restrict',
        index=True,
    )
    move_type = fields.Selection([
        ('in', 'Entrada (INCM)'),
        ('out', 'Saida (Expedicao)'),
        ('breakdown', 'Quebra'),
        ('recovery', 'Recuperacao'),
        ('recovery_found', 'Estampilha Encontrada'),
        ('adjust', 'Ajuste Manual'),
    ], string='Tipo', required=True)
    qty = fields.Integer(
        string='Quantidade',
        required=True,
    )
    balance_after = fields.Integer(
        string='Saldo Apos Movimento',
        readonly=True,
    )
    lot_id = fields.Many2one(
        'tobacco.stamp.lot',
        string='Lote INCM',
    )
    reference = fields.Char(
        string='Referencia',
        help='Documento de origem (SO/MO/Picking)',
    )
    picking_id = fields.Many2one(
        'stock.picking',
        string='Expedicao',
        ondelete='set null',
    )
    date = fields.Datetime(
        string='Data',
        required=True,
        default=fields.Datetime.now,
        readonly=True,
    )
    user_id = fields.Many2one(
        'res.users',
        string='Utilizador',
        default=lambda self: self.env.user,
        readonly=True,
    )
    notes = fields.Text(
        string='Observacoes',
        help='Obrigatorio para quebras e ajustes',
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            zone = self.env[
                'tobacco.stamp.zone'
            ].browse(vals['zone_id'])
            current_balance = zone.balance
            qty = vals.get('qty', 0)
            move_type = vals.get('move_type', '')
            if move_type in ('in', 'recovery', 'recovery_found'):
                vals['balance_after'] = (
                    current_balance + qty
                )
            else:
                vals['balance_after'] = (
                    current_balance - qty
                )
        return super().create(vals_list)

    def unlink(self):
        raise UserError(
            'Nao e permitido eliminar movimentos '
            'de estampilhas IEC. '
            'Utilize um ajuste manual se necessario.'
        )

    @api.constrains('qty')
    def _check_qty_positive(self):
        for move in self:
            if move.qty <= 0:
                raise UserError(
                    'A quantidade deve ser positiva.'
                )

    @api.constrains('notes', 'move_type')
    def _check_notes_required(self):
        for move in self:
            if (move.move_type in
                    ('breakdown', 'adjust')
                    and not move.notes):
                raise UserError(
                    'As observacoes sao obrigatorias '
                    'para quebras e ajustes manuais.'
                )
