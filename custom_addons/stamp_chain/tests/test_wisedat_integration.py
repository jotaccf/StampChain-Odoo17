# -*- coding: utf-8 -*-
from unittest.mock import patch
from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError
from odoo import fields


class TestWisedatIntegration(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.config = cls.env[
            'tobacco.wisedat.config'
        ].create({
            'name': 'Test Wisedat',
            'api_url': 'http://wisedat-test:8080',
            'api_key': 'test-key-abc123',
            'api_username': 'test-user',
            'api_password': 'test-pass',
            'sync_customers': True,
            'sync_products': True,
            'sync_orders': True,
        })
        cls.wh = cls.env['stock.warehouse'].search(
            [], limit=1
        )
        cls.env['tobacco.warehouse.config'].create({
            'name': 'A1 Test Map',
            'warehouse_id': cls.wh.id,
            'wisedat_warehouse_code': 'A1',
            'warehouse_type': 'main_warehouse',
            'wisedat_config_id': cls.config.id,
        })

    def _mock_commit(self):
        """Neutraliza cr.commit() para nao
        destruir o savepoint do TransactionCase."""
        return patch.object(
            type(self.env.cr), 'commit',
            lambda *a: None
        )

    @patch(
        'odoo.addons.stamp_chain.models'
        '.wisedat_sync.WisedatConfig'
        '._fetch_customers_detail_batch'
    )
    @patch(
        'odoo.addons.stamp_chain.models'
        '.wisedat_sync.WisedatConfig'
        '._api_call_with_retry'
    )
    def test_sync_customers_creates_partner(
        self, mock_api, mock_detail
    ):
        cust = {
            'id': 8001,
            'name': 'Distribuidora Norte SA',
            'tax_id': '501234567',
            'email': 'norte@dist.pt',
            'phone': '220000001',
            'billing_address': {
                'street': 'Rua do Norte 1',
                'city': 'Porto',
                'postal_code': '4000-001',
            },
        }
        mock_api.return_value = {
            'customers': [cust],
            'pagination': {
                'number_pages': 1,
                'number_items': 1,
            },
        }
        mock_detail.return_value = {8001: cust}
        with self._mock_commit():
            self.config._sync_customers_batch()
        partner = self.env['res.partner'].search(
            [('wisedat_id', '=', 8001)], limit=1
        )
        self.assertTrue(partner)
        self.assertEqual(
            partner.name, 'Distribuidora Norte SA'
        )
        self.assertEqual(
            partner.email, 'norte@dist.pt'
        )

    @patch(
        'odoo.addons.stamp_chain.models'
        '.wisedat_sync.WisedatConfig'
        '._fetch_customers_detail_batch'
    )
    @patch(
        'odoo.addons.stamp_chain.models'
        '.wisedat_sync.WisedatConfig'
        '._api_call_with_retry'
    )
    def test_sync_customers_wisedat_is_master(
        self, mock_api, mock_detail
    ):
        partner = self.env['res.partner'].create({
            'name': 'Nome Antigo',
            'wisedat_id': 8002,
        })
        cust = {
            'id': 8002,
            'name': 'Nome Actualizado Wisedat',
            'tax_id': '509876543',
        }
        mock_api.return_value = {
            'customers': [cust],
            'pagination': {
                'number_pages': 1,
                'number_items': 1,
            },
        }
        mock_detail.return_value = {8002: cust}
        with self._mock_commit():
            self.config._sync_customers_batch()
        partner.invalidate_recordset()
        self.assertEqual(
            partner.name, 'Nome Actualizado Wisedat'
        )

    @patch(
        'odoo.addons.stamp_chain.models'
        '.wisedat_sync.WisedatConfig'
        '._fetch_customers_detail_batch'
    )
    @patch(
        'odoo.addons.stamp_chain.models'
        '.wisedat_sync.WisedatConfig'
        '._api_call_with_retry'
    )
    def test_sync_customers_finds_by_vat(
        self, mock_api, mock_detail
    ):
        partner = self.env['res.partner'].create({
            'name': 'Por NIF',
            'vat': 'PT999999990',
        })
        cust = {
            'id': 8003,
            'name': 'Por NIF',
            'tax_id': 'PT999999990',
        }
        mock_api.return_value = {
            'customers': [cust],
            'pagination': {
                'number_pages': 1,
                'number_items': 1,
            },
        }
        mock_detail.return_value = {8003: cust}
        with self._mock_commit():
            self.config._sync_customers_batch()
        partner.invalidate_recordset()
        self.assertEqual(partner.wisedat_id, 8003)

    @patch(
        'odoo.addons.stamp_chain.models'
        '.wisedat_sync.WisedatConfig'
        '._fetch_products_detail_batch'
    )
    @patch(
        'odoo.addons.stamp_chain.models'
        '.wisedat_sync.WisedatConfig'
        '._api_call_with_retry'
    )
    def test_sync_products_creates_product(
        self, mock_api, mock_detail
    ):
        prod = {
            'id': 5001,
            'name': 'TAB-NEW-001',
            'description': 'Tabaco Novo',
            'price': 12.50,
            'active': True,
            'barcode': '5601234567890',
            'tax': {
                'id': 1,
                'value': 23,
                'description': 'IVA 23%',
            },
            'unit': {
                'id': 1,
                'description': 'Unidade',
            },
        }
        mock_api.return_value = {
            'products': [prod],
            'pagination': {
                'number_pages': 1,
                'number_items': 1,
            },
        }
        mock_detail.return_value = {5001: prod}
        with self._mock_commit():
            self.config._sync_products_batch()
        product = self.env['product.product'].search(
            [('default_code', '=', 'TAB-NEW-001')],
            limit=1
        )
        self.assertTrue(product)
        self.assertEqual(
            product.barcode, '5601234567890'
        )
        self.assertEqual(
            product.wisedat_tax_description,
            'IVA 23%'
        )

    @patch(
        'odoo.addons.stamp_chain.models'
        '.wisedat_sync.WisedatConfig'
        '._fetch_products_detail_batch'
    )
    @patch(
        'odoo.addons.stamp_chain.models'
        '.wisedat_sync.WisedatConfig'
        '._api_call_with_retry'
    )
    def test_sync_products_updates_existing(
        self, mock_api, mock_detail
    ):
        product = self.env['product.product'].create({
            'name': 'Existente',
            'default_code': 'TAB-EXIST-001',
            'list_price': 5.00,
        })
        prod = {
            'id': 5002,
            'name': 'TAB-EXIST-001',
            'description': 'Actualizado',
            'price': 8.75,
            'active': True,
        }
        mock_api.return_value = {
            'products': [prod],
            'pagination': {
                'number_pages': 1,
                'number_items': 1,
            },
        }
        mock_detail.return_value = {5002: prod}
        with self._mock_commit():
            self.config._sync_products_batch()
        product.invalidate_recordset()
        self.assertAlmostEqual(
            product.list_price, 8.75
        )

    @patch(
        'odoo.addons.stamp_chain.models'
        '.wisedat_sync.WisedatConfig'
        '._api_call_with_retry'
    )
    def test_api_error_sets_error_status(
        self, mock_api
    ):
        mock_api.side_effect = Exception(
            'Connection refused'
        )
        with self._mock_commit():
            self.config._sync_customers_batch()
        self.assertEqual(
            self.config.sync_status, 'error'
        )

    @patch(
        'odoo.addons.stamp_chain.models'
        '.wisedat_sync.WisedatConfig'
        '._fetch_customers_detail_batch'
    )
    @patch(
        'odoo.addons.stamp_chain.models'
        '.wisedat_sync.WisedatConfig'
        '._api_call_with_retry'
    )
    @patch(
        'odoo.addons.stamp_chain.models'
        '.wisedat_sync.WisedatConfig._api_call'
    )
    def test_full_sync_updates_status(
        self, mock_api, mock_api_retry,
        mock_detail
    ):
        mock_api.return_value = {
            'customers': [],
            'items': [],
        }
        mock_api_retry.return_value = {
            'customers': [],
            'categories': [],
            'products': [],
            'pagination': {
                'number_pages': 1,
                'number_items': 0,
            },
        }
        mock_detail.return_value = {}
        with self._mock_commit():
            self.config.action_full_sync()
        self.assertIn(
            self.config.sync_status, ('ok', 'error')
        )

    def test_warehouse_not_mapped_raises_error(self):
        unmapped = self.env['stock.warehouse'].create({
            'name': 'Unmapped',
            'code': 'UNM',
        })
        with self.assertRaises(UserError):
            self.config._get_warehouse_code(unmapped.id)
