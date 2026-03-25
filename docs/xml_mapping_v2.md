# StampChain -- Mapeamento XML AT v2.0

**Estado:** PREPARADO -- aguarda ficheiros reais

**Data:** 2026-03-25

---

## 1. Processo de mapeamento (quando ficheiros reais AT chegarem)

1. Comparar XML preenchido (exemplo real AT) com XML vazio (template XSD)
2. Identificar campos obrigatorios vs opcionais
3. Mapear cada campo AT para o campo correspondente em StampChain
4. Actualizar funcoes `_generate_edic_xml` e `_generate_eda_xml` no modulo
5. Validar XML gerado contra o XSD oficial da AT
6. Testar submissao no ambiente de testes AT (se disponivel)

---

## 2. Estrutura XML generica actual -- eDIC

```xml
<?xml version="1.0" encoding="UTF-8"?>
<eDIC>
  <Header>
    <DocumentNumber></DocumentNumber>
    <IssueDate></IssueDate>
    <SenderTIN></SenderTIN>
    <ReceiverTIN></ReceiverTIN>
    <WarehouseOrigin></WarehouseOrigin>
    <WarehouseDestination></WarehouseDestination>
  </Header>
  <StampLots>
    <Lot>
      <LotID></LotID>
      <ProductCode></ProductCode>
      <Quantity></Quantity>
      <UnitPrice></UnitPrice>
    </Lot>
  </StampLots>
  <Serials>
    <Serial>
      <SerialNumber></SerialNumber>
      <LotRef></LotRef>
      <Status></Status>
    </Serial>
  </Serials>
  <ATCode>
    <ValidationCode></ValidationCode>
    <SubmissionDate></SubmissionDate>
  </ATCode>
</eDIC>
```

---

## 3. TODO -- Mapeamento de campos eDIC

### 3.1 Header fields

| Campo StampChain          | Campo AT Real | TODO                        |
|---------------------------|---------------|-----------------------------|
| `edic_number`             | ?             | Aguarda XML real            |
| `issue_date`              | ?             | Aguarda XML real            |
| `sender_vat`              | ?             | Aguarda XML real            |
| `receiver_vat`            | ?             | Aguarda XML real            |
| `warehouse_origin_id`     | ?             | Aguarda XML real            |
| `warehouse_dest_id`       | ?             | Aguarda XML real            |

### 3.2 Lot fields

| Campo StampChain          | Campo AT Real | TODO                        |
|---------------------------|---------------|-----------------------------|
| `lot_id`                  | ?             | Aguarda XML real            |
| `product_code`            | ?             | Aguarda XML real            |
| `quantity`                | ?             | Aguarda XML real            |
| `unit_price`              | ?             | Aguarda XML real            |

### 3.3 Serial fields

| Campo StampChain          | Campo AT Real | TODO                        |
|---------------------------|---------------|-----------------------------|
| `serial_number`           | ?             | Aguarda XML real            |
| `lot_ref`                 | ?             | Aguarda XML real            |
| `status`                  | ?             | Aguarda XML real            |

---

## 4. Estrutura XML generica actual -- e-DA

```xml
<?xml version="1.0" encoding="UTF-8"?>
<eDA>
  <Header>
    <DocumentNumber></DocumentNumber>
    <IssueDate></IssueDate>
    <OperatorTIN></OperatorTIN>
    <CustomsOffice></CustomsOffice>
    <MovementType></MovementType>
  </Header>
  <StampLots>
    <Lot>
      <LotID></LotID>
      <ProductCode></ProductCode>
      <Quantity></Quantity>
    </Lot>
  </StampLots>
  <Serials>
    <Serial>
      <SerialNumber></SerialNumber>
      <LotRef></LotRef>
      <Status></Status>
    </Serial>
  </Serials>
  <ATCode>
    <ValidationCode></ValidationCode>
    <SubmissionDate></SubmissionDate>
  </ATCode>
</eDA>
```

### 4.1 Header fields (e-DA)

| Campo StampChain          | Campo AT Real | TODO                        |
|---------------------------|---------------|-----------------------------|
| `eda_number`              | ?             | Aguarda XML real            |
| `issue_date`              | ?             | Aguarda XML real            |
| `operator_vat`            | ?             | Aguarda XML real            |
| `customs_office`          | ?             | Aguarda XML real            |
| `movement_type`           | ?             | Aguarda XML real            |

### 4.2 Lot fields (e-DA)

| Campo StampChain          | Campo AT Real | TODO                        |
|---------------------------|---------------|-----------------------------|
| `lot_id`                  | ?             | Aguarda XML real            |
| `product_code`            | ?             | Aguarda XML real            |
| `quantity`                | ?             | Aguarda XML real            |

### 4.3 Serial fields (e-DA)

| Campo StampChain          | Campo AT Real | TODO                        |
|---------------------------|---------------|-----------------------------|
| `serial_number`           | ?             | Aguarda XML real            |
| `lot_ref`                 | ?             | Aguarda XML real            |
| `status`                  | ?             | Aguarda XML real            |

---

## 5. Referencias

- Portal AT: https://www.portaldasfinancas.gov.pt
- EMCS (Excise Movement and Control System): https://ec.europa.eu/taxation_customs/emcs
- DGAIEC: https://www.dgaiec.gov.pt

---

**Autor:** jotaccf
