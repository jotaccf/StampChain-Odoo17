# StampChain
### Odoo 17 Community — IEC Stamp Management Module

> Vertical module for complete lifecycle management of tobacco products subject to Special Consumption Tax (IEC) in Portugal.

## Features

- Real-time IEC stamp account per geographic zone (Mainland, Madeira, Azores)
- Individual serial number traceability per stamp
- Strict FIFO enforcement by INCM lot
- Bidirectional Wisedat invoicing integration
- Android handheld guided picking via browser
- QR code generation for warehouse locations and products
- Stamp recovery workflow with dual validation and quarantine
- Configurable security stock per zone (manager only, with audit history)
- XML export architecture for AT/DGAIEC (v2.0 roadmap)

## Requirements

- Odoo 17.0 Community Edition
- PostgreSQL 15+
- Python 3.11+

### Odoo Module Dependencies

`stock`, `mrp`, `sale_management`, `purchase`, `account`, `delivery`, `mail`

### OCA Module Dependencies (branch 17.0)

`barcodes_generator_location`, `barcodes_generator_product`, `product_multi_barcode`, `stock_picking_product_barcode_report`, `quality_control_oca`

## Installation

### Development (Docker)

```bash
git clone https://github.com/jotaccf/StampChain-Odoo17
cd StampChain-Odoo17
cp .env.example .env
# Edit .env with your credentials
docker compose up -d
docker compose exec odoo odoo \
  -d stampchain_dev \
  -i stamp_chain \
  --stop-after-init --no-http
```

### Production (Hyper-V)

```bash
cd /odoo/custom_addons/stamp_chain
git pull origin main
docker exec odoo odoo \
  -d production \
  -u stamp_chain \
  --stop-after-init
```

## Module Structure

```
stamp_chain/
├── models/          # Data models
├── views/           # XML views & menus
├── wizard/          # Transient models
├── security/        # Groups & ACL
├── data/            # Initial data (3 IEC zones)
├── report/          # PDF reports
├── static/          # OWL 2.0 dashboard
└── tests/           # Unit tests
```

## IEC Zones

| Zone | Code | Description |
|------|------|-------------|
| Mainland | PT_C | Continental Portugal |
| Madeira | PT_M | Madeira Autonomous Region |
| Azores | PT_A | Azores Autonomous Region |

## Key Business Rules

- Physical product is identical across zones — zone is determined exclusively by the stamp
- Stamp balance deducted ONLY on shipment validation (stock.picking)
- FIFO strictly enforced — older lots consumed first, violations blocked automatically
- Broken stamp recovery requires dual validation (quarantine → manager approval → available)
- Security stock editable by Manager only, with mandatory reason and full audit history

## Running Tests

```bash
docker compose exec odoo odoo \
  -d stampchain_dev \
  --test-enable \
  --test-tags stamp_chain \
  --stop-after-init --no-http
```

## Roadmap

See [ROADMAP.md](ROADMAP.md) for detailed version history and planned features.

## License

GNU Lesser General Public License v3.0 — See [LICENSE](LICENSE) for details.

## Author

**jotaccf**
