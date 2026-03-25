# StampChain -- Mapeamento API Wisedat

**Estado:** MOCK -- aguarda validacao API real

**Data:** 2026-03-25

---

## 1. Endpoints mapeados

| Endpoint               | Metodo | Descricao                        | Assumido | Validado |
|-------------------------|--------|----------------------------------|----------|----------|
| `/customers`            | GET    | Listar clientes                  | V        | X        |
| `/customers`            | POST   | Criar cliente                    | V        | X        |
| `/customers/{id}`       | PUT    | Actualizar cliente               | V        | X        |
| `/items`                | GET    | Listar artigos                   | V        | X        |
| `/items`                | POST   | Criar artigo                     | V        | X        |
| `/sales`                | POST   | Registar venda                   | V        | X        |
| `/stock?warehouse=X`    | GET    | Consultar stock por armazem      | V        | X        |

---

## 2. Processo de validacao (quando API real disponivel)

1. Obter credenciais de acesso ao ambiente de testes Wisedat
2. Testar cada endpoint com dados reais e comparar resposta com mock
3. Ajustar mapeamento de campos conforme resposta real
4. Actualizar estruturas de dados no modulo `wisedat_connector`
5. Validar fluxo completo: criacao de cliente -> artigo -> venda -> consulta stock
6. Marcar coluna "Validado" com V para cada endpoint confirmado
7. Documentar diferencas entre mock e API real

---

## 3. Estrutura JSON mock -- resposta `/customers` GET

```json
{
  "status": "success",
  "data": [
    {
      "id": 1,
      "code": "CLI001",
      "name": "Empresa Exemplo Lda",
      "vat": "PT123456789",
      "address": {
        "street": "Rua do Exemplo 123",
        "city": "Lisboa",
        "postal_code": "1000-001",
        "country": "PT"
      },
      "contact": {
        "email": "geral@exemplo.pt",
        "phone": "+351210000000"
      },
      "active": true
    }
  ],
  "pagination": {
    "page": 1,
    "per_page": 50,
    "total": 1
  }
}
```

---

**Autor:** jotaccf
