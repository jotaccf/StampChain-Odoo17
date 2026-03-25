# -*- coding: utf-8 -*-
from datetime import timedelta
from odoo import models, fields, api
from odoo.exceptions import UserError


class StampZone(models.Model):
    _name = 'tobacco.stamp.zone'
    _description = 'Zona de Estampilha IEC'
    _order = 'name'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(
        string='Nome da Zona',
        required=True,
        tracking=True,
    )
    code = fields.Selection([
        ('PT_C', 'Continente'),
        ('PT_M', 'Madeira'),
        ('PT_A', 'Açores'),
    ], string='Código de Zona',
       required=True,
       tracking=True,
    )
    balance = fields.Integer(
        string='Saldo Actual',
        compute='_compute_balance',
        store=False,
        help='Saldo calculado em tempo real',
    )
    min_stock_alert = fields.Integer(
        string='Stock Mínimo de Alerta',
        default=2000,
        tracking=True,
        help='Alerta quando saldo baixar deste valor',
    )
    alert_active = fields.Boolean(
        string='Alerta Activo',
        compute='_compute_alert_active',
        store=False,
    )
    movement_ids = fields.One2many(
        'tobacco.stamp.movement',
        'zone_id',
        string='Movimentos',
    )
    lot_ids = fields.One2many(
        'tobacco.stamp.lot',
        'zone_id',
        string='Lotes INCM',
    )
    history_ids = fields.One2many(
        'tobacco.stamp.zone.history',
        'zone_id',
        string='Historico Stock Minimo',
    )
    color = fields.Integer(
        string='Cor Kanban',
        compute='_compute_color',
        store=False,
    )
    total_received = fields.Integer(
        string='Total Recebido',
        compute='_compute_totals',
        store=False,
    )
    total_used = fields.Integer(
        string='Total Utilizado',
        compute='_compute_totals',
        store=False,
    )
    total_broken = fields.Integer(
        string='Total Quebras',
        compute='_compute_totals',
        store=False,
    )

    @api.depends('movement_ids',
                 'movement_ids.qty',
                 'movement_ids.move_type')
    def _compute_balance(self):
        for zone in self:
            entradas = sum(
                zone.movement_ids.filtered(
                    lambda m: m.move_type in
                    ('in', 'recovery', 'recovery_found')
                ).mapped('qty')
            )
            saidas = sum(
                zone.movement_ids.filtered(
                    lambda m: m.move_type in
                    ('out', 'breakdown')
                ).mapped('qty')
            )
            zone.balance = entradas - saidas

    @api.depends('movement_ids',
                 'movement_ids.qty',
                 'movement_ids.move_type')
    def _compute_totals(self):
        for zone in self:
            zone.total_received = sum(
                zone.movement_ids.filtered(
                    lambda m: m.move_type == 'in'
                ).mapped('qty')
            )
            zone.total_used = sum(
                zone.movement_ids.filtered(
                    lambda m: m.move_type == 'out'
                ).mapped('qty')
            )
            zone.total_broken = sum(
                zone.movement_ids.filtered(
                    lambda m: m.move_type == 'breakdown'
                ).mapped('qty')
            )

    @api.depends('balance', 'min_stock_alert')
    def _compute_alert_active(self):
        for zone in self:
            zone.alert_active = (
                zone.balance <= zone.min_stock_alert
            )

    @api.depends('balance', 'min_stock_alert')
    def _compute_color(self):
        for zone in self:
            if zone.balance == 0:
                zone.color = 1    # vermelho
            elif zone.balance <= zone.min_stock_alert:
                zone.color = 3    # laranja
            else:
                zone.color = 10   # verde

    # -- Discrepancia --
    stock_theoretical = fields.Integer(
        string='Stock Teorico',
        compute='_compute_discrepancy_fields',
        store=False,
    )
    stock_real_auto = fields.Integer(
        string='Stock Real (automatico)',
        compute='_compute_discrepancy_fields',
        store=False,
    )
    stock_real = fields.Integer(
        string='Stock Real',
        compute='_compute_discrepancy_fields',
        store=False,
    )
    discrepancy = fields.Integer(
        string='Discrepancia',
        compute='_compute_discrepancy_fields',
        store=False,
    )
    discrepancy_active = fields.Boolean(
        string='Tem Discrepancia',
        compute='_compute_discrepancy_fields',
        store=False,
    )
    discrepancy_direction = fields.Selection([
        ('ok', 'Sem Discrepancia'),
        ('missing', 'Faltam Estampilhas'),
        ('surplus', 'Sobram Estampilhas'),
    ], string='Sentido',
       compute='_compute_discrepancy_fields',
       store=False,
    )
    last_physical_count = fields.Integer(
        string='Ultima Contagem Fisica',
        readonly=True,
        default=0,
    )
    last_physical_count_date = fields.Datetime(
        string='Data Ultima Contagem',
        readonly=True,
    )
    last_physical_count_user = fields.Many2one(
        'res.users',
        string='Contagem por',
        readonly=True,
    )
    audit_ids = fields.One2many(
        'tobacco.stamp.audit',
        'zone_id',
        string='Registos de Auditoria',
    )
    audit_open_count = fields.Integer(
        string='Discrepancias Abertas',
        compute='_compute_audit_open_count',
        store=False,
    )
    physical_count_ids = fields.One2many(
        'tobacco.stamp.physical.count',
        'zone_id',
        string='Contagens Fisicas',
    )

    def _compute_discrepancy_fields(self):
        """C2: stock_theoretical reutiliza balance.
        C1: usa fields.Datetime.now().
        C3: sem @api.depends (store=False)."""
        threshold = timedelta(hours=24)
        now = fields.Datetime.now()
        for zone in self:
            theoretical = zone.balance
            zone.stock_theoretical = theoretical
            real_auto = len(
                zone.lot_ids.mapped(
                    'serial_ids'
                ).filtered(
                    lambda s: s.state in (
                        'available', 'broken',
                        'quarantine',
                    )
                )
            )
            zone.stock_real_auto = real_auto
            use_manual = (
                zone.last_physical_count > 0
                and zone.last_physical_count_date
                and (now - zone.last_physical_count_date)
                < threshold
            )
            real = (
                zone.last_physical_count
                if use_manual else real_auto
            )
            zone.stock_real = real
            disc = theoretical - real
            zone.discrepancy = disc
            zone.discrepancy_active = disc != 0
            if disc > 0:
                zone.discrepancy_direction = 'missing'
            elif disc < 0:
                zone.discrepancy_direction = 'surplus'
            else:
                zone.discrepancy_direction = 'ok'

    def _compute_audit_open_count(self):
        for zone in self:
            zone.audit_open_count = len(
                zone.audit_ids.filtered(
                    lambda a: a.state == 'open'
                )
            )

    def action_open_physical_count_wizard(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Contagem Fisica — {self.name}',
            'res_model': (
                'tobacco.stamp.physical.count.wizard'
            ),
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_zone_id': self.id,
                'default_stock_real_auto':
                    self.stock_real_auto,
                'default_stock_theoretical':
                    self.stock_theoretical,
            },
        }

    def action_open_audit(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Auditoria — {self.name}',
            'res_model': 'tobacco.stamp.audit',
            'view_mode': 'list,form',
            'domain': [('zone_id', '=', self.id)],
            'context': {'default_zone_id': self.id},
        }

    def _send_stock_alert(self):
        for zone in self:
            if zone.alert_active:
                zone.message_post(
                    body=(
                        f'ALERTA StampChain: '
                        f'Saldo zona {zone.name} '
                        f'em {zone.balance} unidades. '
                        f'Minimo: {zone.min_stock_alert}.'
                        f' Efectuar pedido INCM.'
                    ),
                    message_type='notification',
                    subtype_xmlid='mail.mt_comment',
                )

    def action_change_min_stock(self):
        self.ensure_one()
        if not self.env.user.has_group(
            'stamp_chain.group_stamp_manager'
        ):
            raise UserError(
                'Apenas o Gestor StampChain '
                'pode alterar o stock minimo.'
            )
        return {
            'type': 'ir.actions.act_window',
            'name': f'Alterar Stock Minimo — '
                    f'{self.name}',
            'res_model': 'tobacco.min.stock.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_zone_id': self.id,
                'default_current_value':
                    self.min_stock_alert,
            },
        }
