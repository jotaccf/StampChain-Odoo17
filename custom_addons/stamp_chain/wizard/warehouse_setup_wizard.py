# -*- coding: utf-8 -*-
from odoo import models, fields
from odoo.exceptions import UserError


class WarehouseSetupWizard(models.TransientModel):
    _name = 'tobacco.warehouse.setup.wizard'
    _description = 'Setup Inicial Armazens EF e A1'

    wisedat_config_id = fields.Many2one(
        'tobacco.wisedat.config',
        string='Configuracao Wisedat',
        required=True,
    )
    ef_warehouse_id = fields.Many2one(
        'stock.warehouse',
        string='Armazem EF (Entreposto Fiscal)',
    )
    a1_warehouse_id = fields.Many2one(
        'stock.warehouse',
        string='Armazem A1 (Principal)',
    )
    create_ef = fields.Boolean(
        string='Criar armazem EF se nao existir',
        default=True,
    )
    create_a1 = fields.Boolean(
        string='Criar armazem A1 se nao existir',
        default=True,
    )

    def action_setup(self):
        self.ensure_one()
        WhConfig = self.env['tobacco.warehouse.config']
        Warehouse = self.env['stock.warehouse']

        ef = self.ef_warehouse_id
        if not ef and self.create_ef:
            ef = Warehouse.create({
                'name': 'Entreposto Fiscal',
                'code': 'EF',
            })
        a1 = self.a1_warehouse_id
        if not a1 and self.create_a1:
            a1 = Warehouse.create({
                'name': 'Armazem Principal',
                'code': 'A1',
            })
        if not ef or not a1:
            raise UserError(
                'E necessario configurar ambos '
                'os armazens EF e A1.'
            )
        if not WhConfig.search([
            ('warehouse_id', '=', ef.id)
        ]):
            WhConfig.create({
                'name': 'Entreposto Fiscal — EF',
                'warehouse_id': ef.id,
                'wisedat_warehouse_code': 'EF',
                'warehouse_type': 'fiscal_warehouse',
                'requires_edic': True,
                'destination_warehouse_id': a1.id,
                'wisedat_config_id':
                    self.wisedat_config_id.id,
            })
        if not WhConfig.search([
            ('warehouse_id', '=', a1.id)
        ]):
            WhConfig.create({
                'name': 'Armazem Principal — A1',
                'warehouse_id': a1.id,
                'wisedat_warehouse_code': 'A1',
                'warehouse_type': 'main_warehouse',
                'requires_edic': False,
                'wisedat_config_id':
                    self.wisedat_config_id.id,
            })
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'StampChain',
                'message': 'Armazens EF e A1 configurados.',
                'type': 'success',
            },
        }
