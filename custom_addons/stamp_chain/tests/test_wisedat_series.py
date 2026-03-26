# -*- coding: utf-8 -*-
from unittest.mock import patch
from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError
from odoo import fields


class TestWisedatSeries(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.config = cls.env[
            'tobacco.wisedat.config'
        ].create({
            'name': 'Test Wisedat Series',
            'api_url': 'http://wisedat-test:8080',
            'api_key': 'test-key-series',
            'api_username': 'test-user',
            'api_password': 'test-pass',
            'sync_customers': True,
            'sync_products': True,
            'sync_invoices': True,
        })
        cls.wh = cls.env['stock.warehouse'].search(
            [], limit=1
        )
        cls.env['tobacco.warehouse.config'].create({
            'name': 'A1 Series Test',
            'warehouse_id': cls.wh.id,
            'wisedat_warehouse_code': 'A1',
            'warehouse_type': 'main_warehouse',
            'wisedat_config_id': cls.config.id,
        })

    @patch(
        'odoo.addons.stamp_chain.models'
        '.wisedat_sync.WisedatConfig'
        '._api_call_with_retry'
    )
    def test_sync_series_creates_records(
        self, mock_api
    ):
        """Sync creates series records from API."""
        mock_api.return_value = {
            'series': [
                {
                    'id': 1,
                    'name': 'GT2026',
                    'description': 'Guias 2026',
                    'active': True,
                    'document_type':
                        'MovementOfGoods',
                },
                {
                    'id': 2,
                    'name': 'FT2026',
                    'description': 'Facturas 2026',
                    'active': True,
                    'document_type': 'SalesInvoice',
                },
                {
                    'id': 3,
                    'name': 'GT2025',
                    'description': 'Guias 2025',
                    'active': False,
                    'document_type':
                        'MovementOfGoods',
                },
            ],
        }
        self.config._sync_series()
        series = self.env[
            'tobacco.wisedat.series'
        ].search([
            ('wisedat_config_id', '=',
             self.config.id)
        ])
        self.assertEqual(len(series), 3)
        gt2026 = series.filtered(
            lambda s: s.wisedat_id == 1
        )
        self.assertEqual(gt2026.name, 'GT2026')
        self.assertEqual(
            gt2026.document_type,
            'movement_of_goods'
        )
        self.assertTrue(gt2026.is_active)
        gt2025 = series.filtered(
            lambda s: s.wisedat_id == 3
        )
        self.assertFalse(gt2025.is_active)

    @patch(
        'odoo.addons.stamp_chain.models'
        '.wisedat_sync.WisedatConfig'
        '._api_call_with_retry'
    )
    def test_sync_series_updates_existing(
        self, mock_api
    ):
        """Sync updates existing series records."""
        self.env['tobacco.wisedat.series'].create({
            'wisedat_id': 10,
            'name': 'OLD',
            'description': 'Old Name',
            'document_type': 'movement_of_goods',
            'is_active': True,
            'wisedat_config_id': self.config.id,
        })
        mock_api.return_value = {
            'series': [{
                'id': 10,
                'name': 'GT2026-V2',
                'description': 'Guias 2026 v2',
                'active': True,
                'document_type':
                    'MovementOfGoods',
            }],
        }
        self.config._sync_series()
        rec = self.env[
            'tobacco.wisedat.series'
        ].search([
            ('wisedat_id', '=', 10),
            ('wisedat_config_id', '=',
             self.config.id),
        ])
        self.assertEqual(len(rec), 1)
        self.assertEqual(rec.name, 'GT2026-V2')

    @patch(
        'odoo.addons.stamp_chain.models'
        '.wisedat_sync.WisedatConfig'
        '._api_call_with_retry'
    )
    def test_sync_series_deactivates_removed(
        self, mock_api
    ):
        """Series removed from API are
        deactivated locally."""
        self.env['tobacco.wisedat.series'].create({
            'wisedat_id': 20,
            'name': 'REMOVED',
            'document_type': 'movement_of_goods',
            'is_active': True,
            'wisedat_config_id': self.config.id,
        })
        mock_api.return_value = {
            'series': [{
                'id': 99,
                'name': 'NEW',
                'description': 'New only',
                'active': True,
                'document_type':
                    'MovementOfGoods',
            }],
        }
        self.config._sync_series()
        removed = self.env[
            'tobacco.wisedat.series'
        ].search([
            ('wisedat_id', '=', 20),
            ('wisedat_config_id', '=',
             self.config.id),
        ])
        self.assertFalse(removed.is_active)

    def test_validate_series_no_config_raises(
        self,
    ):
        """Validation raises if no series is
        configured."""
        self.config.transport_guide_series_id = (
            False
        )
        with self.assertRaises(UserError):
            self.config._validate_transport_guide_series()

    def test_validate_series_inactive_raises(
        self,
    ):
        """Validation raises if series is
        inactive."""
        series = self.env[
            'tobacco.wisedat.series'
        ].create({
            'wisedat_id': 30,
            'name': 'INACTIVE',
            'document_type': 'movement_of_goods',
            'is_active': False,
            'wisedat_config_id': self.config.id,
        })
        self.config.transport_guide_series_id = (
            series.id
        )
        with self.assertRaises(UserError):
            self.config._validate_transport_guide_series()

    def test_validate_series_active_returns_id(
        self,
    ):
        """Validation returns wisedat_id when
        series is active."""
        series = self.env[
            'tobacco.wisedat.series'
        ].create({
            'wisedat_id': 40,
            'name': 'ACTIVE',
            'document_type': 'movement_of_goods',
            'is_active': True,
            'wisedat_config_id': self.config.id,
        })
        self.config.transport_guide_series_id = (
            series.id
        )
        result = (
            self.config
            ._validate_transport_guide_series()
        )
        self.assertEqual(result, 40)

    @patch(
        'odoo.addons.stamp_chain.models'
        '.wisedat_sync.WisedatConfig'
        '._api_call_with_retry'
    )
    def test_action_sync_series_returns_notification(
        self, mock_api
    ):
        """Button action returns success
        notification."""
        mock_api.return_value = {'series': []}
        result = self.config.action_sync_series()
        self.assertEqual(
            result['type'],
            'ir.actions.client'
        )
        self.assertEqual(
            result['params']['type'],
            'success'
        )

    @patch(
        'odoo.addons.stamp_chain.models'
        '.wisedat_sync.WisedatConfig'
        '._api_call_with_retry'
    )
    def test_sync_series_api_error_raises(
        self, mock_api
    ):
        """API error during sync raises
        UserError."""
        mock_api.side_effect = Exception(
            'Connection refused'
        )
        with self.assertRaises(UserError):
            self.config._sync_series()

    def test_series_sql_constraint(self):
        """Duplicate wisedat_id per config is
        blocked."""
        self.env['tobacco.wisedat.series'].create({
            'wisedat_id': 50,
            'name': 'FIRST',
            'document_type': 'movement_of_goods',
            'is_active': True,
            'wisedat_config_id': self.config.id,
        })
        with self.assertRaises(Exception):
            self.env['tobacco.wisedat.series'].create({
                'wisedat_id': 50,
                'name': 'DUPLICATE',
                'document_type':
                    'movement_of_goods',
                'is_active': True,
                'wisedat_config_id': self.config.id,
            })
