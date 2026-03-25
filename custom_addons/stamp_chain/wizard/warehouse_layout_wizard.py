# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import (
    UserError, ValidationError
)


class WarehouseLayoutWizard(models.TransientModel):
    _name = 'tobacco.warehouse.layout.wizard'
    _description = 'Configuracao Layout Armazem'

    warehouse_config_id = fields.Many2one(
        'tobacco.warehouse.config',
        string='Configuracao Armazem',
        readonly=True,
    )
    warehouse_id = fields.Many2one(
        'stock.warehouse',
        string='Armazem',
        required=True,
    )
    num_corridors = fields.Integer(
        string='Numero de Corredores',
        required=True,
        default=2,
        help='Corredores nomeados A, B, C...',
    )
    num_shelves = fields.Integer(
        string='Estantes por Corredor',
        required=True,
        default=4,
    )
    num_levels = fields.Integer(
        string='Niveis por Estante',
        required=True,
        default=3,
        help='L1 (baixo) a L3 (cima). '
             'FIFO: L1 primeiro.',
    )
    num_positions = fields.Integer(
        string='Posicoes por Nivel',
        required=True,
        default=2,
    )
    total_locations = fields.Integer(
        string='Total de Localizacoes',
        compute='_compute_total',
        store=False,
    )
    preview_text = fields.Text(
        string='Preview',
        compute='_compute_preview',
        store=False,
    )
    existing_count = fields.Integer(
        string='Localizacoes ja existentes',
        compute='_compute_existing',
        store=False,
    )

    @api.onchange('warehouse_id')
    def _onchange_warehouse_id(self):
        """Carrega defaults do warehouse_config
        quando o operador selecciona armazem."""
        if not self.warehouse_id:
            return
        config = self.env[
            'tobacco.warehouse.config'
        ].search([
            ('warehouse_id', '=',
             self.warehouse_id.id),
        ], limit=1)
        if config:
            self.warehouse_config_id = config.id
            self.num_corridors = (
                config.num_corridors or 2
            )
            self.num_shelves = (
                config.num_shelves or 4
            )
            self.num_levels = (
                config.num_levels or 3
            )
            self.num_positions = (
                config.num_positions or 2
            )

    @api.constrains(
        'num_corridors', 'num_shelves',
        'num_levels', 'num_positions',
    )
    def _check_positive(self):
        for wiz in self:
            for field_name, label in [
                ('num_corridors', 'Corredores'),
                ('num_shelves', 'Estantes'),
                ('num_levels', 'Niveis'),
                ('num_positions', 'Posicoes'),
            ]:
                if getattr(wiz, field_name) < 1:
                    raise ValidationError(
                        f'{label} deve ser >= 1.'
                    )
            if wiz.num_corridors > 26:
                raise ValidationError(
                    'Maximo 26 corredores (A-Z).'
                )

    @api.depends(
        'num_corridors', 'num_shelves',
        'num_levels', 'num_positions',
    )
    def _compute_total(self):
        for wiz in self:
            wiz.total_locations = (
                wiz.num_corridors
                * wiz.num_shelves
                * wiz.num_levels
                * wiz.num_positions
            )

    @api.depends(
        'num_corridors', 'num_shelves',
        'num_levels', 'num_positions',
    )
    def _compute_preview(self):
        for wiz in self:
            if wiz.total_locations == 0:
                wiz.preview_text = ''
                continue
            lines = []
            first = self._gen_code(0, 1, 1, 1)
            last = self._gen_code(
                wiz.num_corridors - 1,
                wiz.num_shelves,
                wiz.num_levels,
                wiz.num_positions,
            )
            lines.append(f'Primeira: {first}')
            lines.append(f'Ultima:   {last}')
            lines.append(
                f'Total:    {wiz.total_locations}'
                f' localizacoes'
            )
            lines.append('')
            lines.append('Exemplos:')
            count = 0
            for c in range(wiz.num_corridors):
                for s in range(
                    1, wiz.num_shelves + 1
                ):
                    for lv in range(
                        1, wiz.num_levels + 1
                    ):
                        for p in range(
                            1,
                            wiz.num_positions + 1
                        ):
                            if count < 6:
                                code = (
                                    self._gen_code(
                                        c, s, lv, p
                                    )
                                )
                                lines.append(
                                    f'  {code}'
                                )
                            count += 1
            if count > 6:
                lines.append(
                    f'  ... (+{count - 6} mais)'
                )
            wiz.preview_text = '\n'.join(lines)

    @api.depends('warehouse_id')
    def _compute_existing(self):
        for wiz in self:
            if not wiz.warehouse_id:
                wiz.existing_count = 0
                continue
            wiz.existing_count = self.env[
                'stock.location'
            ].search_count([
                ('location_id', '=',
                 wiz.warehouse_id.lot_stock_id.id),
                ('usage', '=', 'internal'),
                ('barcode', '!=', False),
            ])

    @staticmethod
    def _gen_code(corridor_idx, shelf,
                  level, pos):
        letter = chr(65 + corridor_idx)
        return (
            f'{letter}-{shelf:02d}'
            f'-L{level}-P{pos:02d}'
        )

    def action_generate(self):
        self.ensure_one()
        if not self.warehouse_id:
            raise UserError(
                'Seleccione um armazem.'
            )
        Location = self.env['stock.location']
        parent = self.warehouse_id.lot_stock_id
        created = 0
        skipped = 0

        for c in range(self.num_corridors):
            for s in range(
                1, self.num_shelves + 1
            ):
                for lv in range(
                    1, self.num_levels + 1
                ):
                    for p in range(
                        1,
                        self.num_positions + 1
                    ):
                        code = self._gen_code(
                            c, s, lv, p
                        )
                        existing = Location.search([
                            ('barcode', '=', code),
                            ('location_id', '=',
                             parent.id),
                        ], limit=1)
                        if existing:
                            skipped += 1
                            continue
                        Location.create({
                            'name': code,
                            'location_id':
                                parent.id,
                            'usage': 'internal',
                            'barcode': code,
                        })
                        created += 1

        # Grava configuracao no modelo permanente
        if self.warehouse_config_id:
            self.warehouse_config_id.write({
                'num_corridors':
                    self.num_corridors,
                'num_shelves': self.num_shelves,
                'num_levels': self.num_levels,
                'num_positions':
                    self.num_positions,
                'last_layout_date':
                    fields.Datetime.now(),
                'last_layout_user':
                    self.env.user.id,
            })

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'StampChain',
                'message': (
                    f'{created} localizacoes '
                    f'criadas no armazem '
                    f'{self.warehouse_id.code}. '
                    f'{skipped} ja existiam.'
                ),
                'type': 'success',
            },
        }
