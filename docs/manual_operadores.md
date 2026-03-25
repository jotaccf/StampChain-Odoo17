# StampChain -- Manual de Operadores

**Versao:** 1.2.0

**Data:** Marco 2026

---

## 1. Acesso ao sistema

### 1.1 Acesso por PC

1. Abrir o browser (Chrome ou Firefox recomendados)
2. Navegar para o endereco interno do servidor (fornecido pelo administrador)
3. Introduzir utilizador e palavra-passe
4. Seleccionar a empresa correcta no canto superior direito

### 1.2 Acesso por handheld Android

1. Ligar o dispositivo Android a rede Wi-Fi do armazem (ou via VPN WireGuard se fora da rede local)
2. Abrir o browser no dispositivo
3. Navegar para o endereco interno do servidor
4. Introduzir utilizador e palavra-passe
5. A interface adapta-se automaticamente ao ecra do dispositivo

---

## 2. Dashboard

Ao entrar no sistema, o operador ve o dashboard principal com resumo de:

- Lotes em stock
- Estampilhas disponiveis por tipo
- Movimentos recentes
- Alertas pendentes

**Nota:** Use o botao Actualizar para refrescar os dados.

---

## 3. Recepcao de lotes INCM

1. No menu principal, seleccionar **Recepcao > Nova Recepcao**
2. Introduzir o numero do documento de transporte INCM
3. Digitalizar (scan) o codigo de barras de cada lote recebido
4. O sistema valida automaticamente o lote contra o documento de transporte
5. Verificar que a quantidade recebida corresponde a quantidade esperada
6. Confirmar a recepcao clicando em **Validar Recepcao**
7. O sistema actualiza o stock e regista a entrada no historico
8. Imprimir o comprovativo de recepcao se necessario

---

## 4. Processo de estampilhagem na linha

O sistema segue a regra **FIFO** (First In, First Out) para consumo de estampilhas:

1. Ao iniciar a linha de producao, o operador selecciona **Estampilhagem > Iniciar Sessao**
2. O sistema sugere automaticamente o lote mais antigo disponivel (FIFO)
3. O operador confirma o lote sugerido ou, em caso excepcional justificado, selecciona outro
4. Registar o inicio de cada rolo/conjunto de estampilhas consumido
5. Ao terminar o rolo, registar o fim e a quantidade utilizada
6. O sistema calcula automaticamente as estampilhas restantes
7. Nao e permitido abrir um novo lote enquanto houver lotes anteriores do mesmo tipo por consumir (regra FIFO)

---

## 5. Picking guiado com handheld Android

1. No handheld, aceder a **Picking > Ordens Pendentes**
2. Seleccionar a ordem de picking atribuida
3. O sistema indica a localizacao do armazem onde recolher cada lote
4. Deslocar-se a localizacao indicada
5. Digitalizar o codigo de barras do lote para confirmar
6. O sistema valida que o lote corresponde a ordem
7. Repetir para todos os itens da ordem
8. Ao concluir, clicar em **Finalizar Picking**
9. O sistema actualiza o stock e prepara o movimento de saida

---

## 6. eDIC -- Submissao no portal AT

### 6.1 Passos no StampChain

1. No menu, seleccionar **eDIC > Criar eDIC**
2. Preencher os campos obrigatorios: origem, destino, lotes a movimentar
3. Verificar os dados na pre-visualizacao
4. Clicar em **Gerar XML**
5. O sistema gera o ficheiro XML no formato exigido pela AT
6. Descarregar o ficheiro XML clicando em **Exportar XML**

### 6.2 Passos no portal AT

1. Aceder ao Portal das Financas: https://www.portaldasfinancas.gov.pt
2. Autenticar com as credenciais da empresa
3. Navegar para a seccao **e-DA/eDIC > Submeter documento**
4. Carregar (upload) o ficheiro XML gerado pelo StampChain
5. Verificar os dados apresentados pelo portal
6. Confirmar a submissao
7. Guardar o codigo de validacao AT devolvido
8. No StampChain, aceder ao eDIC criado e registar o codigo AT em **Registar Codigo AT**

---

## 7. Registo de quebras

1. No menu, seleccionar **Quebras > Registar Quebra**
2. Identificar o lote e a estampilha afectada (digitalizar codigo se possivel)
3. Seleccionar o tipo de quebra:
   - Dano mecanico
   - Defeito de fabrico
   - Outro (especificar)
4. Introduzir a quantidade de estampilhas quebradas
5. Adicionar observacoes ou fotografias se aplicavel
6. Clicar em **Confirmar Quebra**
7. O sistema desconta as estampilhas do stock disponivel e regista no historico

---

## 8. Recuperacao de estampilhas quebradas

### 8.1 Passos do operador

1. Recolher as estampilhas danificadas
2. No StampChain, aceder a **Quebras > Solicitar Recuperacao**
3. Seleccionar as quebras registadas que podem ser recuperadas
4. Adicionar justificacao para a recuperacao
5. Submeter o pedido para aprovacao do gestor

### 8.2 Passos do gestor

1. Aceder a **Quebras > Pedidos de Recuperacao Pendentes**
2. Analisar o pedido e a justificacao do operador
3. Aprovar ou rejeitar o pedido
4. Se aprovado, o sistema reintroduz as estampilhas no stock com estado "recuperada"
5. O movimento fica registado no historico com a identificacao do gestor que aprovou

---

## 9. Resolucao de problemas comuns

| Problema                                    | Solucao                                                         |
|---------------------------------------------|-----------------------------------------------------------------|
| Nao consigo aceder ao sistema               | Verificar ligacao a rede. Confirmar URL e credenciais.          |
| O scanner nao le o codigo de barras         | Limpar a lente do scanner. Verificar se o codigo esta danificado.|
| O sistema nao sugere lote FIFO              | Verificar se existem lotes do tipo pretendido em stock.         |
| Erro ao gerar XML do eDIC                   | Verificar campos obrigatorios. Contactar administrador.         |
| Quantidade de stock nao corresponde         | Registar divergencia e contactar o gestor de armazem.           |
| Handheld nao liga a rede                    | Verificar configuracao Wi-Fi ou VPN WireGuard.                  |
| Picking indica localizacao errada           | Confirmar com o gestor. Nao recolher sem validacao do sistema.  |

---

StampChain v1.2.0 -- Uso interno -- jotaccf
