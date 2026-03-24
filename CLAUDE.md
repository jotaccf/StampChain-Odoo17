# CLAUDE.md — StampChain Project Memory
> Este ficheiro é lido automaticamente pelo Claude Code em cada sessão.
> Contém todo o contexto do projecto, decisões técnicas e regras de desenvolvimento.
> Última actualização: Março 2026

---

## 1. IDENTIDADE DO PROJECTO

- **Nome comercial:** StampChain
- **Nome técnico (módulo Odoo):** `stamp_chain`
- **Versão:** 17.0.1.0.0
- **Plataforma:** Odoo 17 Community Edition
- **Base de dados dev:** `stampchain_dev`
- **Repositório:** Git privado (branch `main` = produção, `dev` = desenvolvimento)

### Descrição
Módulo vertical Odoo 17 Community para gestão completa do ciclo de vida
de produtos sujeitos a IEC (Imposto Especial de Consumo) — tabaco.
Inclui gestão de armazém, linha de produção, controlo de estampilhas IEC,
integração bidirecional Wisedat e arquitectura XML AT/DGAIEC.

---

## 2. AMBIENTE DE DESENVOLVIMENTO

### Docker
```bash
# Localização do projecto
cd stampchain/

# Iniciar ambiente
docker compose up -d

# Ver logs Odoo (vão para ficheiro, não stdout)
docker exec stampchain-odoo-1 bash -c "tail -100 /var/log/odoo/odoo.log"

# Instalar módulo (primeira vez)
docker compose exec odoo odoo -d stampchain_dev -i stamp_chain --stop-after-init --no-http

# Actualizar módulo (após alterações)
docker compose exec odoo odoo -d stampchain_dev -u stamp_chain --stop-after-init --no-http

# Correr testes (DENTRO do container — Git Bash Windows interpreta / como path)
docker exec stampchain-odoo-1 bash -c "odoo -d stampchain_dev --test-enable --test-tags /stamp_chain --stop-after-init --no-http"

# Acesso à BD
docker compose exec db psql -U odoo -d stampchain_dev
```

### URLs
- Odoo: http://localhost:8069
- Database manager: http://localhost:8069/web/database/manager

### Credenciais dev
- Admin: admin@stampchain.pt
- BD: stampchain_dev (ver .env para password)

---

## 3. MÓDULOS ODOO INSTALADOS

### Base Odoo 17 Community
| Módulo | Nome | Função |
|--------|------|--------|
| stock | Inventory | Stock, FIFO, lotes, séries |
| mrp | Manufacturing | Ordens produção, linha |
| sale_management | Sales | Encomendas B2B |
| purchase | Purchase | Compras bulk |
| account | Accounting | Facturas Wisedat |
| delivery | Delivery | Expedição, trigger fiscal |
| mail | Discuss | Alertas, notificações |

### OCA Barcodes (branch 17.0, repo OCA/stock-logistics-barcode)
| Módulo | Função |
|--------|--------|
| barcodes_generator_abstract | Base de geração de barcodes |
| barcodes_generator_location | QR para prateleiras |
| barcodes_generator_product | QR para produtos |
| product_multi_barcode | Múltiplos barcodes |
| stock_picking_product_barcode_report | Relatório picking |

### OCA Quality (branch 17.0, repo OCA/manufacture)
| Módulo | Função |
|--------|--------|
| quality_control_oca | Controlo qualidade base |
| quality_control_stock_oca | Qualidade no stock |
| quality_control_mrp_oca | Qualidade na produção |

NOTA: Os modelos OCA de qualidade usam prefixo `qc.` (qc.inspection, qc.test, qc.trigger)

### NÃO DISPONÍVEIS (Enterprise only)
- ❌ stock_barcode — usar browser Android nativo
- ❌ stock_barcodes OCA — sem branch 17.0 (só 16.0, incompatível)
- ❌ quality_control Enterprise — usar quality_control_oca de OCA/manufacture

---

## 4. ARQUITECTURA DO MÓDULO

### Localização
```
stampchain/custom_addons/stamp_chain/
```

### Modelos principais
| Modelo | Ficheiro | Descrição |
|--------|----------|-----------|
| tobacco.stamp.zone | models/stamp_zone.py | 3 zonas IEC: PT_C, PT_M, PT_A |
| tobacco.stamp.lot | models/stamp_lot.py | Lotes INCM (500 unid/lote) |
| tobacco.stamp.serial | models/stamp_serial.py | Série individual por estampilha |
| tobacco.stamp.movement | models/stamp_movement.py | Conta corrente — IMUTÁVEL |
| tobacco.stamp.breakdown | models/stamp_breakdown.py | Quebras com justificação |
| tobacco.stamp.recovery | models/stamp_recovery.py | Recuperação quebradas + quarentena |
| tobacco.stamp.zone.history | models/stamp_zone_history.py | Histórico stock mínimo |
| tobacco.wisedat.config | models/wisedat_sync.py | Integração Wisedat REST |
| tobacco.xml.export | models/xml_export.py | XML AT/DGAIEC (v2.0) |

### Modelos extendidos
| Modelo base | Ficheiro | Campos adicionados |
|-------------|----------|--------------------|
| mrp.production | models/production_order.py | stamp_zone_id, stamp_serial_ids, FIFO |
| stock.picking | models/stock_picking.py | trigger fiscal na expedição |
| res.partner | models/res_partner.py | stamp_zone_id, wisedat_id |
| sale.order | models/sale_order.py | stamp_zone_id (related), stamp_qty_required |

---

## 5. REGRAS DE NEGÓCIO CRÍTICAS

### FIFO — NUNCA VIOLAR
1. Lotes ordenados por `fifo_sequence ASC`
2. Seriais consumidos por `serial_number ASC`
3. Bloqueio imediato se tentar usar lote mais recente
4. Zona do lote DEVE corresponder à zona do cliente
5. Violação = infracção fiscal grave

### Estampilhas IEC — Regras fundamentais
- Produto físico é ÚNICO — sem distinção de zona no stock
- A zona é definida EXCLUSIVAMENTE pela estampilha colada
- Cada cliente B2B tem zona fiscal fixa em `res.partner.stamp_zone_id`
- 1 maço = 1 estampilha (sempre)
- Baixa na conta corrente APENAS ao validar `stock.picking` (expedição)
- Movimentos de conta corrente são IMUTÁVEIS após criação

### Estados do serial
```
available → reserved → used
                    ↘ broken → quarantine → available (via recovery)
                                          → broken (rejeitado)
```

### Tipos de movimento conta corrente
| Tipo | Sinal | Trigger |
|------|-------|---------|
| in | + | Recepção lote INCM |
| out | - | Validação expedição |
| breakdown | - | Wizard quebra |
| recovery | + | Libertação quarentena |
| adjust | +/- | Manual (só manager) |

### Recuperação de estampilhas quebradas
1. Operador submete → seriais vão para `quarantine`
2. Gestor aprova → estado `approved`
3. Gestor liberta → seriais voltam a `available`
4. Gera movimento `recovery` na conta corrente
5. Registo da quebra original NUNCA apagado
6. Apenas `group_stamp_manager` pode aprovar/libertar/rejeitar

### Stock de segurança (min_stock_alert)
- Editável APENAS por `group_stamp_manager`
- Alteração via wizard dedicado (motivo obrigatório)
- Histórico completo em `tobacco.stamp.zone.history`
- Notificação automática ao gestor após alteração

---

## 6. GRUPOS DE UTILIZADORES

| Grupo | ID técnico | Permissões |
|-------|-----------|------------|
| Operador de Armazém | group_stamp_user | Leitura/escrita: lotes, picking. Sem financeiro. |
| Responsável de Produção | group_stamp_production | Ordens produção, quebras, reservas FIFO |
| Gestor StampChain | group_stamp_manager | Acesso total + aprovação recuperações + min_stock |
| Contabilidade/Fiscal | group_stamp_fiscal | Leitura geral + Wisedat + XML export |

---

## 7. INTEGRAÇÃO WISEDAT

### Configuração
- Modelo: `tobacco.wisedat.config`
- API disponível: Wisedat Professional/Advanced
- URL config: Wisedat Comercial > Preferências > API Server

### Endpoints utilizados
| Método | Endpoint | Direcção |
|--------|----------|----------|
| GET/POST/PUT | /customers | Bidirecional |
| GET/POST | /items | Bidirecional |
| POST | /sales | Odoo → Wisedat |
| GET | /sales/{id} | Wisedat → Odoo |

### Trigger de sincronização
- Facturas: automático após validação de expedição
- Clientes/artigos: agendado (realtime/hourly/daily)

---

## 8. ARMAZÉM E HANDHELD

### Sistema de endereçamento
```
CORREDOR-ESTANTE-NIVEL-POSICAO
Exemplo: A-03-L1-P01
```
- Cada nível = localização separada no Odoo
- FIFO vertical: L1 (baixo) antes de L2, L2 antes de L3
- Scan de nível errado = bloqueio automático

### Handheld Android
- Interface: browser Android → Odoo stock nativo
- VPN: WireGuard (VM 4 Hyper-V)
- WiFi: 2× Ubiquiti UniFi U6-Lite (VLAN isolada)
- Impressora: Zebra ZD421 WiFi (zona recepção)
- Hardware recomendado: Zebra TC2x

### Picking guiado
- Lista ordenada por rota de armazém
- Scan prateleira + produto por linha
- Validação zona fiscal no embalamento
- Sem papel — 100% digital

### Código de cores etiquetas
- 🟢 Verde: bulk/matéria-prima
- 🟡 Amarelo: quarentena
- 🔴 Vermelho: cofre estampilhas
- 🔵 Azul: produto acabado
- ⬜ Branco + zona: expedição

---

## 9. SERVIDOR DE PRODUÇÃO (HYPER-V)

### 4 VMs configuradas
| VM | OS | Specs | Função |
|----|-----|-------|--------|
| VM1 StampChain | Ubuntu 22.04 | 4vCPU 8GB 60GB NVMe | Odoo 17 |
| VM2 PostgreSQL | Ubuntu 22.04 | 4vCPU 8GB RAM estática 200GB NVMe | BD |
| VM3 Nginx+SSL | Ubuntu 22.04 | 2vCPU 2GB 20GB | Reverse proxy |
| VM4 WireGuard | Ubuntu 22.04 | 2vCPU 2GB 20GB | VPN |

### Deploy produção
```bash
cd /odoo/custom_addons/stamp_chain
git pull origin main
docker exec odoo odoo -d producao -u stamp_chain --stop-after-init
```

### Backup 3-2-1
- Cópia 1: NVMe produção (dados activos)
- Cópia 2: HDD local (snapshot Hyper-V diário)
- Cópia 3: Backblaze B2 offsite (restic encriptado)

---

## 10. FORMATO DE NÚMEROS DE SÉRIE

```
{ZONE_CODE}-{YYYY}-{INCM_REF}-{NNNNNN}

Exemplos:
PT_C-2026-INCM-REF-2024001-000001  (Continente)
PT_M-2026-INCM-REF-2024002-000001  (Madeira)
PT_A-2026-INCM-REF-2024003-000001  (Açores)
```

---

## 11. SEQUÊNCIAS ODOO

| Sequência | Prefixo | Exemplo |
|-----------|---------|---------|
| tobacco.stamp.lot | SC/LOT/%(year)s/ | SC/LOT/2026/00001 |
| tobacco.stamp.breakdown | SC/BRK/%(year)s/ | SC/BRK/2026/00001 |
| tobacco.stamp.recovery | SC/REC/%(year)s/ | SC/REC/2026/00001 |
| tobacco.xml.export | SC/XML/%(year)s/ | SC/XML/2026/00001 |

---

## 12. TESTES UNITÁRIOS

```bash
# Correr todos os testes (DENTRO do container — evita Git Bash interpretar /)
docker exec stampchain-odoo-1 bash -c \
  "odoo -d stampchain_dev --test-enable --test-tags /stamp_chain \
  -u stamp_chain --stop-after-init --no-http"

# Verificar resultados
docker exec stampchain-odoo-1 bash -c \
  "grep -E '(ERROR:.*Test|Starting Test)' /var/log/odoo/odoo.log | tail -30"

# NOTA: Instalar dependência antes da primeira execução:
# docker exec -u root stampchain-odoo-1 bash -c "pip3 install odoo-test-helper"
```

### Ficheiros de teste
- test_stamp_zones.py — zonas, saldos, alertas
- test_fifo.py — FIFO rigoroso, bloqueios
- test_incm_reception.py — wizard recepção
- test_breakdown.py — wizard quebra
- test_recovery.py — recuperação + quarentena
- test_min_stock.py — stock segurança
- test_expedition_trigger.py — trigger fiscal

---

## 13. PRÓXIMAS PROMPTS A EXECUTAR

- [ ] **Prompt 4** — Integração Wisedat completa + relatório PDF + deploy
- [ ] **Prompt 5** — Testes de aceitação + formação operadores
- [ ] **v2.0** — Exportação XML AT/DGAIEC

---

## 14. DECISÕES TÉCNICAS REGISTADAS

| Data | Decisão | Motivo |
|------|---------|--------|
| Mar 2026 | stock_barcode Enterprise → browser nativo | Não disponível na Community 17.0 |
| Mar 2026 | quality → quality_control OCA | Módulo base não disponível |
| Mar 2026 | stock_barcodes OCA não tem branch 17.0 | Usar barcodes_generator_* OCA |
| Mar 2026 | FIFO vertical (antigo em baixo) | Visibilidade + QR por nível como compensação |
| Mar 2026 | Baixa estampilhas na expedição | Não na produção — produto único sem zona |
| Mar 2026 | Quarentena obrigatória na recuperação | Compliance fiscal DGAIEC |
| Mar 2026 | min_stock via wizard (não edição directa) | Rastreabilidade auditoria fiscal |
| Mar 2026 | 4 VMs separadas no Hyper-V | HA, isolamento, snapshots independentes |

---

## 15. REFERÊNCIAS LEGAIS

- Decreto-Lei n.º 73/2010 — Código IEC (CIEC)
- Portaria n.º 289/2019 — Norma CIUS-PT
- Decreto-Lei n.º 198/2012 — SAF-T PT
- INCM — Normas estampilhas fiscais tabaco
