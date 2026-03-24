# -*- coding: utf-8 -*-
from odoo import models, fields
from odoo.exceptions import UserError


class TobaccoXmlExport(models.Model):
    _name = 'tobacco.xml.export'
    _description = 'Exportacao XML AT/DGAIEC'
    _order = 'create_date desc'

    name = fields.Char(
        string='Referencia',
        required=True,
        default=lambda self:
            self.env['ir.sequence'].next_by_code(
                'tobacco.xml.export'
            ),
    )
    export_type = fields.Selection([
        ('saft_inventory', 'SAF-T Inventario'),
        ('stamp_declaration', 'Declaracao IEC'),
        ('stamp_map', 'Mapa de Series'),
        ('cius_pt', 'CIUS-PT'),
    ], string='Tipo de Exportacao', required=True)
    period_from = fields.Date(
        string='Data Inicio', required=True,
    )
    period_to = fields.Date(
        string='Data Fim', required=True,
    )
    zone_id = fields.Many2one(
        'tobacco.stamp.zone',
        string='Zona (opcional)',
    )
    state = fields.Selection([
        ('draft', 'Rascunho'),
        ('generated', 'Gerado'),
        ('validated', 'Validado'),
        ('submitted', 'Submetido'),
    ], default='draft')
    xml_file = fields.Binary(
        string='Ficheiro XML',
        readonly=True,
        attachment=True,
    )
    xml_filename = fields.Char(readonly=True)
    validation_errors = fields.Text(
        string='Erros de Validacao',
        readonly=True,
    )

    def action_generate(self):
        raise UserError(
            'Exportacao XML AT/DGAIEC sera '
            'activada na versao 2.0 do StampChain. '
            'Consultar documentacao DGAIEC para '
            'schemas XSD actualizados.'
        )
