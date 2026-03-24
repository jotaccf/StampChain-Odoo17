# agent_skills.md — StampChain
> Competências consolidadas de cada agente especializado utilizado no projecto.
> Usar como referência ao formular prompts para tarefas específicas.

---

## AGENTE 1 — Tech Lead / Arquitecto de Software

### Especialidade
Decisões arquitecturais, estrutura de módulos Odoo, 
padrões de desenvolvimento, gestão de complexidade.

### Skills demonstradas neste projecto
- Scaffold completo de módulo Odoo 17 Community
- Definição de dependências e ordem de instalação
- Decisão entre Enterprise vs Community vs OCA
- Arquitectura de 4 VMs Hyper-V para produção
- Estratégia de backup 3-2-1
- Definição de grupos de utilizadores e permissões
- Padrões ORM Odoo 17 (model_create_multi, constrains, compute)

### Prompts eficazes para este agente
```
"És um arquitecto sénior de módulos Odoo 17 Community.
Cria o scaffold do módulo [nome] com dependências [lista].
Segue OCA guidelines. Inclui __manifest__.py completo."
```

### Regras que este agente aplica
- Sempre verificar branch 17.0 nos repos OCA antes de instalar
- Módulos com Enterprise equivalent → procurar OCA primeiro
- Ordem instalação: stock → mrp → sale → purchase → account → delivery
- Nunca avançar sem confirmar sucesso de cada passo

---

## AGENTE 2 — Backend Developer Python / Odoo ORM

### Especialidade
Modelos Python Odoo, lógica de negócio, ORM, 
computed fields, constrains, wizards.

### Skills demonstradas neste projecto
- Modelos com computed fields store=False (balance em tempo real)
- Override de create() para lógica de negócio automática
- Constrains SQL (`_sql_constraints`) e Python (`@api.constrains`)
- TransientModel para wizards (recepção INCM, quebra, recuperação)
- Extensão de modelos base (mrp.production, stock.picking)
- Lógica FIFO em Python puro
- Geração automática de números de série em batch
- Savepoint para rollback parcial sem desfazer o picking

### Padrões de código estabelecidos
```python
# Computed field em tempo real
@api.depends('movement_ids', 'movement_ids.qty')
def _compute_balance(self):
    for zone in self:
        zone.balance = sum_in - sum_out

# Override create com lógica automática
@api.model_create_multi
def create(self, vals_list):
    for vals in vals_list:
        # lógica aqui
    return super().create(vals_list)

# Savepoint para operações críticas
with self.env.cr.savepoint():
    # operação fiscal crítica
```

### Regras que este agente aplica
- Movimentos de conta corrente são IMUTÁVEIS (unlink levanta UserError)
- Notas obrigatórias para move_type in ('breakdown', 'adjust')
- FIFO: ordenar por fifo_sequence ASC, depois serial_number ASC
- Trigger fiscal APENAS em stock.picking com picking_type_code='outgoing'

---

## AGENTE 3 — Especialista em Logística e Armazém

### Especialidade
Fluxos operacionais de armazém, picking, FIFO físico,
layout de armazém, sistemas de endereçamento, handheld.

### Skills demonstradas neste projecto
- Princípio fluxo em U para armazém com 1 operador
- FIFO vertical vs horizontal (prós/contras)
- Wave picking adaptado a baixo volume
- Sistema de endereçamento hierárquico (A-03-L1-P01)
- Código de cores para etiquetas físicas
- Especificação hardware handheld Android industrial
- QR code com URL directo ao registo Odoo
- Separação picking (produto genérico) vs embalamento (zona fiscal)
- Verificação de peso para detectar maços em falta

### Decisões chave deste agente
- Produto único sem zona → zona apenas na estampilha
- FIFO vertical com QR por nível (L1/L2/L3 = localizações separadas)
- Scan obrigatório da prateleira antes do produto
- Picking totalmente paperless via browser Android
- Cofre estampilhas adjacente à linha de produção

### Prompt eficaz para este agente
```
"Actua como especialista em logística de armazém e packaging.
O produto é [descrição]. O operador é [contexto].
Sugere melhorias para [fluxo específico] considerando
compliance fiscal IEC e rastreabilidade de estampilhas."
```

---

## AGENTE 4 — Frontend Developer OWL 2.0 / QWeb

### Especialidade
Componentes OWL 2.0, templates QWeb, 
dashboard em tempo real, integração Odoo backend.

### Skills demonstradas neste projecto
- Componente OWL 2.0 com useState e useInterval
- Polling automático a cada 30 segundos
- useService("orm") para searchRead
- useService("action") para navegação
- Template QWeb com t-foreach, t-if, t-attf-class
- Registo em registry.category("actions")
- Cards com cor dinâmica por estado de alerta

### Padrão de componente OWL estabelecido
```javascript
/** @odoo-module **/
import { Component, useState, onWillStart, useInterval } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

class MeuComponente extends Component {
    static template = "modulo.MeuTemplate";
    setup() {
        this.orm = useService("orm");
        this.state = useState({ dados: [], loading: true });
        onWillStart(async () => await this.loadData());
        useInterval(async () => await this.loadData(), 30000);
    }
    async loadData() {
        const dados = await this.orm.searchRead(
            "modelo.odoo", [], ["campo1", "campo2"]
        );
        Object.assign(this.state, { dados, loading: false });
    }
}
registry.category("actions").add("modulo.acao", MeuComponente);
```

---

## AGENTE 5 — DevOps / Infra / Docker

### Especialidade
Docker, Hyper-V, Ubuntu Server, PostgreSQL, 
Nginx, WireGuard VPN, backup, CI/CD.

### Skills demonstradas neste projecto
- docker-compose.yml para Odoo 17 + PostgreSQL 15
- Mapeamento de volumes custom_addons
- Instalação de módulos via docker exec
- Adição de paths OCA ao odoo.conf via sed
- 4 VMs Hyper-V com funções separadas
- Estratégia backup 3-2-1 (NVMe + HDD local + Backblaze B2)
- WireGuard VPN para handhelds Android
- RAID 1 NVMe para dados críticos

### Comandos essenciais estabelecidos
```bash
# Instalar módulo
docker compose exec odoo odoo -d DB -i MODULO --stop-after-init --no-http

# Actualizar módulo
docker compose exec odoo odoo -d DB -u MODULO --stop-after-init --no-http

# Verificar módulos instalados
docker compose exec db psql -U odoo -d DB \
  -c "SELECT name, state FROM ir_module_module WHERE state='installed' ORDER BY name;"

# Adicionar path OCA ao odoo.conf
docker compose exec odoo bash -c \
  "sed -i 's|addons_path=.*|addons_path=NOVO_PATH|' /etc/odoo/odoo.conf"

# Instalar git no container
docker compose exec odoo bash -c "apt-get update -qq && apt-get install -y -qq git"

# Clonar repo OCA
docker compose exec odoo bash -c \
  "cd /mnt/extra-addons/oca && git clone URL -b 17.0 --depth 1 --single-branch NOME"
```

### Regras deste agente
- Sempre verificar branch 17.0 nos repos OCA
- PARAR e informar se branch não existir
- RAM estática para VM PostgreSQL
- UPS obrigatório para HA on-premise
- Nunca commitar .env no Git

---

## AGENTE 6 — Especialista Fiscal / Compliance IEC

### Especialidade
Legislação IEC Portugal, DGAIEC, estampilhas fiscais,
rastreabilidade legal, SAF-T PT, CIUS-PT.

### Skills demonstradas neste projecto
- Estrutura de rastreabilidade por número de série
- Processo de recuperação com auditoria completa
- Imutabilidade dos movimentos de conta corrente
- Arquitectura preparada para XML AT/DGAIEC (v2.0)
- Formatos SAF-T PT e CIUS-PT
- Obrigação de conservação 10 anos (backup offsite obrigatório)
- Bloqueio FIFO como obrigação fiscal

### Regras fiscais implementadas no código
- Movimentos de conta corrente NUNCA eliminados
- Histórico de quebras mantido mesmo após recuperação
- Dupla validação para recuperação de quebras
- min_stock_alert com histórico de alterações auditável
- Números de série no formato rastreável pela DGAIEC
- XML export arquitectado desde v1 para não exigir migração de dados

---

## AGENTE 7 — Especialista Integração Wisedat

### Especialidade
REST API Wisedat, sincronização bidirecional,
faturação portuguesa, NIF, CIUS-PT.

### Skills demonstradas neste projecto
- Modelo de configuração com API key encriptada
- Método _api_call com retry logic
- Mapeamento campos Odoo ↔ Wisedat
- Validação NIF português no mapeamento
- Trigger automático de sync na expedição
- Teste de ligação com action_test_connection

### Endpoints Wisedat mapeados
```
GET/POST/PUT /customers → res.partner (bidirecional)
GET/POST     /items     → product.product (bidirecional)
POST         /sales     → account.move (Odoo → Wisedat)
GET          /sales/{id}→ verificação estado
```

### Regras deste agente
- API key sempre em groups='base.group_system'
- Validar NIF português antes de sincronizar
- Formato postal_code: XXXX-XXX (Portugal)
- Wisedat requer Professional/Advanced para API

---

## AGENTE 8 — Marketing / Naming

### Especialidade
Naming de produtos, identidade, posicionamento,
avaliação de nomes técnicos e comerciais.

### Decisão tomada
Nome escolhido: **StampChain** (`stamp_chain`)
- Score: 24/25
- Motivo: Evoca cadeia de custódia fiscal
- Escalável para outros produtos IEC (álcool, combustíveis)
- Não fica preso ao tabaco

### Critérios de avaliação usados
1. Memorável (1-5)
2. Único tecnicamente (1-5)
3. Descreve a função (1-5)
4. Internacional (1-5)
5. Escalável para futuro (1-5)

---

## COMO USAR ESTE FICHEIRO

Ao iniciar uma nova tarefa, identifica qual agente é mais relevante
e usa o padrão de prompt indicado. Para tarefas complexas,
combina múltiplos agentes na mesma prompt.

### Exemplo de combinação
```
"Actua como Backend Developer Python (Agente 2) com input
do Especialista Fiscal (Agente 6). Implementa o método
_process_xml_export() no modelo tobacco.xml.export seguindo
as regras de imutabilidade fiscal e o formato SAF-T PT."
```
