#!/usr/bin/env bash
set -uo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"
mkdir -p results

if ! command -v k6 >/dev/null 2>&1; then
  echo "ERROR: k6 no está instalado o no está disponible en PATH." >&2
  exit 127
fi

status_50=0
status_100=0

echo "=== Ejecutando escenario independiente de 50 TPS durante 1 minuto ==="
k6 run --env TPS=50 --env DURATION=1m k6/products-add.js 2>&1 | tee results/run-50tps.log
status_50=${PIPESTATUS[0]}

echo "=== Ejecutando escenario independiente de 100 TPS durante 1 minuto ==="
k6 run --env TPS=100 --env DURATION=1m k6/products-add.js 2>&1 | tee results/run-100tps.log
status_100=${PIPESTATUS[0]}

echo "=== Generando reporte ejecutivo ==="
python reports/generate_report.py \
  --summary-50 results/summary-50tps.json \
  --summary-100 results/summary-100tps.json \
  --output reports/Reporte_ejecutivo_k6.pdf
status_report=$?

if [[ $status_50 -ne 0 || $status_100 -ne 0 || $status_report -ne 0 ]]; then
  echo "Al menos un escenario terminó con código distinto de cero. Revisar reportes y umbrales." >&2
  exit 1
fi

echo "Ejecución terminada. Revisar reports/Reporte_ejecutivo_k6.pdf y results/."
