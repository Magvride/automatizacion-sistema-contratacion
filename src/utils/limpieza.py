# -*- coding: utf-8 -*-
"""
Purga automática de archivos generados por el flujo.

Se conservan solo los N más recientes de cada tipo (según fecha de modificación)
y se eliminan los más antiguos. Esto evita que las carpetas del proyecto
(screenshots, diagnóstico, logs y reportes) crezcan sin límite.
"""

import glob
import os
import shutil
import sys
import time
from datetime import datetime, date

if not getattr(sys, "frozen", False):
    _SRC_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _SRC_DIR not in sys.path:
        sys.path.insert(0, _SRC_DIR)

from utils.logger import configurar_logger
from config import INTERNO_DIR, REPORTES_DIR, RESULTADOS_DIR

logger = configurar_logger("limpieza")

# Entregables que se conservan en la carpeta de resultados.
ENTREGABLES = {"Auditoria_Contratos.xlsx", "Informe_Auditoria_Contrato.html"}

# (carpeta_relativa, patrón_glob, mantener, descripción)
REGLAS = [
    ("logs", "ejecucion_*.log", 5, "logs de ejecución"),
    ("logs/diagnostico", "*.html", 10, "HTML de diagnóstico"),
    ("logs/screenshots", "*.png", 10, "capturas de pantalla"),
]


def _es_de_hoy(ruta: str) -> bool:
    """True si el archivo corresponde a la fecha de hoy (por nombre DD-MM-YYYY o por mtime)."""
    nombre = os.path.basename(ruta)
    if datetime.now().strftime("%d-%m-%Y") in nombre:
        return True
    try:
        if date.fromtimestamp(os.path.getmtime(ruta)) == date.today():
            return True
    except OSError:
        pass
    return False


def _purgar_por_patron(base_dir: str, carpeta: str, patron: str, mantener: int, conservar_hoy: bool = False) -> int:
    """Elimina los archivos de ``carpeta/patron`` conservando los ``mantener`` más recientes.

    Con ``conservar_hoy=True``, los archivos generados hoy (validación del día)
    jamás se eliminan. Devuelve el número de archivos eliminados.
    """
    ruta_carpeta = os.path.join(base_dir, carpeta)
    if not os.path.isdir(ruta_carpeta):
        return 0

    archivos = [
        f for f in glob.glob(os.path.join(ruta_carpeta, patron))
        if os.path.isfile(f)
    ]
    if conservar_hoy:
        archivos = [f for f in archivos if not _es_de_hoy(f)]
    if len(archivos) <= mantener:
        return 0

    # Más recientes primero.
    archivos.sort(key=lambda f: os.path.getmtime(f), reverse=True)

    eliminados = 0
    for f in archivos[mantener:]:
        try:
            os.remove(f)
            eliminados += 1
            logger.info("Purgado (antiguo): %s", os.path.relpath(f, base_dir))
        except OSError as exc:
            logger.warning("No se pudo eliminar %s: %s", f, exc)
    return eliminados


def limpiar(base_dir: str, serie: str = None) -> dict:
    """Ejecuta la purga sobre todas las reglas (y reportes por serie si se indica).

    ``serie`` permite purgar también los reportes por serie de ``archivos/04_Contratos_Descargados_UISARD/``
    conservando los 3 más recientes por cada tipo (contrato/convenio/proyecto).
    Devuelve un resumen {descripción: eliminados}.
    """
    resumen = {}

    for carpeta, patron, mantener, descripcion in REGLAS:
        resumen[descripcion] = _purgar_por_patron(base_dir, carpeta, patron, mantener)

    if serie:
        for prefijo in ("contrato", "convenio", "proyecto"):
            n = _purgar_por_patron(
                base_dir,
                os.path.relpath(REPORTES_DIR, base_dir),
                f"{prefijo}_reporte_*.xlsx",
                3,
                conservar_hoy=True,
            )
            resumen[f"reportes {prefijo}"] = n

    total = sum(resumen.values())
    logger.info("Limpieza finalizada: %d archivos purgados (%s).", total, ", ".join(f"{k}={v}" for k, v in resumen.items()))
    return resumen


def limpiar_salidas(base_dir: str = None) -> dict:
    """Deja limpia la entrega: vacía ``_interno`` y conserva solo los entregables.

    Se llama al finalizar cada ejecución para que no se acumulen archivos de
    sesiones pasadas. En ``archivos/05_Datos_filtrados`` solo se conservan
    ``Auditoria_Contratos.xlsx`` e ``Informe_Auditoria_Contrato.html``.
    """
    eliminados = 0

    if INTERNO_DIR.is_dir():
        for ruta in INTERNO_DIR.iterdir():
            if ruta.name == ".gitkeep":
                continue
            try:
                if ruta.is_dir():
                    shutil.rmtree(ruta)
                else:
                    ruta.unlink()
                eliminados += 1
            except OSError as exc:
                logger.warning("No se pudo eliminar %s: %s", ruta, exc)

    if RESULTADOS_DIR.is_dir():
        for ruta in RESULTADOS_DIR.iterdir():
            if not ruta.is_file() or ruta.name in ENTREGABLES or ruta.name == ".gitkeep":
                continue
            try:
                ruta.unlink()
                eliminados += 1
            except OSError as exc:
                logger.warning("No se pudo eliminar %s: %s", ruta, exc)

    logger.info("Salidas limpiadas: %d archivos eliminados.", eliminados)
    return {"eliminados": eliminados}


if __name__ == "__main__":
    base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    print(limpiar(base, serie=True))
