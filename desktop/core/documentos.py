# -*- coding: utf-8 -*-
"""Documentos de entrada que el usuario carga manualmente.

Reemplaza la extracción automática (login a "nuevas versiones" y scraping de
UISARD): el usuario selecciona 4 archivos Excel y aquí se copian a las carpetas
que el pipeline existente ya consume.

* **Nuevas versiones** → ``archivos/01_Contratos_Descargados/contratos_*.xlsx``
  (lo usa ``seguimiento_p2``).
* **Convenios / Contratos / Proyectos** → ``archivos/04_Contratos_Descargados_UISARD/``
  (los usa ``conciliacion_datos``).
"""

import logging
import os
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

logger = logging.getLogger("app")


@dataclass(frozen=True)
class DocumentoEntrada:
    """Descripción de un archivo que el usuario debe cargar."""

    id: str
    nombre: str
    descripcion: str
    carpeta: Path
    plantilla_destino: str
    patron_limpieza: str
    extensiones: tuple

    @property
    def filtro(self) -> str:
        if self.extensiones == (".xlsx",):
            return "Excel (*.xlsx)"
        return "Excel/CSV (*.xlsx *.xls *.csv)"


_DOCUMENTOS: tuple[DocumentoEntrada, ...] | None = None


def documentos() -> tuple[DocumentoEntrada, ...]:
    """Devuelve la lista de documentos de entrada (resuelve rutas perezosamente)."""
    global _DOCUMENTOS
    if _DOCUMENTOS is None:
        from config import CONTRATOS_DIR, REPORTES_DIR

        _DOCUMENTOS = (
            DocumentoEntrada(
                "nuevas_versiones",
                "Excel de nuevas versiones",
                "Reporte financiero descargado de la plataforma",
                CONTRATOS_DIR,
                "contratos_{fecha}{ext}",
                "contratos_*.xlsx",
                (".xlsx",),
            ),
            DocumentoEntrada(
                "convenios",
                "Reporte de convenios",
                "Serie Convenios de UISARD",
                REPORTES_DIR,
                "convenio_reporte_{fecha}{ext}",
                "convenio_reporte_*",
                (".xlsx", ".xls", ".csv"),
            ),
            DocumentoEntrada(
                "contratos",
                "Reporte de contratos",
                "Serie Contratos de UISARD",
                REPORTES_DIR,
                "contrato_reporte_{fecha}{ext}",
                "contrato_reporte_*",
                (".xlsx", ".xls", ".csv"),
            ),
            DocumentoEntrada(
                "proyectos",
                "Reporte de proyectos",
                "Serie Proyectos de UISARD",
                REPORTES_DIR,
                "proyecto_reporte_{fecha}{ext}",
                "proyecto_reporte_*",
                (".xlsx", ".xls", ".csv"),
            ),
        )
    return _DOCUMENTOS


def por_id(doc_id: str) -> DocumentoEntrada | None:
    for documento in documentos():
        if documento.id == doc_id:
            return documento
    return None


def preparar_entradas(rutas: dict) -> list:
    """Copia los archivos seleccionados a las carpetas de trabajo del pipeline.

    Limpia antes los archivos previos del mismo tipo para no mezclar ejecuciones.
    Devuelve la lista de rutas destino. Lanza excepción si falta algún archivo.
    """
    fecha = datetime.now().strftime("%Y%m%d_%H%M%S")
    copiados = []

    for documento in documentos():
        origen = rutas.get(documento.id, "")
        if not origen or not os.path.isfile(origen):
            raise FileNotFoundError(
                f"No se seleccionó el archivo requerido: {documento.nombre}."
            )

        ext = os.path.splitext(origen)[1].lower()
        if ext not in documento.extensiones:
            permitidas = "/".join(documento.extensiones)
            raise ValueError(
                f"'{documento.nombre}' debe tener formato {permitidas} (recibido '{ext}')."
            )

        documento.carpeta.mkdir(parents=True, exist_ok=True)
        for anterior in documento.carpeta.glob(documento.patron_limpieza):
            try:
                anterior.unlink()
            except OSError:
                pass

        destino = documento.carpeta / documento.plantilla_destino.format(
            fecha=fecha, ext=ext
        )
        shutil.copy2(origen, destino)
        logger.info("Documento '%s' preparado: %s", documento.nombre, destino.name)
        copiados.append(str(destino))

    return copiados
