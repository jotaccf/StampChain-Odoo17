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
        '.wisedat_sync.WisedatConfig._api_call'
    )
    def test_sync_customers_creates_partner(
        self, mock_api
    ):
        mock_api.return_value = {
            'customers': [{
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
            }],
        }
        synced, errors = self.config._sync_customers()
        self.assertEqual(synced, 1)
        self.assertEqual(errors, 0)
        partner = self.env['res.partner'].search(
            [('wisedat_id', '=', 8001)]
        )
        self.assertTrue(partner)
        self.assertEqual(
            partner.name, 'Distribuidora Norte SA'
        )

    @patch(
        'odoo.addons.stamp_chain.models'
        '.wisedat_sync.WisedatConfig._api_call'
    )
    def test_sync_customers_wisedat_is_master(
        self, mock_api
    ):
        partner = self.env['res.partner'].create({
            'name': 'Nome Antigo',
            'wisedat_id': 8002,
        })
        mock_api.return_value = {
            'customers': [{
                'id': 8002,
                'name': 'Nome Actualizado Wisedat',
                'tax_id': '509876543',
            }],
        }
        self.config._sync_customers()
        partner.invalidate_recordset()
        self.assertEqual(
            partner.name, 'Nome Actualizado Wisedat'
        )

    @patch(
        'odoo.addons.stamp_chain.models'
        '.wisedat_sync.WisedatConfig._api_call'
    )
    def test_sync_customers_finds_by_vat(
        self, mock_api
    ):
        partner = self.env['res.partner'].create({
            'name': 'Por NIF',
            'vat': 'PT500000001',
        })
        mock_api.return_value = {
            'customers': [{
                'id': 8003,
                'name': 'Por NIF',
                'tax_id': 'PT500000001',
            }],
        }
        self.config._sync_customers()
        partner.invalidate_recordset()
        self.assertEqual(partner.wisedat_id, 8003)

    @patch(
        'odoo.addons.stamp_chain.models'
        '.wisedat_sync.WisedatConfig._api_call'
    )
    def test_sync_products_creates_product(
        self, mock_api
    ):
        mock_api.return_value = {
            'items': [{
                'code': 'TAB-NEW-001',
                'name': 'Tabaco Novo',
                'price': 12.50,
            }],
        }
        synced, errors = self.config._sync_products()
        self.assertEqual(synced, 1)
        product = self.env['product.product'].search(
            [('default_code', '=', 'TAB-NEW-001')]
        )
        self.assertTrue(product)

    @patch(
        'odoo.addons.stamp_chain.models'
        '.wisedat_sync.WisedatConfig._api_call'
    )
    def test_sync_products_updates_existing(
        self, mock_api
    ):
        product = self.env['product.product'].create({
            'name': 'Existente',
            'default_code': 'TAB-EXIST-001',
            'list_price': 5.00,
        })
        mock_api.return_value = {
            'items': [{
                'code': 'TAB-EXIST-001',
                'name': 'Actualizado',
                'price': 8.75,
            }],
        }
        self.config._sync_products()
        product.invalidate_recordset()
        self.assertAlmostEqual(product.list_price, 8.75)

    @patch(
        'odoo.addons.stamp_chain.models'
        '.wisedat_sync.WisedatConfig._api_call'
    )
    def test_api_error_raises_user_error(
        self, mock_api
    ):
        mock_api.side_effect = UserError('Connection refused')
        with self.assertRaises(UserError):
            self.config._sync_customers()

    @patch(
        'odoo.addons.stamp_chain.models'
        '.wisedat_sync.WisedatConfig._api_call'
    )
    def test_full_sync_updates_status(
        self, mock_api
    ):
        mock_api.return_value = {
            'customers': [],
            'items': [],
        }
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
