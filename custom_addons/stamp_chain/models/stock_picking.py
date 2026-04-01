# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    stamp_movement_ids = fields.One2many(
        'tobacco.stamp.movement',
        'picking_id',
        string='Movimentos de Estampilhas',
    )
    stamp_validated_at = fields.Datetime(
        string='Estampilhas Baixadas Em',
        readonly=True,
    )
    stamp_validated_by = fields.Many2one(
        'res.users',
        string='Baixado Por',
        readonly=True,
    )
    wisedat_doc_id = fields.Char(
        string='ID Documento Wisedat',
        readonly=True,
    )
    wisedat_order_status = fields.Selection([
        ('pending', 'Pendente'),
        ('sent', 'Enviado'),
        ('failed', 'Falhou'),
    ], string='Estado Encomenda Wisedat',
       readonly=True,
       copy=False,
    )
    wisedat_retry_count = fields.Integer(
        string='Tentativas Wisedat',
        default=0,
        readonly=True,
    )
    wisedat_error_message = fields.Text(
        string='Erro Wisedat',
        readonly=True,
    )
    is_ef_to_a1_transfer = fields.Boolean(
        string='Transferencia EF -> A1',
        compute='_compute_is_ef_transfer',
        store=True,
    )
    fiscal_document_id = fields.Many2one(
        'tobacco.fiscal.document',
        string='Documento Fiscal (eDIC/e-DA)',
        readonly=True,
    )
    # — Handheld picking —
    current_move_line_id = fields.Many2one(
        'stock.move.line',
        string='Linha Actual Handheld',
    )
    picking_mode = fields.Selection([
        ('normal', 'Normal'),
        ('handheld', 'Handheld Guiado'),
    ], default='normal')
    scan_location_validated = fields.Boolean(
        default=False,
    )
    scan_product_validated = fields.Boolean(
        default=False,
    )

    @api.depends(
        'picking_type_id',
        'picking_type_id.code',
        'picking_type_id.warehouse_id')
    def _compute_is_ef_transfer(self):
        for picking in self:
            config = self.env[
                'tobacco.warehouse.config'
            ].search([
                ('warehouse_type', '=',
                 'fiscal_warehouse'),
            ], limit=1)
            picking.is_ef_to_a1_transfer = (
                picking.picking_type_id.code
                == 'internal'
                and bool(config)
                and picking.picking_type_id
                .warehouse_id.id
                == config.warehouse_id.id
            )

    def _get_sorted_move_lines(self):
        """Linhas ordenadas por rota de armazem."""
        self.ensure_one()
        return self.move_line_ids.sorted(
            key=lambda l: (
                l.location_id.complete_name or ''
            )
        )

    def action_open_handheld(self):
        """C2: ir.actions.client via metodo."""
        self.ensure_one()
        return {
            'type': 'ir.actions.client',
            'tag': 'stamp_chain.picking_handheld',
            'context': {'picking_id': self.id},
        }

    def action_validate_location_scan(
        self, scanned_barcode
    ):
        self.ensure_one()
        lines = self._get_sorted_move_lines()
        if not lines:
            return {
                'ok': False,
                'message': 'Sem linhas de picking',
            }
        current = (
            self.current_move_line_id
            or lines[0]
        )
        expected = (
            current.location_id.barcode
            or current.location_id.name
        )
        if scanned_barcode == expected:
            self.write({
                'scan_location_validated': True,
                'current_move_line_id': current.id,
            })
            return {
                'ok': True,
                'location': expected,
                'product': current.product_id.name,
                'qty_todo': current.quantity,
                'move_line_id': current.id,
            }
        return {
            'ok': False,
            'message': (
                f'Localizacao errada!\n'
                f'Esperado: {expected}\n'
                f'Lido: {scanned_barcode}'
            ),
        }

    def action_validate_product_scan(
        self, scanned_barcode
    ):
        self.ensure_one()
        if not self.scan_location_validated:
            return {
                'ok': False,
                'message': (
                    'Valide a localizacao primeiro'
                ),
            }
        current = self.current_move_line_id
        if not current:
            return {
                'ok': False,
                'message': 'Sem linha activa',
            }
        product = current.product_id
        valid = [
            product.barcode,
            product.default_code,
        ]
        try:
            if product.barcode_ids:
                valid += (
                    product.barcode_ids.mapped(
                        'name'
                    )
                )
        except Exception:
            pass
        valid = [b for b in valid if b]
        if scanned_barcode in valid:
            self.scan_product_validated = True
            return {
                'ok': True,
                'product': product.name,
                'qty_todo': current.quantity,
                'move_line_id': current.id,
            }
        return {
            'ok': False,
            'message': (
                f'Produto errado!\n'
                f'Esperado: {product.name}\n'
                f'Lido: {scanned_barcode}'
            ),
        }

    def action_confirm_qty(
        self, qty_done, move_line_id
    ):
        """C5: recebe move_line_id."""
        self.ensure_one()
        line = self.env[
            'stock.move.line'
        ].browse(move_line_id)
        if not line.exists():
            return {
                'ok': False,
                'message': 'Linha invalida',
            }
        line.quantity = qty_done
        lines = self._get_sorted_move_lines()
        line_ids = list(lines.ids)
        current_idx = (
            line_ids.index(move_line_id)
            if move_line_id in line_ids
            else -1
        )
        next_idx = current_idx + 1
        if next_idx >= len(lines):
            self.write({
                'current_move_line_id': False,
                'scan_location_validated': False,
                'scan_product_validated': False,
            })
            return {
                'ok': True,
                'done': True,
                'message': 'Picking concluido!',
            }
        next_line = lines[next_idx]
        self.write({
            'current_move_line_id': next_line.id,
            'scan_location_validated': False,
            'scan_product_validated': False,
        })
        return {
            'ok': True,
            'done': False,
            'next_location': (
                next_line.location_id.barcode
                or next_line.location_id.name
            ),
            'next_product':
                next_line.product_id.name,
            'next_qty': next_line.quantity,
            'next_move_line_id': next_line.id,
            'progress': (
                f'{next_idx + 1}/{len(lines)}'
            ),
        }

    def _check_ef_shipment_block(self):
        for picking in self:
            if picking.picking_type_id.code != 'outgoing':
                continue
            ef_config = self.env[
                'tobacco.warehouse.config'
            ].search([
                ('warehouse_type', '=',
                 'fiscal_warehouse'),
                ('warehouse_id', '=',
                 picking.picking_type_id
                 .warehouse_id.id),
            ], limit=1)
            if ef_config:
                raise UserError(
                    'Nao e possivel expedir '
                    'directamente do Entreposto '
                    'Fiscal (EF).\n'
                    'Realize a eDIC e transfira '
                    'para A1 primeiro.'
                )

    def button_validate(self):
        self._check_ef_shipment_block()
        res = super().button_validate()
        for picking in self:
            if (picking.picking_type_code == 'outgoing'
                    and picking.state == 'done'):
                picking._process_stamp_usage()
                config = self.env[
                    'tobacco.wisedat.config'
                ].search([], limit=1)
                if config and config.sync_orders:
                    picking._send_wisedat_order(config)
        return res

    def _send_wisedat_order(self, config):
        """Envia encomenda ECL ao Wisedat.
        Nao bloqueia o picking em caso de erro.
        Regista estado e erro para retry."""
        self.ensure_one()
        self.wisedat_order_status = 'pending'
        try:
            config._create_wisedat_order(self.id)
            self.write({
                'wisedat_order_status': 'sent',
                'wisedat_error_message': False,
            })
        except Exception as e:
            error_msg = str(e)
            _logger.warning(
                'Encomenda Wisedat falhou '
                '(nao bloqueia): %s', e
            )
            self.write({
                'wisedat_order_status': 'failed',
                'wisedat_retry_count': (
                    self.wisedat_retry_count + 1
                ),
                'wisedat_error_message': error_msg,
            })
            self.message_post(
                body=(
                    '<b>Erro Wisedat</b><br/>'
                    'A encomenda nao foi enviada '
                    'para o Wisedat.<br/>'
                    f'<i>{error_msg}</i><br/>'
                    'Use o botao "Reenviar Wisedat" '
                    'para tentar novamente.'
                ),
                message_type='notification',
                subtype_xmlid='mail.mt_note',
            )

    def action_retry_wisedat_order(self):
        """Botao retry — reenvia encomenda ECL
        ao Wisedat."""
        self.ensure_one()
        config = self.env[
            'tobacco.wisedat.config'
        ].search([], limit=1)
        if not config:
            raise UserError(
                'Configuracao Wisedat nao encontrada.'
            )
        self._send_wisedat_order(config)
        if self.wisedat_order_status == 'sent':
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'StampChain',
                    'message': (
                        'Encomenda reenviada com '
                        'sucesso!'
                    ),
                    'type': 'success',
                },
            }
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'StampChain',
                'message': (
                    'Reenvio falhou. Verifique '
                    'a ligacao ao Wisedat.'
                ),
                'type': 'danger',
            },
        }

    def _process_stamp_usage(self):
        self.ensure_one()
        sale = self.env['sale.order'].search(
            [('name', '=', self.origin)],
            limit=1,
        )
        if not sale or not sale.stamp_zone_id:
            return

        with self.env.cr.savepoint():
            try:
                serials = self.env[
                    'tobacco.stamp.serial'
                ].search([
                    ('sale_order_id', '=', sale.id),
                    ('state', '=', 'reserved'),
                ])
                if not serials:
                    _logger.warning(
                        'StampChain: Sem seriais '
                        'reservados para %s', self.name
                    )
                    return

                serials.write({
                    'state': 'used',
                    'picking_id': self.id,
                    'used_date': fields.Datetime.now(),
                })

                self.env[
                    'tobacco.stamp.movement'
                ].create({
                    'zone_id': sale.stamp_zone_id.id,
                    'move_type': 'out',
                    'qty': len(serials),
                    'reference': self.name,
                    'picking_id': self.id,
                    'notes': (
                        f'Expedicao validada: '
                        f'{self.name} — '
                        f'Encomenda: {sale.name}'
                    ),
                })

                self.write({
                    'stamp_validated_at':
                        fields.Datetime.now(),
                    'stamp_validated_by':
                        self.env.user.id,
                })

                sale.stamp_zone_id._send_stock_alert()

            except Exception as e:
                _logger.error(
                    'StampChain erro na baixa '
                    'de estampilhas: %s', e
                )
