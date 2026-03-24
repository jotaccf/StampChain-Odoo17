# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase
from odoo.exceptions import ValidationError


class TestBreakdown(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Zone = cls.env['tobacco.stamp.zone']
        cls.Lot = cls.env['tobacco.stamp.lot']
        cls.Serial = cls.env['tobacco.stamp.serial']
        cls.Breakdown = cls.env['tobacco.stamp.breakdown']

        cls.zone = cls.Zone.create({
            'name': 'Breakdown Zone',
            'code': 'PT_M',
            'min_stock_alert': 100,
        })
        cls.lot = cls.Lot.create({
            'name': 'BRK-LOT-001',
            'incm_ref': 'BRK-INCM',
            'zone_id': cls.zone.id,
            'qty_received': 500,
            'state': 'received',
            'fifo_sequence': 1,
        })

    def test_breakdown_qty_computed(self):
        serial1 = self.Serial.create({
            'serial_number': 'BRK-TEST-000001',
            'lot_id': self.lot.id,
            'state': 'broken',
        })
        serial2 = self.Serial.create({
            'serial_number': 'BRK-TEST-000002',
            'lot_id': self.lot.id,
            'state': 'broken',
        })
        # Need a production order for the breakdown
        product = self.env['product.product'].create({
            'name': 'Test Product BRK',
            'type': 'product',
        })
        bom = self.env['mrp.bom'].create({
            'product_tmpl_id': product.product_tmpl_id.id,
            'product_qty': 1,
        })
        production = self.env['mrp.production'].create({
            'product_id': product.id,
            'product_qty': 10,
            'bom_id': bom.id,
        })
        breakdown = self.Breakdown.create({
            'production_id': production.id,
            'serial_ids': [(6, 0, [serial1.id, serial2.id])],
            'breakdown_reason': 'handling_error',
        })
        self.assertEqual(breakdown.qty_broken, 2)
