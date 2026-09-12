# -*- coding: utf-8 -*-
"""Auditoría documental de expedientes contra el diccionario de documentos.

Reimplementa la lógica del proyecto de referencia ``documentacion_contratos``:
dado el listado real de archivos de una carpeta de Alfresco y los documentos
obligatorios que exige el diccionario, determina por documento si está
``ENCONTRADO``, ``FALTANTE`` o ``NO APLICA``.

Submódulos:
    match       — normalización y reglas de coincidencia (puro, testeable).
    diccionario — carga del diccionario/etapas y clases de contrato.
    workbook    — plantilla Excel de salida (Resumen + etapas + granular).
"""

from .match import (  # noqa: F401
    evaluar_contrato,
    match_documento,
    normalize,
)
