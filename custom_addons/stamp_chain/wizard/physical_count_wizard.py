# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import UserError


class PhysicalCountWizard(models.TransientModel):
    _name = 'tobacco.stamp.physical.count.wizard'
    _description = 'Wizard Contagem Fisica'

    zone_id = fields.Many2one(
        'tobacco.stamp.zone',
        string='Zona',
        required=True,
        readonly=True,
    )
    stock_theoretical = fields.Integer(
        string='Stock Teorico (sistema)',
        readonly=True,
    )
    stock_real_auto = fields.Integer(
        string='Stock Real (automatico)',
        readonly=True,
    )
    qty_counted = fields.Integer(
        string='Contagem Fisica Real',
        required=True,
    )
    discrepancy_preview = fields.Integer(
        string='Discrepancia Prevista',
        compute='_compute_preview',
        store=False,
    )
    direction_preview = fields.Char(
        string='Sentido',
        compute='_compute_preview',
        store=False,
    )
    notes = fields.Text(string='Observacoes')
    has_discrepancy = fields.Boolean(
        string='Tem discrepancia',
        default=False,
    )

    @api.onchange('qty_counted')
    def _onchange_qty_counted(self):
        disc = self.stock_theoretical - self.qty_counted
        self.has_discrepancy = disc != 0

    @api.depends('qty_counted', 'stock_theoretical')
    def _compute_preview(self):
        for wiz in self:
            disc = (
                wiz.stock_theoretical - wiz.qty_counted
            )
            wiz.discrepancy_preview = disc
            if disc > 0:
                wiz.direction_preview = (
                    f'Faltam {disc} estampilhas'
                )
            elif disc < 0:
                wiz.direction_preview = (
                    f'Sobram {abs(disc)} estampilhas'
                )
            else:
                wiz.direction_preview = (
                    'Sem discrepancia'
                )

    def action_confirm(self):
        self.ensure_one()
        zone = self.zone_id
        theoretical = self.stock_theoretical
        disc = theoretical - self.qty_counted

        count = self.env[
            'tobacco.stamp.physical.count'
        ].create({
            'zone_id': zone.id,
            'qty_counted': self.qty_counted,
            'stock_theoretical_snapshot': theoretical,
            'stock_real_auto_snapshot':
                self.stock_real_auto,
            'discrepancy_snapshot': disc,
            'notes': self.notes,
        })

        zone.write({
            'last_physical_count': self.qty_counted,
            'last_physical_count_date':
                fields.Datetime.now(),
            'last_physical_count_user':
                self.env.user.id,
        })

        audit = None
        if disc != 0:
            audit = self.env[
                'tobacco.stamp.audit'
            ].create({
                'zone_id': zone.id,
                'stock_theoretical': theoretical,
                'stock_real': self.qty_counted,
                'stock_real_auto': self.stock_real_auto,
                'stock_real_manual': self.qty_counted,
                'discrepancy': disc,
                'discrepancy_direction': (
                    'missing' if disc > 0
                    else 'surplus'
                ),
                'audit_type': 'physical_count',
            })
            count.write({'audit_id': audit.id})

        msg = (
            f'Contagem fisica registada: '
            f'{self.qty_counted} estampilhas.'
        )
        if audit:
            msg += (
                f' Discrepancia detectada: '
                f'{disc:+d}. '
                f'Auditoria: {audit.name}'
            )
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'StampChain',
                'message': msg,
                'type': (
                    'warning' if disc != 0
                    else 'success'
                ),
            },
        }
