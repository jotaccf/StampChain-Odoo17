# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import UserError
import requests
import logging
import time
import json
import base64
from datetime import timedelta
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

    # — Session HTTP (classe, nao instancia — V10) —
    _http_session = None

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

    # — Progresso clientes —
    sync_last_page = fields.Integer(
        default=0, readonly=True)
    sync_total_pages = fields.Integer(
        default=0, readonly=True)
    sync_progress = fields.Integer(
        default=0, readonly=True)
    sync_errors = fields.Integer(
        default=0, readonly=True)
    last_sync_customers = fields.Integer(
        default=0, readonly=True)
    last_sync_errors = fields.Integer(
        default=0, readonly=True)
    last_sync_pages = fields.Integer(
        default=0, readonly=True)

    # — Progresso produtos —
    product_sync_last_page = fields.Integer(
        default=0, readonly=True)
    product_sync_total_pages = fields.Integer(
        default=0, readonly=True)
    product_sync_progress = fields.Integer(
        default=0, readonly=True)
    product_sync_errors = fields.Integer(
        default=0, readonly=True)
    last_sync_products = fields.Integer(
        default=0, readonly=True)

    # — Progresso facturas —
    invoice_sync_last_page = fields.Integer(
        default=0, readonly=True)
    invoice_sync_total_pages = fields.Integer(
        default=0, readonly=True)
    invoice_sync_progress = fields.Integer(
        default=0, readonly=True)
    invoice_sync_errors = fields.Integer(
        default=0, readonly=True)
    last_sync_invoices = fields.Integer(
        default=0, readonly=True)

    # — Fase cron —
    sync_phase = fields.Selection([
        ('idle', 'Parado'),
        ('categories', 'Categorias'),
        ('customers', 'Clientes'),
        ('products', 'Produtos'),
        ('stock', 'Stock'),
        ('invoices', 'Facturas'),
    ], default='idle', readonly=True)
    sync_phase_started = fields.Datetime(
        string='Fase Iniciada Em',
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

    # ── Connection pooling (V10 — classe) ────

    @classmethod
    def _get_session(cls):
        if cls._http_session is None:
            session = requests.Session()
            adapter = requests.adapters.HTTPAdapter(
                pool_connections=1,
                pool_maxsize=1,
                max_retries=0,
            )
            session.mount('http://', adapter)
            session.mount('https://', adapter)
            cls._http_session = session
        return cls._http_session

    # ── API calls ────────────────────────────

    def _api_call(self, method, endpoint,
                  payload=None):
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
                f'Erro Wisedat: {str(e)}'
            )

    def _api_call_with_retry(self, method,
                              endpoint,
                              payload=None):
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
                    raise

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
                'Armazem nao mapeado para Wisedat.'
            )
        return mapping[0].wisedat_warehouse_code

    # ── Categorias (V4 — com paginacao) ──────

    def _sync_categories(self):
        _logger.info('StampChain: sync categorias')
        Category = self.env['product.category']
        all_categories = []
        page = 1
        try:
            while True:
                response = (
                    self._api_call_with_retry(
                        'GET',
                        f'/categories?limit=200'
                        f'&page={page}'
                    )
                )
                categories = (
                    response.get('categories', [])
                    if isinstance(response, dict)
                    else response
                    if isinstance(response, list)
                    else []
                )
                all_categories.extend(categories)
                pagination = (
                    response.get('pagination', {})
                    if isinstance(response, dict)
                    else {}
                )
                total_pages = pagination.get(
                    'number_pages', 1
                )
                if page >= total_pages:
                    break
                page += 1
            # Pass 1: pais
            for cat in all_categories:
                if not cat.get('id_parent'):
                    self._sync_single_category(
                        cat, Category
                    )
            self.env.cr.commit()
            # Pass 2: filhos
            for cat in all_categories:
                if cat.get('id_parent'):
                    self._sync_single_category(
                        cat, Category
                    )
            self.env.cr.commit()
            self.env.invalidate_all()
            _logger.info(
                'StampChain: %d categorias sync',
                len(all_categories)
            )
        except Exception as e:
            _logger.error(
                'Erro sync categorias: %s', e
            )
            self.sync_status = 'error'
            self.env.cr.commit()
            raise

    def _sync_single_category(self, cat_data,
                                Category):
        existing = Category.search([
            ('wisedat_id', '=', cat_data['id'])
        ], limit=1)
        parent = False
        if cat_data.get('id_parent'):
            parent_cat = Category.search([
                ('wisedat_id', '=',
                 cat_data['id_parent'])
            ], limit=1)
            parent = (
                parent_cat.id if parent_cat
                else False
            )
        vals = {
            'name': cat_data.get('name', ''),
            'wisedat_id': cat_data['id'],
        }
        if parent:
            vals['parent_id'] = parent
        if existing:
            existing.write(vals)
        else:
            Category.create(vals)

    # ── Clientes (chunked + incremental) ─────

    def _prepare_customer_vals(self, cust_data):
        billing = (
            cust_data.get('billing_address', {})
            or {}
        )
        country_code = 'PT'
        country_obj = billing.get('country', {})
        if isinstance(country_obj, dict):
            country_code = country_obj.get(
                'iso_3166_1', 'PT'
            )
        country_id = self.env[
            'res.country'
        ].search([
            ('code', '=', country_code)
        ], limit=1)
        return {
            'name': cust_data.get('name', ''),
            'vat': cust_data.get('tax_id'),
            'email': cust_data.get('email'),
            'phone': cust_data.get('phone'),
            'website': cust_data.get('website'),
            'comment': cust_data.get('notes'),
            'customer_rank': 1,
            'wisedat_id': cust_data.get('id'),
            'wisedat_synced': True,
            'wisedat_sync_date':
                fields.Datetime.now(),
            'street': billing.get('street', ''),
            'city': billing.get('city', ''),
            'zip': billing.get(
                'postal_code', ''
            ),
            'country_id': (
                country_id.id
                if country_id else False
            ),
        }

    def _sync_customers_batch(self):
        Partner = self.env['res.partner']
        start_page = (
            (self.sync_last_page or 0) + 1
        )
        synced = errors = 0
        for page_offset in range(
            self.SYNC_BATCH_PAGES
        ):
            page = start_page + page_offset
            endpoint = (
                f'/customers?limit='
                f'{self.API_PAGE_SIZE}'
                f'&page={page}'
            )
            if self.last_sync_date:
                endpoint += (
                    f'&modified_since='
                    f'{self.last_sync_date.isoformat()}'
                )
            try:
                response = (
                    self._api_call_with_retry(
                        'GET', endpoint
                    )
                )
            except Exception as e:
                _logger.error(
                    'API error clientes pag %d: %s',
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
                })
                self.env.cr.commit()
            # Bulk search
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
            self.env.cr.commit()
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
            self.env.invalidate_all()
            _logger.info(
                'StampChain: clientes pag %d/%d',
                page, total_pages
            )
            synced = errors = 0
            if page >= total_pages:
                self._finish_customer_sync(0, 0)
                return False
        return True

    def _finish_customer_sync(self, synced,
                               errors):
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
            'last_sync_customers': total_synced,
            'last_sync_errors': total_errors,
            'last_sync_pages': (
                self.sync_total_pages or 0
            ),
        })
        self.env.cr.commit()

    # Legacy
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

    # ── Produtos (chunked) ───────────────────

    def _prepare_product_vals(self, item_data):
        categ_id = False
        categories = item_data.get(
            'categories', []
        )
        if categories:
            main_cat = categories[0]
            cat = self.env[
                'product.category'
            ].search([
                ('wisedat_id', '=',
                 main_cat.get('id'))
            ], limit=1)
            if cat:
                categ_id = cat.id
        vals = {
            'name': item_data.get(
                'description',
                item_data.get('name', '')
            ),
            'default_code': item_data.get('name'),
            'list_price': item_data.get(
                'price', 0
            ),
            'active': item_data.get(
                'active', True
            ),
            'wisedat_id': item_data.get('id'),
            'wisedat_synced': True,
            'wisedat_sync_date':
                fields.Datetime.now(),
        }
        if categ_id:
            vals['categ_id'] = categ_id
        if item_data.get('parent_id'):
            vals['wisedat_parent_id'] = (
                item_data['parent_id']
            )
        return vals

    def _sync_products_batch(self):
        Product = self.env['product.product']
        start_page = (
            (self.product_sync_last_page or 0) + 1
        )
        synced = errors = 0
        for page_offset in range(
            self.SYNC_BATCH_PAGES
        ):
            page = start_page + page_offset
            endpoint = (
                f'/products?limit='
                f'{self.API_PAGE_SIZE}'
                f'&page={page}'
            )
            if self.last_sync_date:
                endpoint += (
                    f'&modified_since='
                    f'{self.last_sync_date.isoformat()}'
                )
            try:
                response = (
                    self._api_call_with_retry(
                        'GET', endpoint
                    )
                )
            except Exception as e:
                _logger.error(
                    'API error produtos pag %d: %s',
                    page, e
                )
                self.sync_status = 'error'
                self.env.cr.commit()
                return False
            items = (
                response.get('products', [])
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
            if not items:
                self._finish_product_sync(
                    synced, errors
                )
                return False
            if page == start_page:
                self.write({
                    'product_sync_total_pages':
                        total_pages,
                })
                self.env.cr.commit()
            wisedat_ids = [
                i.get('id') for i in items
                if i.get('id')
            ]
            existing = Product.search([
                ('wisedat_id', 'in', wisedat_ids)
            ])
            existing_map = {
                p.wisedat_id: p for p in existing
            }
            create_vals_list = []
            for item in items:
                try:
                    vals = (
                        self._prepare_product_vals(
                            item
                        )
                    )
                    product = existing_map.get(
                        item.get('id')
                    )
                    if not product:
                        code = item.get('name')
                        if code:
                            product = Product.search([
                                ('default_code', '=',
                                 code),
                                ('wisedat_id', '=',
                                 False),
                            ], limit=1)
                    if product:
                        product.write(vals)
                    else:
                        vals.update({
                            'type': 'product',
                            'sale_ok': True,
                        })
                        create_vals_list.append(vals)
                    synced += 1
                except Exception as e:
                    errors += 1
                    _logger.error(
                        'Erro produto %s: %s',
                        item.get('id'), e
                    )
            if create_vals_list:
                Product.create(create_vals_list)
            self.env.cr.commit()
            self.write({
                'product_sync_last_page': page,
                'product_sync_progress': (
                    (self.product_sync_progress
                     or 0) + synced
                ),
                'product_sync_errors': (
                    (self.product_sync_errors
                     or 0) + errors
                ),
            })
            self.env.cr.commit()
            self.env.invalidate_all()
            _logger.info(
                'StampChain: produtos pag %d/%d',
                page, total_pages
            )
            synced = errors = 0
            if page >= total_pages:
                self._finish_product_sync(0, 0)
                return False
        return True

    def _finish_product_sync(self, synced,
                              errors):
        total_synced = (
            (self.product_sync_progress or 0)
            + synced
        )
        total_errors = (
            (self.product_sync_errors or 0)
            + errors
        )
        self.write({
            'product_sync_last_page': 0,
            'product_sync_total_pages': 0,
            'product_sync_progress': 0,
            'product_sync_errors': 0,
            'last_sync_products': total_synced,
        })
        self.env.cr.commit()

    def _sync_single_product(self, item_data):
        vals = self._prepare_product_vals(
            item_data
        )
        Product = self.env['product.product']
        product = Product.search([
            ('default_code', '=',
             item_data.get('name'))
        ], limit=1)
        if product:
            product.write(vals)
        else:
            vals.update({
                'type': 'product',
                'sale_ok': True,
            })
            Product.create(vals)

    # ── Stock (V3 — is_iec_product) ──────────

    def _sync_stock_by_warehouse(self):
        for mapping in self.warehouse_mapping_ids:
            try:
                response = (
                    self._api_call_with_retry(
                        'GET',
                        f'/products?warehouse='
                        f'{mapping.wisedat_warehouse_code}'
                    )
                )
                items = (
                    response.get('products', [])
                    if isinstance(response, dict)
                    else response
                    if isinstance(response, list)
                    else []
                )
                for item in items:
                    product = self.env[
                        'product.product'
                    ].search([
                        ('wisedat_id', '=',
                         item.get('id'))
                    ], limit=1)
                    if not product:
                        continue
                    wisedat_qty = sum(
                        s.get('current_stock', 0)
                        for s in item.get(
                            'stocks', []
                        )
                    )
                    if product.is_iec_product:
                        _logger.info(
                            'Stock IEC %s: '
                            'Wisedat=%d (info)',
                            product.default_code,
                            int(wisedat_qty)
                        )
                    else:
                        self._update_odoo_stock(
                            item,
                            mapping.warehouse_id
                        )
            except Exception as e:
                _logger.error(
                    'Erro sync stock %s: %s',
                    mapping.wisedat_warehouse_code,
                    e
                )
        self.env.cr.commit()

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

    # ── Facturas (leitura) ───────────────────

    def _sync_invoices_batch(self):
        Invoice = self.env[
            'tobacco.wisedat.invoice'
        ]
        start_page = (
            (self.invoice_sync_last_page or 0) + 1
        )
        synced = errors = 0
        for page_offset in range(
            self.SYNC_BATCH_PAGES
        ):
            page = start_page + page_offset
            endpoint = (
                f'/salesinvoices?limit='
                f'{self.API_PAGE_SIZE}'
                f'&page={page}'
            )
            if self.last_sync_date:
                endpoint += (
                    f'&modified_since='
                    f'{self.last_sync_date.isoformat()}'
                )
            try:
                response = (
                    self._api_call_with_retry(
                        'GET', endpoint
                    )
                )
            except Exception as e:
                _logger.error(
                    'API error facturas pag %d: %s',
                    page, e
                )
                self.sync_status = 'error'
                self.env.cr.commit()
                return False
            invoices = (
                response.get('salesinvoices', [])
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
            if not invoices:
                self._finish_invoice_sync(
                    synced, errors
                )
                return False
            if page == start_page:
                self.write({
                    'invoice_sync_total_pages':
                        total_pages,
                })
                self.env.cr.commit()
            wisedat_ids = [
                str(i.get('id')) for i in invoices
                if i.get('id')
            ]
            existing = Invoice.search([
                ('wisedat_id', 'in', wisedat_ids)
            ])
            existing_map = {
                i.wisedat_id: i for i in existing
            }
            create_vals_list = []
            for inv in invoices:
                try:
                    inv_id = str(inv.get('id'))
                    customer = False
                    cust_data = inv.get(
                        'customer', {}
                    )
                    if isinstance(cust_data, dict):
                        customer = self.env[
                            'res.partner'
                        ].search([
                            ('wisedat_id', '=',
                             cust_data.get('id'))
                        ], limit=1)
                    vals = {
                        'wisedat_id': inv_id,
                        'document_number': str(
                            inv.get(
                                'document_number',
                                ''
                            )
                        ),
                        'date': inv.get('date'),
                        'customer_id': (
                            customer.id
                            if customer else False
                        ),
                        'total': inv.get(
                            'total', 0
                        ),
                        'merchandise': inv.get(
                            'merchandise', 0
                        ),
                        'taxes': inv.get(
                            'taxes', 0
                        ),
                        'currency': str(
                            inv.get(
                                'currency', 'EUR'
                            )
                        ),
                        'wisedat_config_id':
                            self.id,
                        'raw_data': json.dumps(
                            inv, default=str
                        ),
                    }
                    existing_inv = (
                        existing_map.get(inv_id)
                    )
                    if existing_inv:
                        existing_inv.write(vals)
                    else:
                        create_vals_list.append(
                            vals
                        )
                    synced += 1
                except Exception as e:
                    errors += 1
                    _logger.error(
                        'Erro factura %s: %s',
                        inv.get('id'), e
                    )
            if create_vals_list:
                Invoice.create(create_vals_list)
            self.env.cr.commit()
            self.write({
                'invoice_sync_last_page': page,
                'invoice_sync_progress': (
                    (self.invoice_sync_progress
                     or 0) + synced
                ),
                'invoice_sync_errors': (
                    (self.invoice_sync_errors
                     or 0) + errors
                ),
            })
            self.env.cr.commit()
            self.env.invalidate_all()
            _logger.info(
                'StampChain: facturas pag %d/%d',
                page, total_pages
            )
            synced = errors = 0
            if page >= total_pages:
                self._finish_invoice_sync(0, 0)
                return False
        return True

    def _finish_invoice_sync(self, synced,
                              errors):
        total_synced = (
            (self.invoice_sync_progress or 0)
            + synced
        )
        total_errors = (
            (self.invoice_sync_errors or 0)
            + errors
        )
        self.write({
            'invoice_sync_last_page': 0,
            'invoice_sync_total_pages': 0,
            'invoice_sync_progress': 0,
            'invoice_sync_errors': 0,
            'last_sync_invoices': total_synced,
        })
        self.env.cr.commit()

    # ── Guia transporte ──────────────────────

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
                        ) else None
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
            ) else None
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
                'POST', '/movementofgoods',
                payload
            )
            wisedat_doc_id = response.get('id')
            picking.wisedat_doc_id = str(
                wisedat_doc_id
            )
            picking.message_post(
                body=(
                    f'Guia Wisedat: {wisedat_doc_id}'
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
        self.write({
            'sync_status': 'syncing',
            'sync_phase': 'categories',
            'sync_last_page': 0,
            'sync_progress': 0,
            'sync_errors': 0,
            'product_sync_last_page': 0,
            'product_sync_progress': 0,
            'product_sync_errors': 0,
            'invoice_sync_last_page': 0,
            'invoice_sync_progress': 0,
            'invoice_sync_errors': 0,
        })
        self.env.cr.commit()
        try:
            self._sync_categories()
            while self._sync_customers_batch():
                pass
            while self._sync_products_batch():
                pass
            self._sync_stock_by_warehouse()
            while self._sync_invoices_batch():
                pass
            self.write({
                'sync_status': 'ok',
                'sync_phase': 'idle',
                'last_sync_date':
                    fields.Datetime.now(),
            })
            self.env.cr.commit()
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'StampChain',
                    'message': 'Sync completa.',
                    'type': 'success',
                },
            }
        except Exception:
            self.sync_status = 'error'
            self.sync_phase = 'idle'
            self.env.cr.commit()
            raise

    def action_full_sync_background(self):
        self.ensure_one()
        self.write({
            'sync_status': 'syncing',
            'sync_phase': 'categories',
            'sync_last_page': 0,
            'sync_progress': 0,
            'sync_errors': 0,
            'product_sync_last_page': 0,
            'product_sync_progress': 0,
            'product_sync_errors': 0,
            'invoice_sync_last_page': 0,
            'invoice_sync_progress': 0,
            'invoice_sync_errors': 0,
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
                    'Sincronizacao agendada.'
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
                        f'Ligacao OK! '
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

    # ── Cron faseado (V7 watchdog) ───────────

    @api.model
    def _cron_sync(self):
        configs = self.search([
            ('active', '=', True)
        ])
        for config in configs:
            # V7: watchdog
            if (config.sync_phase != 'idle'
                    and config.sync_phase_started
                    and (fields.Datetime.now()
                         - config.sync_phase_started)
                    > timedelta(minutes=30)):
                _logger.warning(
                    'StampChain: fase %s presa. '
                    'Reset.',
                    config.sync_phase
                )
                config.write({
                    'sync_phase': 'idle',
                    'sync_status': 'error',
                })
                config.env.cr.commit()
            try:
                config.sync_status = 'syncing'
                config.env.cr.commit()
                # Fase 0: Categorias
                if config.sync_phase in (
                    'idle', 'categories'
                ):
                    config.write({
                        'sync_phase': 'categories',
                        'sync_phase_started':
                            fields.Datetime.now(),
                    })
                    config.env.cr.commit()
                    config._sync_categories()
                    config.write({
                        'sync_phase': 'customers',
                        'sync_phase_started':
                            fields.Datetime.now(),
                    })
                    config.env.cr.commit()
                # Fase 1: Clientes
                if (config.sync_phase == 'customers'
                        and config.sync_customers):
                    has_more = (
                        config._sync_customers_batch()
                    )
                    if has_more:
                        self._reschedule_cron(2)
                        return
                    config.write({
                        'sync_phase': 'products',
                        'sync_phase_started':
                            fields.Datetime.now(),
                    })
                    config.env.cr.commit()
                # Fase 2: Produtos
                if (config.sync_phase == 'products'
                        and config.sync_products):
                    has_more = (
                        config._sync_products_batch()
                    )
                    if has_more:
                        self._reschedule_cron(2)
                        return
                    config.write({
                        'sync_phase': 'stock',
                        'sync_phase_started':
                            fields.Datetime.now(),
                    })
                    config.env.cr.commit()
                # Fase 3: Stock
                if config.sync_phase == 'stock':
                    config._sync_stock_by_warehouse()
                    config.write({
                        'sync_phase': 'invoices',
                        'sync_phase_started':
                            fields.Datetime.now(),
                    })
                    config.env.cr.commit()
                # Fase 4: Facturas
                if (config.sync_phase == 'invoices'
                        and config.sync_invoices):
                    has_more = (
                        config._sync_invoices_batch()
                    )
                    if has_more:
                        self._reschedule_cron(2)
                        return
                # Concluido
                config.write({
                    'sync_status': 'ok',
                    'sync_phase': 'idle',
                    'sync_phase_started': False,
                    'last_sync_date':
                        fields.Datetime.now(),
                })
                config.env.cr.commit()
            except Exception as e:
                config.env.cr.rollback()
                _logger.error(
                    'Cron sync erro: %s', e
                )
                try:
                    config.write({
                        'sync_status': 'error',
                        'sync_phase': 'idle',
                        'sync_phase_started': False,
                    })
                    config.env.cr.commit()
                except Exception:
                    config.env.cr.rollback()

    def _reschedule_cron(self, minutes=2):
        cron = self.env.ref(
            'stamp_chain.ir_cron_wisedat_sync'
        )
        cron.nextcall = (
            fields.Datetime.now()
            + timedelta(minutes=minutes)
        )
