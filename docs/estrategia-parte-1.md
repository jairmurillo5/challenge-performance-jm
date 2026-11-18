# Parte 1 - Estrategia de pruebas de performance

## Contexto y dimensionamiento inicial

- Operación promedio: aproximadamente **1 500 ventas por día**.
- Fechas especiales: el volumen diario se quintuplica, hasta aproximadamente **7 500 ventas por día**.
- Promedio aritmético distribuido en 24 horas: 1 500 / 86 400 = **0,0174 ventas/s**; 7 500 / 86 400 = **0,0868 ventas/s**.

Estos promedios no representan el pico real y tampoco equivalen a TPS del backend: una venta puede disparar múltiples llamadas (catálogo, carrito, inventario, pricing, autenticación, checkout, pago, antifraude, notificaciones, etc.). Antes de fijar una carga definitiva se deben obtener curvas de tráfico por minuto/segundo, distribución por endpoint, concurrencia, tasa de conversión y tiempos de respuesta de producción.

## Pruebas recomendadas

### Escenarios expresados con Gherkin

```gherkin
Feature: Rendimiento de la tienda en operación normal y campañas

  Background:
    Given la tienda registra aproximadamente 1500 ventas por día
    And la carga de fechas especiales puede alcanzar aproximadamente 7500 ventas por día
    And existe un ambiente aislado con datos representativos y pagos simulados

  Scenario: Verificar el comportamiento con la carga normal
    Given se conoce la distribución horaria y por minuto de las ventas normales
    When se ejecuta una prueba baseline con la carga promedio observada
    Then el sistema mantiene los SLO acordados
    And registra una tasa de errores aceptable
    And conserva la consistencia de inventario, órdenes y pagos

  Scenario: Verificar el comportamiento durante una campaña
    Given se conoce el pico real de tráfico de una campaña
    When se ejecuta el flujo completo de compra con el perfil de carga de campaña
    Then el sistema procesa la demanda sin degradación por encima del SLO
    And no pierde ni duplica órdenes ni pagos

  Scenario: Detectar el punto de degradación
    Given el sistema opera en estado estable
    When la carga se incrementa gradualmente por encima del pico de campaña
    Then se identifica el punto en el que comienza la degradación
    And se registra el rendimiento de CPU, memoria, base de datos y dependencias

  Scenario: Evaluar una ráfaga de tráfico
    Given el sistema opera con carga baja
    When llega una ráfaga rápida hasta el pico esperado
    And el tráfico vuelve a la carga inicial
    Then el sistema permanece estable durante el incremento
    And recupera su rendimiento normal sin pérdida de transacciones

  Scenario: Detectar degradaciones prolongadas
    Given se configura una carga estable representativa
    When la prueba se ejecuta durante varias horas
    Then no aparecen fugas de memoria ni crecimiento anormal de conexiones
    And el tiempo de respuesta no se degrada progresivamente

  Scenario: Validar la recuperación ante fallos
    Given una dependencia o instancia presenta una falla controlada
    When el sistema continúa procesando tráfico
    Then aplica la degradación o recuperación definida
    And evita la pérdida o duplicidad de órdenes y pagos
```

| Prueba | Objetivo | Modelo sugerido |
|---|---|---|
| Baseline | Establecer latencia y errores con carga baja y estable | Flujo de compra completo con la carga promedio observada |
| Load / carga esperada | Validar operación normal | Perfil horario real de un día ordinario; ramp-up y meseta |
| Peak / carga de campaña | Validar la demanda quintuplicada | Perfil de campaña calculado con los picos reales; no asumir distribución uniforme |
| Stress | Encontrar el límite y el punto de degradación | Incrementos graduales por encima del pico de campaña |
| Spike | Evaluar promociones, campañas o ráfagas de tráfico | Salto rápido desde carga baja hasta el pico y retorno |
| Soak / endurance | Detectar fugas de memoria, degradación y acumulación de conexiones | Carga estable representativa durante varias horas |
| Volume / datos | Evaluar consultas y escrituras con crecimiento de catálogo, órdenes e historial | Dataset cercano al volumen esperado en campaña y al crecimiento futuro |
| Resiliencia / recuperación | Verificar comportamiento ante fallos parciales y recuperación | Latencia/errores de dependencias, reinicio de instancias, degradación controlada |
| Escalabilidad | Comprobar que la capacidad aumenta al escalar recursos | Repetir el mismo perfil antes y después de escalar horizontal/verticalmente |

## Flujo crítico y cobertura

El principal escenario debe representar el recorrido real de compra: navegación/búsqueda, detalle de producto, carrito, validación de stock, cálculo de precio/descuento, checkout, autorización de pago y confirmación de orden. Añadir escenarios de lectura intensiva y escritura concurrente, además de pruebas aisladas por endpoint para localizar cuellos de botella.

## Métricas y criterios

Medir throughput (RPS/TPS por endpoint y por transacción de negocio), latencia p50/p90/p95/p99, tasa de errores, timeouts, iteraciones descartadas, concurrencia, CPU/memoria, pool de conexiones, colas, locks, saturación de base de datos, dependencias externas y tasa de éxito de compra.

Los umbrales finales deben acordarse con negocio y arquitectura (SLO/SLA). Para campaña, el criterio principal no es solo soportar 5x ventas diarias: es sostener el pico medido, mantener la experiencia dentro de los SLO y recuperarse sin pérdida ni duplicidad de órdenes/pagos.

## Plan de ejecución

1. Obtener telemetría productiva por intervalos de 1 minuto o menos y descomponer cada venta en requests por servicio.
2. Construir datos de prueba representativos y controlar efectos colaterales (pagos simulados, inventario aislado, limpieza de datos).
3. Ejecutar baseline y carga normal; validar consistencia funcional y métricas.
4. Ejecutar perfil de campaña con rampa, meseta y descenso.
5. Ejecutar spike, stress y soak en ambientes aislados.
6. Correlacionar métricas de k6 con APM, logs, métricas de infraestructura y base de datos.
7. Repetir después de optimizaciones y comparar resultados con el baseline.

## Conclusión

La multiplicación por cinco es un factor de volumen diario, no una tasa de 5x TPS aplicable sin más a cada endpoint. La carga de prueba debe derivarse de la distribución temporal de ventas y del mapa de llamadas por transacción. Se recomienda una estrategia combinada de baseline, load, peak, stress, spike y soak, priorizando el checkout y el pago por su impacto directo en ingresos y consistencia transaccional.
