# -*- coding: utf-8 -*-
from odoo import models, fields, api


class WisedatSeries(models.Model):
    _name = 'tobacco.wisedat.series'
    _description = 'Serie Documental Wisedat'
    _order = 'wisedat_id'
    _rec_name = 'display_name'

    wisedat_id = fields.Char(
        string='ID Wisedat',
        required=True,
        index=True,
        copy=False,
    )
    name = fields.Char(
        string='Codigo da Serie',
        required=True,
        help='Codigo/nome da serie no Wisedat',
    )
    description = fields.Char(
        string='Descricao',
    )
    is_active = fields.Boolean(
        string='Activa no Wisedat',
        default=True,
        help='Indica se a serie esta activa no '
             'Wisedat. Actualizado via sync.',
    )
    wisedat_config_id = fields.Many2one(
        'tobacco.wisedat.config',
        string='Configuracao Wisedat',
        required=True,
        ondelete='cascade',
        index=True,
    )
    last_sync_date = fields.Datetime(
        string='Ultima Sincronizacao',
        readonly=True,
    )
    display_name = fields.Char(
        string='Nome',
        compute='_compute_display_name',
        store=True,
    )

    _sql_constraints = [
        ('wisedat_id_config_uniq',
         'UNIQUE(wisedat_id, wisedat_config_id)',
         'Ja existe uma serie com este ID Wisedat '
         'nesta configuracao.'),
    ]

    @api.depends('name', 'description', 'wisedat_id')
    def _compute_display_name(self):
        for rec in self:
            parts = []
            if rec.name:
                parts.append(rec.name)
            if rec.description:
                parts.append(
                    f'({rec.description})'
                )
            rec.display_name = (
                ' '.join(parts)
                if parts
                else f'Serie #{rec.wisedat_id}'
            )
