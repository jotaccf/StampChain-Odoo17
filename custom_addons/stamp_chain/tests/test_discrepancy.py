# -*- coding: utf-8 -*-
from datetime import timedelta
from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError
from odoo import fields


class TestDiscrepancy(TransactionCase):

    def setUp(self):
        super().setUp()
        self.zone = self.env[
            'tobacco.stamp.zone'
        ].search([('code', '=', 'PT_C')], limit=1)
        # Garantir grupo manager
        manager_group = self.env.ref(
            'stamp_chain.group_stamp_manager'
        )
        self.env.user.write({
            'groups_id': [(4, manager_group.id)],
        })

    def _create_lot(self, prefix, incm_ref):
        lot = self.env['tobacco.stamp.lot'].create({
            'incm_ref': incm_ref,
            'zone_id': self.zone.id,
            'reception_date': fields.Date.today(),
            'qty_received': 500,
            'state': 'received',
            'fifo_sequence': self.env[
                'tobacco.stamp.lot'
            ]._get_next_fifo_sequence(self.zone.id),
            'first_serial_code': f'{prefix}000',
            'serial_prefix': prefix,
            'serial_suffix_start': 0,
            'serial_suffix_end': 499,
            'lot_status': 'reception',
        })
        self.env['tobacco.stamp.serial'].create([
            {
                'serial_number': f'{prefix}{i:03d}',
                'lot_id': lot.id,
                'state': 'available',
            }
            for i in range(500)
        ])
        self.env['tobacco.stamp.movement'].create({
            'zone_id': self.zone.id,
            'move_type': 'in',
            'qty': 500,
            'lot_id': lot.id,
            'reference': lot.name,
            'notes': f'Recepcao {incm_ref}',
        })
        return lot

    def test_no_discrepancy_initial(self):
        self._create_lot('ZZAAA', 'DISC-001')
        self.assertEqual(self.zone.discrepancy, 0)
        self.assertFalse(self.zone.discrepancy_active)
        self.assertEqual(
            self.zone.discrepancy_direction, 'ok'
        )

    def test_discrepancy_missing(self):
        lot = self._create_lot('ZZAAB', 'DISC-002')
        lot.serial_ids[:3].write({'state': 'used'})
        self.assertGreater(self.zone.discrepancy, 0)
        self.assertEqual(
            self.zone.discrepancy_direction, 'missing'
        )

    def test_discrepancy_surplus(self):
        lot = self._create_lot('ZZAAC', 'DISC-003')
        self.env['tobacco.stamp.movement'].create({
            'zone_id': self.zone.id,
            'move_type': 'out',
            'qty': 5,
            'lot_id': lot.id,
            'reference': 'TEST-OUT',
            'notes': 'Teste surplus',
        })
        self.assertLess(self.zone.discrepancy, 0)
        self.assertEqual(
            self.zone.discrepancy_direction, 'surplus'
        )

    def test_audit_immutable(self):
        audit = self.env['tobacco.stamp.audit'].create({
            'zone_id': self.zone.id,
            'stock_theoretical': 500,
            'stock_real': 497,
            'stock_real_auto': 497,
            'discrepancy': 3,
            'discrepancy_direction': 'missing',
            'audit_type': 'manual',
        })
        with self.assertRaises(UserError):
            audit.unlink()

    def test_audit_justify(self):
        audit = self.env['tobacco.stamp.audit'].create({
            'zone_id': self.zone.id,
            'stock_theoretical': 500,
            'stock_real': 498,
            'stock_real_auto': 498,
            'discrepancy': 2,
            'discrepancy_direction': 'missing',
            'audit_type': 'manual',
        })
        audit.justification = (
            'Estampilhas perdidas na maquina.'
        )
        audit.action_justify()
        self.assertEqual(audit.state, 'justified')
        self.assertTrue(audit.is_justified)
        self.assertTrue(audit.exists())

    def test_audit_requires_justification(self):
        audit = self.env['tobacco.stamp.audit'].create({
            'zone_id': self.zone.id,
            'stock_theoretical': 500,
            'stock_real': 499,
            'stock_real_auto': 499,
            'discrepancy': 1,
            'discrepancy_direction': 'missing',
            'audit_type': 'manual',
        })
        with self.assertRaises(UserError):
            audit.action_justify()

    def test_found_stamp_approved(self):
        """C4: usa lote existente, serial novo
        dentro do range mas marcado como used."""
        lot = self._create_lot('ZZFND', 'DISC-FND-001')
        # Marca ZZFND050 como used (simula perda)
        serial_lost = lot.serial_ids.filtered(
            lambda s: s.serial_number == 'ZZFND050'
        )
        serial_lost.write({'state': 'used'})

        audit = self.env['tobacco.stamp.audit'].create({
            'zone_id': self.zone.id,
            'stock_theoretical': 500,
            'stock_real': 499,
            'stock_real_auto': 499,
            'discrepancy': 1,
            'discrepancy_direction': 'missing',
            'audit_type': 'manual',
        })
        # Usa codigo genuinamente novo (ZZFNX)
        # que nao tem lote — lot_id sera False
        # Precisamos criar com lote existente
        # para satisfazer required=True
        # Alternativa: usar serial que nao existe
        # no lote ZZFND
        found = self.env['tobacco.stamp.found'].create({
            'audit_id': audit.id,
            'serial_code': 'ZZFND500',
            'found_location': 'Chao da maquina',
        })
        # ZZFND500 nao existe como serial
        # (lote tem 000-499), lot_id computed = ZZFND
        found.action_approve()
        self.assertEqual(found.state, 'approved')
        self.assertTrue(found.serial_id)
        movement = self.env[
            'tobacco.stamp.movement'
        ].search([
            ('move_type', '=', 'recovery_found'),
            ('reference', '=', found.name),
        ], limit=1)
        self.assertTrue(movement)
        self.assertEqual(movement.qty, 1)

    def test_found_only_manager(self):
        audit = self.env['tobacco.stamp.audit'].create({
            'zone_id': self.zone.id,
            'stock_theoretical': 500,
            'stock_real': 499,
            'stock_real_auto': 499,
            'discrepancy': 1,
            'discrepancy_direction': 'missing',
            'audit_type': 'manual',
        })
        found = self.env['tobacco.stamp.found'].create({
            'audit_id': audit.id,
            'serial_code': 'ZZYYY000',
            'found_location': 'Teste',
        })
        manager_group = self.env.ref(
            'stamp_chain.group_stamp_manager'
        )
        self.env.user.write({
            'groups_id': [(3, manager_group.id)],
        })
        with self.assertRaises(UserError):
            found.action_approve()

    def test_physical_count_overrides_auto(self):
        self._create_lot('ZZPHY', 'DISC-PHY-001')
        self.zone.invalidate_recordset()
        auto = self.zone.stock_real_auto
        self.assertEqual(self.zone.stock_real, auto)
        self.zone.write({
            'last_physical_count': auto - 5,
            'last_physical_count_date':
                fields.Datetime.now(),
            'last_physical_count_user':
                self.env.user.id,
        })
        self.zone.invalidate_recordset()
        self.assertEqual(
            self.zone.stock_real, auto - 5
        )

    def test_physical_count_expired(self):
        self._create_lot('ZZEXP', 'DISC-EXP-001')
        self.zone.invalidate_recordset()
        auto = self.zone.stock_real_auto
        old_date = (
            fields.Datetime.now() - timedelta(hours=25)
        )
        self.zone.write({
            'last_physical_count': auto - 10,
            'last_physical_count_date': old_date,
        })
        self.zone.invalidate_recordset()
        self.assertEqual(self.zone.stock_real, auto)
