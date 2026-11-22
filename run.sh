#!/usr/bin/env bash
set -euo pipefail

echo "============================================================"
echo "  RADAR DE EXPANSÃO - ATLAS FITNESS (PIPELINE E2E)          "
echo "============================================================"

if [ -f ".env" ]; then
  echo "[INFO] Carregando variáveis de ambiente de .env..."
else
  echo "[WARN] Arquivo .env não encontrado. Usando configurações padrão / modo local."
fi

export PYTHONPATH="${PYTHONPATH:-}:$(pwd)"

python -m src.main

echo "============================================================"
echo "  EXECUÇÃO CONCLUÍDA COM SUCESSO!                           "
echo "  Artefatos disponíveis em: ./output/                       "
echo "============================================================"
