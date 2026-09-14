# -*- coding: utf-8 -*-
"""
Borradores de correo a partir del diagnóstico documental.

Carga las plantillas de la hoja ``CORREOS`` del Excel de documentos y las
combina con las columnas de la hoja ``DIAGNOSTICO`` (ver
``auditoria_documental.workbook.fila_diagnostico``).

Plantillas reconocidas por su título: solicitud de faltantes, inconsistencia con
la matriz, carpeta no localizada, expediente completo y consolidado por unidad.
La selección por contrato depende de ``ESTADO`` y de
``COINCIDE CON MATRIZ DE SEGUIMIENTO``.
"""

import os
import re
import unicodedata

from utils.logger import configurar_logger
from .diccionario import _abrir_libro, buscar_diccionario
from .workbook import fila_diagnostico

logger = configurar_logger("correos")

HOJAS_CORREOS = ("CORREOS",)

# Tipos de plantilla (se detectan por palabra clave en el título).
TIPOS = ("faltante", "inconsistencia", "no_localizada", "completo", "consolidado")

_CAMPO_RE = re.compile(r"\{\{\s*([A-Z_]+)\s*\}\}")


def _clave(texto) -> str:
    """Mayúsculas sin acentos para comparar etiquetas."""
    t = unicodedata.normalize("NFKD", str(texto or ""))
    t = "".join(c for c in t if not unicodedata.combining(c))
    return t.strip().upper()


def _parsear(hoja) -> list:
    """Convierte la hoja CORREOS en una lista de plantillas."""
    plantillas = []
    actual = None
    for fila in hoja.iter_rows(values_only=True):
        c1 = str(fila[0]).strip() if fila and fila[0] is not None else ""
        c2 = str(fila[1]).strip() if fila and len(fila) > 1 and fila[1] is not None else ""

        if re.match(r"^\d+\.\s", c1):
            actual = {
                "titulo": re.sub(r"^\d+\.\s*", "", c1),
                "cuando": "",
                "para": "",
                "asunto": "",
                "cuerpo": "",
            }
            plantillas.append(actual)
            continue
        if actual is None:
            continue

        etiqueta = _clave(c1)
        if etiqueta == "CUANDO SE ENVIA":
            actual["cuando"] = c2
        elif etiqueta == "PARA":
            actual["para"] = c2
        elif etiqueta == "ASUNTO":
            actual["asunto"] = c2
        elif etiqueta == "CUERPO":
            actual["cuerpo"] = c2

    return [p for p in plantillas if p["cuerpo"]]


def cargar_plantillas(ruta: str = "") -> list:
    """Carga las plantillas de la hoja CORREOS (autodetecta el archivo si vacío)."""
    ruta = buscar_diccionario(ruta)
    if not ruta:
        logger.warning("No se encontró el archivo de documentos para leer las plantillas de correo.")
        return []

    libro = _abrir_libro(ruta)
    try:
        for nombre in HOJAS_CORREOS:
            if nombre in libro.sheetnames:
                plantillas = _parsear(libro[nombre])
                logger.info("Plantillas de correo cargadas: %d.", len(plantillas))
                return plantillas
    finally:
        libro.close()
    logger.warning("El archivo no contiene la hoja %s.", " / ".join(HOJAS_CORREOS))
    return []


def renderizar(texto, valores: dict) -> str:
    """Reemplaza los campos ``{{CAMPO}}`` por su valor (vacío si no existe)."""
    return _CAMPO_RE.sub(lambda m: str(valores.get(m.group(1), "")), str(texto or ""))


def _tipo_de(plantilla: dict) -> str:
    titulo = plantilla.get("titulo", "").lower()
    for tipo in TIPOS:
        palabra = tipo.replace("_", " ")
        if palabra in titulo:
            return tipo
    return ""


def _por_tipo(plantillas: list, tipo: str):
    for plantilla in plantillas:
        if _tipo_de(plantilla) == tipo:
            return plantilla
    return None


def elegir_plantilla(plantillas: list, fila: dict):
    """Selecciona la plantilla adecuada según el estado del contrato."""
    estado = str(fila.get("ESTADO", "")).strip()
    coincide = str(fila.get("COINCIDE CON MATRIZ DE SEGUIMIENTO", "")).strip().lower()

    if estado == "No encontrada":
        return _por_tipo(plantillas, "no_localizada")
    if coincide.startswith("no coincide"):
        return _por_tipo(plantillas, "inconsistencia")
    if estado == "Completo":
        return _por_tipo(plantillas, "completo")
    if estado == "Incompleto":
        return _por_tipo(plantillas, "faltante")
    return None


def construir_mensajes(
    contratos: list,
    plantillas: list,
    fecha_revision: str = "",
    fecha_limite: str = "",
    unidad_por_contrato: dict = None,
) -> list:
    """Construye los borradores de correo (uno por contrato que lo requiera)."""
    unidad_por_contrato = unidad_por_contrato or {}
    mensajes = []
    for contrato in contratos or []:
        fila = fila_diagnostico(contrato, fecha_revision)
        plantilla = elegir_plantilla(plantillas, fila)
        if not plantilla:
            continue

        contrato_id = fila["CONTRATO"]
        valores = {
            "CONTRATO": contrato_id,
            "CLASE": fila["CLASE"],
            "SUPERVISOR": fila["SUPERVISOR / DESTINATARIO"],
            "ENLACE_CARPETA": fila["ENLACE CARPETA ALFRESCO"],
            "LISTADO_FALTANTES": fila["LISTADO DE FALTANTES"],
            "PORCENTAJE": fila["% COMPLETITUD"],
            "OBSERVACION": fila["OBSERVACIÓN (PARA EL CORREO)"],
            "FECHA_LIMITE": fecha_limite,
            "UNIDAD": unidad_por_contrato.get(contrato_id, contrato.get("centro_costo", "")),
        }
        mensajes.append(
            {
                "contrato": contrato_id,
                "tipo": plantilla["titulo"],
                "para": fila["SUPERVISOR / DESTINATARIO"],
                "asunto": renderizar(plantilla["asunto"], valores),
                "cuerpo": renderizar(plantilla["cuerpo"], valores),
            }
        )
    return mensajes


def escribir_borradores(mensajes: list, ruta: str) -> str:
    """Escribe los borradores en un archivo de texto."""
    lineas = []
    for mensaje in mensajes:
        lineas.append("=" * 72)
        lineas.append(f"PARA: {mensaje['para']}")
        lineas.append(f"ASUNTO: {mensaje['asunto']}")
        lineas.append("")
        lineas.append(mensaje["cuerpo"])
        lineas.append("")

    os.makedirs(os.path.dirname(ruta) or ".", exist_ok=True)
    with open(ruta, "w", encoding="utf-8") as archivo:
        archivo.write("\n".join(lineas))
    logger.info("Borradores de correo escritos: %s (%d).", ruta, len(mensajes))
    return ruta


def generar_borradores(
    contratos: list,
    ruta: str,
    ruta_diccionario: str = "",
    fecha_revision: str = "",
    fecha_limite: str = "",
    unidad_por_contrato: dict = None,
) -> dict:
    """Carga plantillas, construye los borradores y los guarda.

    Devuelve ``{ruta, total, por_tipo}``.
    """
    plantillas = cargar_plantillas(ruta_diccionario)
    mensajes = construir_mensajes(
        contratos,
        plantillas,
        fecha_revision=fecha_revision,
        fecha_limite=fecha_limite,
        unidad_por_contrato=unidad_por_contrato,
    )
    escribir_borradores(mensajes, ruta)

    por_tipo = {}
    for mensaje in mensajes:
        por_tipo[mensaje["tipo"]] = por_tipo.get(mensaje["tipo"], 0) + 1
    return {"ruta": ruta, "total": len(mensajes), "por_tipo": por_tipo}
