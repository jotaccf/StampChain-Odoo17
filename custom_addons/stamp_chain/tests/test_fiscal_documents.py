# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError
from odoo import fields


class TestFiscalDocuments(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        manager_group = cls.env.ref(
            'stamp_chain.group_stamp_manager'
        )
        cls.env.user.groups_id |= manager_group

        cls.wh_ef = cls.env['stock.warehouse'].create({
            'name': 'EF Test',
            'code': 'TEF',
        })
        cls.wh_a1 = cls.env['stock.warehouse'].create({
            'name': 'A1 Test',
            'code': 'TA1',
        })
        cls.zone = cls.env['tobacco.stamp.zone'].search(
            [('code', '=', 'PT_C')], limit=1
        )
        cls.product = cls.env['product.product'].create({
            'name': 'Tabaco Fiscal Test',
            'default_code': 'TAB-FIS-001',
            'type': 'product',
        })
        bom = cls.env['mrp.bom'].create({
            'product_id': cls.product.id,
            'product_tmpl_id':
                cls.product.product_tmpl_id.id,
            'product_qty': 1,
        })
        cls.production = cls.env['mrp.production'].create({
            'product_id': cls.product.id,
            'product_qty': 10,
            'bom_id': bom.id,
        })
        cls.lot = cls.env['tobacco.stamp.lot'].create({
            'name': 'FIS-LOT-001',
            'incm_ref': 'TEST-INCM-FIS',
            'zone_id': cls.zone.id,
            'reception_date': fields.Date.today(),
            'qty_received': 500,
            'state': 'received',
            'fifo_sequence': 999,
        })
        cls.serials = cls.env['tobacco.stamp.serial'].create([
            {
                'serial_number':
                    f'PT_C-2026-FIS-{i:06d}',
                'lot_id': cls.lot.id,
                'state': 'reserved',
                'production_id': cls.production.id,
            }
            for i in range(1, 6)
        ])
        cls.wisedat_config = cls.env[
            'tobacco.wisedat.config'
        ].create({
            'name': 'Test Config',
            'api_url': 'http://test:8080',
            'api_key': 'test-key',
            'api_username': 'test-user',
            'api_password': 'test-pass',
        })
        cls.env['tobacco.warehouse.config'].create({
            'name': 'EF Config',
            'warehouse_id': cls.wh_ef.id,
            'wisedat_warehouse_code': 'EF',
            'warehouse_type': 'fiscal_warehouse',
            'requires_edic': True,
            'destination_warehouse_id': cls.wh_a1.id,
            'wisedat_config_id': cls.wisedat_config.id,
        })

    def _create_doc(self, doc_type='edic', **kwargs):
        vals = {
            'document_type': doc_type,
            'origin_warehouse_id': self.wh_ef.id,
            'destination_warehouse_id': self.wh_a1.id,
            'lot_ids': [(4, self.lot.id)],
            'serial_ids': [(4, s.id) for s in self.serials],
            'period_from': fields.Date.today(),
            'period_to': fields.Date.today(),
        }
        vals.update(kwargs)
        return self.env['tobacco.fiscal.document'].create(vals)

    def test_edic_xml_generation(self):
        doc = self._create_doc()
        doc.action_generate_xml()
        self.assertEqual(doc.state, 'xml_ready')
        self.assertIn('<eDIC', doc.xml_content)
        self.assertIn('TEST-INCM-FIS', doc.xml_content)

    def test_eda_xml_generation(self):
        doc = self._create_doc(doc_type='eda')
        doc.action_generate_xml()
        self.assertEqual(doc.state, 'xml_ready')
        self.assertIn('<eDA', doc.xml_content)

    def test_state_flow_correct(self):
        doc = self._create_doc(
            email_recipient='at@test.pt'
        )
        self.assertEqual(doc.state, 'draft')
        doc.action_generate_xml()
        self.assertEqual(doc.state, 'xml_ready')

    def test_email_requires_recipient(self):
        doc = self._create_doc()
        doc.action_generate_xml()
        with self.assertRaises(UserError):
            doc.action_send_email()

    def test_at_code_links_to_lot(self):
        doc = self._create_doc(state='at_pending')
        wizard = self.env['tobacco.at.code.wizard'].create({
            'fiscal_document_id': doc.id,
            'document_type': 'edic',
            'at_code': 'AT-TEST-12345',
            'confirmation': True,
        })
        wizard.action_confirm()
        self.assertEqual(doc.state, 'at_approved')
        self.lot.invalidate_recordset()
        self.assertEqual(self.lot.edic_ref, 'AT-TEST-12345')

    def test_ef_direct_shipment_blocked(self):
        picking_type = self.env[
            'stock.picking.type'
        ].search([
            ('warehouse_id', '=', self.wh_ef.id),
            ('code', '=', 'outgoing'),
        ], limit=1)
        if not picking_type:
            return
        picking = self.env['stock.picking'].create({
            'picking_type_id': picking_type.id,
            'location_id':
                self.wh_ef.lot_stock_id.id,
            'location_dest_id':
                self.env.ref(
                    'stock.stock_location_customers'
                ).id,
        })
        with self.assertRaises(UserError):
            picking.button_validate()

    def test_transfer_creates_stock_moves(self):
        doc = self._create_doc(
            state='at_approved',
            at_code='AT-MOVE-TEST-999',
        )
        doc.action_create_transfer()
        self.assertTrue(doc.transfer_picking_id)
        self.assertTrue(
            doc.transfer_picking_id.move_ids
        )
        move_products = (
            doc.transfer_picking_id.move_ids
            .mapped('product_id')
        )
        self.assertIn(self.product, move_products)
        total_qty = sum(
            doc.transfer_picking_id.move_ids
            .mapped('product_uom_qty')
        )
        self.assertEqual(
            total_qty, len(self.serials)
        )
        for serial in self.serials:
            serial.invalidate_recordset()
            self.assertEqual(
                serial.edic_ref, 'AT-MOVE-TEST-999'
            )
        self.assertEqual(doc.state, 'transferred')
