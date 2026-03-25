# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError
from odoo import fields


class TestOcrWizards(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        manager_group = cls.env.ref(
            'stamp_chain.group_stamp_manager'
        )
        cls.env.user.groups_id |= manager_group
        cls.zone = cls.env['tobacco.stamp.zone'].search(
            [('code', '=', 'PT_C')], limit=1
        )
        cls.product = cls.env['product.product'].create({
            'name': 'Tabaco OCR Test',
            'default_code': 'TAB-OCR',
            'type': 'product',
        })
        cls.bom = cls.env['mrp.bom'].create({
            'product_id': cls.product.id,
            'product_tmpl_id':
                cls.product.product_tmpl_id.id,
            'product_qty': 1,
        })

    def _create_ocr_lot(self, code, incm_ref):
        wiz = self.env[
            'tobacco.incm.ocr.reception.wizard'
        ].create({
            'zone_id': self.zone.id,
            'reception_date': fields.Date.today(),
            'incm_ref': incm_ref,
            'first_serial_ocr': code,
            'ocr_confirmed': True,
        })
        result = wiz.action_confirm()
        return self.env['tobacco.stamp.lot'].browse(
            result['res_id']
        )

    # --- Recepcao OCR ---

    def test_ocr_extrapolation_correct(self):
        wiz = self.env[
            'tobacco.incm.ocr.reception.wizard'
        ].create({
            'zone_id': self.zone.id,
            'incm_ref': 'EXTRAP-001',
            'first_serial_ocr': 'ZZAYC000',
            'ocr_confirmed': True,
        })
        self.assertEqual(wiz.serial_prefix, 'ZZAYC')
        self.assertEqual(wiz.serial_suffix_start, 0)
        self.assertEqual(
            wiz.serial_suffix_end_preview, 499
        )
        self.assertEqual(
            wiz.last_serial_preview, 'ZZAYC499'
        )
        self.assertEqual(wiz.qty_total, 500)

    def test_ocr_creates_500_serials(self):
        lot = self._create_ocr_lot(
            'ZZAYF000', 'OCR-500-001'
        )
        self.assertEqual(len(lot.serial_ids), 500)
        codes = lot.serial_ids.mapped('serial_number')
        self.assertIn('ZZAYF000', codes)
        self.assertIn('ZZAYF499', codes)

    def test_non_consecutive_lots(self):
        lot_c = self._create_ocr_lot(
            'ZZAYC000', 'NONCONSEC-C'
        )
        lot_f = self._create_ocr_lot(
            'ZZAYF000', 'NONCONSEC-F'
        )
        self.assertEqual(len(lot_c.serial_ids), 500)
        self.assertEqual(len(lot_f.serial_ids), 500)
        self.assertNotEqual(
            lot_c.serial_prefix,
            lot_f.serial_prefix
        )

    def test_invalid_format_rejected(self):
        for bad in ['ZZAYC', 'zzayc000', '', 'ZZAYC1000']:
            wiz = self.env[
                'tobacco.incm.ocr.reception.wizard'
            ].create({
                'zone_id': self.zone.id,
                'incm_ref': 'BAD',
                'first_serial_ocr': bad,
                'ocr_confirmed': True,
            })
            with self.assertRaises(UserError):
                wiz.action_confirm()

    def test_requires_confirmation(self):
        wiz = self.env[
            'tobacco.incm.ocr.reception.wizard'
        ].create({
            'zone_id': self.zone.id,
            'incm_ref': 'NOCONF',
            'first_serial_ocr': 'ZZAYC000',
            'ocr_confirmed': False,
        })
        with self.assertRaises(UserError):
            wiz.action_confirm()

    def test_duplicate_rejected(self):
        self._create_ocr_lot('ZZAYB000', 'DUP-1')
        wiz = self.env[
            'tobacco.incm.ocr.reception.wizard'
        ].create({
            'zone_id': self.zone.id,
            'incm_ref': 'DUP-2',
            'first_serial_ocr': 'ZZAYB000',
            'ocr_confirmed': True,
        })
        with self.assertRaises(UserError):
            wiz.action_confirm()

    # --- Calculo consumo ---

    def test_consumption_full_lot(self):
        lot = self._create_ocr_lot(
            'ZZAXA000', 'FULL-001'
        )
        prod = self.env['mrp.production'].create({
            'product_id': self.product.id,
            'product_qty': 500,
            'bom_id': self.bom.id,
        })
        prod.stamp_zone_id = self.zone.id
        wiz = self.env[
            'tobacco.production.end.wizard'
        ].create({
            'production_id': prod.id,
            'lot1_id': lot.id,
            'lot1_exhausted': True,
            'lot2_id': lot.id,
            'lot2_exhausted': True,
        })
        # Need a second lot for lot2
        lot2 = self._create_ocr_lot(
            'ZZAXB000', 'FULL-002'
        )
        wiz.lot2_id = lot2.id
        wiz.action_confirm()
        self.assertEqual(lot.lot_status, 'exhausted')
        used = lot.serial_ids.filtered(
            lambda s: s.state == 'used'
        )
        self.assertEqual(len(used), 500)

    def test_consumption_partial(self):
        lot = self._create_ocr_lot(
            'ZZAXC000', 'PARTIAL-001'
        )
        lot2 = self._create_ocr_lot(
            'ZZAXD000', 'PARTIAL-002'
        )
        prod = self.env['mrp.production'].create({
            'product_id': self.product.id,
            'product_qty': 300,
            'bom_id': self.bom.id,
        })
        prod.stamp_zone_id = self.zone.id
        wiz = self.env[
            'tobacco.production.end.wizard'
        ].create({
            'production_id': prod.id,
            'lot1_id': lot.id,
            'lot1_last_scan': 'ZZAXC187',
            'lot1_scan_confirmed': True,
            'lot2_id': lot2.id,
            'lot2_exhausted': True,
        })
        wiz.action_confirm()
        # Lot 1: ZZAXC188-499 = 312 used
        used_lot1 = lot.serial_ids.filtered(
            lambda s: s.state == 'used'
        )
        self.assertEqual(len(used_lot1), 312)
        # Lot 1: ZZAXC000-187 = 188 available
        avail_lot1 = lot.serial_ids.filtered(
            lambda s: s.state == 'available'
        )
        self.assertEqual(len(avail_lot1), 188)
        self.assertEqual(lot.lot_status, 'partial')

    def test_current_suffix_end_updates(self):
        lot = self._create_ocr_lot(
            'ZZAXE000', 'SUFFIX-001'
        )
        self.assertEqual(
            lot.current_suffix_end, 499
        )
        lot2 = self._create_ocr_lot(
            'ZZAXF000', 'SUFFIX-002'
        )
        prod = self.env['mrp.production'].create({
            'product_id': self.product.id,
            'product_qty': 100,
            'bom_id': self.bom.id,
        })
        prod.stamp_zone_id = self.zone.id
        wiz = self.env[
            'tobacco.production.end.wizard'
        ].create({
            'production_id': prod.id,
            'lot1_id': lot.id,
            'lot1_last_scan': 'ZZAXE397',
            'lot1_scan_confirmed': True,
            'lot2_id': lot2.id,
            'lot2_exhausted': True,
        })
        wiz.action_confirm()
        lot.invalidate_recordset()
        self.assertEqual(
            lot.current_suffix_end, 397
        )

    def test_account_movements_correct(self):
        lot = self._create_ocr_lot(
            'ZZAXG000', 'MOVE-001'
        )
        lot2 = self._create_ocr_lot(
            'ZZAXH000', 'MOVE-002'
        )
        balance_before = self.zone.balance
        prod = self.env['mrp.production'].create({
            'product_id': self.product.id,
            'product_qty': 100,
            'bom_id': self.bom.id,
        })
        prod.stamp_zone_id = self.zone.id
        wiz = self.env[
            'tobacco.production.end.wizard'
        ].create({
            'production_id': prod.id,
            'lot1_id': lot.id,
            'lot1_last_scan': 'ZZAXG187',
            'lot1_scan_confirmed': True,
            'lot2_id': lot2.id,
            'lot2_exhausted': True,
        })
        wiz.action_confirm()
        # 312 from lot1 + 500 from lot2 = 812
        self.assertEqual(
            self.zone.balance,
            balance_before - 812
        )
