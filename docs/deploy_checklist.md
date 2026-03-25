# StampChain -- Checklist de Deploy

**Servidor Hyper-V Producao**

**Data:** 2026-03-25

---

## 1. Pre-requisitos

- [ ] **VM1** -- Odoo (aplicacao StampChain)
- [ ] **VM2** -- PostgreSQL (base de dados)
- [ ] **VM3** -- Nginx (reverse proxy + SSL)
- [ ] **VM4** -- WireGuard (VPN para handhelds Android)
- [ ] RAID 1 configurado e verificado no host Hyper-V
- [ ] UPS ligada e testada (verificar autonomia minima de 15 minutos)
- [ ] Rede interna entre VMs configurada e testada (ping entre todas as VMs)

---

## 2. Docker setup -- VM1

- [ ] Docker e Docker Compose instalados
- [ ] Ficheiro `docker-compose.yml` configurado com imagem Odoo correcta
- [ ] Volumes persistentes mapeados para `/var/lib/odoo` e `/mnt/extra-addons`
- [ ] Variavel `DB_HOST` a apontar para VM2
- [ ] Portas 8069 e 8072 expostas apenas na rede interna
- [ ] Container Odoo arranca sem erros: `docker compose up -d`
- [ ] Verificar logs: `docker compose logs -f odoo`

---

## 3. PostgreSQL -- VM2

- [ ] PostgreSQL instalado (versao 15 ou superior)
- [ ] RAM estatica atribuida a VM (nao utilizar memoria dinamica)
- [ ] `postgresql.conf` -- `shared_buffers` ajustado (25% da RAM da VM)
- [ ] `postgresql.conf` -- `effective_cache_size` ajustado (50-75% da RAM)
- [ ] `postgresql.conf` -- `listen_addresses` configurado para aceitar ligacoes da VM1
- [ ] `pg_hba.conf` -- regra de acesso para o IP da VM1
- [ ] WAL archiving activado:
  - [ ] `wal_level = replica`
  - [ ] `archive_mode = on`
  - [ ] `archive_command` configurado para copiar WAL para storage externo
- [ ] Base de dados `stampchain_prod` criada
- [ ] Utilizador Odoo criado com permissoes correctas
- [ ] Testar ligacao a partir da VM1: `psql -h VM2_IP -U odoo -d stampchain_prod`

---

## 4. Nginx reverse proxy -- VM3

- [ ] Nginx instalado
- [ ] Certificado SSL instalado (Let's Encrypt ou certificado interno)
- [ ] Configuracao do virtual host:

```nginx
upstream odoo {
    server VM1_IP:8069;
}
upstream odoo-chat {
    server VM1_IP:8072;
}
server {
    listen 443 ssl;
    server_name stampchain.dominio.local;

    ssl_certificate     /etc/nginx/ssl/cert.pem;
    ssl_certificate_key /etc/nginx/ssl/key.pem;

    proxy_read_timeout 720s;
    proxy_connect_timeout 720s;
    proxy_send_timeout 720s;

    location / {
        proxy_pass http://odoo;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /websocket {
        proxy_pass http://odoo-chat;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

- [ ] Redirect HTTP 80 para HTTPS 443 configurado
- [ ] Testar acesso HTTPS pelo browser
- [ ] Verificar headers de seguranca (X-Frame-Options, HSTS)

---

## 5. WireGuard VPN -- VM4

- [ ] WireGuard instalado na VM4
- [ ] Par de chaves do servidor gerado
- [ ] Interface `wg0` configurada com subnet dedicada (ex: 10.10.10.0/24)
- [ ] Regra de forwarding para a rede interna (acesso a VM3/Nginx)
- [ ] Perfil de cliente gerado para cada handheld Android
- [ ] App WireGuard instalada nos handhelds
- [ ] QR code do perfil importado em cada dispositivo
- [ ] Testar acesso ao StampChain via VPN a partir de handheld
- [ ] Firewall: apenas porta UDP do WireGuard exposta ao exterior

---

## 6. Deploy do modulo StampChain -- VM1

1. Aceder a VM1 por SSH
2. Navegar para o directorio dos addons:
   ```bash
   cd /mnt/extra-addons/stampchain
   ```
3. Obter a versao mais recente:
   ```bash
   git pull origin main
   ```
4. Actualizar o modulo no Odoo:
   ```bash
   docker compose exec odoo odoo -u stampchain_base,stampchain_warehouse,stampchain_edic -d stampchain_prod --stop-after-init
   ```
5. Reiniciar o container Odoo:
   ```bash
   docker compose restart odoo
   ```
6. Verificar logs de arranque:
   ```bash
   docker compose logs -f --tail=100 odoo
   ```

---

## 7. Testes pos-deploy

- [ ] Login com utilizador operador -- sucesso
- [ ] Login com utilizador gestor -- sucesso
- [ ] Dashboard carrega sem erros
- [ ] Recepcao de lote INCM (teste com dados de teste) -- sucesso
- [ ] Processo de estampilhagem FIFO -- sucesso
- [ ] Geracao de XML eDIC -- sucesso
- [ ] Picking via handheld Android (via VPN) -- sucesso
- [ ] Registo de quebra -- sucesso
- [ ] Consulta de stock -- valores correctos
- [ ] Performance: tempo de resposta do dashboard < 3 segundos

---

## 8. Procedimento de rollback

Se o deploy falhar ou forem detectados problemas criticos:

1. Parar o container Odoo:
   ```bash
   docker compose stop odoo
   ```
2. Reverter o codigo para a versao anterior:
   ```bash
   cd /mnt/extra-addons/stampchain
   git checkout <tag-versao-anterior>
   ```
3. Restaurar a base de dados a partir do ultimo backup:
   ```bash
   pg_restore -h VM2_IP -U odoo -d stampchain_prod --clean /backups/stampchain_prod_YYYYMMDD.dump
   ```
4. Reiniciar o container Odoo:
   ```bash
   docker compose up -d odoo
   ```
5. Verificar que o sistema esta funcional na versao anterior
6. Documentar o problema encontrado para analise posterior

---

## 9. Verificacao de backup 3-2-1

Regra 3-2-1: 3 copias, 2 tipos de media diferentes, 1 copia offsite.

- [ ] **Copia 1:** Backup diario PostgreSQL no disco local da VM2 (`pg_dump` automatico via cron)
- [ ] **Copia 2:** Replicacao para NAS/storage externo no mesmo local (rsync diario)
- [ ] **Copia 3:** Copia offsite (cloud storage ou disco externo rotativo levado para fora do local)
- [ ] Testar restauro a partir de cada tipo de copia (pelo menos 1x por mes)
- [ ] Verificar que os WAL archives estao a ser copiados correctamente
- [ ] Verificar retencao: minimo 30 dias de backups diarios, 12 meses de backups mensais

---

**Autor:** jotaccf
