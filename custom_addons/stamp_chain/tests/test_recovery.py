# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError, ValidationError


class TestRecovery(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        manager_group = cls.env.ref(
            'stamp_chain.group_stamp_manager'
        )
        cls.env.user.groups_id |= manager_group
        cls.Zone = cls.env['tobacco.stamp.zone']
        cls.Lot = cls.env['tobacco.stamp.lot']
        cls.Serial = cls.env['tobacco.stamp.serial']
        cls.Recovery = cls.env['tobacco.stamp.recovery']

        cls.zone = cls.Zone.create({
            'name': 'Recovery Zone',
            'code': 'PT_A',
            'min_stock_alert': 100,
        })
        cls.lot = cls.Lot.create({
            'name': 'REC-LOT-001',
            'incm_ref': 'REC-INCM',
            'zone_id': cls.zone.id,
            'qty_received': 500,
            'state': 'received',
            'fifo_sequence': 1,
        })
        cls.serial = cls.Serial.create({
            'serial_number': 'REC-TEST-000001',
            'lot_id': cls.lot.id,
            'state': 'broken',
        })

    def test_submit_moves_to_quarantine(self):
        recovery = self.Recovery.create({
            'serial_ids': [(6, 0, [self.serial.id])],
            'inspection_notes': 'Inspeccao manual OK',
        })
        recovery.action_submit()
        self.assertEqual(recovery.state, 'submitted')
        self.assertEqual(self.serial.state, 'quarantine')

    def test_submit_requires_notes(self):
        recovery = self.Recovery.create({
            'serial_ids': [(6, 0, [self.serial.id])],
        })
        with self.assertRaises(UserError):
            recovery.action_submit()

    def test_reject_restores_broken(self):
        serial2 = self.Serial.create({
            'serial_number': 'REC-TEST-000002',
            'lot_id': self.lot.id,
            'state': 'broken',
        })
        recovery = self.Recovery.create({
            'serial_ids': [(6, 0, [serial2.id])],
            'inspection_notes': 'Test reject',
        })
        recovery.action_submit()
        self.assertEqual(serial2.state, 'quarantine')
        recovery.action_reject()
        self.assertEqual(recovery.state, 'rejected')
        serial2.invalidate_recordset()
        self.assertEqual(serial2.state, 'broken')

    def test_different_zones_raises(self):
        zone2 = self.Zone.create({
            'name': 'Other Zone',
            'code': 'PT_M',
            'min_stock_alert': 100,
        })
        lot2 = self.Lot.create({
            'name': 'REC-LOT-002',
            'incm_ref': 'REC-INCM-2',
            'zone_id': zone2.id,
            'qty_received': 500,
            'state': 'received',
            'fifo_sequence': 1,
        })
        serial_other = self.Serial.create({
            'serial_number': 'REC-OTHER-000001',
            'lot_id': lot2.id,
            'state': 'broken',
        })
        with self.assertRaises(ValidationError):
            self.Recovery.create({
                'serial_ids': [
                    (6, 0, [self.serial.id, serial_other.id])
                ],
                'inspection_notes': 'Mixed zones',
            })
