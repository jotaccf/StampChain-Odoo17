# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase
from odoo.exceptions import ValidationError


class TestIncmReception(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Zone = cls.env['tobacco.stamp.zone']
        cls.Wizard = cls.env['tobacco.incm.reception.wizard']
        cls.zone = cls.Zone.create({
            'name': 'Reception Test Zone',
            'code': 'PT_C',
            'min_stock_alert': 100,
        })

    def test_wizard_creates_lot(self):
        wiz = self.Wizard.create({
            'incm_ref': 'TEST-REF-001',
            'zone_id': self.zone.id,
            'qty_lots': 1,
        })
        result = wiz.action_confirm()
        self.assertEqual(result['res_model'], 'tobacco.stamp.lot')
        lot = self.env['tobacco.stamp.lot'].browse(result['res_id'])
        self.assertEqual(lot.qty_received, 500)
        self.assertEqual(lot.state, 'received')
        self.assertEqual(len(lot.serial_ids), 500)

    def test_serial_format(self):
        wiz = self.Wizard.create({
            'incm_ref': 'FMT-001',
            'zone_id': self.zone.id,
            'qty_lots': 1,
        })
        result = wiz.action_confirm()
        lot = self.env['tobacco.stamp.lot'].browse(result['res_id'])
        first = lot.serial_ids.sorted('serial_number')[0]
        self.assertTrue(first.serial_number.startswith('PT_C-'))

    def test_movement_created(self):
        wiz = self.Wizard.create({
            'incm_ref': 'MOV-001',
            'zone_id': self.zone.id,
            'qty_lots': 2,
        })
        wiz.action_confirm()
        movements = self.env['tobacco.stamp.movement'].search([
            ('zone_id', '=', self.zone.id),
            ('move_type', '=', 'in'),
        ])
        self.assertTrue(len(movements) > 0)
        self.assertEqual(movements[0].qty, 1000)

    def test_qty_lots_min(self):
        with self.assertRaises(ValidationError):
            self.Wizard.create({
                'incm_ref': 'MIN-001',
                'zone_id': self.zone.id,
                'qty_lots': 0,
            })
