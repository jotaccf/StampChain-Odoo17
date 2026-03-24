# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase


class TestStampZones(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Zone = cls.env['tobacco.stamp.zone']
        cls.Movement = cls.env['tobacco.stamp.movement']
        cls.zone_c = cls.Zone.create({
            'name': 'Test Continente',
            'code': 'PT_C',
            'min_stock_alert': 100,
        })

    def test_zone_creation(self):
        self.assertEqual(self.zone_c.code, 'PT_C')
        self.assertEqual(self.zone_c.balance, 0)

    def test_balance_with_movements(self):
        self.Movement.create({
            'zone_id': self.zone_c.id,
            'move_type': 'in',
            'qty': 500,
            'notes': 'Test entry',
        })
        self.assertEqual(self.zone_c.balance, 500)

        self.Movement.create({
            'zone_id': self.zone_c.id,
            'move_type': 'out',
            'qty': 100,
            'notes': 'Test exit',
        })
        self.assertEqual(self.zone_c.balance, 400)

    def test_balance_includes_recovery(self):
        self.Movement.create({
            'zone_id': self.zone_c.id,
            'move_type': 'in',
            'qty': 500,
            'notes': 'Entry',
        })
        self.Movement.create({
            'zone_id': self.zone_c.id,
            'move_type': 'breakdown',
            'qty': 50,
            'notes': 'Breakdown test',
        })
        self.Movement.create({
            'zone_id': self.zone_c.id,
            'move_type': 'recovery',
            'qty': 10,
            'notes': 'Recovery test',
        })
        self.assertEqual(self.zone_c.balance, 460)

    def test_alert_active_below_min(self):
        self.Movement.create({
            'zone_id': self.zone_c.id,
            'move_type': 'in',
            'qty': 50,
            'notes': 'Below min',
        })
        self.assertTrue(self.zone_c.alert_active)

    def test_alert_inactive_above_min(self):
        self.Movement.create({
            'zone_id': self.zone_c.id,
            'move_type': 'in',
            'qty': 500,
            'notes': 'Above min',
        })
        self.assertFalse(self.zone_c.alert_active)

    def test_color_computation(self):
        self.assertEqual(self.zone_c.color, 1)  # 0 balance = red
        self.Movement.create({
            'zone_id': self.zone_c.id,
            'move_type': 'in',
            'qty': 50,
            'notes': 'Color test',
        })
        self.assertEqual(self.zone_c.color, 3)  # below min = orange
        self.Movement.create({
            'zone_id': self.zone_c.id,
            'move_type': 'in',
            'qty': 500,
            'notes': 'Color test 2',
        })
        self.assertEqual(self.zone_c.color, 10)  # above min = green
