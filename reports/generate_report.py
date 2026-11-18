#!/usr/bin/env python3
"""Genera un PDF ejecutivo a partir de los JSON resumen de k6.

Si los archivos aún no existen, genera un informe de plantilla explícitamente
marcado como pendiente de ejecución; nunca inventa métricas.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether
)


def load_summary(path: Path, target_tps: int) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"No se pudo leer {path}: {exc}") from exc
    metrics = raw.get("metrics", raw)
    if "http_req_duration" not in metrics and "http_req_duration" in raw.get("metrics", {}):
        metrics = raw["metrics"]
    return {"target_tps": target_tps, "metrics": metrics, "source": str(path)}


def fmt(value: Any, suffix: str = "") -> str:
    if value is None:
        return "N/D"
    if isinstance(value, bool):
        return "Sí" if value else "No"
    if isinstance(value, (int, float)):
        return f"{value:,.2f}{suffix}"
    return f"{value}{suffix}"


def extract_case(case: dict[str, Any] | None, target_tps: int) -> dict[str, Any]:
    if not case:
        return {"target_tps": target_tps, "available": False}
    metrics = case.get("metrics", {})

    def metric_value(name: str, value_name: str):
        metric = metrics.get(name)
        if isinstance(metric, dict):
            values = metric.get("values", metric)
            if isinstance(values, dict):
                return values.get(value_name)
        return metric if value_name in ("count", "rate", "max") else None

    result = {
        "target_tps": target_tps,
        "available": True,
        "requests": metric_value("product_requests", "count") or metric_value("iterations", "count"),
        "created": metric_value("products_created", "count"),
        "failed_products": metric_value("product_create_failures", "count"),
        "avg": metric_value("product_req_duration", "avg"),
        "p95": metric_value("product_req_duration", "p(95)"),
        "p99": metric_value("product_req_duration", "p(99)"),
        "max": metric_value("product_req_duration", "max"),
        "failure_rate": metric_value("product_request_failure_rate", "rate"),
        "checks_rate": metric_value("product_checks", "rate"),
        "dropped": metric_value("dropped_iterations", "count"),
        "vus_max": metric_value("vus", "max")
    }
    result["pass"] = (
        result["p95"] is not None and result["failure_rate"] is not None
        and result["checks_rate"] is not None and result["dropped"] is not None
        and result["p95"] < 2000 and result["failure_rate"] < 0.01
        and result["checks_rate"] > 0.99 and result["dropped"] == 0
    )
    return result


def build_pdf(output: Path, case50: dict[str, Any], case100: dict[str, Any]) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name="CoverTitle", parent=styles["Title"], fontName="Helvetica-Bold",
        fontSize=23, leading=28, textColor=colors.HexColor("#16324F"), alignment=TA_LEFT,
        spaceAfter=8
    ))
    styles.add(ParagraphStyle(
        name="Section", parent=styles["Heading2"], fontName="Helvetica-Bold",
        fontSize=13, leading=17, textColor=colors.HexColor("#16324F"), spaceBefore=9, spaceAfter=5
    ))
    styles.add(ParagraphStyle(
        name="BodySmall", parent=styles["BodyText"], fontName="Helvetica",
        fontSize=9, leading=13, textColor=colors.HexColor("#263238"), spaceAfter=5
    ))
    styles.add(ParagraphStyle(
        name="Muted", parent=styles["BodyText"], fontName="Helvetica-Oblique",
        fontSize=8, leading=11, textColor=colors.HexColor("#5F6B73"), spaceAfter=5
    ))

    doc = SimpleDocTemplate(
        str(output), pagesize=A4,
        rightMargin=18 * mm, leftMargin=18 * mm,
        topMargin=16 * mm, bottomMargin=14 * mm,
        title="Reporte ejecutivo de pruebas de performance - Monnet Payments",
        author="Jair Murillo"
    )
    story: list[Any] = []
    all_available = case50["available"] and case100["available"]
    if all_available:
        status_text = "RESULTADOS MEDIDOS - revisar veredicto por escenario"
        status_color = colors.HexColor("#DCEFE7")
    else:
        status_text = "PLANTILLA - PENDIENTE DE EJECUCIÓN K6"
        status_color = colors.HexColor("#FFF1CC")

    story.append(Paragraph("Reporte ejecutivo", styles["CoverTitle"]))
    story.append(Paragraph("Pruebas de carga - Monnet Payments", styles["Heading2"]))
    status = Table([[Paragraph(f"<b>{status_text}</b>", styles["BodySmall"])]], colWidths=[174 * mm])
    status.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), status_color),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#C8D0D5")),
        ("LEFTPADDING", (0, 0), (-1, -1), 9),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2)
    ]))
    story.extend([status, Spacer(1, 5 * mm)])

    story.append(Paragraph("1. Objetivo", styles["Section"]))
    story.append(Paragraph(
        "Evaluar el endpoint <b>POST https://dummyjson.com/products/add</b> con dos perfiles "
        "independientes: 50 y 100 iteraciones por segundo (TPS), durante un minuto cada uno. "
        "Cada request envía un título único y un JWT generado previamente por POST /auth/login.",
        styles["BodySmall"]
    ))
    story.append(Paragraph("2. Diseño de la prueba", styles["Section"]))
    design_data = [
        ["Escenario", "Carga objetivo", "Duración", "Estrategia"],
        ["A", "50 TPS", "1 minuto", "constant-arrival-rate"],
        ["B", "100 TPS", "1 minuto", "constant-arrival-rate"],
    ]
    design = Table(design_data, colWidths=[23 * mm, 33 * mm, 34 * mm, 84 * mm])
    design.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#16324F")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#CAD2D8")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F3F6F8")]),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.extend([design, Spacer(1, 3 * mm)])

    story.append(Paragraph("3. Resultados", styles["Section"]))
    rows = [["Indicador", "50 TPS", "100 TPS"]]
    labels = [
        ("Requests al endpoint", "requests"),
        ("Productos con checks exitosos", "created"),
        ("Latencia promedio (ms)", "avg"),
        ("Latencia p95 (ms)", "p95"),
        ("Latencia p99 (ms)", "p99"),
        ("Latencia máxima (ms)", "max"),
        ("Tasa de error HTTP", "failure_rate"),
        ("Tasa de checks exitosos", "checks_rate"),
        ("Iteraciones descartadas", "dropped"),
        ("Máximo de VUs", "vus_max"),
    ]
    for label, key in labels:
        left = fmt(case50.get(key), "" if key not in ("failure_rate", "checks_rate") else "") if case50["available"] else "N/D - no ejecutado"
        right = fmt(case100.get(key), "" if key not in ("failure_rate", "checks_rate") else "") if case100["available"] else "N/D - no ejecutado"
        if key in ("failure_rate", "checks_rate"):
            left = f"{case50[key] * 100:.2f}%" if case50["available"] and case50.get(key) is not None else "N/D - no ejecutado"
            right = f"{case100[key] * 100:.2f}%" if case100["available"] and case100.get(key) is not None else "N/D - no ejecutado"
        rows.append([label, left, right])
    metrics_table = Table(rows, colWidths=[75 * mm, 49.5 * mm, 49.5 * mm], repeatRows=1)
    metrics_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#16324F")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 7.5),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#CAD2D8")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F3F6F8")]),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    story.extend([metrics_table, Spacer(1, 3 * mm)])

    story.append(Paragraph("4. Criterios de aceptación propuestos", styles["Section"]))
    story.append(Paragraph(
        "El script aplica los siguientes umbrales iniciales: tasa de errores HTTP menor a 1%; "
        "latencia p95 menor a 2 000 ms; checks exitosos superior a 99%; y cero iteraciones descartadas. "
        "Son criterios de evaluación propuestos para este ejercicio, no un SLA entregado por el negocio.",
        styles["BodySmall"]
    ))

    story.append(Paragraph("5. Conclusión ejecutiva", styles["Section"]))
    if all_available:
        for case in (case50, case100):
            scenario = f"{case['target_tps']} TPS"
            result = "cumple" if case.get("pass") else "no cumple o presenta métricas incompletas"
            story.append(Paragraph(
                f"El escenario de <b>{scenario}</b> {result} los criterios de aceptación configurados. "
                "Revisar latencias, errores, checks e iteraciones descartadas en conjunto antes de emitir "
                "una conclusión de capacidad.", styles["BodySmall"]
            ))
        story.append(Paragraph(
            "La API DummyJSON simula la creación y devuelve un objeto de respuesta; no persiste el producto "
            "en el servidor. Por tanto, estos resultados caracterizan el endpoint de demostración y no "
            "acreditan la capacidad de una plataforma de pagos/productiva.", styles["BodySmall"]
        ))
    else:
        story.append(Paragraph(
            "No se adjuntaron resultados de una ejecución k6 en este paquete. Los campos numéricos se "
            "mantienen como N/D para evitar presentar datos ficticios. Ejecute <b>./run-all.sh</b> "
            "(Linux/macOS) o <b>run-all.ps1</b> (Windows); el generador reemplazará este informe con "
            "las métricas de ambos escenarios.", styles["BodySmall"]
        ))

    story.append(Paragraph("6. Alcance y limitaciones", styles["Section"]))
    story.append(Paragraph(
        "El login se ejecuta una vez en la fase setup y queda fuera del TPS medido. Los escenarios de 50 "
        "y 100 TPS se ejecutan de forma secuencial e independiente para evitar sumar ambas cargas. "
        "La carga se compone de una iteración HTTP por request de creación. DummyJSON documenta que "
        "POST /products/add simula la creación sin guardar el producto de forma permanente.",
        styles["BodySmall"]
    ))
    story.append(Paragraph("Preparado por: Jair Murillo | Challenge QA Engineer SR", styles["Muted"]))

    def add_footer(canvas, document):
        canvas.saveState()
        canvas.setStrokeColor(colors.HexColor("#D4DCE2"))
        canvas.line(18 * mm, 13 * mm, 192 * mm, 13 * mm)
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(colors.HexColor("#5F6B73"))
        canvas.drawString(18 * mm, 8 * mm, "Monnet Payments | Informe de pruebas de performance")
        canvas.drawRightString(192 * mm, 8 * mm, f"Página {document.page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=add_footer, onLaterPages=add_footer)


def main() -> None:
    parser = argparse.ArgumentParser(description="Genera reporte PDF ejecutivo a partir de resúmenes k6.")
    parser.add_argument("--summary-50", type=Path, default=Path("results/summary-50tps.json"))
    parser.add_argument("--summary-100", type=Path, default=Path("results/summary-100tps.json"))
    parser.add_argument("--output", type=Path, default=Path("reports/Reporte_ejecutivo_k6.pdf"))
    args = parser.parse_args()

    case50 = extract_case(load_summary(args.summary_50, 50), 50)
    case100 = extract_case(load_summary(args.summary_100, 100), 100)
    build_pdf(args.output, case50, case100)
    print(f"Reporte generado: {args.output}")


if __name__ == "__main__":
    main()
