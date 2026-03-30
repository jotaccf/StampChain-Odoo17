# -*- coding: utf-8 -*-
from unittest.mock import patch, call, PropertyMock
from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError


class TestEntityTypeFilter(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.config = cls.env[
            'tobacco.wisedat.config'
        ].create({
            'name': 'Test Entity Filter',
            'api_url': 'http://wisedat-test:8080',
            'api_key': 'test-key-entity',
            'api_username': 'test-user',
            'api_password': 'test-pass',
            'sync_customers': True,
            'sync_products': True,
            'sync_orders': True,
            # B2B only defaults
            'sync_entity_cliente_final': False,
            'sync_entity_revendedor': True,
            'sync_entity_grossista': True,
            'sync_entity_distribuicao': True,
        })
        cls.wh = cls.env['stock.warehouse'].search(
            [], limit=1
        )
        cls.env['tobacco.warehouse.config'].create({
            'name': 'A1 Entity Test',
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

    def test_allowed_types_b2b_only(self):
        """Default config returns B2B types."""
        allowed = (
            self.config._get_allowed_entity_types()
        )
        self.assertIn('0002', allowed)
        self.assertIn('0003', allowed)
        self.assertIn('0004', allowed)
        self.assertNotIn('0001', allowed)

    def test_allowed_types_all(self):
        """All checkboxes returns all types."""
        self.config.sync_entity_cliente_final = True
        allowed = (
            self.config._get_allowed_entity_types()
        )
        self.assertEqual(len(allowed), 4)
        self.assertIn('0001', allowed)

    def test_allowed_types_none(self):
        """No checkboxes returns empty set."""
        self.config.write({
            'sync_entity_cliente_final': False,
            'sync_entity_revendedor': False,
            'sync_entity_grossista': False,
            'sync_entity_distribuicao': False,
        })
        allowed = (
            self.config._get_allowed_entity_types()
        )
        self.assertEqual(len(allowed), 0)

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
    def test_sync_skips_existing_b2c_partner(
        self, mock_api, mock_detail
    ):
        """Existing partner with entity_type 0001
        is skipped when B2C disabled."""
        self.config.sync_entity_cliente_final = (
            False
        )
        partner = self.env['res.partner'].create({
            'name': 'Cliente Final Existente',
            'wisedat_id': 9001,
            'wisedat_entity_type': '0001',
        })
        cust = {
            'id': 9001,
            'name': 'Nome Novo',
            'tax_id': '',
        }
        mock_api.return_value = {
            'customers': [cust],
            'pagination': {
                'number_pages': 1,
                'number_items': 1,
            },
        }
        mock_detail.return_value = {9001: cust}
        with self._mock_commit():
            self.config._sync_customers_batch()
        partner.invalidate_recordset()
        # Name should NOT have changed
        self.assertEqual(
            partner.name,
            'Cliente Final Existente'
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
    def test_sync_updates_allowed_type_partner(
        self, mock_api, mock_detail
    ):
        """Existing partner with entity_type 0002
        is updated during sync."""
        partner = self.env['res.partner'].create({
            'name': 'Revendedor Existente',
            'wisedat_id': 9002,
            'wisedat_entity_type': '0002',
        })
        cust = {
            'id': 9002,
            'name': 'Revendedor Actualizado',
            'tax_id': '',
        }
        mock_api.return_value = {
            'customers': [cust],
            'pagination': {
                'number_pages': 1,
                'number_items': 1,
            },
        }
        mock_detail.return_value = {9002: cust}
        with self._mock_commit():
            self.config._sync_customers_batch()
        partner.invalidate_recordset()
        self.assertEqual(
            partner.name,
            'Revendedor Actualizado'
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
    def test_sync_fetches_full_details(
        self, mock_api, mock_detail
    ):
        """Sync automatically fetches full
        customer details via parallel GETs."""
        mock_api.return_value = {
            'customers': [{
                'id': 9003,
                'name': 'Novo Cliente',
                'tax_id': '',
            }],
            'pagination': {
                'number_pages': 1,
                'number_items': 1,
            },
        }
        mock_detail.return_value = {
            9003: {
                'id': 9003,
                'name': 'Novo Cliente Completo',
                'tax_id': '',
                'email': 'novo@teste.pt',
                'phone': '210000099',
                'entity_type': '0003',
                'billing_address': {
                    'street': 'Rua Nova 1',
                    'city': 'Porto',
                    'postal_code': '4000-001',
                },
            },
        }
        with self._mock_commit():
            self.config._sync_customers_batch()
        partner = self.env['res.partner'].search([
            ('wisedat_id', '=', 9003)
        ], limit=1)
        self.assertTrue(partner)
        self.assertEqual(
            partner.name, 'Novo Cliente Completo'
        )
        self.assertEqual(
            partner.email, 'novo@teste.pt'
        )
        self.assertEqual(
            partner.street, 'Rua Nova 1'
        )
        self.assertEqual(
            partner.wisedat_entity_type, '0003'
        )
        self.assertTrue(
            partner.wisedat_entity_type_checked
        )

    @patch(
        'odoo.addons.stamp_chain.models'
        '.wisedat_sync.WisedatConfig'
        '._fetch_customers_detail_batch'
    )
    def test_enrich_updates_all_fields(
        self, mock_detail
    ):
        """action_classify_entity_types enriches
        partners with full Wisedat data."""
        p1 = self.env['res.partner'].create({
            'name': 'Sem Dados',
            'wisedat_id': 9010,
        })
        mock_detail.return_value = {
            9010: {
                'id': 9010,
                'name': 'Com Dados',
                'email': 'dados@teste.pt',
                'entity_type': '0002',
                'billing_address': {
                    'street': 'Rua Enriquecida 5',
                    'city': 'Braga',
                    'postal_code': '4700-001',
                },
            },
        }
        with self._mock_commit():
            result = (
                self.config
                .action_classify_entity_types()
            )
        self.assertEqual(
            result['params']['type'], 'success'
        )
        p1.invalidate_recordset()
        self.assertEqual(
            p1.email, 'dados@teste.pt'
        )
        self.assertEqual(
            p1.street, 'Rua Enriquecida 5'
        )
        self.assertEqual(
            p1.wisedat_entity_type, '0002'
        )
        self.assertTrue(
            p1.wisedat_entity_type_checked
        )

    def test_entity_type_field_on_partner(self):
        """wisedat_entity_type field stores
        correctly on res.partner."""
        partner = self.env['res.partner'].create({
            'name': 'Test Entity Field',
            'wisedat_entity_type': '0003',
        })
        self.assertEqual(
            partner.wisedat_entity_type, '0003'
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
    def test_sync_full_customer_fields(
        self, mock_api, mock_detail
    ):
        """Sync maps all Wisedat customer
        fields via automatic detail fetch."""
        full_data = {
            'id': 9050,
            'code': 'CLI050',
            'name': 'Empresa Completa',
            'tax_id': '999999990',
            'email': 'geral@completa.pt',
            'phone': '210000001',
            'website': 'www.completa.pt',
            'notes': 'Obs de teste',
            'entity_type': '0002',
            'country': {
                'iso_3166_1': 'PT',
                'name': 'Portugal',
            },
            'payment_condition': {
                'id': 1,
                'description': '30 dias',
            },
            'payment_method': {
                'id': 2,
                'description': 'Transferencia',
            },
            'currency': {
                'id': 1,
                'description': 'Euro',
                'symbol': 'EUR',
            },
            'billing_address': {
                'street': 'Rua Teste 100',
                'city': 'Lisboa',
                'postal_code': '1000-001',
                'postal_code_location':
                    'Lisboa',
                'region': 'Lisboa',
                'country': {
                    'iso_3166_1': 'PT',
                },
            },
        }
        mock_api.return_value = {
            'customers': [{
                'id': 9050,
                'name': 'Empresa Completa',
                'tax_id': '999999990',
            }],
            'pagination': {
                'number_pages': 1,
                'number_items': 1,
            },
        }
        mock_detail.return_value = {
            9050: full_data,
        }
        with self._mock_commit():
            self.config._sync_customers_batch()
        partner = self.env['res.partner'].search([
            ('wisedat_id', '=', 9050)
        ], limit=1)
        self.assertTrue(partner)
        self.assertEqual(partner.ref, 'CLI050')
        self.assertEqual(
            partner.email, 'geral@completa.pt'
        )
        self.assertEqual(
            partner.phone, '210000001'
        )
        self.assertEqual(
            partner.website, 'www.completa.pt'
        )
        self.assertEqual(
            partner.comment, 'Obs de teste'
        )
        self.assertEqual(
            partner.street, 'Rua Teste 100'
        )
        self.assertEqual(
            partner.zip, '1000-001'
        )
        self.assertEqual(
            partner.wisedat_payment_condition,
            '30 dias'
        )
        self.assertEqual(
            partner.wisedat_payment_method,
            'Transferencia'
        )
        self.assertEqual(
            partner.wisedat_currency, 'Euro'
        )
        self.assertEqual(
            partner.wisedat_entity_type, '0002'
        )
