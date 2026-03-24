# -*- coding: utf-8 -*-
from odoo import models, fields
from odoo.exceptions import UserError
import requests
import logging

_logger = logging.getLogger(__name__)


class WisedatConfig(models.Model):
    _name = 'tobacco.wisedat.config'
    _description = 'Configuracao Integracao Wisedat'

    name = fields.Char(
        string='Nome',
        default='Configuracao Wisedat',
        required=True,
    )
    api_url = fields.Char(
        string='URL da API Wisedat',
        required=True,
        help='Ex: http://servidor:porta/api',
    )
    api_key = fields.Char(
        string='Chave API',
        required=True,
        groups='base.group_system',
    )
    company_id = fields.Many2one(
        'res.company',
        string='Empresa',
        default=lambda self: self.env.company,
    )
    sync_customers = fields.Boolean(
        string='Sincronizar Clientes',
        default=True,
    )
    sync_products = fields.Boolean(
        string='Sincronizar Artigos',
        default=True,
    )
    sync_invoices = fields.Boolean(
        string='Sincronizar Facturas',
        default=True,
    )
    sync_frequency = fields.Selection([
        ('realtime', 'Tempo Real'),
        ('hourly', 'Horaria'),
        ('daily', 'Diaria'),
    ], string='Frequencia',
       default='realtime',
    )
    last_sync_date = fields.Datetime(
        string='Ultima Sincronizacao',
        readonly=True,
    )
    sync_status = fields.Selection([
        ('ok', 'OK'),
        ('error', 'Erro'),
        ('syncing', 'A Sincronizar'),
    ], string='Estado',
       default='ok',
       readonly=True,
    )

    def _get_headers(self):
        return {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self.api_key}',
        }

    def _api_call(self, method, endpoint,
                  payload=None):
        url = f'{self.api_url}{endpoint}'
        try:
            response = requests.request(
                method,
                url,
                headers=self._get_headers(),
                json=payload,
                timeout=30,
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            _logger.error('Wisedat API error: %s', e)
            raise UserError(
                f'Erro na comunicacao com Wisedat: '
                f'{str(e)}'
            )

    def action_test_connection(self):
        self.ensure_one()
        try:
            self._api_call('GET', '/customers?limit=1')
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'StampChain',
                    'message': (
                        'Ligacao ao Wisedat '
                        'estabelecida com sucesso!'
                    ),
                    'type': 'success',
                },
            }
        except UserError as e:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Erro de Ligacao',
                    'message': str(e),
                    'type': 'danger',
                },
            }
