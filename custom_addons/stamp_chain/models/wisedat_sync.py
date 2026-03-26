# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import UserError
import requests
import logging
import time
import base64
from Crypto.PublicKey import RSA
from Crypto.Cipher import PKCS1_v1_5

_logger = logging.getLogger(__name__)


class WisedatConfig(models.Model):
    _name = 'tobacco.wisedat.config'
    _description = 'Configuracao Integracao Wisedat'

    # — Constantes sync —
    SYNC_BATCH_PAGES = 10
    API_PAGE_SIZE = 200
    MAX_RETRIES = 3
    RETRY_BACKOFF = 2.0

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

    # — Campos de progresso sync —
    sync_last_page = fields.Integer(
        string='Ultima Pagina Sincronizada',
        default=0,
        readonly=True,
    )
    sync_total_pages = fields.Integer(
        string='Total Paginas',
        default=0,
        readonly=True,
    )
    sync_progress = fields.Integer(
        string='Clientes Sincronizados',
        default=0,
        readonly=True,
    )
    sync_errors = fields.Integer(
        string='Erros Sync',
        default=0,
        readonly=True,
    )

    _jwt_tokens = {}

    # ── Autenticacao RSA ─────────────────────

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

    # ── Connection pooling ───────────────────

    def _get_session(self):
        """requests.Session com connection pooling."""
        if not hasattr(self, '_http_session'):
            self._http_session = None
        if self._http_session is None:
            session = requests.Session()
            adapter = requests.adapters.HTTPAdapter(
                pool_connections=1,
                pool_maxsize=1,
                max_retries=0,
            )
            session.mount('http://', adapter)
            session.mount('https://', adapter)
            self._http_session = session
        return self._http_session

    # ── API call com retry ───────────────────

    def _api_call(self, method, endpoint,
                  payload=None):
        """API call basico (sem retry)."""
        url = f'{self.api_url}{endpoint}'
        try:
            response = requests.request(
                method, url,
                headers=self._get_headers(),
                json=payload,
                timeout=30,
            )
            if response.status_code == 401:
                WisedatConfig._jwt_tokens.pop(
                    self.id, None
                )
                response = requests.request(
                    method, url,
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

    def _api_call_with_retry(self, method,
                              endpoint,
                              payload=None):
        """API call com retry e session pooling."""
        session = self._get_session()
        url = f'{self.api_url}{endpoint}'
        for attempt in range(self.MAX_RETRIES):
            try:
                response = session.request(
                    method, url,
                    headers=self._get_headers(),
                    json=payload,
                    timeout=30,
                )
                if response.status_code == 401:
                    WisedatConfig._jwt_tokens.pop(
                        self.id, None
                    )
                    response = session.request(
                        method, url,
                        headers=self._get_headers(),
                        json=payload,
                        timeout=30,
                    )
                response.raise_for_status()
                return response.json()
            except requests.exceptions.RequestException as e:
                if attempt < self.MAX_RETRIES - 1:
                    wait = (
                        self.RETRY_BACKOFF
                        * (attempt + 1)
                    )
                    _logger.warning(
                        'Wisedat retry %d/%d: %s '
                        '(wait %.1fs)',
                        attempt + 1,
                        self.MAX_RETRIES, e, wait
                    )
                    time.sleep(wait)
                else:
                    _logger.error(
                        'Wisedat failed after %d '
                        'retries: %s',
                        self.MAX_RETRIES, e
                    )
                    raise UserError(
                        f'Erro Wisedat apos '
                        f'{self.MAX_RETRIES} '
                        f'tentativas: {e}'
                    )

    # ── Armazens ─────────────────────────────

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

    # ── Sync clientes (chunked) ──────────────

    def _prepare_customer_vals(self, cust_data):
        """Prepara vals para um cliente."""
        billing = (
            cust_data.get('billing_address', {})
            or {}
        )
        return {
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

    def _sync_customers_batch(self):
        """Processa BATCH_PAGES paginas.
        Retorna True se ha mais trabalho."""
        Partner = self.env['res.partner']
        start_page = (self.sync_last_page or 0) + 1
        synced = errors = 0

        for page_offset in range(
            self.SYNC_BATCH_PAGES
        ):
            page = start_page + page_offset
            try:
                response = (
                    self._api_call_with_retry(
                        'GET',
                        f'/customers?limit='
                        f'{self.API_PAGE_SIZE}'
                        f'&page={page}'
                    )
                )
            except Exception as e:
                _logger.error(
                    'API error pagina %d: %s',
                    page, e
                )
                self.sync_status = 'error'
                self.env.cr.commit()
                return False

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

            if not customers:
                self._finish_customer_sync(
                    synced, errors
                )
                return False

            if page == start_page:
                self.write({
                    'sync_total_pages': total_pages,
                    'sync_status': 'syncing',
                })
                self.env.cr.commit()

            # C3: Bulk search
            wisedat_ids = [
                c.get('id') for c in customers
                if c.get('id')
            ]
            existing = Partner.search([
                ('wisedat_id', 'in', wisedat_ids)
            ])
            existing_map = {
                p.wisedat_id: p for p in existing
            }

            # C4: Batch create
            create_vals_list = []
            for cust in customers:
                try:
                    vals = (
                        self._prepare_customer_vals(
                            cust
                        )
                    )
                    partner = existing_map.get(
                        cust.get('id')
                    )
                    if (not partner
                            and cust.get('tax_id')):
                        partner = Partner.search([
                            ('vat', '=',
                             cust['tax_id'])
                        ], limit=1)
                    if partner:
                        partner.write(vals)
                    else:
                        create_vals_list.append(vals)
                    synced += 1
                except Exception as e:
                    errors += 1
                    _logger.error(
                        'Erro cliente %s: %s',
                        cust.get('id'), e
                    )

            if create_vals_list:
                Partner.create(create_vals_list)

            # C1: Commit apos cada pagina
            self.env.cr.commit()

            # C8: Checkpoint
            self.write({
                'sync_last_page': page,
                'sync_progress': (
                    (self.sync_progress or 0)
                    + synced
                ),
                'sync_errors': (
                    (self.sync_errors or 0)
                    + errors
                ),
            })
            self.env.cr.commit()

            # C2: Limpar cache ORM
            self.env.invalidate_all()

            _logger.info(
                'StampChain: clientes pagina '
                '%d/%d — %d sync, %d erros',
                page, total_pages, synced, errors
            )

            synced = errors = 0

            if page >= total_pages:
                self._finish_customer_sync(0, 0)
                return False

        return True

    def _finish_customer_sync(self, synced,
                               errors):
        """Reset checkpoint e finaliza."""
        total_synced = (
            (self.sync_progress or 0) + synced
        )
        total_errors = (
            (self.sync_errors or 0) + errors
        )
        self.write({
            'sync_last_page': 0,
            'sync_total_pages': 0,
            'sync_progress': 0,
            'sync_errors': 0,
            'last_sync_date': fields.Datetime.now(),
            'sync_status': (
                'ok' if total_errors == 0
                else 'error'
            ),
        })
        self.env.cr.commit()
        _logger.info(
            'StampChain: sync clientes completa '
            '— %d sync, %d erros',
            total_synced, total_errors
        )

    # — Legacy (mantido para referencia) —
    def _sync_single_customer(self, cust_data):
        vals = self._prepare_customer_vals(
            cust_data
        )
        Partner = self.env['res.partner']
        partner = Partner.search([
            ('wisedat_id', '=',
             cust_data.get('id'))
        ], limit=1)
        if not partner and cust_data.get(
            'tax_id'
        ):
            partner = Partner.search([
                ('vat', '=',
                 cust_data['tax_id'])
            ], limit=1)
        if partner:
            partner.write(vals)
        else:
            Partner.create(vals)

    # ── Sync produtos ────────────────────────

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

    # ── Sync stock ───────────────────────────

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
                    mapping.wisedat_warehouse_code, e
                )

    def _update_odoo_stock(self, item_data,
                            warehouse):
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

    # ── Guia de transporte ───────────────────

    def _create_wisedat_transport_guide(
        self, picking_id
    ):
        picking = self.env[
            'stock.picking'
        ].browse(picking_id)
        if not picking.exists():
            return None
        sale = self.env['sale.order'].search(
            [('name', '=', picking.origin)],
            limit=1,
        )
        if not sale:
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
                        if hasattr(
                            product, 'wisedat_id'
                        )
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
            return None
        wisedat_customer_id = (
            sale.partner_id.wisedat_id
            if hasattr(
                sale.partner_id, 'wisedat_id'
            )
            else None
        )
        if not wisedat_customer_id:
            raise UserError(
                f'Cliente {sale.partner_id.name} '
                f'nao sincronizado com Wisedat.'
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
                'POST', '/movementsofgoods',
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

    # ── Actions ──────────────────────────────

    def action_full_sync(self):
        """Sync completa sincrona."""
        self.write({
            'sync_status': 'syncing',
            'sync_last_page': 0,
            'sync_progress': 0,
            'sync_errors': 0,
        })
        self.env.cr.commit()
        errors_total = 0
        try:
            while self._sync_customers_batch():
                pass
            _, e2 = self._sync_products()
            errors_total += e2
            self._sync_stock_by_warehouse()
            self.write({
                'sync_status': (
                    'ok' if errors_total == 0
                    else 'error'
                ),
                'last_sync_date':
                    fields.Datetime.now(),
            })
            self.env.cr.commit()
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'StampChain',
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
            self.env.cr.commit()
            raise

    def action_full_sync_background(self):
        """Trigger sync via cron imediato.
        C10: Sem threading."""
        self.ensure_one()
        self.write({
            'sync_status': 'syncing',
            'sync_last_page': 0,
            'sync_progress': 0,
            'sync_errors': 0,
        })
        cron = self.env.ref(
            'stamp_chain.ir_cron_wisedat_sync'
        )
        cron.nextcall = fields.Datetime.now()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'StampChain',
                'message': (
                    'Sincronizacao agendada. '
                    'Sera executada em breve.'
                ),
                'type': 'success',
            },
        }

    def action_test_connection(self):
        self.ensure_one()
        try:
            company = self._api_call(
                'GET', '/company'
            )
            company_name = company.get(
                'name', 'desconhecida'
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

    # ── Cron job (C9: @api.model) ────────────

    @api.model
    def _cron_sync(self):
        """Processa batch de paginas. Se ha mais,
        agenda proximo cron em 2 min."""
        configs = self.search([
            ('active', '=', True)
        ])
        for config in configs:
            try:
                config.sync_status = 'syncing'
                config.env.cr.commit()
                has_more = (
                    config._sync_customers_batch()
                )
                if has_more:
                    cron = self.env.ref(
                        'stamp_chain.'
                        'ir_cron_wisedat_sync'
                    )
                    cron.nextcall = (
                        fields.Datetime.add(
                            fields.Datetime.now(),
                            minutes=2,
                        )
                    )
                    _logger.info(
                        'StampChain: mais paginas, '
                        'proximo cron em 2 min'
                    )
                config.env.cr.commit()
            except Exception as e:
                config.env.cr.rollback()
                _logger.error(
                    'Cron sync erro: %s', e
                )
                try:
                    config.sync_status = 'error'
                    config.env.cr.commit()
                except Exception:
                    config.env.cr.rollback()
