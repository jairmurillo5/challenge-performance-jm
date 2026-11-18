$ErrorActionPreference = 'Continue'
New-Item -ItemType Directory -Force -Path '.\results' | Out-Null

k6 run --env TPS=50 --env DURATION=1m .\k6\products-add.js 2>&1 | Tee-Object -FilePath .\results\run-50tps.log
$status50 = $LASTEXITCODE

k6 run --env TPS=100 --env DURATION=1m .\k6\products-add.js 2>&1 | Tee-Object -FilePath .\results\run-100tps.log
$status100 = $LASTEXITCODE

python .\reports\generate_report.py --summary-50 .\results\summary-50tps.json --summary-100 .\results\summary-100tps.json --output .\reports\Reporte_ejecutivo_k6.pdf
$statusReport = $LASTEXITCODE
if ($status50 -ne 0 -or $status100 -ne 0 -or $statusReport -ne 0) { exit 1 }
