# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError


class TestFIFO(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Zone = cls.env['tobacco.stamp.zone']
        cls.Lot = cls.env['tobacco.stamp.lot']
        cls.Serial = cls.env['tobacco.stamp.serial']

        cls.zone = cls.Zone.create({
            'name': 'FIFO Test Zone',
            'code': 'PT_C',
            'min_stock_alert': 100,
        })

        # Create 2 lots with different FIFO sequence
        cls.lot1 = cls.Lot.create({
            'name': 'LOT-FIFO-001',
            'incm_ref': 'INCM-001',
            'zone_id': cls.zone.id,
            'qty_received': 500,
            'state': 'received',
            'fifo_sequence': 1,
        })
        cls.lot2 = cls.Lot.create({
            'name': 'LOT-FIFO-002',
            'incm_ref': 'INCM-002',
            'zone_id': cls.zone.id,
            'qty_received': 500,
            'state': 'received',
            'fifo_sequence': 2,
        })

        # Create serials for lot1
        serials1 = [{
            'serial_number': f'FIFO-1-{i:06d}',
            'lot_id': cls.lot1.id,
            'state': 'available',
        } for i in range(1, 6)]
        cls.Serial.create(serials1)

        # Create serials for lot2
        serials2 = [{
            'serial_number': f'FIFO-2-{i:06d}',
            'lot_id': cls.lot2.id,
            'state': 'available',
        } for i in range(1, 6)]
        cls.Serial.create(serials2)

    def test_fifo_sequence_order(self):
        self.assertTrue(
            self.lot1.fifo_sequence < self.lot2.fifo_sequence
        )

    def test_get_next_fifo_sequence(self):
        next_seq = self.Lot._get_next_fifo_sequence(
            self.zone.id
        )
        self.assertEqual(next_seq, 3)
