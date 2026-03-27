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
        '._api_call_with_retry'
    )
    def test_sync_skips_existing_b2c_partner(
        self, mock_api
    ):
        """Existing partner with entity_type 0001
        is skipped during sync."""
        partner = self.env['res.partner'].create({
            'name': 'Cliente Final Existente',
            'wisedat_id': 9001,
            'wisedat_entity_type': '0001',
        })
        mock_api.return_value = {
            'customers': [{
                'id': 9001,
                'name': 'Nome Novo',
                'tax_id': '',
            }],
            'pagination': {
                'number_pages': 1,
                'number_items': 1,
            },
        }
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
        '._api_call_with_retry'
    )
    def test_sync_updates_allowed_type_partner(
        self, mock_api
    ):
        """Existing partner with entity_type 0002
        is updated during sync."""
        partner = self.env['res.partner'].create({
            'name': 'Revendedor Existente',
            'wisedat_id': 9002,
            'wisedat_entity_type': '0002',
        })
        mock_api.return_value = {
            'customers': [{
                'id': 9002,
                'name': 'Revendedor Actualizado',
                'tax_id': '',
            }],
            'pagination': {
                'number_pages': 1,
                'number_items': 1,
            },
        }
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
        '._api_call_with_retry'
    )
    def test_sync_creates_new_customer_without_type(
        self, mock_api
    ):
        """New customer is created without
        entity_type check (classification is
        a separate step)."""
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
        with self._mock_commit():
            self.config._sync_customers_batch()
        partner = self.env['res.partner'].search([
            ('wisedat_id', '=', 9003)
        ], limit=1)
        self.assertTrue(partner)
        # entity_type not set yet (needs classify)
        self.assertFalse(
            partner.wisedat_entity_type
        )

    @patch(
        'odoo.addons.stamp_chain.models'
        '.wisedat_sync.WisedatConfig'
        '._fetch_entity_types_batch'
    )
    def test_classify_parallel(
        self, mock_batch_fetch
    ):
        """action_classify_entity_types uses
        parallel fetch and marks checked."""
        p1 = self.env['res.partner'].create({
            'name': 'Sem Tipo 1',
            'wisedat_id': 9010,
        })
        p2 = self.env['res.partner'].create({
            'name': 'Sem Tipo 2',
            'wisedat_id': 9011,
        })
        p3 = self.env['res.partner'].create({
            'name': 'Sem Tipo 3',
            'wisedat_id': 9012,
        })
        mock_batch_fetch.return_value = {
            9010: '0002',
            9011: '0004',
            9012: False,  # sem entity_type
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
        p2.invalidate_recordset()
        p3.invalidate_recordset()
        self.assertEqual(
            p1.wisedat_entity_type, '0002'
        )
        self.assertTrue(
            p1.wisedat_entity_type_checked
        )
        self.assertEqual(
            p2.wisedat_entity_type, '0004'
        )
        self.assertTrue(
            p2.wisedat_entity_type_checked
        )
        # p3 has no entity_type but IS checked
        self.assertFalse(
            p3.wisedat_entity_type
        )
        self.assertTrue(
            p3.wisedat_entity_type_checked
        )

    def test_classify_all_checked_skips(self):
        """Classify returns early when all
        partners are already checked."""
        self.env['res.partner'].create({
            'name': 'Ja Verificado',
            'wisedat_id': 9020,
            'wisedat_entity_type_checked': True,
        })
        result = (
            self.config
            .action_classify_entity_types()
        )
        self.assertIn(
            'classificados',
            result['params']['message']
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
