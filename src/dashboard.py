# -*- coding: utf-8 -*-
"""
FASE 3.7 — Dashboards del proceso (HTML autocontenido).

Genera dos archivos en ``archivos/05_Datos_filtrados/``:

    - ``04_Tablero_Resumen.html``: informe visual del proceso (UISARD,
      nuevas versiones, intersección, expedientes encontrados/faltantes en
      Alfresco, gráfico por estado y vista previa de contratos).
    - ``05_Tablero_en_Vivo.html``: panel en tiempo real que muestra el expediente
      que se está buscando y el avance de la verificación en Alfresco. Se
      auto-refresca en el navegador.

No usan dependencias externas (solo HTML/CSS/SVG embebido), por lo que pueden
abrirse directamente en cualquier navegador.

Este módulo es parte del flujo. Se ejecuta desde ``main.py``:
    python main.py
"""

import html
import os
from datetime import datetime

import pandas as pd

from utils.logger import configurar_logger
from config import RESULTADOS_DIR

logger = configurar_logger("dashboard")

RUTA_DASHBOARD = str(RESULTADOS_DIR / "04_Tablero_Resumen.html")
RUTA_VIVO = str(RESULTADOS_DIR / "05_Tablero_en_Vivo.html")

# Paleta por estado del contrato.
COLORES_ESTADO = {
    "EN UISARD - CON ARCHIVOS": "#16a34a",
    "EN UISARD - SIN ARCHIVOS": "#dc2626",
    "EN UISARD - PENDIENTE": "#f59e0b",
    "NO ESTA EN UISARD": "#64748b",
}

_CSS = """
:root { --line:#e2e8f0; --muted:#64748b; }
* { box-sizing:border-box; }
body { font-family:"Segoe UI",Roboto,Arial,sans-serif; margin:0; background:#f1f5f9; color:#0f172a; }
header { background:#0f172a; color:#fff; padding:18px 24px; }
header h1 { margin:0; font-size:20px; }
header p { margin:4px 0 0; color:#cbd5e1; font-size:13px; }
.wrap { padding:20px 24px 48px; max-width:1200px; margin:0 auto; }
.kpis { display:flex; flex-wrap:wrap; gap:14px; }
.kpi { background:#fff; border:1px solid var(--line); border-radius:12px; padding:14px 18px; min-width:150px; flex:1; }
.kpi .v { font-size:28px; font-weight:700; }
.kpi .l { font-size:12px; color:var(--muted); margin-top:4px; }
.section { background:#fff; border:1px solid var(--line); border-radius:12px; padding:18px; margin-top:18px; }
.section h2 { margin:0 0 12px; font-size:16px; }
.grid2 { display:flex; flex-wrap:wrap; gap:18px; }
.grid2 > * { flex:1; min-width:280px; }
.bar-row { display:flex; align-items:center; gap:10px; margin:8px 0; }
.bar-lbl { width:230px; font-size:13px; }
.bar-track { flex:1; background:#e2e8f0; border-radius:8px; height:16px; overflow:hidden; }
.bar-fill { height:100%; border-radius:8px; }
.bar-val { width:52px; text-align:right; font-weight:600; font-size:13px; }
table { border-collapse:collapse; width:100%; font-size:12px; }
th,td { border-bottom:1px solid var(--line); padding:6px 8px; text-align:left; }
th { background:#f8fafc; }
.badge { padding:2px 8px; border-radius:999px; font-size:11px; font-weight:600; }
.si { background:#dcfce7; color:#166534; }
.no { background:#fee2e2; color:#991b1b; }
.na { background:#e2e8f0; color:#475569; }
.big { font-size:34px; font-weight:800; }
.muted { color:var(--muted); font-size:13px; }
.venn text { font:700 22px "Segoe UI",Arial; fill:#0f172a; text-anchor:middle; }
.venn .cap { font-size:11px; fill:#475569; font-weight:600; }
.progress { background:#e2e8f0; border-radius:10px; height:24px; overflow:hidden; margin-top:10px; }
.progress > div { height:100%; background:linear-gradient(90deg,#2563eb,#16a34a); color:#fff; font-size:12px; text-align:center; line-height:24px; }
.now { font-size:22px; font-weight:800; color:#1d4ed8; word-break:break-all; }
.pill { display:inline-block; padding:3px 10px; border-radius:999px; font-size:12px; font-weight:700; margin-left:8px; }
.pill.buscar { background:#dbeafe; color:#1e40af; }
.pill.ok { background:#dcfce7; color:#166534; }
.pill.err { background:#fee2e2; color:#991b1b; }
.pill.wait { background:#fef3c7; color:#92400e; }
"""


def _normalizar(df) -> pd.DataFrame:
    if df is None:
        return pd.DataFrame()
    df = pd.DataFrame(df)
    if df.empty:
        return df
    df = df.fillna("").copy()
    for col in df.columns:
        df[col] = df[col].astype(str).str.strip()
    return df


def _page(titulo: str, body: str, refresh: int = 0) -> str:
    refresh_tag = f'<meta http-equiv="refresh" content="{refresh}">' if refresh else ""
    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
{refresh_tag}
<title>{html.escape(titulo)}</title>
<style>{_CSS}</style>
</head>
<body>
{body}
</body>
</html>"""


def _kpi(label: str, valor, color: str = "#0f172a") -> str:
    return (
        f'<div class="kpi"><div class="v" style="color:{color}">{valor}</div>'
        f'<div class="l">{html.escape(label)}</div></div>'
    )


def _barra(label: str, valor: int, total: int, color: str) -> str:
    pct = (valor / total * 100) if total else 0
    return (
        f'<div class="bar-row"><div class="bar-lbl">{html.escape(label)}</div>'
        f'<div class="bar-track"><div class="bar-fill" style="width:{pct:.1f}%;background:{color}"></div></div>'
        f'<div class="bar-val">{valor}</div></div>'
    )


def _badge(valor) -> str:
    v = str(valor).strip().upper()
    if v == "SI":
        return '<span class="badge si">SI</span>'
    if v == "NO":
        return '<span class="badge no">NO</span>'
    return '<span class="badge na">&mdash;</span>'


def _guardar(contenido: str, ruta: str) -> str:
    ruta = str(ruta)
    os.makedirs(os.path.dirname(ruta) or ".", exist_ok=True)
    try:
        with open(ruta, "w", encoding="utf-8") as fh:
            fh.write(contenido)
    except OSError as exc:
        logger.warning("No se pudo escribir el dashboard %s: %s", ruta, exc)
    return ruta


def resumen_proceso(resultados: pd.DataFrame) -> dict:
    """Calcula los totales del proceso a partir del reporte maestro (03)."""
    df = _normalizar(resultados)
    total = len(df)
    vacio = {
        "total": 0, "nuevas_total": 0, "uisard_total": 0, "ambos": 0,
        "solo_nuevas": 0, "solo_uisard": 0, "encontrados": 0, "faltantes": 0,
        "pendientes": 0, "sin_expediente": 0, "total_archivos": 0, "estados": {},
    }
    if total == 0:
        return vacio

    if "origen" in df.columns:
        origen = df["origen"].str.upper()
        ambos = int((origen == "AMBOS").sum())
        solo_nuevas = int((origen == "NUEVAS VERSIONES").sum())
        solo_uisard = int((origen == "UISARD").sum())
    else:
        # Modo degradado si el consolidado es anterior a la columna 'origen'.
        uis = df.get("uisard", pd.Series([""] * total)).str.upper() == "SI"
        ambos, solo_nuevas, solo_uisard = 0, int((~uis).sum()), int(uis.sum())

    alfresco = df["alfresco"].str.upper() if "alfresco" in df.columns else pd.Series([""] * total)
    uis = df["uisard"].str.upper() == "SI" if "uisard" in df.columns else pd.Series([False] * total)

    encontrados = int((alfresco == "SI").sum())
    faltantes = int((alfresco == "NO").sum())
    pendientes = int((uis & (alfresco == "")).sum())

    archivos = 0
    if "cantidad_archivos" in df.columns:
        cant = pd.to_numeric(df["cantidad_archivos"], errors="coerce").fillna(0)
        archivos = int(cant.sum())

    estados = df["estado"].value_counts().to_dict() if "estado" in df.columns else {}

    return {
        "total": total,
        "nuevas_total": ambos + solo_nuevas,
        "uisard_total": ambos + solo_uisard,
        "ambos": ambos,
        "solo_nuevas": solo_nuevas,
        "solo_uisard": solo_uisard,
        "encontrados": encontrados,
        "faltantes": faltantes,
        "pendientes": pendientes,
        "sin_expediente": int((~uis).sum()),
        "total_archivos": archivos,
        "estados": estados,
    }


def _venn(m: dict) -> str:
    return f"""<svg class="venn" width="360" height="210" viewBox="0 0 360 210">
  <circle cx="140" cy="105" r="78" fill="#7c3aed" fill-opacity="0.30" stroke="#7c3aed"/>
  <circle cx="220" cy="105" r="78" fill="#2563eb" fill-opacity="0.30" stroke="#2563eb"/>
  <text x="140" y="70" class="cap">NUEVAS VERSIONES</text>
  <text x="220" y="70" class="cap">UISARD</text>
  <text x="92" y="112">{m['solo_nuevas']}</text>
  <text x="180" y="112">{m['ambos']}</text>
  <text x="268" y="112">{m['solo_uisard']}</text>
  <text x="180" y="200" class="cap">Intersección: {m['ambos']}</text>
</svg>"""


def _tabla_preview(df: pd.DataFrame, limite: int = 15) -> str:
    columnas = [
        "contrato", "ordenador", "origen", "uisard",
        "NOMBRE EXPEDIENTE", "alfresco", "cantidad_archivos", "estado",
    ]
    columnas = [c for c in columnas if c in df.columns]
    filas = []
    for _, r in df.head(limite).iterrows():
        celdas = []
        for c in columnas:
            valor = html.escape(str(r.get(c, "")))
            if c in ("uisard", "alfresco"):
                valor = _badge(r.get(c, ""))
            celdas.append(f"<td>{valor}</td>")
        filas.append("<tr>" + "".join(celdas) + "</tr>")
    encabezado = "".join(f"<th>{html.escape(c)}</th>" for c in columnas)
    return f"<table><thead><tr>{encabezado}</tr></thead><tbody>{''.join(filas)}</tbody></table>"


def _informe(m: dict) -> str:
    return (
        f"Se procesaron <b>{m['total']}</b> contratos en total. De ellos, "
        f"<b>{m['nuevas_total']}</b> provienen del reporte de nuevas versiones y "
        f"<b>{m['uisard_total']}</b> están registrados en UISARD, con "
        f"<b>{m['ambos']}</b> contratos presentes en ambos sistemas "
        f"(<b>{m['solo_nuevas']}</b> solo en nuevas versiones y "
        f"<b>{m['solo_uisard']}</b> solo en UISARD).<br><br>"
        f"De los <b>{m['uisard_total']}</b> expedientes registrados en UISARD, "
        f"<b>{m['encontrados']}</b> se corroboraron en Alfresco "
        f"(<b>{m['total_archivos']}</b> archivos en total), "
        f"<b>{m['faltantes']}</b> no se encontraron y "
        f"<b>{m['pendientes']}</b> quedaron pendientes de verificar. "
        f"<b>{m['sin_expediente']}</b> contratos de nuevas versiones no tienen "
        f"expediente en UISARD."
    )


def generar_dashboard(resultados: pd.DataFrame, ruta: str = RUTA_DASHBOARD) -> str:
    """Genera el informe visual del proceso y lo guarda en ``ruta``."""
    df = _normalizar(resultados)
    m = resumen_proceso(df)
    ahora = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

    body = [
        f'<header><h1>Informe del proceso de contrataci&oacute;n</h1>'
        f'<p>Generado: {ahora} &middot; Insumo: 03_Resultado_Final.xlsx</p></header>',
        '<div class="wrap">',
        '<div class="kpis">',
        _kpi("UISARD", m["uisard_total"], "#2563eb"),
        _kpi("Nuevas versiones", m["nuevas_total"], "#7c3aed"),
        _kpi("Intersección (ambos)", m["ambos"], "#0891b2"),
        _kpi("Total unión", m["total"], "#0f172a"),
        "</div>",
        '<div class="section"><h2>Cobertura entre sistemas</h2>'
        '<div class="grid2">'
        f'<div>{_venn(m)}</div>'
        '<div>'
        + _barra("Solo nuevas versiones", m["solo_nuevas"], m["total"] or 1, "#7c3aed")
        + _barra("En ambos (intersección)", m["ambos"], m["total"] or 1, "#0891b2")
        + _barra("Solo UISARD", m["solo_uisard"], m["total"] or 1, "#2563eb")
        + f'<p class="muted">Nuevas versiones: {m["nuevas_total"]} &middot; '
          f'UISARD: {m["uisard_total"]} &middot; Uni&oacute;n: {m["total"]}</p>'
        "</div></div></div>",
        '<div class="section"><h2>Verificaci&oacute;n en Alfresco</h2>',
        '<div class="kpis">',
        _kpi("Encontrados (con archivos)", m["encontrados"], "#16a34a"),
        _kpi("No encontrados", m["faltantes"], "#dc2626"),
        _kpi("Pendientes", m["pendientes"], "#f59e0b"),
        _kpi("Archivos corroborados", m["total_archivos"], "#0f172a"),
        "</div>",
        '<div style="margin-top:14px">'
        + _barra("Encontrados", m["encontrados"], m["uisard_total"] or 1, "#16a34a")
        + _barra("No encontrados", m["faltantes"], m["uisard_total"] or 1, "#dc2626")
        + _barra("Pendientes", m["pendientes"], m["uisard_total"] or 1, "#f59e0b")
        + "</div></div>",
        '<div class="section"><h2>Resumen por estado</h2>',
    ]

    if m["estados"]:
        for estado, valor in sorted(m["estados"].items(), key=lambda x: -x[1]):
            color = COLORES_ESTADO.get(estado, "#64748b")
            body.append(_barra(estado, int(valor), m["total"] or 1, color))
    else:
        body.append('<p class="muted">Sin datos de estado todav&iacute;a.</p>')
    body.append("</div>")

    body.append('<div class="section"><h2>Informe del proceso</h2>'
                f'<p class="muted">{_informe(m)}</p></div>')

    body.append('<div class="section"><h2>Vista previa de contratos '
                f'(primeros {min(15, len(df))} de {len(df)})</h2>'
                + _tabla_preview(df) + "</div>")
    body.append("</div>")

    contenido = _page("Informe del proceso de contratación", "".join(body))
    _guardar(contenido, ruta)
    logger.info("[OK] Dashboard del proceso: %s", ruta)
    return ruta


def _contar_resumen(resumen) -> tuple:
    """Devuelve (encontrados, faltantes) a partir de la lista de resultados."""
    if not resumen:
        return 0, 0
    df = pd.DataFrame(resumen)
    if "alfresco" not in df.columns:
        return 0, 0
    alf = df["alfresco"].astype(str).str.strip().str.upper()
    return int((alf == "SI").sum()), int((alf == "NO").sum())


def _ultimos(resumen, n: int = 10) -> str:
    if not resumen:
        return '<p class="muted">A&uacute;n no hay expedientes evaluados.</p>'
    df = pd.DataFrame(resumen).tail(n)
    filas = []
    for _, r in df.iterrows():
        nombre = html.escape(str(r.get("NOMBRE EXPEDIENTE", "")))
        alf = str(r.get("alfresco", "")).strip().upper()
        cant = html.escape(str(r.get("cantidad_archivos", "")))
        motivo = html.escape(str(r.get("MOTIVO", "")))
        filas.append(
            f"<tr><td>{nombre}</td><td>{_badge(alf)}</td><td>{cant}</td>"
            f"<td>{motivo}</td></tr>"
        )
    return (
        "<table><thead><tr><th>Expediente</th><th>Alfresco</th>"
        "<th>Archivos</th><th>Motivo</th></tr></thead><tbody>"
        + "".join(filas) + "</tbody></table>"
    )


def generar_estado_vivo(
    expediente: str = "",
    indice: int = 0,
    total: int = 0,
    fase: str = "",
    resumen=None,
    ruta: str = RUTA_VIVO,
    estado: str = "BUSCANDO",
) -> str:
    """Genera el panel en tiempo real (se auto-refresca cada 5 s)."""
    resumen = resumen or []
    encontrados, faltantes = _contar_resumen(resumen)
    procesados = encontrados + faltantes
    pendientes = max(total - procesados, 0)
    pct = (procesados / total * 100) if total else 0
    ahora = datetime.now().strftime("%H:%M:%S")

    etiquetas = {
        "BUSCANDO": ('<span class="pill buscar">BUSCANDO</span>', "#1d4ed8"),
        "ENCONTRADO": ('<span class="pill ok">ENCONTRADO</span>', "#16a34a"),
        "REINTENTO": ('<span class="pill wait">PASA A REINTENTO</span>', "#92400e"),
        "LISTO": ('<span class="pill wait">EVALUADO</span>', "#92400e"),
    }
    pill, _ = etiquetas.get(estado, etiquetas["BUSCANDO"])

    body = [
        f'<header><h1>Verificaci&oacute;n en Alfresco &mdash; en vivo</h1>'
        f'<p>Actualizado: {ahora} &middot; se refresca autom&aacute;ticamente cada 5 s</p></header>',
        '<div class="wrap">',
        '<div class="section"><h2>Expediente en curso</h2>'
        f'<div class="now">{html.escape(expediente) or "&mdash;"} {pill}</div>'
        f'<p class="muted">Fase: {html.escape(fase) or "&mdash;"} '
        f'&middot; {indice}/{total}</p>'
        f'<div class="progress"><div style="width:{pct:.1f}%">{pct:.0f}%</div></div>'
        "</div>",
        '<div class="kpis">',
        _kpi("Encontrados", encontrados, "#16a34a"),
        _kpi("No encontrados", faltantes, "#dc2626"),
        _kpi("Pendientes", pendientes, "#f59e0b"),
        _kpi("Procesados", f"{procesados}/{total}", "#0f172a"),
        "</div>",
        '<div class="section"><h2>&Uacute;ltimos expedientes evaluados</h2>'
        + _ultimos(resumen) + "</div>",
        "</div>",
    ]

    contenido = _page("Verificación en vivo", "".join(body), refresh=5)
    _guardar(contenido, ruta)
    return ruta


def main():
    # Rechaza la ejecución directa: el flujo debe pasar por main.py.
    print("Este script forma parte del flujo. Ejecuta: python main.py")
    import sys
    sys.exit(0)


if __name__ == "__main__":
    main()
