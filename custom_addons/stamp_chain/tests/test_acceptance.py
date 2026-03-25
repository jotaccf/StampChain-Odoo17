# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError
from odoo import fields


class TestAcceptance(TransactionCase):
    """Testes de aceitacao — self-contained.
    Criam os proprios dados no setUp."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        manager_group = cls.env.ref(
            'stamp_chain.group_stamp_manager'
        )
        cls.env.user.groups_id |= manager_group

        # Armazens de teste (nao EF/A1 reais)
        cls.wh_ef = cls.env['stock.warehouse'].create({
            'name': 'EF Acceptance',
            'code': 'AEF',
        })
        cls.wh_a1 = cls.env['stock.warehouse'].create({
            'name': 'A1 Acceptance',
            'code': 'AA1',
        })
        # Wisedat config
        cls.wisedat_config = cls.env[
            'tobacco.wisedat.config'
        ].create({
            'name': 'Acceptance Config',
            'api_url': 'http://test:8080',
            'api_key': 'test-key',
        })
        # Warehouse config
        cls.env['tobacco.warehouse.config'].create({
            'name': 'EF Acceptance Config',
            'warehouse_id': cls.wh_ef.id,
            'wisedat_warehouse_code': 'EF',
            'warehouse_type': 'fiscal_warehouse',
            'requires_edic': True,
            'destination_warehouse_id': cls.wh_a1.id,
            'wisedat_config_id': cls.wisedat_config.id,
        })
        # Produto
        cls.product = cls.env['product.product'].create({
            'name': 'Tabaco Acceptance',
            'default_code': 'TAB-ACC-001',
            'type': 'product',
        })
        cls.bom = cls.env['mrp.bom'].create({
            'product_id': cls.product.id,
            'product_tmpl_id':
                cls.product.product_tmpl_id.id,
            'product_qty': 1,
        })
        # Parceiro
        cls.zone_ptc = cls.env[
            'tobacco.stamp.zone'
        ].search([('code', '=', 'PT_C')], limit=1)
        cls.partner = cls.env['res.partner'].create({
            'name': 'Cliente Aceitacao SA',
            'customer_rank': 1,
            'stamp_zone_id': cls.zone_ptc.id,
        })

    def test_three_zones_exist(self):
        zones = self.env['tobacco.stamp.zone'].search([])
        codes = zones.mapped('code')
        self.assertIn('PT_C', codes)
        self.assertIn('PT_M', codes)
        self.assertIn('PT_A', codes)

    def test_incm_reception_creates_500_serials(self):
        zone = self.zone_ptc
        balance_before = zone.balance
        wizard = self.env[
            'tobacco.incm.reception.wizard'
        ].create({
            'incm_ref': 'ACC-INCM-001',
            'zone_id': zone.id,
            'reception_date': fields.Date.today(),
            'qty_lots': 1,
        })
        result = wizard.action_confirm()
        lot = self.env['tobacco.stamp.lot'].browse(
            result['res_id']
        )
        self.assertEqual(lot.qty_received, 500)
        self.assertEqual(len(lot.serial_ids), 500)
        self.assertTrue(
            lot.serial_ids[0].serial_number.startswith(
                'PT_C-'
            )
        )
        self.assertEqual(
            zone.balance, balance_before + 500
        )

    def test_fifo_order_enforced(self):
        zone_m = self.env[
            'tobacco.stamp.zone'
        ].search([('code', '=', 'PT_M')], limit=1)
        w1 = self.env[
            'tobacco.incm.reception.wizard'
        ].create({
            'incm_ref': 'FIFO-ACC-001',
            'zone_id': zone_m.id,
            'qty_lots': 1,
        })
        r1 = w1.action_confirm()
        w2 = self.env[
            'tobacco.incm.reception.wizard'
        ].create({
            'incm_ref': 'FIFO-ACC-002',
            'zone_id': zone_m.id,
            'qty_lots': 1,
        })
        r2 = w2.action_confirm()
        lot1 = self.env['tobacco.stamp.lot'].browse(
            r1['res_id']
        )
        lot2 = self.env['tobacco.stamp.lot'].browse(
            r2['res_id']
        )
        self.assertLess(
            lot1.fifo_sequence,
            lot2.fifo_sequence,
        )

    def test_breakdown_reduces_balance(self):
        zone_a = self.env[
            'tobacco.stamp.zone'
        ].search([('code', '=', 'PT_A')], limit=1)
        wizard = self.env[
            'tobacco.incm.reception.wizard'
        ].create({
            'incm_ref': 'BRK-ACC-001',
            'zone_id': zone_a.id,
            'qty_lots': 1,
        })
        result = wizard.action_confirm()
        lot = self.env['tobacco.stamp.lot'].browse(
            result['res_id']
        )
        balance_before = zone_a.balance
        production = self.env['mrp.production'].create({
            'product_id': self.product.id,
            'product_qty': 5,
            'bom_id': self.bom.id,
        })
        production.stamp_zone_id = zone_a.id
        serials = lot.serial_ids[:5]
        serials.write({
            'state': 'reserved',
            'production_id': production.id,
        })
        brk_wiz = self.env[
            'tobacco.stamp.breakdown.wizard'
        ].create({
            'production_id': production.id,
            'serial_ids': [(4, serials[0].id)],
            'breakdown_reason': 'handling_error',
        })
        brk_wiz.action_confirm()
        self.assertEqual(serials[0].state, 'broken')
        self.assertEqual(
            zone_a.balance, balance_before - 1
        )

    def test_security_stock_manager_only(self):
        user_no_mgr = self.env['res.users'].create({
            'name': 'Operador Acc',
            'login': 'op_acc_test',
            'groups_id': [(4, self.env.ref(
                'stamp_chain.group_stamp_user'
            ).id)],
        })
        # Criar como admin (tem permissao)
        wizard = self.env[
            'tobacco.min.stock.wizard'
        ].create({
            'zone_id': self.zone_ptc.id,
            'current_value':
                self.zone_ptc.min_stock_alert,
            'new_value':
                self.zone_ptc.min_stock_alert + 500,
            'change_reason': 'Teste aceitacao',
        })
        # Executar como non-manager
        with self.assertRaises(UserError):
            wizard.with_user(
                user_no_mgr
            ).action_confirm()

    def test_edic_xml_contains_required_fields(self):
        wizard = self.env[
            'tobacco.incm.reception.wizard'
        ].create({
            'incm_ref': 'EDIC-ACC-001',
            'zone_id': self.zone_ptc.id,
            'qty_lots': 1,
        })
        result = wizard.action_confirm()
        lot = self.env['tobacco.stamp.lot'].browse(
            result['res_id']
        )
        doc = self.env[
            'tobacco.fiscal.document'
        ].create({
            'document_type': 'edic',
            'origin_warehouse_id': self.wh_ef.id,
            'destination_warehouse_id': self.wh_a1.id,
            'lot_ids': [(4, lot.id)],
            'serial_ids': [
                (4, s.id) for s in lot.serial_ids[:5]
            ],
            'period_from': fields.Date.today(),
            'period_to': fields.Date.today(),
        })
        doc.action_generate_xml()
        self.assertEqual(doc.state, 'xml_ready')
        self.assertIn('<eDIC', doc.xml_content)
        self.assertIn('EDIC-ACC-001', doc.xml_content)
        self.assertIn('PT_C', doc.xml_content)
        self.assertTrue(
            doc.xml_filename.endswith('.xml')
        )

    def test_transfer_creates_moves(self):
        wizard = self.env[
            'tobacco.incm.reception.wizard'
        ].create({
            'incm_ref': 'TRF-ACC-001',
            'zone_id': self.zone_ptc.id,
            'qty_lots': 1,
        })
        result = wizard.action_confirm()
        lot = self.env['tobacco.stamp.lot'].browse(
            result['res_id']
        )
        production = self.env['mrp.production'].create({
            'product_id': self.product.id,
            'product_qty': 5,
            'bom_id': self.bom.id,
        })
        serials = lot.serial_ids[:5]
        serials.write({
            'state': 'reserved',
            'production_id': production.id,
        })
        doc = self.env[
            'tobacco.fiscal.document'
        ].create({
            'document_type': 'edic',
            'origin_warehouse_id': self.wh_ef.id,
            'destination_warehouse_id': self.wh_a1.id,
            'lot_ids': [(4, lot.id)],
            'serial_ids': [
                (4, s.id) for s in serials
            ],
            'period_from': fields.Date.today(),
            'period_to': fields.Date.today(),
            'state': 'at_approved',
            'at_code': 'AT-ACC-TEST-999',
        })
        doc.action_create_transfer()
        self.assertTrue(doc.transfer_picking_id)
        self.assertTrue(
            doc.transfer_picking_id.move_ids
        )
        self.assertEqual(doc.state, 'transferred')
        for s in serials:
            s.invalidate_recordset()
            self.assertEqual(
                s.edic_ref, 'AT-ACC-TEST-999'
            )
