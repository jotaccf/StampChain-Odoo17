# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import UserError


class MinStockWizard(models.TransientModel):
    _name = 'tobacco.min.stock.wizard'
    _description = 'Alterar Stock de Seguranca'

    zone_id = fields.Many2one(
        'tobacco.stamp.zone',
        string='Zona',
        required=True,
        readonly=True,
    )
    current_value = fields.Integer(
        string='Valor Actual',
        readonly=True,
    )
    new_value = fields.Integer(
        string='Novo Valor Minimo',
        required=True,
    )
    change_reason = fields.Text(
        string='Motivo da Alteracao',
        required=True,
        help='Obrigatorio — ficara registado '
             'no historico de auditoria',
    )

    @api.constrains('new_value')
    def _check_new_value(self):
        for wiz in self:
            if wiz.new_value < 0:
                raise UserError(
                    'O stock minimo nao pode '
                    'ser negativo.'
                )
            if wiz.new_value == wiz.current_value:
                raise UserError(
                    'O novo valor e igual '
                    'ao valor actual.'
                )

    def action_confirm(self):
        self.ensure_one()
        if not self.env.user.has_group(
            'stamp_chain.group_stamp_manager'
        ):
            raise UserError(
                'Apenas o Gestor StampChain '
                'pode alterar o stock minimo '
                'de seguranca.'
            )
        self.env[
            'tobacco.stamp.zone.history'
        ].create({
            'zone_id': self.zone_id.id,
            'previous_value': self.current_value,
            'new_value': self.new_value,
            'change_reason': self.change_reason,
        })
        self.zone_id.write({
            'min_stock_alert': self.new_value,
        })
        self.zone_id.message_post(
            body=(
                f'Stock de seguranca alterado '
                f'por {self.env.user.name}: '
                f'{self.current_value} -> '
                f'{self.new_value}. '
                f'Motivo: {self.change_reason}'
            ),
            message_type='notification',
            subtype_xmlid='mail.mt_comment',
        )
        self.zone_id._send_stock_alert()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'StampChain',
                'message': (
                    f'Stock minimo da zona '
                    f'{self.zone_id.name} '
                    f'actualizado para '
                    f'{self.new_value}.'
                ),
                'type': 'success',
            },
        }
