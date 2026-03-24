# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError


class TestMinStock(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        manager_group = cls.env.ref(
            'stamp_chain.group_stamp_manager'
        )
        cls.env.user.groups_id |= manager_group
        cls.Zone = cls.env['tobacco.stamp.zone']
        cls.Wizard = cls.env['tobacco.min.stock.wizard']
        cls.History = cls.env['tobacco.stamp.zone.history']
        cls.zone = cls.Zone.create({
            'name': 'MinStock Zone',
            'code': 'PT_C',
            'min_stock_alert': 2000,
        })

    def test_change_creates_history(self):
        wiz = self.Wizard.create({
            'zone_id': self.zone.id,
            'current_value': 2000,
            'new_value': 3000,
            'change_reason': 'Aumento por precaucao',
        })
        wiz.action_confirm()
        self.assertEqual(self.zone.min_stock_alert, 3000)
        history = self.History.search([
            ('zone_id', '=', self.zone.id),
        ])
        self.assertEqual(len(history), 1)
        self.assertEqual(history.previous_value, 2000)
        self.assertEqual(history.new_value, 3000)

    def test_negative_value_raises(self):
        with self.assertRaises(UserError):
            self.Wizard.create({
                'zone_id': self.zone.id,
                'current_value': 2000,
                'new_value': -1,
                'change_reason': 'Test',
            })

    def test_same_value_raises(self):
        with self.assertRaises(UserError):
            self.Wizard.create({
                'zone_id': self.zone.id,
                'current_value': 2000,
                'new_value': 2000,
                'change_reason': 'Test',
            })
