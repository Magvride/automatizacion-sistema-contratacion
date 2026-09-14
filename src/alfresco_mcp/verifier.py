# -*- coding: utf-8 -*-
"""
Verificación de un contrato contra Alfresco (lógica pura).

Dado un contrato (``contrato`` + ``contratista``), resuelve su carpeta en
Alfresco, lista los archivos reales y evalúa los documentos obligatorios del
diccionario. No depende del transporte: recibe un ``AlfrescoGateway``.

Produce, entre otras cosas, la fila ``06_Verificacion_Alfresco.csv`` con el
esquema histórico y las filas de la hoja granular del Excel de auditoría.
"""

import re

from utils.logger import configurar_logger
from auditoria_documental import match as _match

logger = configurar_logger("alfresco_verifier")

# Valores de MOTIVO (esquema 06).
MOTIVO_OK = ""
MOTIVO_CARPETA = "carpeta_no_encontrada"
MOTIVO_EXPEDIENTE = "expediente_no_encontrado"
MOTIVO_ERROR = "error_consulta"


def numero_y_pad(contrato) -> tuple:
    """Devuelve ``(numero, pad)`` a partir del código de contrato.

    ``"20-2026000003"`` → ``("2026000003", "0020")``.
    ``"270-2026000050"`` → ``("2026000050", "0270")``.
    """
    texto = str(contrato or "").strip()
    bloques = re.findall(r"\d+", texto)
    if not bloques:
        return "", ""

    if "-" in texto:
        prefijo, resto = texto.split("-", 1)
        pad = re.sub(r"\D", "", prefijo)
        numero = re.sub(r"\D", "", resto) or bloques[-1]
        return numero, pad.zfill(4) if pad else ""

    if len(bloques) > 1:
        return bloques[-1], bloques[0].zfill(4)
    return bloques[-1], ""


def _partes_carpeta(nombre: str) -> tuple:
    """Separa ``(prefijo, numero)`` del nombre de una carpeta de contrato.

    Reconoce las variantes observadas en Alfresco, con guion o guion bajo y con
    o sin ceros a la izquierda en el prefijo::

        ``0020_2026000379_7083`` → ``("0020", "2026000379")``
        ``298-2026000271_2127``  → ``("298", "2026000271")``
        ``234_2026008330_2170``  → ``("234", "2026008330")``
    """
    coincidencia = re.match(r"^(\d+)[-_](\d+)", str(nombre or "").strip())
    if not coincidencia:
        return "", ""
    return coincidencia.group(1), coincidencia.group(2)


def _mismo_entero(izquierda, derecha) -> bool:
    """Compara dos valores numéricos ignorando ceros a la izquierda."""
    try:
        return int(izquierda) == int(derecha)
    except (TypeError, ValueError):
        return False


def elegir_carpeta(candidatas: list, numero: str, pad: str) -> tuple:
    """Elige la carpeta que coincide en **tipo (prefijo) y número**.

    El número de contrato no es único: se repite entre tipos (p. ej. ``298``,
    ``0018`` y ``0270`` comparten ``2026000271``). La carpeta válida es la que
    combina el prefijo del tipo con el número; nunca se elige una carpeta de
    otro tipo solo por compartir el número.

    Se prefieren las coincidencias con el prefijo tal cual (``estricto=True``);
    si solo coincide sin los ceros a la izquierda (``20`` vs ``0020``, ``298``
    vs ``0298``) se acepta como ``estricto=False``. Devuelve ``(carpeta,
    estricto)`` o ``(None, False)``.
    """
    if not numero:
        return None, False

    estricta = None
    laxa = None
    for candidata in candidatas or []:
        prefijo_carpeta, numero_carpeta = _partes_carpeta(candidata.get("nombre", ""))
        if not _mismo_entero(numero_carpeta, numero):
            continue
        if not pad:
            # Sin tipo conocido, el número basta.
            if laxa is None:
                laxa = candidata
            continue
        if prefijo_carpeta == str(pad):
            if estricta is None:
                estricta = candidata
        elif _mismo_entero(prefijo_carpeta, pad) and laxa is None:
            laxa = candidata

    if estricta is not None:
        return estricta, True
    if laxa is not None:
        return laxa, False
    return None, False


def _etapas(filas: list) -> dict:
    """Agrupa las filas por etapa en ``{etapa: (encontrados, esperados)}``."""
    conteo = {}
    for fila in filas or []:
        etapa = fila.get("ETAPA", "") or "Sin etapa"
        encontrados, esperados = conteo.get(etapa, (0, 0))
        estado = str(fila.get("ESTADO", "")).upper()
        if estado == _match.ENCONTRADO:
            conteo[etapa] = (encontrados + 1, esperados + 1)
        elif estado == _match.FALTANTE:
            conteo[etapa] = (encontrados, esperados + 1)
        else:  # NO APLICA no cuenta como esperado
            conteo[etapa] = (encontrados, esperados)
    return conteo


def _enriquecer_fechas(filas: list, archivos: list) -> list:
    """Agrega ``FECHA CREACIÓN/CARGA`` y ``ÚLTIMA MODIFICACIÓN`` a cada fila."""
    por_nombre = {archivo.get("NOMBRE", ""): archivo for archivo in archivos or []}
    for fila in filas:
        nombres = [n.strip() for n in str(fila.get("ARCHIVO", "")).split("|") if n.strip()]
        fechas_creacion = []
        fechas_mod = []
        for nombre in nombres:
            archivo = por_nombre.get(nombre)
            if archivo:
                if archivo.get("FECHA_CREACION"):
                    fechas_creacion.append(str(archivo["FECHA_CREACION"]))
                if archivo.get("FECHA_MODIFICACION"):
                    fechas_mod.append(str(archivo["FECHA_MODIFICACION"]))
        fila["FECHA CREACIÓN/CARGA"] = " | ".join(fechas_creacion)
        fila["ÚLTIMA MODIFICACIÓN"] = " | ".join(fechas_mod)
    return filas


def _fila_verificacion(contrato, nombre, uaa, serie, subserie, encontrado, motivo, cantidad, descripcion):
    return {
        "NOMBRE EXPEDIENTE": nombre,
        "UAA": uaa,
        "SERIE": serie,
        "SUB-SERIE": subserie,
        "alfresco": "SI" if encontrado else "NO",
        "cantidad_archivos": cantidad,
        "MOTIVO": motivo,
        "EXPEDIENTE_ENCONTRADO": "SI" if encontrado else "NO",
        "DESCRIPCION": descripcion,
    }


def verificar_contrato(
    contrato: dict,
    gateway,
    obligatorios: list,
    es_tipo_18: bool = False,
    max_archivos: int = 100,
) -> dict:
    """Verifica un contrato y devuelve su resultado completo.

    ``contrato`` es un dict con al menos ``contrato`` (código) y, opcionalmente,
    ``contratista``, ``uaa``, ``serie``, ``subserie``, ``carpeta`` y ``node_id``
    (si ya se conocen). ``obligatorios`` son los documentos exigidos por clase.
    """
    codigo = contrato.get("contrato", "")
    numero, pad = numero_y_pad(codigo)
    uaa = contrato.get("uaa", "")
    serie = contrato.get("serie", "")
    subserie = contrato.get("subserie", "")

    nombre = contrato.get("carpeta", "")
    node_id = contrato.get("node_id", "")
    estricto = True
    descripcion = ""

    if not node_id:
        candidatas = gateway.buscar_carpetas(numero, max_items=25) if numero else []
        carpeta, estricto = elegir_carpeta(candidatas, numero, pad)
        if carpeta is None:
            filas = _enriquecer_fechas(
                _match.evaluar_contrato([], obligatorios, es_tipo_18)["filas"], []
            )
            return _resultado(
                contrato, f"{pad}_{numero}" if pad else numero, "", False,
                MOTIVO_CARPETA, 0, filas,
                "No se encontró carpeta en Alfresco para el número de contrato.",
            )
        node_id = carpeta.get("id", "")
        nombre = carpeta.get("nombre", "")
        if not estricto:
            descripcion = f"Encontrada por número sin pad estricto ('{nombre}')."

    listado = gateway.listar_archivos(node_id, max_items=max_archivos)
    archivos = listado.get("archivos", [])
    total = int(listado.get("total", len(archivos)) or len(archivos))

    encontrado = total > 0
    if not encontrado:
        filas = _enriquecer_fechas(
            _match.evaluar_contrato(archivos, obligatorios, es_tipo_18)["filas"], archivos
        )
        return _resultado(
            contrato, nombre, node_id, False, MOTIVO_EXPEDIENTE, 0, filas,
            descripcion or "La carpeta existe pero no contiene archivos.",
        )

    evaluacion = _match.evaluar_contrato(archivos, obligatorios, es_tipo_18)
    filas = _enriquecer_fechas(evaluacion["filas"], archivos)

    return _resultado(
        contrato, nombre, node_id, True, MOTIVO_OK, total, filas, descripcion,
    )


def _resultado(contrato, nombre, node_id, encontrado, motivo, cantidad, filas, descripcion):
    """Ensambla el dict de resultado (workbook + fila 06)."""
    codigo = contrato.get("contrato", "")
    esperados = sum(1 for f in filas if str(f.get("ESTADO", "")).upper() != _match.NO_APLICA)
    encontrados = sum(1 for f in filas if str(f.get("ESTADO", "")).upper() == _match.ENCONTRADO)
    faltantes = sum(1 for f in filas if str(f.get("ESTADO", "")).upper() == _match.FALTANTE)
    pct = round(encontrados * 100 / esperados, 1) if esperados else 0.0

    fila_ver = _fila_verificacion(
        contrato,
        nombre,
        contrato.get("uaa", ""),
        contrato.get("serie", ""),
        contrato.get("subserie", ""),
        encontrado,
        motivo,
        cantidad,
        descripcion,
    )

    return {
        "contrato": codigo,
        "contratista": contrato.get("contratista", ""),
        "tipo": contrato.get("tipo", ""),
        "carpeta": nombre,
        "node_id": node_id,
        "estado_alfresco": "ENCONTRADA" if encontrado else "NO SE EVIDENCIA",
        "cantidad_archivos": cantidad,
        "filas": filas,
        "etapas": _etapas(filas),
        "esperados": esperados,
        "encontrados": encontrados,
        "faltantes": faltantes,
        "pct_cumpl": pct,
        "verificacion": fila_ver,
    }


def resultado_error(
    contrato: dict,
    obligatorios: list,
    es_tipo_18: bool = False,
    motivo: str = MOTIVO_ERROR,
    descripcion: str = "",
) -> dict:
    """Resultado de un contrato que falló al consultar Alfresco.

    Marca todos los documentos como faltantes para no perder la fila del
    contrato en el reporte, y deja el motivo para diagnóstico.
    """
    filas = _match.evaluar_contrato([], obligatorios, es_tipo_18)["filas"]
    numero, pad = numero_y_pad(contrato.get("contrato", ""))
    nombre = f"{pad}_{numero}" if pad else numero
    return _resultado(contrato, nombre, "", False, motivo, 0, filas, descripcion)

