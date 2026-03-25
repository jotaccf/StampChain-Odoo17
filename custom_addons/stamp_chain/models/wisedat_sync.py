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

    warehouse_mapping_ids = fields.One2many(
        'tobacco.warehouse.config',
        'wisedat_config_id',
        string='Mapeamento de Armazens',
    )

    def _get_warehouse_code(self, warehouse_id):
        mapping = self.warehouse_mapping_ids.filtered(
            lambda m: m.warehouse_id.id == warehouse_id
        )
        if not mapping:
            raise UserError(
                'Armazem nao mapeado para Wisedat. '
                'Configure em Definicoes > Armazens.'
            )
        return mapping[0].wisedat_warehouse_code

    def _sync_customers(self):
        _logger.info('StampChain: sync clientes Wisedat->Odoo')
        try:
            response = self._api_call('GET', '/customers')
            customers = (
                response.get('customers', [])
                if isinstance(response, dict)
                else response
                if isinstance(response, list)
                else []
            )
            synced = errors = 0
            for cust in customers:
                try:
                    self._sync_single_customer(cust)
                    synced += 1
                except Exception as e:
                    errors += 1
                    _logger.error(
                        'Erro sync cliente %s: %s',
                        cust.get('id'), e
                    )
            self.write({
                'last_sync_date': fields.Datetime.now(),
                'sync_status': 'ok' if errors == 0 else 'error',
            })
            return synced, errors
        except UserError:
            self.sync_status = 'error'
            raise

    def _sync_single_customer(self, cust_data):
        Partner = self.env['res.partner']
        partner = Partner.search([
            ('wisedat_id', '=', cust_data.get('id'))
        ], limit=1)
        if not partner and cust_data.get('tax_id'):
            partner = Partner.search([
                ('vat', '=', cust_data['tax_id'])
            ], limit=1)
        billing = cust_data.get('billing_address', {}) or {}
        vals = {
            'name': cust_data.get('name', ''),
            'vat': cust_data.get('tax_id'),
            'email': cust_data.get('email'),
            'phone': cust_data.get('phone'),
            'customer_rank': 1,
            'wisedat_id': cust_data.get('id'),
            'wisedat_synced': True,
            'wisedat_sync_date': fields.Datetime.now(),
            'street': billing.get('street', ''),
            'city': billing.get('city', ''),
            'zip': billing.get('postal_code', ''),
        }
        if partner:
            partner.write(vals)
        else:
            Partner.create(vals)

    def _sync_products(self):
        _logger.info('StampChain: sync artigos Wisedat->Odoo')
        try:
            response = self._api_call('GET', '/items')
            items = (
                response.get('items', [])
                if isinstance(response, dict)
                else response
                if isinstance(response, list)
                else []
            )
            synced = errors = 0
            for item in items:
                try:
                    self._sync_single_product(item)
                    synced += 1
                except Exception as e:
                    errors += 1
                    _logger.error(
                        'Erro sync artigo %s: %s',
                        item.get('code'), e
                    )
            return synced, errors
        except UserError:
            raise

    def _sync_single_product(self, item_data):
        Product = self.env['product.product']
        product = Product.search([
            ('default_code', '=', item_data.get('code'))
        ], limit=1)
        vals = {
            'name': item_data.get('name', ''),
            'default_code': item_data.get('code'),
            'list_price': item_data.get('price', 0),
            'type': 'product',
            'sale_ok': True,
        }
        if product:
            product.write(vals)
        else:
            Product.create(vals)

    def _sync_stock_by_warehouse(self):
        for mapping in self.warehouse_mapping_ids:
            try:
                response = self._api_call(
                    'GET',
                    f'/stock?warehouse='
                    f'{mapping.wisedat_warehouse_code}'
                )
                items = (
                    response.get('items', [])
                    if isinstance(response, dict)
                    else response
                    if isinstance(response, list)
                    else []
                )
                for item in items:
                    self._update_odoo_stock(
                        item, mapping.warehouse_id
                    )
            except Exception as e:
                _logger.error(
                    'Erro sync stock armazem %s: %s',
                    mapping.wisedat_warehouse_code, e
                )

    def _update_odoo_stock(self, item_data, warehouse):
        product_code = item_data.get('code')
        qty = item_data.get('quantity', 0)
        if not product_code:
            return
        product = self.env['product.product'].search(
            [('default_code', '=', product_code)],
            limit=1,
        )
        if not product:
            _logger.warning(
                'Produto %s nao encontrado no Odoo.',
                product_code
            )
            return
        location = warehouse.lot_stock_id
        quant = self.env['stock.quant'].search([
            ('product_id', '=', product.id),
            ('location_id', '=', location.id),
        ], limit=1)
        if quant:
            quant.sudo().inventory_quantity = qty
            quant.sudo().action_apply_inventory()
        else:
            self.env['stock.quant'].sudo().create({
                'product_id': product.id,
                'location_id': location.id,
                'quantity': qty,
            })

    def _create_wisedat_transport_guide(self, picking_id):
        picking = self.env['stock.picking'].browse(picking_id)
        if not picking.exists():
            _logger.warning('Picking %s nao encontrado.', picking_id)
            return None
        sale = self.env['sale.order'].search(
            [('name', '=', picking.origin)],
            limit=1,
        )
        if not sale:
            _logger.warning(
                'Encomenda nao encontrada para picking %s',
                picking.name
            )
            return None
        wisedat_warehouse = self._get_warehouse_code(
            picking.picking_type_id.warehouse_id.id
        )
        lines = []
        for move in picking.move_ids:
            if move.state == 'done':
                product = move.product_id
                order_line = sale.order_line.filtered(
                    lambda l: l.product_id == product
                )[:1]
                lines.append({
                    'code': product.default_code,
                    'name': product.name,
                    'quantity': move.quantity_done,
                    'price': order_line.price_unit if order_line else 0,
                    'unit': move.product_uom.name,
                })
        if not lines:
            _logger.warning(
                'Picking %s sem linhas done.',
                picking.name
            )
            return None
        payload = {
            'reference': picking.name,
            'sale_order': sale.name,
            'customer_tax_id': sale.partner_id.vat or '',
            'customer_wisedat_id': sale.partner_id.wisedat_id or None,
            'warehouse': wisedat_warehouse,
            'date': str(fields.Date.today()),
            'items': lines,
            'stamp_zone': (
                sale.stamp_zone_id.code
                if sale.stamp_zone_id else None
            ),
        }
        try:
            response = self._api_call('POST', '/sales', payload)
            wisedat_doc_id = response.get('id')
            picking.wisedat_doc_id = str(wisedat_doc_id)
            picking.message_post(
                body=(
                    f'Guia de Transporte criada '
                    f'no Wisedat: {wisedat_doc_id}.'
                ),
            )
            return wisedat_doc_id
        except Exception as e:
            _logger.error('Erro Guia Wisedat: %s', e)
            raise

    def action_full_sync(self):
        self.sync_status = 'syncing'
        errors_total = 0
        try:
            _, e1 = self._sync_customers()
            errors_total += e1
            _, e2 = self._sync_products()
            errors_total += e2
            self._sync_stock_by_warehouse()
            self.sync_status = (
                'ok' if errors_total == 0 else 'error'
            )
            self.last_sync_date = fields.Datetime.now()
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'StampChain — Wisedat Sync',
                    'message': (
                        f'Sincronizacao concluida. '
                        f'Erros: {errors_total}'
                    ),
                    'type': 'success'
                    if errors_total == 0 else 'warning',
                },
            }
        except Exception:
            self.sync_status = 'error'
            raise

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
