# -*- coding: utf-8 -*-
from odoo import models, fields
from odoo.exceptions import UserError
import requests
import logging
import threading
import base64
from Crypto.PublicKey import RSA
from Crypto.Cipher import PKCS1_v1_5

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
        help='Ex: http://servidor:porta',
    )
    api_key = fields.Char(
        string='Chave API',
        required=True,
        groups='stamp_chain.group_stamp_manager',
    )
    api_username = fields.Char(
        string='Utilizador API',
        required=True,
        groups='stamp_chain.group_stamp_manager',
    )
    api_password = fields.Char(
        string='Password API',
        required=True,
        groups='stamp_chain.group_stamp_manager',
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
    active = fields.Boolean(
        string='Activo',
        default=True,
    )

    _jwt_tokens = {}

    def _authenticate(self):
        try:
            status_r = requests.get(
                f'{self.api_url}/status',
                headers={
                    'Authorization':
                        f'WDAPI {self.api_key}',
                    'Accept': 'application/json',
                },
                timeout=30,
            )
            status_r.raise_for_status()
            data = status_r.json()

            pub_key_data = data['PublicKey']
            modulus = int.from_bytes(
                base64.b64decode(pub_key_data[0]),
                'big'
            )
            exponent = int.from_bytes(
                base64.b64decode(pub_key_data[1]),
                'big'
            )
            pub_key = RSA.construct(
                (modulus, exponent)
            )
            cipher = PKCS1_v1_5.new(pub_key)

            credentials = (
                f'{self.api_key}'
                f';{self.api_username}'
                f';{self.api_password}'
            )
            encrypted = cipher.encrypt(
                credentials.encode('utf-8')
            )
            auth_header = base64.b64encode(
                encrypted
            ).decode('utf-8')

            login_r = requests.post(
                f'{self.api_url}/authentication/login',
                headers={
                    'Authorization':
                        f'WDAPI {auth_header}',
                    'Accept': 'application/json',
                    'Content-Type': 'application/json',
                },
                timeout=30,
            )
            login_r.raise_for_status()
            WisedatConfig._jwt_tokens[self.id] = (
                login_r.json().get('auth_token')
            )
            _logger.info(
                'StampChain: JWT Wisedat obtido.'
            )
        except requests.exceptions.RequestException as e:
            _logger.error(
                'Wisedat auth error: %s', e
            )
            WisedatConfig._jwt_tokens.pop(
                self.id, None
            )
            raise UserError(
                f'Erro na autenticacao Wisedat: '
                f'{str(e)}'
            )

    def _get_headers(self):
        token = WisedatConfig._jwt_tokens.get(
            self.id
        )
        if not token:
            self._authenticate()
            token = WisedatConfig._jwt_tokens.get(
                self.id
            )
        return {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'Authorization': f'Bearer {token}',
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
            if response.status_code == 401:
                _logger.info(
                    'Wisedat: token expirado, '
                    're-auth.'
                )
                WisedatConfig._jwt_tokens.pop(
                    self.id, None
                )
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
            _logger.error(
                'Wisedat API error: %s', e
            )
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
            lambda m: m.warehouse_id.id
            == warehouse_id
        )
        if not mapping:
            raise UserError(
                'Armazem nao mapeado para Wisedat. '
                'Configure em Definicoes > Armazens.'
            )
        return mapping[0].wisedat_warehouse_code

    def _sync_customers(self, limit=50,
                        max_pages=None):
        _logger.info(
            'StampChain: sync clientes Wisedat->Odoo'
        )
        try:
            page = 1
            synced = errors = 0
            while True:
                response = self._api_call(
                    'GET',
                    f'/customers?limit={limit}'
                    f'&page={page}'
                )
                customers = (
                    response.get('customers', [])
                    if isinstance(response, dict)
                    else response
                    if isinstance(response, list)
                    else []
                )
                pagination = (
                    response.get('pagination', {})
                    if isinstance(response, dict)
                    else {}
                )
                total_pages = pagination.get(
                    'number_pages', 1
                )
                for cust in customers:
                    try:
                        self._sync_single_customer(
                            cust
                        )
                        synced += 1
                    except Exception as e:
                        errors += 1
                        _logger.error(
                            'Erro sync cliente %s: %s',
                            cust.get('id'), e
                        )
                _logger.info(
                    'StampChain: clientes pagina '
                    '%d/%d — %d sincronizados',
                    page, total_pages, synced
                )
                if page >= total_pages:
                    break
                if max_pages and page >= max_pages:
                    _logger.info(
                        'StampChain: limite de '
                        '%d paginas atingido.',
                        max_pages
                    )
                    break
                page += 1
            self.write({
                'last_sync_date':
                    fields.Datetime.now(),
                'sync_status':
                    'ok' if errors == 0
                    else 'error',
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
        billing = (
            cust_data.get('billing_address', {})
            or {}
        )
        vals = {
            'name': cust_data.get('name', ''),
            'vat': cust_data.get('tax_id'),
            'email': cust_data.get('email'),
            'phone': cust_data.get('phone'),
            'customer_rank': 1,
            'wisedat_id': cust_data.get('id'),
            'wisedat_synced': True,
            'wisedat_sync_date':
                fields.Datetime.now(),
            'street': billing.get('street', ''),
            'city': billing.get('city', ''),
            'zip': billing.get('postal_code', ''),
        }
        if partner:
            partner.write(vals)
        else:
            Partner.create(vals)

    def _sync_products(self):
        _logger.info(
            'StampChain: sync artigos Wisedat->Odoo'
        )
        try:
            response = self._api_call(
                'GET', '/products'
            )
            items = (
                response.get('products', [])
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
                        item.get('id'), e
                    )
            return synced, errors
        except UserError:
            raise

    def _sync_single_product(self, item_data):
        Product = self.env['product.product']
        product = Product.search([
            ('default_code', '=',
             item_data.get('name'))
        ], limit=1)
        vals = {
            'name': item_data.get(
                'description',
                item_data.get('name', '')
            ),
            'default_code': item_data.get('name'),
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
                    f'/products?warehouse='
                    f'{mapping.wisedat_warehouse_code}'
                )
                items = (
                    response.get('products', [])
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
                    mapping.wisedat_warehouse_code,
                    e
                )

    def _update_odoo_stock(
        self, item_data, warehouse
    ):
        product_code = item_data.get('name')
        stocks = item_data.get('stocks', [])
        if not product_code or not stocks:
            return
        product = self.env[
            'product.product'
        ].search(
            [('default_code', '=', product_code)],
            limit=1,
        )
        if not product:
            _logger.warning(
                'Produto %s nao encontrado.',
                product_code
            )
            return
        total_qty = sum(
            s.get('current_stock', 0)
            for s in stocks
        )
        location = warehouse.lot_stock_id
        quant = self.env['stock.quant'].search([
            ('product_id', '=', product.id),
            ('location_id', '=', location.id),
        ], limit=1)
        if quant:
            quant.sudo().inventory_quantity = (
                total_qty
            )
            quant.sudo().action_apply_inventory()
        else:
            self.env['stock.quant'].sudo().create({
                'product_id': product.id,
                'location_id': location.id,
                'quantity': total_qty,
            })

    def _create_wisedat_transport_guide(
        self, picking_id
    ):
        picking = self.env[
            'stock.picking'
        ].browse(picking_id)
        if not picking.exists():
            _logger.warning(
                'Picking %s nao encontrado.',
                picking_id
            )
            return None
        sale = self.env['sale.order'].search(
            [('name', '=', picking.origin)],
            limit=1,
        )
        if not sale:
            _logger.warning(
                'Encomenda nao encontrada '
                'para picking %s',
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
                    'id': (
                        product.wisedat_id
                        if hasattr(product, 'wisedat_id')
                        else None
                    ),
                    'description': product.name,
                    'quantity': move.quantity_done,
                    'price': (
                        order_line.price_unit
                        if order_line else 0
                    ),
                    'type': 1,
                    'warehouse': wisedat_warehouse,
                })
        if not lines:
            _logger.warning(
                'Picking %s sem linhas done.',
                picking.name
            )
            return None

        wisedat_customer_id = (
            sale.partner_id.wisedat_id
            if hasattr(sale.partner_id, 'wisedat_id')
            else None
        )
        if not wisedat_customer_id:
            raise UserError(
                f'Cliente {sale.partner_id.name} '
                f'nao sincronizado com Wisedat. '
                f'Execute a sincronizacao primeiro.'
            )

        payload = {
            'customer': wisedat_customer_id,
            'date': str(fields.Date.today()),
            'expiration_date': str(
                fields.Date.today()
            ),
            'your_reference': picking.name,
            'notes': sale.name,
            'items': lines,
        }
        try:
            response = self._api_call(
                'POST',
                '/movementsofgoods',
                payload
            )
            wisedat_doc_id = response.get('id')
            picking.wisedat_doc_id = str(
                wisedat_doc_id
            )
            picking.message_post(
                body=(
                    f'Guia de Transporte criada '
                    f'no Wisedat: {wisedat_doc_id}.'
                ),
            )
            return wisedat_doc_id
        except Exception as e:
            _logger.error(
                'Erro Guia Wisedat: %s', e
            )
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
                'ok' if errors_total == 0
                else 'error'
            )
            self.last_sync_date = (
                fields.Datetime.now()
            )
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': (
                        'StampChain — Wisedat Sync'
                    ),
                    'message': (
                        f'Sincronizacao concluida. '
                        f'Erros: {errors_total}'
                    ),
                    'type': (
                        'success'
                        if errors_total == 0
                        else 'warning'
                    ),
                },
            }
        except Exception:
            self.sync_status = 'error'
            raise

    def action_test_connection(self):
        self.ensure_one()
        try:
            company = self._api_call(
                'GET', '/company'
            )
            company_name = company.get(
                'name', 'desconhecida'
            )
            _logger.info(
                'StampChain: Wisedat ligado. '
                'Empresa: %s', company_name
            )
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'StampChain',
                    'message': (
                        f'Ligacao estabelecida! '
                        f'Empresa: {company_name}'
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

    # — Cron job sync —

    @classmethod
    def _cron_sync(cls):
        """Chamado pelo cron job. Nao retorna
        notificacao. Protege contra ficar preso
        em 'syncing' se falhar."""
        from odoo import api, SUPERUSER_ID
        from odoo.modules.registry import Registry
        db_name = cls.pool.db_name
        registry = Registry(db_name)
        with registry.cursor() as cr:
            env = api.Environment(
                cr, SUPERUSER_ID, {}
            )
            configs = env[
                'tobacco.wisedat.config'
            ].search([('active', '=', True)])
            for config in configs:
                try:
                    config.sync_status = 'syncing'
                    cr.commit()
                    config.action_full_sync()
                    cr.commit()
                except Exception as e:
                    cr.rollback()
                    _logger.error(
                        'Cron sync falhou para %s: %s',
                        config.name, e
                    )
                    try:
                        config.sync_status = 'error'
                        cr.commit()
                    except Exception:
                        cr.rollback()

    # — Background sync (botao UI) —

    def action_full_sync_background(self):
        """Lanca sync em thread separado.
        Nao bloqueia o browser."""
        self.ensure_one()
        record_id = self.id
        db_name = self.env.cr.dbname
        thread = threading.Thread(
            target=self._run_sync_thread,
            args=(db_name, record_id),
        )
        thread.daemon = True
        thread.start()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'StampChain',
                'message': (
                    'Sincronizacao iniciada '
                    'em background. Consulta '
                    'o estado na configuracao.'
                ),
                'type': 'success',
            },
        }

    @staticmethod
    def _run_sync_thread(db_name, record_id):
        """Executa sync num thread separado
        com cursor proprio. try/finally
        garante que cursor fecha sempre."""
        from odoo import api, SUPERUSER_ID
        from odoo.modules.registry import Registry
        registry = Registry(db_name)
        cr = registry.cursor()
        try:
            env = api.Environment(
                cr, SUPERUSER_ID, {}
            )
            config = env[
                'tobacco.wisedat.config'
            ].browse(record_id)
            if config.exists():
                config.action_full_sync()
                cr.commit()
        except Exception as e:
            cr.rollback()
            _logger.error(
                'Erro sync background: %s', e
            )
            try:
                env = api.Environment(
                    cr, SUPERUSER_ID, {}
                )
                config = env[
                    'tobacco.wisedat.config'
                ].browse(record_id)
                config.sync_status = 'error'
                cr.commit()
            except Exception:
                cr.rollback()
        finally:
            cr.close()
