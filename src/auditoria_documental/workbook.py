# -*- coding: utf-8 -*-
"""
Generación del Excel de auditoría documental.

Replica el layout verificado del proyecto de referencia
(``documentacion_contratos/docs/METODOLOGIA.md`` §3.4):

* Hoja ``Resumen_Cruce_Corregido`` — 19 columnas (A-S) con semáforo.
* Hoja ``Cruce_por_Etapa_Corr`` — matriz ETAPA × contrato.
* Una hoja por contrato (``20_2026000003``) con el detalle documento a documento.
* Hoja ``Notas_Diccionario`` — trazabilidad del diccionario.

La entrada es una lista de dicts por contrato (ver ``generar_auditoria``). El
módulo no consulta Alfresco ni lee el diccionario: solo pinta lo que le entregan,
por lo que es testeable de forma aislada.
"""

import os
import re
from datetime import datetime

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.hyperlink import Hyperlink

from utils.logger import configurar_logger

logger = configurar_logger("workbook_auditoria")

# --- Paleta y estilos (idénticos al ejemplo verificado) ---------------------
COLOR_HEADER = "1F4E78"
COLOR_BORDE = "B4C6E7"
COLOR_VERDE = "E2EFDA"
COLOR_AMARILLO = "FFF2CC"
COLOR_ROJO = "FCE4D6"
COLOR_GRIS = "D9D9D9"
COLOR_ENLACE = "0563C1"

FUENTE_HEADER = Font(name="Calibri", size=9, bold=True, color="FFFFFF")
FUENTE_DATO = Font(name="Calibri", size=9)
FUENTE_TITULO = Font(name="Calibri", size=14, bold=True, color=COLOR_HEADER)
FUENTE_ENLACE = Font(name="Calibri", size=9, color=COLOR_ENLACE, underline="single")

RELLENO_HEADER = PatternFill("solid", fgColor=COLOR_HEADER)
RELLENO_VERDE = PatternFill("solid", fgColor=COLOR_VERDE)
RELLENO_AMARILLO = PatternFill("solid", fgColor=COLOR_AMARILLO)
RELLENO_ROJO = PatternFill("solid", fgColor=COLOR_ROJO)
RELLENO_GRIS = PatternFill("solid", fgColor=COLOR_GRIS)

_BORDE = Border(
    left=Side(style="thin", color=COLOR_BORDE),
    right=Side(style="thin", color=COLOR_BORDE),
    top=Side(style="thin", color=COLOR_BORDE),
    bottom=Side(style="thin", color=COLOR_BORDE),
)

# Encabezados del resumen y sus anchos.
CABECERAS_RESUMEN = [
    "#", "CÓDIGO CONTRATO", "CÓD", "TIPO", "CONTRATISTA", "CENTRO DE COSTO",
    "ORDENADOR", "VALOR", "FECHA INICIO", "FECHA FIN", "REQ", "REP", "%",
    "FALTAN", "ESTADO ALFRESCO", "CARPETA", "ESPERADOS", "ENCONTRADOS",
    "FALTANTES", "% CUMPL DIC", "VÍNCULO CARPETA", "VÍNCULO HOJA",
]
ANCHOS_RESUMEN = [
    4, 16, 6, 14, 30, 30, 26, 14, 12, 11, 6, 6, 6, 7, 16, 22, 11, 12, 11, 9, 30, 16,
]

CABECERAS_GRANULAR = [
    "#", "ID_DOC", "DOCUMENTO", "FORMATO", "ETAPA", "ALIAS", "ESTADO",
    "ARCHIVO", "FECHA CREACIÓN/CARGA", "ÚLTIMA MODIFICACIÓN",
]
ANCHOS_GRANULAR = [4, 8, 40, 10, 26, 40, 12, 45, 18, 18]

# Hoja DIAGNOSTICO: una fila por contrato (formato pedido por la División),
# enriquecida con la información del reporte de nuevas versiones.
CABECERAS_DIAGNOSTICO = [
    "CONTRATO", "CLASE", "CONTRATISTA", "VALOR", "FECHA INICIO", "FECHA FIN",
    "TIPO", "UNIDAD", "ESTADO CONTRATO",
    "ENLACE CARPETA ALFRESCO", "CARPETA ENCONTRADA", "DESCARGADA",
    "COINCIDE CON MATRIZ DE SEGUIMIENTO", "Nº PAGOS",
    "DOCS REQUERIDOS", "DOCS HALLADOS", "DOCS FALTANTES", "LISTADO DE FALTANTES",
    "% COMPLETITUD", "ESTADO", "DOCUMENTACIÓN COPIADA",
    "SUPERVISOR / DESTINATARIO", "CORREO ORDENADOR",
    "OBSERVACIÓN (PARA EL CORREO)", "FECHA REVISIÓN",
]
ANCHOS_DIAGNOSTICO = [
    16, 8, 30, 15, 12, 12, 20, 34, 16,
    46, 16, 12, 26, 10,
    14, 12, 12, 46, 12, 14, 16, 26, 30, 50, 14,
]


def _col_diagnostico(nombre: str) -> int:
    """Número de columna (1-based) de una cabecera del DIAGNOSTICO."""
    return CABECERAS_DIAGNOSTICO.index(nombre) + 1


def _col_resumen(nombre: str) -> int:
    """Número de columna (1-based) de una cabecera del resumen."""
    return CABECERAS_RESUMEN.index(nombre) + 1

URL_CARPETA = (
    "https://gesdoc.uis.edu.co/share/page/folder-details"
    "?nodeRef=workspace://SpacesStore/{node_id}"
)


def _color_pct(pct) -> str:
    """Color de semáforo según el porcentaje de cumplimiento."""
    try:
        valor = float(pct)
    except (TypeError, ValueError):
        return ""
    if valor >= 80:
        return COLOR_VERDE
    if valor >= 50:
        return COLOR_AMARILLO
    return COLOR_ROJO


def _color_estado(estado: str) -> str:
    """Color de semáforo para la columna ESTADO ALFRESCO."""
    estado = str(estado or "").upper()
    if "ENCONTRADA" in estado:
        return COLOR_VERDE
    if "NO" in estado:
        return COLOR_ROJO
    return ""


def _nombre_hoja(contrato: str, usados: set) -> str:
    """Nombre de hoja válido (≤31 chars, sin caracteres prohibidos) y único."""
    base = re.sub(r"[^0-9A-Za-z]+", "_", str(contrato or "contrato")).strip("_") or "contrato"
    base = base[:31]
    nombre = base
    contador = 2
    while nombre in usados:
        sufijo = f"_{contador}"
        nombre = base[: 31 - len(sufijo)] + sufijo
        contador += 1
    usados.add(nombre)
    return nombre


def _conteos(contrato: dict) -> tuple:
    """(esperados, encontrados, faltantes, pct) a partir de las filas o del dict."""
    filas = contrato.get("filas") or []
    if filas:
        encontrados = sum(1 for f in filas if str(f.get("ESTADO", "")).upper() == "ENCONTRADO")
        faltantes = sum(1 for f in filas if str(f.get("ESTADO", "")).upper() == "FALTANTE")
        esperados = encontrados + faltantes
        pct = round(encontrados * 100 / esperados, 1) if esperados else 0.0
        return esperados, encontrados, faltantes, pct
    esperados = int(contrato.get("esperados", 0) or 0)
    encontrados = int(contrato.get("encontrados", 0) or 0)
    faltantes = int(contrato.get("faltantes", 0) or 0)
    pct = contrato.get("pct_cumpl")
    if pct is None:
        pct = round(encontrados * 100 / esperados, 1) if esperados else 0.0
    return esperados, encontrados, faltantes, pct


def _escribir_resumen(ws, contratos: list, titulo: str):
    ws.cell(row=1, column=1, value=titulo).font = FUENTE_TITULO
    ws.cell(
        row=2, column=1,
        value=(
            "Match corregido: formato FCO exige código exacto o alias completo; "
            "equivalencias Seguridad↔Parafiscales, ARL↔Estándares/Constancia; "
            "regla FCO.74 exime cierre (NO APLICA)."
        ),
    ).font = FUENTE_DATO

    fila_header = 4
    for col, cabecera in enumerate(CABECERAS_RESUMEN, start=1):
        celda = ws.cell(row=fila_header, column=col, value=cabecera)
        celda.font = FUENTE_HEADER
        celda.fill = RELLENO_HEADER
        celda.border = _BORDE
        celda.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

    fila = fila_header + 1
    for i, contrato in enumerate(contratos, start=1):
        esperados, encontrados, faltantes, pct = _conteos(contrato)
        node_id = contrato.get("node_id", "")
        carpeta = contrato.get("carpeta", "")
        estado_alf = contrato.get("estado_alfresco", "")
        valores = [
            i,
            contrato.get("contrato", ""),
            contrato.get("cod", ""),
            contrato.get("tipo", ""),
            contrato.get("contratista", ""),
            contrato.get("centro_costo", ""),
            contrato.get("supervisor", ""),
            contrato.get("valor", ""),
            contrato.get("fecha_inicio", ""),
            contrato.get("fecha_fin", ""),
            contrato.get("req", ""),
            contrato.get("rep", ""),
            contrato.get("pct", ""),
            contrato.get("faltan", ""),
            estado_alf,
            carpeta,
            esperados,
            encontrados,
            faltantes,
            pct,
        ]
        for col, valor in enumerate(valores, start=1):
            celda = ws.cell(row=fila, column=col, value=valor)
            celda.font = FUENTE_DATO
            celda.border = _BORDE

        # Semáforo en %, ESTADO ALFRESCO y % CUMPL DIC.
        for col, color in (
            (_col_resumen("%"), _color_pct(contrato.get("pct"))),
            (_col_resumen("ESTADO ALFRESCO"), _color_estado(estado_alf)),
            (_col_resumen("% CUMPL DIC"), _color_pct(pct)),
        ):
            if color:
                ws.cell(row=fila, column=col).fill = PatternFill("solid", fgColor=color)

        # Vínculo externo a la carpeta y vínculo interno a la hoja.
        if node_id:
            celda = ws.cell(row=fila, column=_col_resumen("VÍNCULO CARPETA"), value="Ver carpeta")
            celda.hyperlink = URL_CARPETA.format(node_id=node_id)
            celda.font = FUENTE_ENLACE
            celda.border = _BORDE

        hoja = contrato.get("_hoja")
        if hoja:
            celda = ws.cell(row=fila, column=_col_resumen("VÍNCULO HOJA"), value="Ir a hoja")
            celda.hyperlink = Hyperlink(
                ref=celda.coordinate, location=f"'{hoja}'!A1"
            )
            celda.font = FUENTE_ENLACE
            celda.border = _BORDE

        fila += 1

    for col, ancho in enumerate(ANCHOS_RESUMEN, start=1):
        ws.column_dimensions[get_column_letter(col)].width = ancho
    ws.freeze_panes = f"A{fila_header + 1}"
    if fila > fila_header + 1:
        fin = get_column_letter(len(CABECERAS_RESUMEN))
        ws.auto_filter.ref = f"A{fila_header}:{fin}{fila - 1}"


def _escribir_cruce_etapas(ws, contratos: list):
    ws.cell(row=1, column=1, value="CUMPLIMIENTO POR ETAPA CORR").font = FUENTE_TITULO

    fila_header = 4
    ws.cell(row=fila_header, column=1, value="ETAPA").font = FUENTE_HEADER
    ws.cell(row=fila_header, column=1).fill = RELLENO_HEADER
    for col, contrato in enumerate(contratos, start=2):
        celda = ws.cell(row=fila_header, column=col, value=contrato.get("contrato", ""))
        celda.font = FUENTE_HEADER
        celda.fill = RELLENO_HEADER

    # Reúne las etapas presentes conservando el orden de aparición.
    etapas = []
    for contrato in contratos:
        for etapa in (contrato.get("etapas") or {}):
            if etapa not in etapas:
                etapas.append(etapa)

    fila = fila_header + 1
    for etapa in etapas:
        celda = ws.cell(row=fila, column=1, value=etapa)
        celda.font = FUENTE_DATO
        celda.border = _BORDE
        for col, contrato in enumerate(contratos, start=2):
            par = (contrato.get("etapas") or {}).get(etapa)
            texto = f"{par[0]}/{par[1]}" if par else ""
            celda = ws.cell(row=fila, column=col, value=texto)
            celda.font = FUENTE_DATO
            celda.border = _BORDE
            celda.alignment = Alignment(horizontal="center")
        fila += 1

    ws.column_dimensions["A"].width = 34
    for col in range(2, len(contratos) + 2):
        ws.column_dimensions[get_column_letter(col)].width = 14


def _faltantes_texto(filas: list) -> str:
    """Lista legible de documentos faltantes (formato + documento)."""
    partes = []
    for fila in filas or []:
        if str(fila.get("ESTADO", "")).upper() != "FALTANTE":
            continue
        formato = str(fila.get("FORMATO", "")).strip()
        documento = str(fila.get("DOCUMENTO", "")).strip()
        partes.append(f"{formato} {documento}".strip())
    return ", ".join(partes)


def _estado_diagnostico(contrato: dict, faltantes: int) -> str:
    """Estado resumido del expediente para la hoja DIAGNOSTICO."""
    if str(contrato.get("estado_alfresco", "")).upper() != "ENCONTRADA":
        return "No encontrada"
    return "Completo" if faltantes == 0 else "Incompleto"


def _escribir_diagnostico(ws, contratos: list, fecha_revision: str):
    ws.cell(row=1, column=1, value="DIAGNÓSTICO POR CONTRATO").font = FUENTE_TITULO
    ws.cell(
        row=2, column=1,
        value=(
            "Una fila por contrato. Las columnas de enlace y observación son las "
            "que alimentan los correos a la unidad o al supervisor."
        ),
    ).font = FUENTE_DATO

    fila_header = 4
    for col, cabecera in enumerate(CABECERAS_DIAGNOSTICO, start=1):
        celda = ws.cell(row=fila_header, column=col, value=cabecera)
        celda.font = FUENTE_HEADER
        celda.fill = RELLENO_HEADER
        celda.border = _BORDE
        celda.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

    fila = fila_header + 1
    for contrato in contratos:
        valores = fila_diagnostico(contrato, fecha_revision)
        for col, cabecera in enumerate(CABECERAS_DIAGNOSTICO, start=1):
            celda = ws.cell(row=fila, column=col, value=valores[cabecera])
            celda.font = FUENTE_DATO
            celda.border = _BORDE

        node_id = contrato.get("node_id", "")
        if node_id:
            celda = ws.cell(row=fila, column=_col_diagnostico("ENLACE CARPETA ALFRESCO"))
            celda.hyperlink = URL_CARPETA.format(node_id=node_id)
            celda.font = FUENTE_ENLACE

        _, _, _, pct = _conteos(contrato)
        color = _color_pct(pct)
        if color:
            ws.cell(row=fila, column=_col_diagnostico("% COMPLETITUD")).fill = PatternFill(
                "solid", fgColor=color
            )
        fila += 1

    for col, ancho in enumerate(ANCHOS_DIAGNOSTICO, start=1):
        ws.column_dimensions[get_column_letter(col)].width = ancho
    ws.freeze_panes = f"A{fila_header + 1}"
    if fila > fila_header + 1:
        fin = get_column_letter(len(CABECERAS_DIAGNOSTICO))
        ws.auto_filter.ref = f"A{fila_header}:{fin}{fila - 1}"


def fila_diagnostico(contrato: dict, fecha_revision: str = "") -> dict:
    """Devuelve la fila DIAGNOSTICO de un contrato como dict cabecera→valor.

    Reutilizable por la hoja ``DIAGNOSTICO`` y por el módulo de correos.
    """
    if not fecha_revision:
        fecha_revision = datetime.now().strftime("%Y-%m-%d")

    esperados, encontrados, faltantes, pct = _conteos(contrato)
    node_id = contrato.get("node_id", "")
    filas = contrato.get("filas") or []
    encontrada = str(contrato.get("estado_alfresco", "")).upper() == "ENCONTRADA"

    observacion = contrato.get("observacion", "")
    if not observacion:
        if not encontrada:
            observacion = "No se encontró la carpeta en Alfresco."
        elif faltantes:
            observacion = f"Faltan {faltantes} documento(s) obligatorio(s)."

    valores = [
        contrato.get("contrato", ""),
        contrato.get("cod", ""),
        contrato.get("contratista", ""),
        contrato.get("valor", ""),
        contrato.get("fecha_inicio", ""),
        contrato.get("fecha_fin", ""),
        contrato.get("tipo", ""),
        contrato.get("unidad", ""),
        contrato.get("estado_contrato", ""),
        URL_CARPETA.format(node_id=node_id) if node_id else "",
        "Encontrada" if encontrada else "No encontrada",
        contrato.get("descargada", "Sí" if encontrada else "No"),
        contrato.get("coincide_matriz", "No evaluado"),
        contrato.get("num_pagos", ""),
        esperados,
        encontrados,
        faltantes,
        _faltantes_texto(filas),
        f"{pct}%",
        _estado_diagnostico(contrato, faltantes),
        contrato.get("documentacion_copiada", "No"),
        contrato.get("supervisor", ""),
        contrato.get("correo_ordenador", ""),
        observacion,
        contrato.get("fecha_revision", fecha_revision),
    ]
    return dict(zip(CABECERAS_DIAGNOSTICO, valores))


def _escribir_granular(ws, contrato: dict, contrato_ref: str = "Resumen_Cruce_Corregido"):
    ws.cell(
        row=1, column=1,
        value=(
            f"CONTRATO {contrato.get('contrato', '')} — "
            f"{contrato.get('contratista', '')} — {contrato.get('tipo', '')}"
        ),
    ).font = FUENTE_TITULO
    ws.cell(
        row=2, column=1,
        value=(
            f"VALOR {contrato.get('valor', '')} | "
            f"INICIO {contrato.get('fecha_inicio', '')} | "
            f"FIN {contrato.get('fecha_fin', '')} | "
            f"ORDENADOR {contrato.get('supervisor', '')} | "
            f"UNIDAD {contrato.get('unidad', '')} | "
            f"ESTADO {contrato.get('estado_contrato', '')}"
        ),
    ).font = FUENTE_DATO
    ws.cell(
        row=3, column=1,
        value=f"ALFRESCO: {contrato.get('carpeta', '')} | {contrato.get('node_id', '')}",
    ).font = FUENTE_DATO

    node_id = contrato.get("node_id", "")
    if node_id:
        celda = ws.cell(row=4, column=1, value=f"VÍNCULO CARPETA: {URL_CARPETA.format(node_id=node_id)}")
        celda.hyperlink = URL_CARPETA.format(node_id=node_id)
        celda.font = FUENTE_ENLACE
        ws.merge_cells(start_row=4, start_column=1, end_row=4, end_column=10)

    for col, cabecera in enumerate(CABECERAS_GRANULAR, start=1):
        celda = ws.cell(row=5, column=col, value=cabecera)
        celda.font = FUENTE_HEADER
        celda.fill = RELLENO_HEADER
        celda.border = _BORDE
        celda.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

    celda = ws.cell(row=6, column=1, value="← Volver al Resumen")
    celda.hyperlink = Hyperlink(ref=celda.coordinate, location=f"'{contrato_ref}'!A1")
    celda.font = FUENTE_ENLACE
    celda.fill = RELLENO_AMARILLO

    fila = 7
    for i, detalle in enumerate(contrato.get("filas") or [], start=1):
        valores = [
            i,
            detalle.get("ID_DOC", ""),
            detalle.get("DOCUMENTO", ""),
            detalle.get("FORMATO", ""),
            detalle.get("ETAPA", ""),
            detalle.get("ALIAS", ""),
            detalle.get("ESTADO", ""),
            detalle.get("ARCHIVO", ""),
            detalle.get("FECHA CREACIÓN/CARGA", ""),
            detalle.get("ÚLTIMA MODIFICACIÓN", ""),
        ]
        for col, valor in enumerate(valores, start=1):
            celda = ws.cell(row=fila, column=col, value=valor)
            celda.font = FUENTE_DATO
            celda.border = _BORDE
        estado = str(detalle.get("ESTADO", "")).upper()
        if estado == "NO APLICA":
            for col in range(1, len(CABECERAS_GRANULAR) + 1):
                ws.cell(row=fila, column=col).fill = RELLENO_GRIS
        fila += 1

    for col, ancho in enumerate(ANCHOS_GRANULAR, start=1):
        ws.column_dimensions[get_column_letter(col)].width = ancho
    ws.freeze_panes = "A7"


def _escribir_notas(ws, notas):
    ws.cell(row=1, column=1, value="NOTAS DEL DICCIONARIO Y DEL MATCH").font = FUENTE_TITULO
    fila = 3
    for nota in notas or []:
        ws.cell(row=fila, column=1, value=str(nota)).font = FUENTE_DATO
        fila += 1
    ws.column_dimensions["A"].width = 120


def generar_auditoria(
    contratos: list,
    ruta_salida: str,
    periodo: str = "",
    notas=None,
    fecha_revision: str = "",
) -> str:
    """Genera el Excel de auditoría y devuelve la ruta.

    Cada elemento de ``contratos`` es un dict con (todas opcionales salvo
    ``contrato``): ``contrato, cod, tipo, contratista, valor, fecha_fin,
    contrato_id, req, rep, pct, faltan, estado_alfresco, carpeta, node_id,
    filas, etapas``. Los conteos y el ``% CUMPL DIC`` se calculan desde ``filas``
    si no se pasan explícitamente. ``fecha_revision`` rellena la columna
    homónima de la hoja ``DIAGNOSTICO`` (por defecto, hoy).
    """
    if not fecha_revision:
        fecha_revision = datetime.now().strftime("%Y-%m-%d")

    libro = Workbook()
    resumen = libro.active
    resumen.title = "Resumen_Cruce_Corregido"

    usados = {resumen.title}
    for contrato in contratos:
        contrato["_hoja"] = _nombre_hoja(contrato.get("contrato", ""), usados)

    titulo = f"{periodo} - CRUCE CORREGIDO".strip(" -") or "CRUCE CORREGIDO"
    _escribir_resumen(resumen, contratos, titulo)
    _escribir_cruce_etapas(libro.create_sheet("Cruce_por_Etapa_Corr"), contratos)
    _escribir_diagnostico(libro.create_sheet("DIAGNOSTICO"), contratos, fecha_revision)

    for contrato in contratos:
        hoja = libro.create_sheet(contrato["_hoja"])
        _escribir_granular(hoja, contrato)

    _escribir_notas(libro.create_sheet("Notas_Diccionario"), notas)

    os.makedirs(os.path.dirname(ruta_salida) or ".", exist_ok=True)
    libro.save(ruta_salida)
    logger.info("Auditoría documental guardada: %s (%d contratos)", ruta_salida, len(contratos))
    return ruta_salida
