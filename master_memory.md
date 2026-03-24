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
- quality_control Enterprise → usar quality_control_oca de OCA/manufacture (NÃO OCA/quality)
- OCA/quality repo não acessível → módulos quality estão em OCA/manufacture
- addons_path com caminhos inexistentes → Odoo crashar com FileNotFoundError (500 em todas as requests)
- BD criada pelo PostgreSQL está vazia → obrigatório "odoo -i base" antes de aceder ao web
- Logs vão para ficheiro (logfile no odoo.conf) → docker compose logs aparece vazio
- Campos computed store=False não podem ser usados em filtros de search view
- menus.xml deve ser ÚLTIMO no manifest (referencia actions dos outros ficheiros)
- Odoo 17 usa required="expr" em vez de attrs={'required': [...]}
- Git Bash Windows interpreta /stamp_chain como C:/Program Files/Git/stamp_chain
- useInterval NÃO existe no OWL 2.0 do Odoo 17 → usar refresh manual
- Testes com has_group() falham se utilizador não tem o grupo → adicionar no setUpClass
- pip3 no container não precisa de --break-system-packages (Ubuntu 22.04 com pip antigo)
- apt-get no container precisa de -u root

### Estado actual
- ✅ Prompt 1 executada — ambiente Docker + Odoo + 16 módulos instalados
- ✅ Prompt 2 executada — módulo stamp_chain instalado (11 modelos, vistas, wizards)
- ✅ Prompt 3 executada — dashboard OWL, recuperação, stock segurança, 20 testes OK
- ⏳ Prompt 4 (Wisedat + deploy) por executar

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
2. quality_control Enterprise — usar quality_control_oca de OCA/manufacture
3. stock_barcodes OCA sem branch 17.0 — usar barcodes_generator_*
4. Módulos OCA podem não ter branch 17.0 — verificar sempre antes de clonar
5. RAM estática para PostgreSQL VM — não usar dinâmica
6. Workers Odoo: ~200-500MB RAM cada

### Docker + Odoo 17 — Regras aprendidas
- Imagem oficial: `odoo:17.0` / PostgreSQL: `postgres:15`
- addons_path deve incluir APENAS caminhos que existem (senão Odoo crashar 500)
- Adicionar caminhos OCA ao odoo.conf SÓ DEPOIS de clonar os repos
- BD criada pelo POSTGRES_DB está vazia — executar `odoo -i base` antes do web
- Reiniciar container após adicionar novos módulos OCA
- `git` precisa ser instalado no container com `-u root`
- `pip3 install` sem --break-system-packages (Ubuntu 22.04)
- Logs vão para /var/log/odoo/odoo.log (não stdout) — usar docker exec para ler
- NÃO usar `version:` no docker-compose.yml (obsoleto, gera warning)

### Odoo 17 — Regras técnicas de desenvolvimento
- R1: Campos computed store=False NÃO podem ser usados em search filters/domain
- R2: Ordem no manifest é CRÍTICA — menus.xml DEVE ser o último
- R3: Usar required="expr" (Odoo 17) em vez de attrs={'required': [...]} (Odoo 16)
- R4: Encoding ASCII nos ficheiros Python (evitar problemas Windows↔Linux)
- R5: Chatter obrigatório se herda mail.thread
- R6: Exit code 255 com RST warnings é do __manifest__.py description — erro real está nos logs
- R7: Testes com has_group() — adicionar grupo ao utilizador no setUpClass
- R8: useInterval NÃO existe no OWL 2.0 — usar refresh manual
- R9: Git Bash Windows converte / em paths — executar testes dentro do container
- R10: Testes OCA precisam de pip3 install odoo-test-helper

### OWL 2.0 — Padrões usados
- `useService("orm")` para acesso à BD
- `useService("action")` para navegação
- `onWillStart` para carregamento inicial
- Template QWeb com `t-name` e `owl="1"`
- Registar em `registry.category("actions")`
- Refresh via botão manual (NÃO useInterval)
- Tag ir.actions.client DEVE coincidir exactamente com registry.add()

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
        ├── stock-logistics-barcode/  ← Repo clonado (no .gitignore)
        ├── quality_control_oca/      ← Copiado de OCA/manufacture
        ├── quality_control_stock_oca/
        └── quality_control_mrp_oca/
```

---

## CHECKLIST DE SESSÃO
Antes de começar cada sessão de desenvolvimento:
- [ ] `docker compose ps` — containers UP?
- [ ] Módulo instalado? `SELECT state FROM ir_module_module WHERE name='stamp_chain';`
- [ ] Branch correcta? `git branch`
- [ ] Últimas alterações commitadas? `git status`
