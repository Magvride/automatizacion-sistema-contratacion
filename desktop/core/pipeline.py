# -*- coding: utf-8 -*-
"""Orquestación del flujo ETL a partir de documentos cargados manualmente.

La extracción automática (login a "nuevas versiones" y scraping de UISARD) se
reemplaza por la carga manual de 4 archivos Excel. A partir de ellos se ejecuta
el mismo pipeline de conciliación y verificación, hasta generar los borradores
de correo:

1. **Nuevas versiones** — ``seguimiento_p2`` actualiza la matriz y exporta los
   contratos normalizados.
2. **UISARD** — conciliación de los reportes de convenios/contratos/proyectos y
   unificación por número de contrato.
3. **Alfresco** — verificación de expedientes e incorporación de resultados.
4. **Notificación** — borradores de correo a los ordenadores de gasto.

Cada etapa reporta su avance mediante callbacks para que la interfaz nunca se
bloquee (el pipeline corre en un :class:`~desktop.core.worker.PipelineWorker`).
"""

import logging
import os
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Callable

from desktop.core import documentos as documentos_mod

logger = logging.getLogger("app")


@dataclass(frozen=True)
class Etapa:
    """Metadatos de una etapa del pipeline."""

    id: str
    nombre: str
    descripcion: str


ETAPAS = (
    Etapa("base", "Nuevas versiones", "Matriz de seguimiento y contratos normalizados"),
    Etapa("uisard", "UISARD", "Conciliación y unificación de reportes"),
    Etapa("alfresco", "Alfresco", "Verificación de expedientes"),
    Etapa("notificacion", "Notificación", "Borradores de correo a ordenadores"),
)


class Interrumpido(Exception):
    """Se lanza cuando el usuario solicita detener el proceso."""


class EtlPipeline:
    """Ejecuta el flujo completo reportando el estado de cada etapa."""

    def __init__(
        self,
        documentos: dict,
        on_etapa: Callable[[str, str, int, str], None],
        on_progreso: Callable[[int, int], None],
        cancelado: Callable[[], bool] = lambda: False,
    ) -> None:
        self.documentos = documentos
        self._on_etapa = on_etapa
        self._on_progreso = on_progreso
        self._cancelado = cancelado
        self._completadas = 0

    # ------------------------------------------------------------------
    # Utilidades internas
    # ------------------------------------------------------------------
    def _emitir(self, etapa_id: str, estado: str, pct: int, detalle: str = "") -> None:
        self._on_etapa(etapa_id, estado, pct, detalle)

    def _check(self) -> None:
        if self._cancelado():
            raise Interrumpido()

    def _args(self) -> SimpleNamespace:
        return SimpleNamespace(
            skip_financiero=True,
            skip_uisard=False,
            skip_alfresco=False,
            ruta_consolidado=None,
            lento=False,
            no_zip=False,
            enviar_correos=False,
            no_notificar=False,
            ruta_unificado=None,
            reporte_nuevas=None,
        )

    @staticmethod
    def _contar_filas(ruta) -> int:
        try:
            with open(ruta, "r", encoding="utf-8-sig") as fh:
                return max(sum(1 for _ in fh) - 1, 0)
        except OSError:
            return 0

    # ------------------------------------------------------------------
    # Etapas
    # ------------------------------------------------------------------
    def _base(self, args, salidas) -> dict:
        import src.seguimiento_p2 as seguimiento_p2
        from config import EXTRACCION_DIR

        self._emitir("base", "running", 20, "Actualizando matriz de seguimiento…")
        seguimiento_p2.main()
        self._check()

        self._emitir("base", "running", 90, "Exportando contratos normalizados…")
        registros = self._contar_filas(
            os.path.join(str(EXTRACCION_DIR), "contratos_normalizados.csv")
        )
        return {"registros": registros, "detalle": f"{registros} contratos nuevos"}

    def _uisard(self, args, salidas) -> dict:
        import main

        self._emitir("uisard", "running", 30, "Conciliando reportes de UISARD…")
        df = main.fase_conciliacion(args, salidas)
        self._check()

        self._emitir("uisard", "running", 75, "Unificando por número de contrato…")
        main.fase_unificacion(args, salidas, df)

        registros = self._contar_filas(salidas.get("csv"))
        return {"registros": registros, "detalle": f"{registros} registros"}

    def _alfresco(self, args, salidas) -> dict:
        import main
        from config import RESULTADOS_DIR

        self._emitir("alfresco", "running", 15, "Verificando expedientes en Alfresco…")
        main.fase_alfresco(args, salidas)
        self._check()

        self._emitir("alfresco", "running", 80, "Incorporando resultados al consolidado…")
        main.fase_merge_alfresco(args, salidas)

        ruta = os.path.join(str(RESULTADOS_DIR), "verificacion_alfresco.csv")
        registros = self._contar_filas(ruta)
        return {"registros": registros, "detalle": f"{registros} expedientes"}

    def _notificacion(self, args, salidas) -> dict:
        import main

        self._emitir("notificacion", "running", 50, "Generando borradores de correo…")
        main.fase_notificacion(args, salidas)
        return {"registros": 0, "detalle": "Borradores generados"}

    # ------------------------------------------------------------------
    # Punto de entrada
    # ------------------------------------------------------------------
    def ejecutar(self) -> None:
        """Ejecuta todas las etapas. Lanza excepción si alguna falla."""
        from config import preparar_directorios
        import main

        preparar_directorios()
        salidas = main.construir_salidas(main.BASE_DIR)
        args = self._args()

        logger.info("Preparando documentos de entrada…")
        documentos_mod.preparar_entradas(self.documentos)

        for etapa in ETAPAS:
            self._check()
            self._emitir(etapa.id, "running", 1, "En proceso…")
            try:
                resumen = getattr(self, f"_{etapa.id}")(args, salidas)
            except Interrumpido:
                self._emitir(etapa.id, "error", 0, "Cancelado por el usuario")
                logger.warning("Etapa '%s' cancelada por el usuario.", etapa.nombre)
                raise
            except SystemExit as exc:
                codigo = exc.code if isinstance(exc.code, int) else 1
                self._emitir(etapa.id, "error", 0, f"Abortado (código {codigo})")
                raise RuntimeError(
                    f"La etapa '{etapa.nombre}' abortó el proceso (código {codigo})."
                ) from exc
            except Exception as exc:  # noqa: BLE001 - se reemite con contexto
                self._emitir(etapa.id, "error", 0, str(exc))
                logger.error("Error en la etapa '%s': %s", etapa.nombre, exc, exc_info=True)
                raise

            self._emitir(etapa.id, "done", 100, resumen.get("detalle", "Completado"))
            self._completadas += 1
            self._on_progreso(self._completadas, len(ETAPAS))

        logger.info("Proceso completo: todas las etapas finalizaron.")
