#!/bin/bash
# StampChain — Production Deploy Script
# Usage: ./scripts/deploy.sh [DB_NAME]
# Author: jotaccf

set -e

DB_NAME=${1:-producao}
ADDON_PATH="/odoo/custom_addons/stamp_chain"
CONTAINER="odoo"

echo "========================================"
echo "  StampChain Deploy — $(date +%Y-%m-%d)"
echo "========================================"

echo "[1/4] Pulling latest changes..."
cd $ADDON_PATH
git pull origin main

echo "[2/4] Updating module in Odoo..."
docker exec $CONTAINER odoo \
  -d $DB_NAME \
  -u stamp_chain \
  --stop-after-init \
  --no-http

echo "[3/4] Restarting Odoo service..."
docker restart $CONTAINER

echo "[4/4] Verifying deployment..."
sleep 10
docker exec $CONTAINER odoo \
  -d $DB_NAME \
  --test-enable \
  --test-tags /stamp_chain \
  --stop-after-init \
  --no-http

echo ""
echo "StampChain deployed successfully!"
echo "  Database: $DB_NAME"
echo "  Timestamp: $(date)"
