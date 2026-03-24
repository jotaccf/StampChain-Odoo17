# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError


class StampBreakdownWizard(models.TransientModel):
    _name = 'tobacco.stamp.breakdown.wizard'
    _description = 'Wizard Registo de Quebra'

    production_id = fields.Many2one(
        'mrp.production',
        string='Ordem de Producao',
        required=True,
    )
    zone_id = fields.Many2one(
        'tobacco.stamp.zone',
        string='Zona',
        related='production_id.stamp_zone_id',
        readonly=True,
    )
    serial_ids = fields.Many2many(
        'tobacco.stamp.serial',
        string='Estampilhas a Marcar como Quebra',
        domain="[('production_id', '=', production_id),"
               " ('state', '=', 'reserved')]",
    )
    breakdown_reason = fields.Selection([
        ('broken_during_application',
         'Danificada durante colagem'),
        ('bad_incm_print',
         'Ma impressao INCM'),
        ('handling_error',
         'Erro de manuseamento'),
        ('other', 'Outro motivo'),
    ], string='Motivo', required=True)
    description = fields.Text(
        string='Descricao',
    )
    photo = fields.Binary(
        string='Evidencia Fotografica',
        attachment=True,
    )
    photo_filename = fields.Char()

    @api.constrains('serial_ids')
    def _check_serials(self):
        for wiz in self:
            if not wiz.serial_ids:
                raise ValidationError(
                    'Seleccione pelo menos uma '
                    'estampilha para marcar como quebra.'
                )

    def action_confirm(self):
        self.ensure_one()

        breakdown = self.env[
            'tobacco.stamp.breakdown'
        ].create({
            'production_id': self.production_id.id,
            'serial_ids': [(6, 0, self.serial_ids.ids)],
            'breakdown_reason': self.breakdown_reason,
            'description': self.description,
            'photo': self.photo,
            'photo_filename': self.photo_filename,
        })

        self.serial_ids.write({
            'state': 'broken',
            'breakdown_id': breakdown.id,
        })

        zone = self.production_id.stamp_zone_id
        if zone:
            movement = self.env[
                'tobacco.stamp.movement'
            ].create({
                'zone_id': zone.id,
                'move_type': 'breakdown',
                'qty': len(self.serial_ids),
                'reference': breakdown.name,
                'notes': (
                    f'Quebra: {breakdown.name} — '
                    f'MO: {self.production_id.name}'
                ),
            })
            breakdown.movement_id = movement.id

        # Alerta se quebras > 5% do planeado
        prod = self.production_id
        if (prod.stamp_qty_broken >
                prod.stamp_qty_planned * 0.05):
            prod.message_post(
                body=(
                    f'ALERTA StampChain: '
                    f'Quebras de estampilhas '
                    f'acima de 5% na ordem '
                    f'{prod.name}. '
                    f'Total quebras: '
                    f'{prod.stamp_qty_broken}/'
                    f'{prod.stamp_qty_planned}'
                ),
                message_type='notification',
            )

        return {
            'type': 'ir.actions.act_window',
            'name': 'Quebra Registada',
            'res_model': 'tobacco.stamp.breakdown',
            'res_id': breakdown.id,
            'view_mode': 'form',
            'target': 'current',
        }
