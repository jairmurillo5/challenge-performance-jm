# Challenge Performance - Monnet Payments

**Herramienta:** Grafana k6. Este repositorio contiene la estrategia de performance (Parte 1) y el script de carga del endpoint indicado (Parte 2).

## 1. Requisitos

- k6 instalado y disponible en `PATH`.
- Python 3.10 o superior para generar el informe PDF.
- Conexión a Internet hacia `dummyjson.com`.

Instalar la dependencia del reporte:

```bash
python -m pip install -r requirements.txt
```

Instalación de k6: seguir la guía oficial según el sistema operativo: <https://grafana.com/docs/k6/latest/set-up/install-k6/>.

## 2. Parte 1 - Estrategia

Leer `docs/estrategia-parte-1.md`. Incluye dimensionamiento inicial, pruebas recomendadas, flujo crítico, métricas y plan de ejecución para una tienda con 1 500 ventas/día y hasta 7 500 ventas/día en campañas.

## 3. Parte 2 - Script k6

El script `k6/products-add.js` ejecuta una iteración por request mediante el executor `constant-arrival-rate`:

- Escenario A: 50 iteraciones/s durante 1 minuto.
- Escenario B: 100 iteraciones/s durante 1 minuto.
- Los escenarios se corren por separado; no se suman 50 + 100 TPS en una sola ejecución.
- La función `setup()` autentica una vez contra `POST /auth/login` y recupera `accessToken`. El login queda fuera del TPS medido.
- Cada request usa `Authorization: Bearer <JWT>` y `Content-Type: application/json`.
- `title` se genera con el nivel de carga, ID de ejecución, VU e iteración; por eso es distinto para cada request.
- `price` es configurable con `PRODUCT_PRICE` y por defecto es `1.23`.

En Windows PowerShell, si `k6` no se reconoce como comando, agrega su ruta de instalación al `PATH` de la sesión antes de ejecutar cualquiera de las opciones siguientes:

```powershell
$env:Path = "C:\Program Files\k6;$env:Path"
k6 version
```

Si k6 está instalado en otra ubicación, reemplaza `C:\Program Files\k6` por esa ruta.

### Ejecutar ambos escenarios

Linux / macOS:

```bash
chmod +x run-all.sh
./run-all.sh
```

Windows PowerShell:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force
.\run-all.ps1
```

El comando `Set-ExecutionPolicy` permite ejecutar el script únicamente en la sesión actual de PowerShell; no cambia la política permanente del sistema.

### Ejecutar un escenario individual

```bash
k6 run --env TPS=50 --env DURATION=1m k6/products-add.js
k6 run --env TPS=100 --env DURATION=1m k6/products-add.js
```

Ejecuta estos comandos desde la carpeta raíz del proyecto, de forma secuencial. En Windows, usa la configuración del `PATH` indicada arriba si PowerShell no reconoce `k6`.

No ejecutes ambos en paralelo contra el endpoint público.

### Variables opcionales

```bash
k6 run --env TPS=50 --env DURATION=1m --env PRODUCT_PRICE=1.23 k6/products-add.js
```

Para credenciales alternativas, pasar `DUMMYJSON_USERNAME` y `DUMMYJSON_PASSWORD` mediante `--env`. Los valores por defecto son las credenciales de demostración indicadas en el documento del challenge (`emilys` / `emilyspass`). No se imprime ni se guarda el JWT.

## 4. Reporte ejecutivo

Cada ejecución genera:

- `results/summary-50tps.json` y `results/summary-100tps.json`: salida k6 completa.
- `results/executive-50tps.json` y `results/executive-100tps.json`: resumen de métricas.
- `results/summary-*.txt`: resumen legible.
- `reports/Reporte_ejecutivo_k6.pdf`: informe orientado a personas no técnicas.

Generar/actualizar el PDF manualmente:

```bash
python reports/generate_report.py \
  --summary-50 results/summary-50tps.json \
  --summary-100 results/summary-100tps.json \
  --output reports/Reporte_ejecutivo_k6.pdf
```

El generador muestra los resultados disponibles en los archivos JSON. Si todavía no se han ejecutado ambos escenarios, los datos faltantes se indican como N/D; al correrlos, vuelve a generar el informe para incluir las métricas observadas.

## 5. Umbrales iniciales

El script incorpora criterios de evaluación propuestos (no entregados como SLA en el challenge):

- HTTP failure rate menor a 1%.
- Latencia p95 menor a 2 000 ms.
- Checks exitosos superior a 99%.
- Cero `dropped_iterations`.

Los umbrales deben ajustarse con negocio/arquitectura si existe un SLO oficial. La carga se considera sostenida solo si k6 puede programar la tasa configurada sin descartar iteraciones; se debe revisar `dropped_iterations`.

## 6. Consideraciones de interpretación

DummyJSON informa que `POST /products/add` simula la creación y no persiste el producto en su servidor. Por tanto, el ejercicio valida el comportamiento del endpoint de demostración, no la capacidad real de un e-commerce ni un sistema de pagos productivo. Los resultados pueden variar por red, disponibilidad y limitación del servicio público.

## 7. Nombre del repositorio

`challenge-performance-jm`

## 8. Autor

Jair Murillo
