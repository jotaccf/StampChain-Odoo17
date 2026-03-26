# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError
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
    sync_orders = fields.Boolean(
        string='Criar Encomendas ECL',
        default=True,
        help='Cria encomenda no Wisedat ao validar '
             'expedicao (POST /orders)',
    )
    sync_frequency = fields.Selection([
        ('realtime', 'Tempo Real'),
        ('hourly', 'Horaria'),
        ('daily', 'Diaria'),
    ], string='Frequencia',
       default='realtime',
    )

    # — Filtro tipo entidade (sync clientes) —
    sync_entity_cliente_final = fields.Boolean(
        string='Cliente Final (0001)',
        default=False,
        help='Sincronizar clientes do tipo '
             'Cliente Final.',
    )
    sync_entity_revendedor = fields.Boolean(
        string='Revendedor (0002)',
        default=True,
        help='Sincronizar clientes do tipo '
             'Revendedor.',
    )
    sync_entity_grossista = fields.Boolean(
        string='Grossista (0003)',
        default=True,
        help='Sincronizar clientes do tipo '
             'Grossista.',
    )
    sync_entity_distribuicao = fields.Boolean(
        string='Distribuicao (0004)',
        default=True,
        help='Sincronizar clientes do tipo '
             'Distribuicao.',
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

    # — Controlo de paragem —
    sync_stop_requested = fields.Boolean(
        string='Paragem Solicitada',
        default=False,
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
    sync_total_records = fields.Integer(
        default=0, readonly=True)
    sync_percent = fields.Integer(
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
    product_sync_total_records = fields.Integer(
        default=0, readonly=True)
    product_sync_percent = fields.Integer(
        default=0, readonly=True)
    last_sync_products = fields.Integer(
        default=0, readonly=True)


    # — Series documentais —
    series_ids = fields.One2many(
        'tobacco.wisedat.series',
        'wisedat_config_id',
        string='Series Documentais',
    )
    order_series_id = fields.Many2one(
        'tobacco.wisedat.series',
        string='Serie Encomendas',
        domain="[('wisedat_config_id', '=', id),"
               " ('is_active', '=', True)]",
        help='Serie a utilizar na criacao de '
             'encomendas ECL no Wisedat.',
    )
    last_sync_series_date = fields.Datetime(
        string='Ultima Sync Series',
        readonly=True,
    )

    # — Fase cron —
    sync_phase = fields.Selection([
        ('idle', 'Parado'),
        ('categories', 'Categorias'),
        ('customers', 'Clientes'),
        ('products', 'Produtos'),
        ('stock', 'Stock'),
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

    # ── Filtro entidade ──────────────────────

    def _get_allowed_entity_types(self):
        """Retorna set de tipos de entidade
        permitidos para sync, baseado nos
        checkboxes do config."""
        allowed = set()
        if self.sync_entity_cliente_final:
            allowed.add('0001')
        if self.sync_entity_revendedor:
            allowed.add('0002')
        if self.sync_entity_grossista:
            allowed.add('0003')
        if self.sync_entity_distribuicao:
            allowed.add('0004')
        return allowed

    def _fetch_customer_entity_type(
        self, wisedat_customer_id
    ):
        """Faz GET /customers?id={id} para obter
        o entity_type de um cliente individual.
        Retorna o codigo (str) ou False."""
        try:
            data = self._api_call_with_retry(
                'GET',
                f'/customers?id={wisedat_customer_id}'
            )
            # Normalizar: pode vir como dict
            # directo ou dentro de 'customer'
            customer = (
                data.get('customer', data)
                if isinstance(data, dict)
                else data
            )
            if isinstance(customer, dict):
                raw = customer.get(
                    'entity_type',
                    customer.get('entitytype', '')
                )
                return str(raw).strip() if raw else False
            return False
        except Exception as e:
            _logger.warning(
                'Erro ao obter entity_type '
                'cliente %s: %s',
                wisedat_customer_id, e
            )
            return False

    def action_classify_entity_types(self):
        """Botao 'Classificar Entidades' —
        faz GET individual para cada parceiro
        sem wisedat_entity_type definido."""
        self.ensure_one()
        partners = self.env['res.partner'].search([
            ('wisedat_id', '!=', 0),
            ('wisedat_entity_type', '=', False),
        ])
        classified = 0
        for partner in partners:
            entity_type = (
                self._fetch_customer_entity_type(
                    partner.wisedat_id
                )
            )
            if entity_type:
                partner.wisedat_entity_type = (
                    entity_type
                )
                classified += 1
            if classified % 50 == 0:
                self.env.cr.commit()
        self.env.cr.commit()
        _logger.info(
            'StampChain: %d parceiros classificados',
            classified
        )
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'StampChain',
                'message': (
                    f'{classified} clientes '
                    f'classificados com sucesso.'
                ),
                'type': 'success',
            },
        }

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
        # VAT prefix fix — Wisedat envia sem prefixo
        raw_vat = (
            cust_data.get('tax_id') or ''
        ).strip()
        if raw_vat:
            if not raw_vat[:2].isalpha():
                raw_vat = country_code + raw_vat
        else:
            raw_vat = False

        return {
            'name': cust_data.get('name', ''),
            'vat': raw_vat,
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
                total_records = pagination.get(
                    'number_items', 0
                )
                self.write({
                    'sync_total_pages': total_pages,
                    'sync_total_records': total_records,
                })
                self.env.cr.commit()
            # Tipos de entidade permitidos
            allowed_types = (
                self._get_allowed_entity_types()
            )
            filtering_active = bool(allowed_types)
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
            skipped = 0
            for cust in customers:
                try:
                    cust_id = cust.get('id')
                    partner = existing_map.get(
                        cust_id
                    )
                    # Filtro entidade: parceiro
                    # existente com tipo conhecido
                    if (filtering_active
                            and partner
                            and partner
                            .wisedat_entity_type
                            and partner
                            .wisedat_entity_type
                            not in allowed_types):
                        skipped += 1
                        continue
                    vals = (
                        self._prepare_customer_vals(
                            cust
                        )
                    )
                    if (not partner
                            and vals.get('vat')):
                        partner = Partner.search([
                            ('vat', '=',
                             vals['vat'])
                        ], limit=1)
                    if partner:
                        # Parceiro existente com tipo
                        # conhecido e fora do filtro
                        if (filtering_active
                                and partner
                                .wisedat_entity_type
                                and partner
                                .wisedat_entity_type
                                not in allowed_types):
                            skipped += 1
                            continue
                        try:
                            partner.write(vals)
                        except (ValidationError, Exception) as e:
                            _logger.warning(
                                'VAT invalido %s, '
                                'sync sem VAT: %s',
                                vals.get('vat'), e
                            )
                            vals['vat'] = False
                            partner.write(vals)
                    else:
                        # Cliente novo: verificar
                        # entity_type via GET
                        # individual antes de criar
                        if filtering_active and cust_id:
                            etype = (
                                self
                                ._fetch_customer_entity_type(
                                    cust_id
                                )
                            )
                            if etype:
                                vals[
                                    'wisedat_entity_type'
                                ] = etype
                                if (etype
                                        not in
                                        allowed_types):
                                    skipped += 1
                                    _logger.debug(
                                        'Cliente %s '
                                        'tipo %s '
                                        'ignorado',
                                        cust_id, etype
                                    )
                                    continue
                        create_vals_list.append(vals)
                    synced += 1
                except Exception as e:
                    errors += 1
                    _logger.error(
                        'Erro cliente %s: %s',
                        cust.get('id'), e
                    )
            if skipped:
                _logger.info(
                    'StampChain: %d clientes '
                    'ignorados (tipo entidade)',
                    skipped
                )
            if create_vals_list:
                try:
                    Partner.create(create_vals_list)
                except (ValidationError, Exception):
                    _logger.warning(
                        'Batch create falhou, '
                        'fallback individual'
                    )
                    for single_vals in create_vals_list:
                        try:
                            Partner.create(single_vals)
                        except (ValidationError, Exception) as e:
                            _logger.warning(
                                'VAT invalido %s, '
                                'criar sem VAT: %s',
                                single_vals.get('vat'),
                                e
                            )
                            try:
                                single_vals['vat'] = False
                                Partner.create(single_vals)
                            except Exception as e2:
                                errors += 1
                                _logger.error(
                                    'Erro criar cliente '
                                    '%s: %s',
                                    single_vals.get(
                                        'wisedat_id'
                                    ), e2
                                )
            self.env.cr.commit()
            new_progress = (
                (self.sync_progress or 0) + synced
            )
            total_rec = self.sync_total_records or 1
            pct = min(
                int(new_progress * 100 / total_rec),
                100
            ) if total_rec > 0 else 0
            self.write({
                'sync_last_page': page,
                'sync_progress': new_progress,
                'sync_errors': (
                    (self.sync_errors or 0)
                    + errors
                ),
                'sync_percent': pct,
            })
            self.env.cr.commit()
            self.env.invalidate_all()
            if self._check_stop_requested():
                return False
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
            'sync_total_records': 0,
            'sync_percent': 0,
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
        if not partner and vals.get('vat'):
            partner = Partner.search([
                ('vat', '=', vals['vat'])
            ], limit=1)
        try:
            if partner:
                partner.write(vals)
            else:
                Partner.create(vals)
        except (ValidationError, Exception) as e:
            _logger.warning(
                'VAT invalido %s, retry sem VAT: %s',
                vals.get('vat'), e
            )
            vals['vat'] = False
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
                total_records = pagination.get(
                    'number_items', 0
                )
                self.write({
                    'product_sync_total_pages':
                        total_pages,
                    'product_sync_total_records':
                        total_records,
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
            new_progress = (
                (self.product_sync_progress or 0)
                + synced
            )
            total_rec = (
                self.product_sync_total_records or 1
            )
            pct = min(
                int(new_progress * 100 / total_rec),
                100
            ) if total_rec > 0 else 0
            self.write({
                'product_sync_last_page': page,
                'product_sync_progress': new_progress,
                'product_sync_errors': (
                    (self.product_sync_errors
                     or 0) + errors
                ),
                'product_sync_percent': pct,
            })
            self.env.cr.commit()
            self.env.invalidate_all()
            if self._check_stop_requested():
                return False
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
            'product_sync_total_records': 0,
            'product_sync_percent': 0,
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

    # ── Series documentais ───────────────────

    def _sync_series(self):
        """Fetch series from Wisedat GET /series
        and create/update local records."""
        self.ensure_one()
        _logger.info('StampChain: sync series Wisedat')
        try:
            response = self._api_call_with_retry(
                'GET', '/series'
            )
        except Exception as e:
            _logger.error(
                'Erro ao obter series Wisedat: %s', e
            )
            raise UserError(
                f'Erro ao obter series do Wisedat: '
                f'{str(e)}'
            )
        # Normalise response to list
        series_list = (
            response.get('series', [])
            if isinstance(response, dict)
            else response
            if isinstance(response, list)
            else []
        )
        if not series_list:
            _logger.warning(
                'StampChain: API /series devolveu '
                '0 series'
            )
        Series = self.env['tobacco.wisedat.series']
        existing = Series.search([
            ('wisedat_config_id', '=', self.id)
        ])
        existing_map = {
            s.wisedat_id: s for s in existing
        }
        synced_ids = set()
        create_vals_list = []
        for s in series_list:
            wisedat_id = str(s.get('id', ''))
            if not wisedat_id:
                continue
            vals = {
                'wisedat_id': wisedat_id,
                'name': str(
                    s.get('name',
                           s.get('description', ''))
                ),
                'description': str(
                    s.get('description', '')
                ),
                'is_active': bool(
                    s.get('active', True)
                ),
                'wisedat_config_id': self.id,
                'last_sync_date':
                    fields.Datetime.now(),
            }
            existing_rec = existing_map.get(
                wisedat_id
            )
            if existing_rec:
                existing_rec.write(vals)
            else:
                create_vals_list.append(vals)
            synced_ids.add(wisedat_id)
        if create_vals_list:
            Series.create(create_vals_list)
        # Deactivate series removed from Wisedat
        removed = existing.filtered(
            lambda s: s.wisedat_id not in synced_ids
        )
        if removed:
            removed.write({'is_active': False})
        # Clear selection if chosen series was
        # deactivated
        if (self.order_series_id
                and not
                self.order_series_id
                .is_active):
            self.order_series_id = False
        self.last_sync_series_date = (
            fields.Datetime.now()
        )
        self.env.cr.commit()
        _logger.info(
            'StampChain: %d series sincronizadas',
            len(synced_ids)
        )

    def action_sync_series(self):
        """Button 'Obter Series' handler."""
        self.ensure_one()
        self._sync_series()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'StampChain',
                'message': (
                    'Series sincronizadas com '
                    'sucesso.'
                ),
                'type': 'success',
            },
        }

    def _validate_order_series(self):
        """Validate that a series is configured
        and active before creating a transport
        guide. Returns the series wisedat_id."""
        self.ensure_one()
        if not self.order_series_id:
            raise UserError(
                'Serie para encomendas nao '
                'configurada.\n'
                'Aceda a Configuracoes > Wisedat e '
                'seleccione uma serie na aba '
                '"Series Documentais".'
            )
        series = self.order_series_id
        if not series.is_active:
            raise UserError(
                f'A serie "{series.display_name}" '
                f'esta inactiva no Wisedat.\n'
                f'Sincronize as series (botao '
                f'"Obter Series") e seleccione '
                f'uma serie activa.'
            )
        return series.wisedat_id

    # ── Encomenda ECL ────────────────────────

    def _create_wisedat_order(
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
        # Validate series is configured
        series_id = (
            self._validate_order_series()
        )
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
                # Determine tax rate from order
                # line fiscal position
                tax_rate = 0.0
                if order_line and order_line.tax_id:
                    tax = order_line.tax_id[:1]
                    tax_rate = (
                        tax.amount
                        if tax.amount_type == 'percent'
                        else 0.0
                    )
                # Determine discount
                discount = 0.0
                if order_line:
                    discount = (
                        order_line.discount or 0.0
                    )
                lines.append({
                    'id': (
                        product.wisedat_id
                        if hasattr(
                            product, 'wisedat_id'
                        ) and product.wisedat_id
                        else None
                    ),
                    'description': product.name,
                    'quantity': move.quantity_done,
                    'price': (
                        order_line.price_unit
                        if order_line else 0
                    ),
                    'tax': tax_rate,
                    'discount': discount,
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
            'series': series_id,
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
            response = self._api_call_with_retry(
                'POST', '/orders',
                payload
            )
            wisedat_doc_id = response.get('id')
            picking.wisedat_doc_id = str(
                wisedat_doc_id
            )
            series_name = (
                self.order_series_id
                .display_name
            )
            picking.message_post(
                body=(
                    f'Encomenda ECL Wisedat: {wisedat_doc_id}'
                    f' (Serie: {series_name})'
                ),
            )
            return wisedat_doc_id
        except Exception as e:
            _logger.error(
                'Erro Encomenda Wisedat: %s', e
            )
            raise

    # ── Actions ──────────────────────────────

    def action_full_sync(self):
        self.write({
            'sync_status': 'syncing',
            'sync_phase': 'categories',
            'sync_stop_requested': False,
            'sync_last_page': 0,
            'sync_progress': 0,
            'sync_errors': 0,
            'sync_total_records': 0,
            'sync_percent': 0,
            'product_sync_last_page': 0,
            'product_sync_progress': 0,
            'product_sync_errors': 0,
            'product_sync_total_records': 0,
            'product_sync_percent': 0,
        })
        self.env.cr.commit()
        try:
            self._sync_categories()
            while self._sync_customers_batch():
                pass
            while self._sync_products_batch():
                pass
            self._sync_stock_by_warehouse()
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
            'sync_stop_requested': False,
            'sync_last_page': 0,
            'sync_progress': 0,
            'sync_errors': 0,
            'sync_total_records': 0,
            'sync_percent': 0,
            'product_sync_last_page': 0,
            'product_sync_progress': 0,
            'product_sync_errors': 0,
            'product_sync_total_records': 0,
            'product_sync_percent': 0,
        })
        cron = self.env.ref(
            'stamp_chain.ir_cron_wisedat_sync'
        )
        cron.write({
            'active': True,
            'nextcall': fields.Datetime.now(),
        })
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

    def action_reset_sync_status(self):
        """Reset manual do estado de sync.
        Permite desbloquear quando fica preso
        em 'syncing' por erro ou timeout."""
        self.ensure_one()
        self.write({
            'sync_status': 'error',
            'sync_phase': 'idle',
            'sync_phase_started': False,
            'sync_stop_requested': False,
            'sync_last_page': 0,
            'sync_progress': 0,
            'sync_errors': 0,
            'sync_total_records': 0,
            'sync_percent': 0,
            'product_sync_last_page': 0,
            'product_sync_progress': 0,
            'product_sync_errors': 0,
            'product_sync_total_records': 0,
            'product_sync_percent': 0,
        })
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'StampChain',
                'message': (
                    'Estado de sync resetado. '
                    'Pode relançar a sync.'
                ),
                'type': 'warning',
            },
        }

    def action_stop_sync(self):
        """Solicita paragem da sync.
        O batch loop verifica a flag a cada
        pagina e para graciosamente."""
        self.ensure_one()
        self.write({
            'sync_stop_requested': True,
        })
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'StampChain',
                'message': (
                    'Paragem solicitada. '
                    'A sync para apos a pagina '
                    'actual ser concluida.'
                ),
                'type': 'warning',
            },
        }

    def _check_stop_requested(self):
        """Verifica se paragem foi solicitada.
        Chamado a cada pagina nos batch loops.
        Retorna True se deve parar."""
        self.env.invalidate_all()
        self_fresh = self.env[
            'tobacco.wisedat.config'
        ].browse(self.id)
        if self_fresh.sync_stop_requested:
            _logger.info(
                'StampChain: paragem solicitada '
                'pelo utilizador.'
            )
            self_fresh.write({
                'sync_stop_requested': False,
                'sync_status': 'ok',
                'sync_phase': 'idle',
                'sync_phase_started': False,
            })
            self_fresh.env.cr.commit()
            return True
        return False

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
                # Concluido (apos stock)
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
        # Desactivar cron quando nao ha mais
        # trabalho (padrao liga/desliga)
        all_idle = all(
            c.sync_phase == 'idle'
            for c in configs
        )
        if all_idle:
            try:
                cron = self.env.ref(
                    'stamp_chain.ir_cron_wisedat_sync'
                )
                cron.active = False
                self.env.cr.commit()
            except Exception:
                pass

    def _reschedule_cron(self, minutes=2):
        cron = self.env.ref(
            'stamp_chain.ir_cron_wisedat_sync'
        )
        cron.nextcall = (
            fields.Datetime.now()
            + timedelta(minutes=minutes)
        )
