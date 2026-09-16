# -*- coding: utf-8 -*-
"""
Motor de auditoría documental (orquesta diccionario + Alfresco + salidas).

Toma los contratos del consolidado 02 (solo nuevas versiones), resuelve su
carpeta en Alfresco, evalúa los documentos obligatorios del diccionario y
genera:

* ``06_Verificacion_Alfresco.csv`` / ``07_Expedientes_Faltantes.csv``
  (esquema histórico, para las fases de merge/reportes/notificación).
* ``Auditoria_Contratos.xlsx`` (entregable detallado).

El transporte se inyecta (``gateway``), por lo que el motor es testeable con un
doble de prueba. La verificación se puede ejecutar en paralelo (varios hilos),
lo que reduce mucho el tiempo total cuando hay muchos contratos.
"""

import os
import re
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

from utils.logger import configurar_logger
from auditoria_documental.diccionario import (
    cargar_diccionario,
    clase_de_contrato,
    obligatorios_por_clase,
)
from auditoria_documental.workbook import generar_auditoria
from .verifier import resultado_error, verificar_contrato
from .writer import escribir_verificacion

logger = configurar_logger("auditoria_motor")

# Claves opcionales del consolidado que se copian al Excel si están presentes.
_CLAVES_EXTRA = (
    "contratista", "tipo", "valor", "total_pagado", "fecha_contrato",
    "fecha_inicio", "fecha_fin", "duracion", "estado_contrato", "unidad",
    "modalidad", "objeto", "centro_costo", "ordenador", "correo_ordenador",
    "correos_apoyo",
    "contrato_id", "req", "rep", "pct", "faltan", "num_pagos", "coincide_matriz",
)

# Códigos de los actos de pago usados para estimar el número de pagos.
_CODIGOS_PAGO = ("fco62", "fco69", "fco74")

# Hilos por defecto para la verificación (configurable con ALFRESCO_WORKERS).
WORKERS_POR_DEFECTO = 4


def _contar_pagos(resultado: dict) -> int:
    """Estima el número de pagos por los actos de pago hallados (FCO.62/69/74)."""
    vistos = set()
    for fila in resultado.get("filas") or []:
        if str(fila.get("ESTADO", "")).upper() != "ENCONTRADO":
            continue
        archivo = str(fila.get("ARCHIVO", ""))
        limpio = re.sub(r"[^a-z0-9]", "", archivo.lower())
        if any(codigo in limpio for codigo in _CODIGOS_PAGO):
            vistos.add(archivo)
    return len(vistos)


def _a_dicts(contratos) -> list:
    """Acepta un DataFrame o una lista de dicts y devuelve una lista de dicts."""
    if contratos is None:
        return []
    if hasattr(contratos, "to_dict"):
        return contratos.to_dict("records")
    return list(contratos)


def _enriquecer(resultado: dict, fila: dict) -> dict:
    for clave in _CLAVES_EXTRA:
        valor = fila.get(clave)
        if valor not in (None, "") and not resultado.get(clave):
            resultado[clave] = valor

    if not resultado.get("supervisor"):
        resultado["supervisor"] = fila.get("ordenador", "")
    if not resultado.get("centro_costo"):
        resultado["centro_costo"] = fila.get("centro_costo", "")
    if not resultado.get("num_pagos"):
        resultado["num_pagos"] = _contar_pagos(resultado)
    return resultado


def _procesar(fila, gateway, diccionario, contratistas, max_archivos):
    """Verifica un contrato y devuelve su resultado enriquecido (o None)."""
    codigo = str(fila.get("contrato", "")).strip()
    if not codigo:
        return None

    contratista = contratistas.get(codigo, fila.get("contratista", ""))
    clase = clase_de_contrato(codigo, contratista)
    obligatorios = obligatorios_por_clase(diccionario, clase)
    if not obligatorios:
        logger.warning(
            "El contrato '%s' tiene clase '%s', pero esa clase no está configurada en el diccionario.",
            codigo,
            clase,
        )

    try:
        resultado = verificar_contrato(
            {"contrato": codigo, "contratista": contratista},
            gateway,
            obligatorios,
            es_tipo_18=clase.startswith("18"),
            max_archivos=max_archivos,
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("Fallo verificando '%s': %s", codigo, exc)
        resultado = resultado_error(
            {"contrato": codigo, "contratista": contratista},
            obligatorios,
            es_tipo_18=clase.startswith("18"),
            descripcion=f"Error al consultar Alfresco: {exc}",
        )

    resultado["cod"] = clase
    if not obligatorios:
        resultado["observacion"] = (
            f"La clase {clase} no tiene documentos obligatorios configurados en el diccionario. "
            "Revisar la configuración antes de concluir la auditoría."
        )
    return _enriquecer(resultado, fila)


def _ejecutar_secuencial(filas, gateway, diccionario, contratistas, max_archivos, on_progreso, on_resultado):
    def emitir(callback, *args):
        if not callback:
            return
        try:
            callback(*args)
        except Exception as exc:  # noqa: BLE001 - un callback no debe abortar la auditoría
            logger.error("Error en callback de auditoría: %s", exc, exc_info=True)

    resultados = []
    total = len(filas)
    for indice, fila in enumerate(filas, start=1):
        resultado = _procesar(fila, gateway, diccionario, contratistas, max_archivos)
        if resultado is None:
            continue
        resultados.append(resultado)
        emitir(on_resultado, resultado)
        emitir(on_progreso, indice, total)
    return resultados


def _ejecutar_paralelo(filas, gateway, diccionario, contratistas, max_archivos, workers, on_progreso, on_resultado):
    """Verifica en paralelo con un gateway (sesión) por hilo.

    Conserva el orden de los resultados y reporta progreso de forma segura.
    """
    resultados = [None] * len(filas)
    total = len(filas)
    completados = 0
    lock = threading.Lock()
    local = threading.local()
    creados = []

    def tarea(indice, fila):
        try:
            gw = getattr(local, "gateway", None)
            if gw is None:
                gw = gateway.clonar()
                local.gateway = gw
                with lock:
                    creados.append(gw)
            return indice, _procesar(fila, gw, diccionario, contratistas, max_archivos)
        except Exception as exc:  # noqa: BLE001 - un contrato fallido no detiene los demás
            codigo = str(fila.get("contrato", "")).strip()
            logger.error("Fallo preparando la consulta de '%s': %s", codigo, exc, exc_info=True)
            clase = clase_de_contrato(codigo, fila.get("contratista", ""))
            resultado = resultado_error(
                {"contrato": codigo, "contratista": fila.get("contratista", "")},
                obligatorios_por_clase(diccionario, clase),
                es_tipo_18=clase.startswith("18"),
                descripcion=f"Error al preparar la consulta de Alfresco: {exc}",
            )
            return indice, _enriquecer(resultado, fila)

    def emitir(callback, *args):
        if not callback:
            return
        try:
            callback(*args)
        except Exception as exc:  # noqa: BLE001 - un callback no debe abortar la auditoría
            logger.error("Error en callback de auditoría: %s", exc, exc_info=True)

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futuros = {executor.submit(tarea, i, f): i for i, f in enumerate(filas)}
        for futuro in as_completed(futuros):
            indice, resultado = futuro.result()
            if resultado is None:
                continue
            resultados[indice] = resultado
            with lock:
                completados += 1
                emitir(on_resultado, resultado)
                emitir(on_progreso, completados, total)

    for gw in creados:
        try:
            gw.cerrar()
        except Exception:  # noqa: BLE001
            pass
    return [r for r in resultados if r is not None]


def ejecutar_auditoria(
    contratos,
    gateway,
    ruta_diccionario: str,
    ruta_06: str,
    ruta_07: str,
    ruta_09: str,
    periodo: str = "",
    fecha_revision: str = "",
    contratistas: dict = None,
    max_archivos: int = 100,
    max_workers: int = None,
    on_progreso=None,
    on_resultado=None,
) -> dict:
    """Ejecuta la auditoría completa y devuelve un resumen.

    ``contratos`` puede ser un DataFrame o una lista de dicts con al menos
    ``contrato``. ``contratistas`` permite inyectar el nombre del contratista
    (necesario para inferir ``18 PN`` vs ``18 PJ``) cuando el consolidado no lo
    trae. ``on_progreso(hechos, total)`` se invoca tras cada contrato y
    ``on_resultado(resultado)`` recibe cada resultado ya enriquecido.

    Con ``max_workers > 1`` (o la variable ``ALFRESCO_WORKERS``) la verificación
    se ejecuta en paralelo usando una sesión por hilo.
    """
    diccionario = cargar_diccionario(ruta_diccionario)["diccionario"]
    filas = _a_dicts(contratos)
    contratistas = contratistas or {}

    if max_workers is None:
        try:
            max_workers = int(os.getenv("ALFRESCO_WORKERS", str(WORKERS_POR_DEFECTO)) or WORKERS_POR_DEFECTO)
        except ValueError:
            max_workers = WORKERS_POR_DEFECTO

    if max_workers > 1 and hasattr(gateway, "clonar"):
        logger.info("Verificación en paralelo con %d hilos.", max_workers)
        resultados = _ejecutar_paralelo(
            filas, gateway, diccionario, contratistas, max_archivos, max_workers,
            on_progreso, on_resultado,
        )
    else:
        resultados = _ejecutar_secuencial(
            filas, gateway, diccionario, contratistas, max_archivos,
            on_progreso, on_resultado,
        )

    resumen_ver = escribir_verificacion(resultados, ruta_06, ruta_07)
    generar_auditoria(resultados, ruta_09, periodo=periodo, fecha_revision=fecha_revision)

    resumen = {
        "total": len(resultados),
        "encontradas": sum(1 for r in resultados if r.get("estado_alfresco") == "ENCONTRADA"),
        "no_encontradas": sum(1 for r in resultados if r.get("estado_alfresco") != "ENCONTRADA"),
        "ruta_06": ruta_06,
        "ruta_07": ruta_07,
        "ruta_09": ruta_09,
        "verificacion": resumen_ver,
    }
    logger.info(
        "Auditoría completada: %d contratos | %d encontradas | %d no encontradas -> %s",
        resumen["total"], resumen["encontradas"], resumen["no_encontradas"], ruta_09,
    )
    return resumen
