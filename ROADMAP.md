# StampChain — Roadmap & Version History

## Versioning Convention

StampChain follows **Semantic Versioning**: `{ODOO_VERSION}.{MAJOR}.{MINOR}.{PATCH}`

| Segment | Meaning | Example |
|---------|---------|---------|
| ODOO_VERSION | Odoo major version | 17 |
| MAJOR | Breaking changes or new modules | 1→2 |
| MINOR | New features, backward compatible | 0→1 |
| PATCH | Bug fixes, minor improvements | 0→1 |

---

## Version History

### v17.0.0.1.0 — Alpha

**Released:** March 2026 | **Status:** Released

Proof of concept — core data models and basic stamp zone management.

- [x] Module scaffold and manifest
- [x] tobacco.stamp.zone model (3 IEC zones)
- [x] tobacco.stamp.lot model (INCM lots)
- [x] tobacco.stamp.serial model (individual serial numbers)
- [x] tobacco.stamp.movement model (immutable account ledger)
- [x] Basic security groups (4 profiles)
- [x] Initial data: PT_C, PT_M, PT_A zones
- [x] Docker development environment

---

### v17.0.0.2.0 — Beta

**Released:** March 2026 | **Status:** Released

Core business logic — FIFO, production integration, expedition trigger.

- [x] FIFO strict enforcement (block on violation)
- [x] mrp.production extension (stamp reservation by zone)
- [x] stock.picking extension (fiscal trigger on validation)
- [x] res.partner extension (fiscal zone per client)
- [x] sale.order extension (required stamps calculation)
- [x] INCM Reception Wizard (serial generation PT_C-YYYY-REF-NNNNNN)
- [x] Stamp account balance (real-time computed per zone)
- [x] Stock minimum alert per zone

---

### v17.0.1.0.0 — Release Candidate

**Released:** March 2026 | **Status:** Released

Full operational module — wizards, dashboard, recovery, security stock.

- [x] OWL 2.0 Dashboard (real-time balance cards)
- [x] Breakdown Wizard (mandatory justification, photo evidence)
- [x] Stamp Recovery Workflow (broken → quarantine → approval → available)
- [x] Dual validation for recovery (manager approval required)
- [x] Security stock management (manager only, audit history)
- [x] tobacco.stamp.zone.history model
- [x] Min stock wizard with mandatory reason
- [x] OCA modules integration
- [x] Wisedat REST API configuration model
- [x] Unit tests (7 test files, 20 tests)

---

### v17.0.1.1.0 — Fiscal Warehouse

**Released:** March 2026 | **Status:** Released

Fiscal warehouse management, eDIC/e-DA, Wisedat integration.

- [x] Wisedat sync (customers, products, stock — mock tested)
- [x] Multi-warehouse: EF (fiscal) + A1 (main)
- [x] eDIC/e-DA XML generation with email dispatch
- [x] AT code insertion with EF→A1 transfer unlock
- [x] Wisedat ECL order creation (POST /orders, try/except, non-blocking)
- [x] EF direct shipment blocked
- [x] deploy.sh production script
- [x] GitHub Actions CI/CD pipeline
- [x] Barcode labels generation (warehouse locations QR codes)
- [x] Wisedat RSA authentication (tested against v02.25.1216.3)

---

### v17.0.1.2.0 — Reports & Documentation

**Released:** March 2026 | **Status:** Released

PDF reports, operator documentation, acceptance tests.

- [x] PDF report: stamp account by zone (QWeb)
- [x] PDF report: INCM lot traceability (QWeb)
- [x] Operator training manual (Portuguese, Markdown)
- [x] XML AT v2.0 mapping documentation (TODO for real files)
- [x] Wisedat API mapping documentation
- [x] Deploy checklist for Hyper-V production
- [x] Acceptance tests (7 self-contained)
- [x] Warehouse EF/A1 configured in dev

---

### v17.0.2.0.0 — Production Ready

**Released:** March 2026 | **Status:** Released

Full operational system: picking handheld, discrepancy audit,
OCR production wizards, complete UI redesign, Wisedat RSA.

- [x] Guided picking handheld (OWL 3-step: location/product/qty)
- [x] Warehouse layout wizard (configurable, saves to config)
- [x] QR label report for locations (Zebra ZD421)
- [x] Discrepancy audit system (immutable, auto-detection)
- [x] Found stamp workflow (dual validation)
- [x] Physical count with 24h override
- [x] OCR reception wizard (INCM serial extrapolation)
- [x] Production start/end wizards (consumption calculation)
- [x] StampChain design system (sc-* CSS, all views)
- [x] Wisedat RSA 2-step authentication (JWT cached)
- [x] Self-contained repo (OCA modules + Dockerfile)
- [x] Unit tests passing

---

### v17.0.2.5.0 — Wisedat Real API

**Released:** March 2026 | **Status:** Released

Real Wisedat API integration — ECL orders, series, chunked sync.

- [x] POST /orders (ECL) replaces /movementofgoods (transport guides removed)
- [x] Invoice sync removed entirely (zero consumers — team decision)
- [x] Document series management (GET /series, generic — no document_type)
- [x] Series validation on order creation
- [x] VAT prefix auto-fix (Wisedat sends NIF without country prefix)
- [x] Batch create fallback for invalid VAT (individual with vat=False)
- [x] Stop sync button (graceful interruption via flag)
- [x] post_load hook for assets cache cleanup on -u
- [x] Connection pooling (requests.Session, class-level)
- [x] API retry with exponential backoff (3 attempts)

---

### v17.0.2.6.0 — Full Customer Sync

**Released:** March 2026 | **Status:** Released

Complete customer field mapping, cron deadlock fix, parallel fetch.

- [x] Automatic full detail fetch during sync (parallel 10 workers per page)
- [x] Complete field mapping: ref, state_id, city, payment_condition, payment_method, currency
- [x] Entity type classification (wisedat_entity_type on res.partner)
- [x] Cron single-run architecture V8 (eliminates deadlock)
- [x] cron._trigger() for immediate execution (PostgreSQL NOTIFY)
- [x] Never modify ir_cron from within cron job (deadlock prevention)
- [x] _fetch_customers_detail_batch with ThreadPoolExecutor (10 workers)
- [x] Single request without retry for individual customer detail (4xx/5xx = skip)
- [x] Reset sync status button (manual recovery from stuck state)
- [x] Robust post_load hook (try/except, isinstance checks)
- [x] 16 test files, all passing

---

### v17.0.2.7.0 — Products, Periodic Sync & ECL Retry

**Released:** April 2026 | **Status:** Released

Complete product sync, automatic periodic re-sync, ECL order retry.

- [x] Complete product field mapping with parallel detail fetch (10 workers)
- [x] Product fields: barcode, image (replace), tax/unit/prices (info), weight, volume
- [x] Category image sync (replace on update)
- [x] brief_description removed (not editable in Wisedat, incorrect data)
- [x] Automatic periodic sync (configurable: 15min/30min/1h/4h/daily/manual)
- [x] Cron V9: runs every 15min, checks sync_frequency vs last_sync_date
- [x] ECL order retry: wisedat_order_status (pending/sent/failed) on stock.picking
- [x] Red alert banner + "Reenviar Wisedat" button when order push fails
- [x] Chatter notification with error details on failed push
- [x] Picking list filter "Wisedat Pendente" for failed orders
- [x] CI fix: pycryptodome + post_init_hook(env) Odoo 17 signature
- [x] Connection pool sized to match ThreadPoolExecutor (pool_maxsize=12)

---

### v17.0.3.0.0 — XML Fiscal

**Target:** Q3 2026 | **Status:** Planned

Fiscal compliance — XML export for AT/DGAIEC.

- [ ] SAF-T PT inventory XML export
- [ ] IEC stamp declaration XML
- [ ] Serial number map XML (full traceability report)
- [ ] CIUS-PT invoice export
- [ ] XSD validation (lxml)
- [ ] AT/DGAIEC submission workflow
- [ ] Multi-company support
- [ ] Multi-warehouse support

---

### v17.0.4.0.0 — Extended IEC

**Target:** Q4 2026 | **Status:** Planned

Extended products — IEC beyond tobacco.

- [ ] Alcohol products IEC support
- [ ] Fuel products IEC support
- [ ] Configurable product categories
- [ ] Generic IEC zone management
- [ ] Extended reporting dashboard

---

## Issue Labels Convention

| Label | Description |
|-------|-------------|
| `bug` | Something is not working |
| `enhancement` | New feature or improvement |
| `fiscal` | Tax/legal compliance related |
| `critical` | Blocking production use |
| `wisedat` | Wisedat integration related |
| `fifo` | FIFO logic related |
| `handheld` | Android/barcode related |
| `documentation` | Docs improvement |
| `v1.1.0` | Target version milestone |
| `v2.0.0` | Future version milestone |

---

*Maintained by jotaccf*
