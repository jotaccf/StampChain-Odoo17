# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase
from odoo import fields


class TestPickingHandheld(TransactionCase):

    def setUp(self):
        super().setUp()
        self.wh = self.env['stock.warehouse'].search(
            [], limit=1
        )
        self.product = self.env[
            'product.product'
        ].create({
            'name': 'Tabaco Pick Test',
            'default_code': 'TAB-PICK-001',
            'type': 'product',
            'barcode': 'TAB-PICK-001',
        })
        self.location = self.env[
            'stock.location'
        ].create({
            'name': 'A-01-L1-P01',
            'location_id': (
                self.wh.lot_stock_id.id
            ),
            'usage': 'internal',
            'barcode': 'A-01-L1-P01',
        })

    def _create_picking(self):
        # Cria stock na localizacao para
        # gerar move_line_ids na reserva
        self.env['stock.quant'].sudo().create({
            'product_id': self.product.id,
            'location_id': self.location.id,
            'quantity': 100,
        })
        picking = self.env[
            'stock.picking'
        ].create({
            'picking_type_id':
                self.wh.int_type_id.id,
            'location_id': self.location.id,
            'location_dest_id': self.env.ref(
                'stock.stock_location_output'
            ).id,
        })
        self.env['stock.move'].create({
            'name': 'Test Move',
            'picking_id': picking.id,
            'product_id': self.product.id,
            'product_uom': self.product.uom_id.id,
            'product_uom_qty': 10,
            'location_id': self.location.id,
            'location_dest_id': self.env.ref(
                'stock.stock_location_output'
            ).id,
        })
        picking.action_confirm()
        picking.action_assign()
        return picking

    def test_location_scan_correct(self):
        picking = self._create_picking()
        result = (
            picking.action_validate_location_scan(
                'A-01-L1-P01'
            )
        )
        self.assertTrue(result['ok'])
        self.assertTrue(
            picking.scan_location_validated
        )

    def test_location_scan_wrong_blocks(self):
        picking = self._create_picking()
        result = (
            picking.action_validate_location_scan(
                'B-02-L3-P01'
            )
        )
        self.assertFalse(result['ok'])
        self.assertIn(
            'errada', result['message'].lower()
        )

    def test_product_scan_requires_location(self):
        picking = self._create_picking()
        result = (
            picking.action_validate_product_scan(
                'TAB-PICK-001'
            )
        )
        self.assertFalse(result['ok'])

    def test_product_scan_correct(self):
        picking = self._create_picking()
        picking.action_validate_location_scan(
            'A-01-L1-P01'
        )
        result = (
            picking.action_validate_product_scan(
                'TAB-PICK-001'
            )
        )
        self.assertTrue(result['ok'])

    def test_product_scan_wrong(self):
        picking = self._create_picking()
        picking.action_validate_location_scan(
            'A-01-L1-P01'
        )
        result = (
            picking.action_validate_product_scan(
                'CODIGO-ERRADO'
            )
        )
        self.assertFalse(result['ok'])

    def test_confirm_qty_with_move_line_id(self):
        picking = self._create_picking()
        picking.action_validate_location_scan(
            'A-01-L1-P01'
        )
        picking.action_validate_product_scan(
            'TAB-PICK-001'
        )
        move_line_id = (
            picking.current_move_line_id.id
        )
        result = picking.action_confirm_qty(
            10, move_line_id
        )
        self.assertTrue(result['ok'])
        self.assertTrue(result.get('done'))

    def test_location_barcode(self):
        self.assertEqual(
            self.location.barcode, 'A-01-L1-P01'
        )


class TestWarehouseLayoutWizard(TransactionCase):

    def setUp(self):
        super().setUp()
        self.wh = self.env[
            'stock.warehouse'
        ].search([], limit=1)
        self.wisedat_config = self.env[
            'tobacco.wisedat.config'
        ].search([], limit=1)
        if not self.wisedat_config:
            self.wisedat_config = self.env[
                'tobacco.wisedat.config'
            ].create({
                'name': 'Test',
                'api_url': 'http://test',
                'api_key': 'test',
                'api_username': 'test-user',
                'api_password': 'test-pass',
            })
        self.wh_config = self.env[
            'tobacco.warehouse.config'
        ].search([
            ('warehouse_id', '=', self.wh.id),
        ], limit=1)
        if not self.wh_config:
            self.wh_config = self.env[
                'tobacco.warehouse.config'
            ].create({
                'name': 'Test WH Config',
                'warehouse_id': self.wh.id,
                'wisedat_warehouse_code': 'TST',
                'warehouse_type': 'other',
                'wisedat_config_id':
                    self.wisedat_config.id,
            })

    def test_creates_locations(self):
        wiz = self.env[
            'tobacco.warehouse.layout.wizard'
        ].create({
            'warehouse_config_id':
                self.wh_config.id,
            'warehouse_id': self.wh.id,
            'num_corridors': 1,
            'num_shelves': 2,
            'num_levels': 2,
            'num_positions': 1,
        })
        wiz.action_generate()
        locs = self.env[
            'stock.location'
        ].search([
            ('location_id', '=',
             self.wh.lot_stock_id.id),
            ('barcode', 'like', 'A-'),
        ])
        self.assertEqual(len(locs), 4)

    def test_idempotent(self):
        wiz = self.env[
            'tobacco.warehouse.layout.wizard'
        ].create({
            'warehouse_config_id':
                self.wh_config.id,
            'warehouse_id': self.wh.id,
            'num_corridors': 1,
            'num_shelves': 1,
            'num_levels': 1,
            'num_positions': 1,
        })
        wiz.action_generate()
        count1 = self.env[
            'stock.location'
        ].search_count([
            ('location_id', '=',
             self.wh.lot_stock_id.id),
            ('barcode', '=', 'A-01-L1-P01'),
        ])
        wiz2 = self.env[
            'tobacco.warehouse.layout.wizard'
        ].create({
            'warehouse_config_id':
                self.wh_config.id,
            'warehouse_id': self.wh.id,
            'num_corridors': 1,
            'num_shelves': 1,
            'num_levels': 1,
            'num_positions': 1,
        })
        wiz2.action_generate()
        count2 = self.env[
            'stock.location'
        ].search_count([
            ('location_id', '=',
             self.wh.lot_stock_id.id),
            ('barcode', '=', 'A-01-L1-P01'),
        ])
        self.assertEqual(count1, count2)

    def test_saves_to_config(self):
        wiz = self.env[
            'tobacco.warehouse.layout.wizard'
        ].create({
            'warehouse_config_id':
                self.wh_config.id,
            'warehouse_id': self.wh.id,
            'num_corridors': 3,
            'num_shelves': 5,
            'num_levels': 4,
            'num_positions': 2,
        })
        wiz.action_generate()
        self.wh_config.invalidate_recordset()
        self.assertEqual(
            self.wh_config.num_corridors, 3
        )
        self.assertEqual(
            self.wh_config.num_shelves, 5
        )
        self.assertIsNotNone(
            self.wh_config.last_layout_date
        )
