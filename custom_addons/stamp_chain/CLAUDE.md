# CLAUDE.md — stamp_chain module
## Módulo: stamp_chain (StampChain)
## BD: stampchain_dev
## Odoo: 17.0 Community

## Comandos rápidos
- Actualizar: docker compose exec odoo odoo -d stampchain_dev -u stamp_chain --stop-after-init --no-http
- Testes: docker exec CONTAINER bash -c "odoo -d stampchain_dev --test-enable --test-tags /stamp_chain --stop-after-init --no-http"

## Regras críticas
- FIFO nunca violar — bloqueio obrigatório
- Movimentos conta corrente são IMUTÁVEIS
- Baixa estampilhas APENAS na expedição
- Zona EXCLUSIVAMENTE na estampilha, não no produto
- Recuperação: broken→quarantine→approved→available
- min_stock_alert: apenas group_stamp_manager

## Modelos principais
- tobacco.stamp.zone (3 zonas: PT_C, PT_M, PT_A)
- tobacco.stamp.lot (lotes INCM, 500/lote)
- tobacco.stamp.serial (série individual)
- tobacco.stamp.movement (conta corrente)
- tobacco.stamp.breakdown (quebras)
- tobacco.stamp.recovery (recuperação)
- tobacco.stamp.zone.history (histórico mínimo)

## Ficheiros de referência completa
- /stampchain/CLAUDE.md
- /stampchain/master_memory.md
- /stampchain/agent_skills.md
