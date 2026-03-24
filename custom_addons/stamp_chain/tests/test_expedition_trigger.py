# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase


class TestExpeditionTrigger(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Zone = cls.env['tobacco.stamp.zone']
        cls.Movement = cls.env['tobacco.stamp.movement']

        cls.zone = cls.Zone.create({
            'name': 'Expedition Zone',
            'code': 'PT_C',
            'min_stock_alert': 100,
        })

    def test_out_movement_reduces_balance(self):
        self.Movement.create({
            'zone_id': self.zone.id,
            'move_type': 'in',
            'qty': 500,
            'notes': 'Entry',
        })
        self.assertEqual(self.zone.balance, 500)

        self.Movement.create({
            'zone_id': self.zone.id,
            'move_type': 'out',
            'qty': 200,
            'notes': 'Exit',
        })
        self.assertEqual(self.zone.balance, 300)

    def test_movement_balance_after(self):
        mov = self.Movement.create({
            'zone_id': self.zone.id,
            'move_type': 'in',
            'qty': 1000,
            'notes': 'Balance test',
        })
        self.assertEqual(mov.balance_after, 1000)

    def test_movement_cannot_be_deleted(self):
        mov = self.Movement.create({
            'zone_id': self.zone.id,
            'move_type': 'in',
            'qty': 100,
            'notes': 'Delete test',
        })
        from odoo.exceptions import UserError
        with self.assertRaises(UserError):
            mov.unlink()
