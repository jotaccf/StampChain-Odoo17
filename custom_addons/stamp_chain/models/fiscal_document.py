# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import UserError
import base64
import logging
from datetime import datetime

_logger = logging.getLogger(__name__)


class TobaccoFiscalDocument(models.Model):
    _name = 'tobacco.fiscal.document'
    _description = 'Documento Fiscal IEC (eDIC/e-DA)'
    _order = 'date desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(
        string='Referencia Interna',
        required=True,
        copy=False,
        default=lambda self:
            self.env['ir.sequence'].next_by_code(
                'tobacco.fiscal.document'
            ),
    )
    document_type = fields.Selection([
        ('edic', 'eDIC — Introducao no Consumo'),
        ('eda', 'e-DA — Documento Administrativo'),
    ], string='Tipo de Documento',
       required=True,
       tracking=True,
    )
    origin_warehouse_id = fields.Many2one(
        'stock.warehouse',
        string='Armazem de Origem',
        required=True,
    )
    destination_warehouse_id = fields.Many2one(
        'stock.warehouse',
        string='Armazem de Destino',
        required=True,
    )
    # Many2many inverso definido em stamp_lot.py
    # Tabela: fiscal_doc_lot_rel
    # Esta coluna: doc_id — outra: lot_id
    lot_ids = fields.Many2many(
        'tobacco.stamp.lot',
        'fiscal_doc_lot_rel',
        'doc_id', 'lot_id',
        string='Lotes INCM Abrangidos',
    )
    serial_ids = fields.Many2many(
        'tobacco.stamp.serial',
        'fiscal_doc_serial_rel',
        'doc_id', 'serial_id',
        string='Seriais Abrangidos',
    )
    stamp_qty = fields.Integer(
        string='Quantidade de Estampilhas',
        compute='_compute_stamp_qty',
        store=True,
    )
    date = fields.Datetime(
        string='Data de Geracao',
        default=fields.Datetime.now,
        readonly=True,
    )
    period_from = fields.Date(
        string='Periodo De',
        required=True,
    )
    period_to = fields.Date(
        string='Periodo Ate',
        required=True,
    )
    zone_id = fields.Many2one(
        'tobacco.stamp.zone',
        string='Zona IEC',
    )
    xml_content = fields.Text(
        string='Conteudo XML',
        readonly=True,
    )
    xml_file = fields.Binary(
        string='Ficheiro XML',
        readonly=True,
        attachment=True,
    )
    xml_filename = fields.Char(readonly=True)
    xml_generated_at = fields.Datetime(
        string='XML Gerado Em',
        readonly=True,
    )
    xml_sent_by_email = fields.Boolean(
        string='Enviado por Email',
        default=False,
        readonly=True,
    )
    xml_sent_at = fields.Datetime(
        string='Email Enviado Em',
        readonly=True,
    )
    # NOT required — validado em action_send_email
    email_recipient = fields.Char(
        string='Email AT Destinatario',
    )
    at_code = fields.Char(
        string='Codigo AT',
        tracking=True,
    )
    at_code_date = fields.Datetime(
        string='Data Insercao Codigo AT',
        readonly=True,
    )
    at_code_inserted_by = fields.Many2one(
        'res.users',
        string='Inserido por',
        readonly=True,
    )
    transfer_picking_id = fields.Many2one(
        'stock.picking',
        string='Transferencia EF -> A1',
        readonly=True,
    )
    state = fields.Selection([
        ('draft', 'Rascunho'),
        ('xml_ready', 'XML Gerado'),
        ('email_sent', 'Email Enviado para AT'),
        ('at_pending', 'Aguarda Codigo AT'),
        ('at_approved', 'AT Aprovada'),
        ('transferred', 'Mercadoria Transferida'),
        ('cancelled', 'Cancelado'),
    ], string='Estado',
       default='draft',
       tracking=True,
    )
    operation_log = fields.Text(
        string='Log de Operacoes',
        readonly=True,
    )

    @api.depends('serial_ids')
    def _compute_stamp_qty(self):
        for rec in self:
            rec.stamp_qty = len(rec.serial_ids)

    def _append_log(self, message):
        timestamp = datetime.now().strftime(
            '%Y-%m-%d %H:%M:%S'
        )
        user = self.env.user.name
        entry = f'[{timestamp}] {user}: {message}'
        current = self.operation_log or ''
        self.operation_log = entry + '\n' + current

    def action_generate_xml(self):
        self.ensure_one()
        if self.state not in ('draft', 'xml_ready'):
            raise UserError(
                'Apenas documentos em rascunho '
                'podem gerar XML.'
            )
        if not self.lot_ids:
            raise UserError(
                'Seleccione pelo menos um Lote INCM.'
            )
        if self.document_type == 'edic':
            xml_content = self._generate_edic_xml()
        else:
            xml_content = self._generate_eda_xml()
        filename = (
            f'StampChain_'
            f'{self.document_type.upper()}_'
            f'{self.name}_'
            f'{datetime.now().strftime("%Y%m%d_%H%M%S")}'
            f'.xml'
        )
        self.write({
            'xml_content': xml_content,
            'xml_file': base64.b64encode(
                xml_content.encode('utf-8')
            ),
            'xml_filename': filename,
            'xml_generated_at': fields.Datetime.now(),
            'state': 'xml_ready',
        })
        self._append_log(f'XML gerado: {filename}')

    def _generate_edic_xml(self):
        self.ensure_one()
        lines = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<eDIC>',
            '  <Header>',
            f'    <DocumentRef>{self.name}</DocumentRef>',
            f'    <DocumentType>eDIC</DocumentType>',
            f'    <GeneratedAt>{fields.Datetime.now()}</GeneratedAt>',
            f'    <PeriodFrom>{self.period_from}</PeriodFrom>',
            f'    <PeriodTo>{self.period_to}</PeriodTo>',
            f'    <OriginWarehouse>{self.origin_warehouse_id.code}</OriginWarehouse>',
            f'    <DestWarehouse>{self.destination_warehouse_id.code}</DestWarehouse>',
            f'    <TotalStamps>{self.stamp_qty}</TotalStamps>',
            '  </Header>',
            '  <StampLots>',
        ]
        for lot in self.lot_ids:
            serials = self.serial_ids.filtered(
                lambda s: s.lot_id == lot
            )
            lines += [
                '    <Lot>',
                f'      <INCMRef>{lot.incm_ref}</INCMRef>',
                f'      <LotRef>{lot.name}</LotRef>',
                f'      <Zone>{lot.zone_id.code}</Zone>',
                f'      <ReceptionDate>{lot.reception_date}</ReceptionDate>',
                f'      <StampCount>{len(serials)}</StampCount>',
                '    </Lot>',
            ]
        lines.append('  </StampLots>')
        lines.append('  <Serials>')
        for s in self.serial_ids:
            lines.append(
                f'    <Serial lot="{s.lot_id.incm_ref}" '
                f'zone="{s.zone_id.code}">'
                f'{s.serial_number}</Serial>'
            )
        lines += ['  </Serials>', '  <ATCode/>', '</eDIC>']
        return '\n'.join(lines)

    def _generate_eda_xml(self):
        self.ensure_one()
        lines = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<eDA>',
            '  <Header>',
            f'    <DocumentRef>{self.name}</DocumentRef>',
            f'    <DocumentType>e-DA</DocumentType>',
            f'    <GeneratedAt>{fields.Datetime.now()}</GeneratedAt>',
            f'    <MovementDate>{self.period_from}</MovementDate>',
            f'    <OriginWarehouse>{self.origin_warehouse_id.code}</OriginWarehouse>',
            f'    <DestWarehouse>{self.destination_warehouse_id.code}</DestWarehouse>',
            f'    <TotalStamps>{self.stamp_qty}</TotalStamps>',
            '  </Header>',
            '  <StampLots>',
        ]
        for lot in self.lot_ids:
            lines += [
                '    <Lot>',
                f'      <INCMRef>{lot.incm_ref}</INCMRef>',
                f'      <LotRef>{lot.name}</LotRef>',
                f'      <Zone>{lot.zone_id.code}</Zone>',
                '    </Lot>',
            ]
        lines += ['  </StampLots>', '  <ATCode/>', '</eDA>']
        return '\n'.join(lines)

    def action_send_email(self):
        self.ensure_one()
        if self.state != 'xml_ready':
            raise UserError('Gere o XML primeiro.')
        if not self.xml_file:
            raise UserError('Ficheiro XML nao encontrado.')
        if not self.email_recipient:
            raise UserError(
                'Defina o email destinatario antes de enviar.'
            )
        mail = self.env['mail.mail'].create({
            'subject': (
                f'StampChain — '
                f'{self.document_type.upper()} '
                f'{self.name} — Portal AT'
            ),
            'email_to': self.email_recipient,
            'body_html': (
                f'<p>Documento fiscal '
                f'{self.document_type.upper()} '
                f'{self.name} para submissao '
                f'no Portal das Financas.</p>'
                f'<p>Origem: {self.origin_warehouse_id.name}<br/>'
                f'Destino: {self.destination_warehouse_id.name}<br/>'
                f'Estampilhas: {self.stamp_qty}</p>'
            ),
            'attachment_ids': [(0, 0, {
                'name': self.xml_filename,
                'datas': self.xml_file,
                'mimetype': 'application/xml',
            })],
        })
        mail.send()
        self.write({
            'state': 'email_sent',
            'xml_sent_by_email': True,
            'xml_sent_at': fields.Datetime.now(),
        })
        self._append_log(
            f'XML enviado para: {self.email_recipient}'
        )

    def action_mark_at_pending(self):
        self.ensure_one()
        if self.state != 'email_sent':
            raise UserError(
                'O email deve ter sido enviado primeiro.'
            )
        self.state = 'at_pending'
        self._append_log(
            'Submissao manual confirmada. '
            'A aguardar codigo AT.'
        )

    def action_insert_at_code(self):
        self.ensure_one()
        if self.state != 'at_pending':
            raise UserError(
                'Estado invalido para insercao de codigo AT.'
            )
        return {
            'type': 'ir.actions.act_window',
            'name': f'Inserir Codigo AT — {self.name}',
            'res_model': 'tobacco.at.code.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_fiscal_document_id': self.id,
                'default_document_type': self.document_type,
            },
        }

    def action_create_transfer(self):
        self.ensure_one()
        if self.state != 'at_approved':
            raise UserError(
                'Codigo AT deve estar aprovado primeiro.'
            )
        if self.transfer_picking_id:
            raise UserError(
                f'Transferencia ja criada: '
                f'{self.transfer_picking_id.name}'
            )
        picking_type = self.env[
            'stock.picking.type'
        ].search([
            ('warehouse_id', '=',
             self.origin_warehouse_id.id),
            ('code', '=', 'internal'),
        ], limit=1)
        if not picking_type:
            raise UserError(
                'Tipo de operacao interna nao '
                'encontrado para o armazem EF.'
            )
        picking = self.env['stock.picking'].create({
            'picking_type_id': picking_type.id,
            'location_id':
                self.origin_warehouse_id.lot_stock_id.id,
            'location_dest_id':
                self.destination_warehouse_id.lot_stock_id.id,
            'origin': self.name,
            'fiscal_document_id': self.id,
            'note': (
                f'EF -> A1 apos '
                f'{self.document_type.upper()} '
                f'{self.name}. '
                f'Codigo AT: {self.at_code}'
            ),
        })
        # Agrupa seriais por produto via production_id
        product_qtys = {}
        for serial in self.serial_ids:
            prod_order = serial.production_id
            if prod_order and prod_order.product_id:
                product = prod_order.product_id
            else:
                _logger.warning(
                    'Serial %s sem production_id — '
                    'ignorado na transferencia',
                    serial.serial_number
                )
                continue
            if product.id not in product_qtys:
                product_qtys[product.id] = {
                    'product': product,
                    'qty': 0,
                }
            product_qtys[product.id]['qty'] += 1

        for data in product_qtys.values():
            self.env['stock.move'].create({
                'name': (
                    f'EF->A1 {self.name} — '
                    f'{data["product"].name}'
                ),
                'picking_id': picking.id,
                'product_id': data['product'].id,
                'product_uom':
                    data['product'].uom_id.id,
                'product_uom_qty': data['qty'],
                'location_id':
                    self.origin_warehouse_id
                    .lot_stock_id.id,
                'location_dest_id':
                    self.destination_warehouse_id
                    .lot_stock_id.id,
            })

        self.write({
            'transfer_picking_id': picking.id,
            'state': 'transferred',
        })
        self._append_log(
            f'Transferencia criada: {picking.name}'
        )
        self.lot_ids.write({
            'warehouse_id':
                self.destination_warehouse_id.id,
        })
        self.serial_ids.write({
            'current_warehouse_id':
                self.destination_warehouse_id.id,
            'edic_ref': self.at_code
            if self.document_type == 'edic' else False,
            'eda_ref': self.at_code
            if self.document_type == 'eda' else False,
        })
        return {
            'type': 'ir.actions.act_window',
            'name': 'Transferencia Criada',
            'res_model': 'stock.picking',
            'res_id': picking.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_cancel(self):
        self.ensure_one()
        if self.state in ('transferred',):
            raise UserError(
                'Documento ja transferido — '
                'nao pode ser cancelado.'
            )
        self.state = 'cancelled'
        self._append_log('Documento cancelado.')
