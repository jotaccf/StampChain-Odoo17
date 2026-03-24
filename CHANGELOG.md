# Changelog

All notable changes to StampChain are documented in this file.

Format: [Keep a Changelog](https://keepachangelog.com)
Versioning: [Semantic Versioning](https://semver.org)

---

## [17.0.1.0.0] — 2026-03-24

### Added
- OWL 2.0 real-time dashboard with balance cards per IEC zone
- Stamp breakdown wizard with mandatory justification and photo evidence
- Stamp recovery workflow: broken → quarantine → manager approval → available
- tobacco.stamp.recovery model with dual validation (manager group required)
- tobacco.stamp.zone.history model for security stock audit trail
- Min stock wizard (manager only) with mandatory change reason
- Recovery movement type in account ledger
- Unit tests: 7 test files covering all core business logic
- OCA modules: barcodes_generator_location, barcodes_generator_product, product_multi_barcode, stock_picking_product_barcode_report, quality_control_oca
- IR sequences: SC/LOT, SC/BRK, SC/REC, SC/XML

### Changed
- stamp_serial state field: added 'quarantine'
- stamp_movement move_type: added 'recovery'
- stamp_zone balance computation: recovery movements count as positive entries
- min_stock_alert field: restricted to group_stamp_manager

## [17.0.0.2.0] — 2026-03-24

### Added
- FIFO strict enforcement with automatic violation blocking
- mrp.production extension: stamp zone computation, FIFO reservation
- stock.picking extension: fiscal trigger on outgoing shipment validation
- res.partner extension: stamp_zone_id, wisedat_id fields
- sale.order extension: stamp zone relay, required stamps calculation
- INCM Reception Wizard: lot creation, serial number generation
- Real-time balance computation per zone
- Minimum stock alert with notification
- tobacco.wisedat.config model (REST API)
- tobacco.xml.export model (v2.0 skeleton)

## [17.0.0.1.0] — 2026-03-24

### Added
- Initial module scaffold
- tobacco.stamp.zone (3 IEC zones: PT_C/M/A)
- tobacco.stamp.lot (INCM lots, 500 units)
- tobacco.stamp.serial (individual serials)
- tobacco.stamp.movement (immutable ledger)
- tobacco.stamp.breakdown (broken stamps)
- 4 security groups: user, production, manager, fiscal
- Initial data: Continente, Madeira, Acores
- Docker development environment
- odoo.conf with OCA addons paths
