# -*- coding: utf-8 -*-
"""Documento Excel que el usuario carga como entrada del flujo."""

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
        patrones = " ".join(f"*{ext}" for ext in self.extensiones)
        return f"Excel ({patrones})"


_DOCUMENTOS: tuple[DocumentoEntrada, ...] | None = None


def documentos() -> tuple[DocumentoEntrada, ...]:
    """Devuelve la lista de documentos de entrada (resuelve rutas perezosamente)."""
    global _DOCUMENTOS
    if _DOCUMENTOS is None:
        from config import CONTRATOS_DIR, MATRIZ_MANUAL_DIR

        _DOCUMENTOS = (
            DocumentoEntrada(
                "nuevas_versiones",
                "Excel de nuevas versiones",
                "Reporte financiero con las incorporaciones del día (.xlsx o .xls)",
                CONTRATOS_DIR,
                "contratos_{fecha}{ext}",
                "contratos_*",
                (".xlsx", ".xls"),
            ),
            DocumentoEntrada(
                "ordenadores",
                "Excel de ordenadores",
                "Ordenadores de gasto con correo y correos de apoyo (.xlsx)",
                MATRIZ_MANUAL_DIR,
                "Ordenadores_{fecha}.xlsx",
                "Ordenadores_20*",
                (".xlsx",),
            ),
        )
    return _DOCUMENTOS


def por_id(doc_id: str) -> DocumentoEntrada | None:
    for documento in documentos():
        if documento.id == doc_id:
            return documento
    return None


def _convertir_xls_a_xlsx(origen: str, destino: Path) -> None:
    """Convierte un Excel antiguo (.xls) a .xlsx usando Excel (COM).

    ``openpyxl`` no puede leer el formato binario ``.xls``, así que se normaliza
    a ``.xlsx`` al preparar las entradas. Requiere Microsoft Excel instalado
    (ya es requisito del flujo por el recálculo COM de ``seguimiento_p2``).
    """
    try:
        import win32com.client  # type: ignore
    except ImportError as exc:  # noqa: BLE001
        raise RuntimeError(
            "No se pudo convertir el archivo .xls a .xlsx porque falta pywin32. "
            "Guarda el reporte como .xlsx o instala pywin32."
        ) from exc

    excel = win32com.client.DispatchEx("Excel.Application")
    excel.Visible = False
    excel.DisplayAlerts = False
    try:
        libro = excel.Workbooks.Open(os.path.abspath(origen))
        # 51 = xlOpenXMLWorkbook (.xlsx)
        libro.SaveAs(str(destino), FileFormat=51)
        libro.Close(SaveChanges=False)
    finally:
        excel.Quit()
    logger.info("Convertido de .xls a .xlsx: %s", destino.name)


def preparar_entradas(rutas: dict) -> list:
    """Copia los archivos seleccionados a las carpetas de trabajo del pipeline.

    Limpia antes los archivos previos del mismo tipo para no mezclar ejecuciones.
    Los ``.xls`` se convierten automáticamente a ``.xlsx``. Devuelve la lista de
    rutas destino. Lanza excepción si falta algún archivo.
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

        origen_path = Path(origen).resolve()
        documento.carpeta.mkdir(parents=True, exist_ok=True)
        for anterior in documento.carpeta.glob(documento.patron_limpieza):
            try:
                if anterior.resolve() == origen_path:
                    continue  # no borrar el archivo que el usuario seleccionó
                anterior.unlink()
            except OSError:
                pass

        destino = documento.carpeta / documento.plantilla_destino.format(
            fecha=fecha, ext=ext
        )
        if ext == ".xls":
            destino = destino.with_suffix(".xlsx")

        if destino.resolve() == origen_path:
            # El archivo seleccionado ya está en su carpeta destino: no hay nada
            # que copiar (y borrarlo antes lo dejaría sin origen).
            logger.info(
                "Documento '%s' ya está en su carpeta: %s",
                documento.nombre, destino.name,
            )
            copiados.append(str(destino))
            continue

        if ext == ".xls":
            _convertir_xls_a_xlsx(origen, destino)
        else:
            shutil.copy2(origen, destino)
        logger.info("Documento '%s' preparado: %s", documento.nombre, destino.name)
        copiados.append(str(destino))

    return copiados
