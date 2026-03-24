# master_memory.md — StampChain
> Memória consolidada de todas as sessões de desenvolvimento.
> Actualizar após cada sessão de trabalho significativa.

---

## SESSÃO 1 — Março 2026
### O que foi feito
- Definição completa do projecto StampChain
- Arquitectura de módulo Odoo 17 Community
- Fluxos de produção, picking, estampilhagem revalidados
- Layout de armazém (fluxo em U, FIFO vertical)
- Sistema de endereçamento hierárquico
- Especificação servidor Hyper-V (4 VMs)
- Prompt 1: Setup Docker + Odoo + módulos base
- Prompt 2: Estrutura módulo + modelos core
- Prompt 3: Dashboard OWL, quebras, recuperações, stock segurança

### Decisões chave tomadas
- Produto físico único — zona apenas na estampilha
- Baixa fiscal APENAS na validação da expedição
- Recuperação com dupla validação (quarentena + gestor)
- stock_barcode Enterprise → browser Android nativo
- FIFO vertical com QR por nível como compensação

### Problemas encontrados e soluções
- stock_barcodes OCA sem branch 17.0 → usar barcodes_generator_*
- quality_control Enterprise → usar OCA/quality
- Módulo quality base → quality_control OCA

### Estado actual
- ✅ Prompts 1, 2, 3 definidas e prontas
- ⏳ Prompt 4 (Wisedat + deploy) por definir
- ⏳ Instalação em curso no ambiente de desenvolvimento

---

## CONTEXTO OPERACIONAL

### Volume de operações
- 1–10 encomendas/dia
- 1 operador de armazém
- Encomendas tipicamente multi-linha
- Clientes B2B com zona fiscal fixa

### Produto
- Maços de tabaco
- 1 maço = 1 estampilha IEC
- Produto físico idêntico para todas as zonas
- Zona definida exclusivamente pela estampilha

### Zonas IEC
| Zona | Código | Min. Alert default |
|------|--------|-------------------|
| Continente | PT_C | 2000 |
| Madeira | PT_M | 2000 |
| Açores | PT_A | 2000 |

---

## APRENDIZAGENS TÉCNICAS

### Odoo 17 Community — Limitações conhecidas
1. stock_barcode não existe — usar browser móvel
2. quality_control Enterprise — usar OCA/quality
3. Módulos OCA podem não ter branch 17.0 — verificar sempre
4. RAM estática para PostgreSQL VM — não usar dinâmica
5. Workers Odoo: ~200-500MB RAM cada

### Docker + Odoo 17
- Imagem oficial: `odoo:17.0`
- PostgreSQL: `postgres:15`
- addons_path deve incluir OCA paths no odoo.conf
- Reiniciar container após adicionar novos módulos OCA
- `git` precisa ser instalado no container para OCA

### OWL 2.0 — Padrões usados
- `useInterval` para polling a cada 30s
- `useService("orm")` para acesso à BD
- `useService("action")` para navegação
- Template QWeb com `t-name` e `owl="1"`
- Registar em `registry.category("actions")`

### PostgreSQL — Optimizações
- RAM estática na VM (não dinâmica)
- WAL archiving activo para point-in-time recovery
- RAID 1 NVMe obrigatório
- Índices em: serial_number, state, zone_id, lot_id

---

## FICHEIROS CRÍTICOS DO PROJECTO

```
stampchain/
├── CLAUDE.md                    ← Este contexto
├── master_memory.md             ← Esta memória
├── agent_skills.md              ← Skills dos agentes
├── docker-compose.yml           ← Ambiente Docker
├── .env                         ← Passwords (não commitar!)
├── config/odoo.conf             ← Config Odoo
└── custom_addons/
    ├── stamp_chain/             ← Módulo principal
    │   ├── CLAUDE.md            ← Contexto módulo
    │   └── ...
    └── oca/                     ← Módulos OCA
        ├── stock-logistics-barcode/
        └── quality/
```

---

## CHECKLIST DE SESSÃO
Antes de começar cada sessão de desenvolvimento:
- [ ] `docker compose ps` — containers UP?
- [ ] Módulo instalado? `SELECT state FROM ir_module_module WHERE name='stamp_chain';`
- [ ] Branch correcta? `git branch`
- [ ] Últimas alterações commitadas? `git status`
