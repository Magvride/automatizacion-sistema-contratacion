# -*- coding: utf-8 -*-
"""Orquestación del flujo ETL a partir de documentos cargados manualmente.

La extracción automática (login a "nuevas versiones" y scraping de UISARD) se
reemplaza por la carga manual de 2 archivos Excel. A partir de ellos se ejecuta
el pipeline de consolidación, verificación en Alfresco (API REST) y auditoría
documental, hasta generar los borradores de correo:

1. **Nuevas versiones** — prepara el Excel recibido.
2. **Corroborar correos** — cruza cada ordenador con su correo.
3. **Corroborar Alfresco** — verifica expedientes y documentos obligatorios.
4. **Mandar correos** — envía los avisos a los ordenadores.

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
    Etapa("base", "Nuevas versiones", "Carga y lectura del Excel recibido"),
    Etapa("consolidar", "Corroborar correos", "Cruce con la tabla de ordenadores"),
    Etapa("alfresco", "Corroborar Alfresco", "Verificación de expedientes y documentos"),
    Etapa("notificacion", "Mandar correos", "Avisos a los ordenadores responsables"),
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
        on_contrato: Callable[[int, int, str], None] = lambda *_: None,
        cancelado: Callable[[], bool] = lambda: False,
        demo: bool = False,
    ) -> None:
        self.documentos = documentos
        self._on_etapa = on_etapa
        self._on_progreso = on_progreso
        self._on_contrato = on_contrato
        self._cancelado = cancelado
        self._completadas = 0
        self.demo = demo

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
            backend_alfresco="mcp",
            ruta_diccionario=None,
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
        from src.consolidar import construir_consolidado_desde_excel

        if self.demo:
            raise RuntimeError("El modo demo ya no está disponible.")
        self._emitir("base", "running", 40, "Leyendo el Excel recibido…")
        resultado = construir_consolidado_desde_excel(
            self.documentos.get("nuevas_versiones", ""), salidas["verificacion"]
        )
        if not resultado.get("encontrado"):
            raise RuntimeError("El Excel no contiene contratos reconocibles.")
        return {"registros": resultado["total"], "detalle": f"{resultado['total']} contratos cargados"}

    @staticmethod
    def _consolidado_demo():
        """Consolidado 02 de ejemplo para el modo demo."""
        import pandas as pd

        from alfresco_mcp.demo import CONTRATOS_DEMO
        from consolidar import COLUMNAS_CONSOLIDADO

        columnas = COLUMNAS_CONSOLIDADO + ["contratista"]
        filas = []
        for contrato in CONTRATOS_DEMO:
            fila = {columna: "" for columna in columnas}
            fila["contrato"] = contrato["contrato"]
            fila["centro_costo"] = contrato.get("centro_costo", "")
            fila["ordenador"] = contrato.get("ordenador", "")
            fila["contratista"] = contrato.get("contratista", "")
            fila["origen"] = "DEMO"
            filas.append(fila)
        return pd.DataFrame(filas, columns=columnas).astype(str)

    def _consolidar(self, args, salidas) -> dict:
        registros = self._contar_filas(salidas.get("verificacion"))
        self._emitir("consolidar", "running", 100, f"{registros} correos corroborados")
        return {"registros": registros, "detalle": f"{registros} contratos con correo cruzado"}

    def _alfresco_demo(self, args, salidas) -> dict:
        """Verificación simulada (sin Alfresco) para el modo demo."""
        import pandas as pd

        import main
        from alfresco_mcp.demo import GatewayDemo, carpetas_demo
        from alfresco_mcp.motor import ejecutar_auditoria
        from auditoria_documental.correos import generar_borradores
        from auditoria_documental.diccionario import cargar_diccionario
        from auditoria_documental.informe_html import generar_informe

        diccionario = cargar_diccionario()["diccionario"]
        interno = salidas.get("interno") or salidas["carpeta"]
        ruta_consolidado = salidas["verificacion"]
        cons = pd.read_csv(ruta_consolidado, encoding="utf-8-sig", dtype=str).fillna("")
        ruta_06 = os.path.join(interno, "06_Verificacion_Alfresco.csv")
        ruta_07 = salidas.get("faltantes") or os.path.join(
            interno, "07_Expedientes_Faltantes.csv"
        )
        ruta_09 = salidas.get("auditoria") or os.path.join(
            salidas["carpeta"], "Auditoria_Contratos.xlsx"
        )

        self._emitir("alfresco", "running", 40, "Verificando expedientes (Alfresco simulado)…")
        resultados = []
        ejecutar_auditoria(
            cons,
            GatewayDemo(carpetas_demo(diccionario)),
            ruta_diccionario="",
            ruta_06=ruta_06,
            ruta_07=ruta_07,
            ruta_09=ruta_09,
            periodo="DEMO",
            on_resultado=resultados.append,
        )
        self._check()

        self._emitir("alfresco", "running", 80, "Generando informe y borradores…")
        main._consolidado_enriquecido(cons, resultados).to_csv(
            ruta_consolidado, index=False, encoding="utf-8-sig"
        )

        ruta_correos = salidas.get("correos_auditoria") or os.path.join(
            interno, "10_Correos_Auditoria.txt"
        )
        generar_borradores(resultados, ruta_correos)

        ruta_informe = salidas.get("informe") or os.path.join(
            salidas["carpeta"], "Informe_Auditoria_Contrato.html"
        )
        generar_informe(resultados, ruta_informe, periodo="DEMO")

        return {
            "registros": len(resultados),
            "detalle": f"{len(resultados)} expedientes (demo)",
        }

    def _alfresco(self, args, salidas) -> dict:
        import main

        if self.demo:
            raise RuntimeError("El modo demo ya no está disponible.")

        self._emitir("alfresco", "running", 15, "Verificando expedientes en Alfresco (REST)…")
        main.fase_alfresco_mcp(
            args,
            salidas,
            on_progreso=lambda hechos, total: self._on_contrato(
                hechos, total, f"Verificando contrato {hechos}/{total}"
            ),
        )
        self._check()

        interno = salidas.get("interno") or salidas["carpeta"]
        ruta = os.path.join(interno, "06_Verificacion_Alfresco.csv")
        registros = self._contar_filas(ruta)
        return {"registros": registros, "detalle": f"{registros} expedientes"}

    def _notificacion(self, args, salidas) -> dict:
        # El envío es una acción manual posterior a la revisión del reporte.
        # La interfaz de Resultados construye los mensajes y solicita autorización.
        self._emitir("notificacion", "running", 100, "Borradores de correo listos…")
        return {"registros": 0, "detalle": "Borradores generados; envío pendiente de autorización"}

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
        if not self.demo:
            copiados = documentos_mod.preparar_entradas(self.documentos)
            # La preparación convierte .xls a .xlsx; las etapas siguientes deben
            # leer la copia normalizada y no la ruta original seleccionada.
            if copiados and "nuevas_versiones" in self.documentos:
                self.documentos["nuevas_versiones"] = copiados[0]

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
