# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import (
    UserError, ValidationError
)


class AtCodeWizard(models.TransientModel):
    _name = 'tobacco.at.code.wizard'
    _description = 'Insercao de Codigo AT'

    fiscal_document_id = fields.Many2one(
        'tobacco.fiscal.document',
        string='Documento Fiscal',
        required=True,
        readonly=True,
    )
    document_type = fields.Char(readonly=True)
    at_code = fields.Char(
        string='Codigo AT',
        required=True,
    )
    confirmation = fields.Boolean(
        string='Confirmo que o codigo AT foi '
               'gerado pelo portal das Financas',
    )

    @api.constrains('at_code')
    def _check_at_code(self):
        for wiz in self:
            if len((wiz.at_code or '').strip()) < 5:
                raise ValidationError(
                    'O codigo AT parece invalido.'
                )

    def action_confirm(self):
        self.ensure_one()
        if not self.confirmation:
            raise UserError(
                'Confirme que o codigo foi '
                'gerado pelo portal AT.'
            )
        doc = self.fiscal_document_id
        doc.write({
            'at_code': self.at_code.strip(),
            'at_code_date': fields.Datetime.now(),
            'at_code_inserted_by': self.env.user.id,
            'state': 'at_approved',
        })
        doc._append_log(
            f'Codigo AT inserido: {self.at_code}'
        )
        for lot in doc.lot_ids:
            if doc.document_type == 'edic':
                lot.edic_ref = self.at_code.strip()
            else:
                lot.eda_ref = self.at_code.strip()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'StampChain',
                'message': (
                    'Codigo AT inserido. '
                    'Use "Criar Transferencia" '
                    'para mover EF -> A1.'
                ),
                'type': 'success',
            },
        }
