# -*- coding: utf-8 -*-
"""Ventana principal: shell con sidebar, panel dinámico y barra de estado."""

import logging
import os
import time
from datetime import datetime

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QMainWindow,
    QMessageBox,
    QScrollArea,
    QSizeGrip,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from desktop.core.documentos import documentos
from desktop.core.logging_bridge import LogBridge, instalar_handler
from desktop.core.pipeline import ETAPAS
from desktop.core.worker import PipelineWorker
from desktop.paths import BASE_DIR, icono_app
from desktop.updater_client import UpdateCheckWorker, launch_update
from desktop import __version__
from desktop.widgets.dashboard_page import DashboardPage
from desktop.widgets.pages import SourcesPage
from desktop.widgets.results_page import ResultsPage
from desktop.widgets.sidebar import Sidebar
from desktop.widgets.status_bar import StatusBar
from desktop.widgets.title_bar import TitleBar

logger = logging.getLogger("app")


def _formatear_duracion(segundos: float) -> str:
    segundos = int(max(0, segundos))
    horas, resto = divmod(segundos, 3600)
    minutos, segs = divmod(resto, 60)
    return f"{horas:02d}:{minutos:02d}:{segs:02d}"


class MainWindow(QMainWindow):
    """Aplicación principal del Sistema Automatizado de Contrataciones."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Sistema Automatizado de Contrataciones")
        self.setWindowIcon(QIcon(icono_app()))
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.Window
        )
        self.resize(1180, 760)
        self.setMinimumSize(980, 640)

        self.worker: PipelineWorker | None = None
        self._historial: list[tuple[str, str, str]] = []
        self._inicio_global = 0.0
        self._inicio_etapa = 0.0
        self._etapa_activa: str | None = None
        self._update_worker: UpdateCheckWorker | None = None

        self.bridge = LogBridge()
        self.bridge.registro.connect(self._on_log)
        instalar_handler(self.bridge)

        self._construir_ui()

        self.timer = QTimer(self)
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self._tick)

        self._on_log("INFO", "Aplicación iniciada.")

    # ------------------------------------------------------------------
    # Construcción de la interfaz
    # ------------------------------------------------------------------
    def _construir_ui(self) -> None:
        raiz = QWidget()
        raiz.setObjectName("Root")
        self.setCentralWidget(raiz)

        layout = QVBoxLayout(raiz)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.title_bar = TitleBar(self)
        self.title_bar.actualizarSolicitado.connect(self._buscar_actualizaciones)
        layout.addWidget(self.title_bar)

        cuerpo = QWidget()
        cuerpo_layout = QHBoxLayout(cuerpo)
        cuerpo_layout.setContentsMargins(0, 0, 0, 0)
        cuerpo_layout.setSpacing(0)

        self.sidebar = Sidebar()
        self.sidebar.navegacion.connect(self._cambiar_pagina)
        cuerpo_layout.addWidget(self.sidebar)

        self.stack = QStackedWidget()
        self.dashboard = DashboardPage()
        self.pagina_resultados = ResultsPage()
        self.pagina_fuentes = SourcesPage()
        for pagina in (
            self.dashboard,
            self.pagina_resultados,
            self.pagina_fuentes,
        ):
            pagina.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
            self.stack.addWidget(self._envolver_scroll(pagina))
        cuerpo_layout.addWidget(self.stack, 1)
        layout.addWidget(cuerpo, 1)

        self.status_bar = StatusBar()
        grip = QSizeGrip(self.status_bar)
        grip.setFixedSize(14, 14)
        self.status_bar.layout().addWidget(grip)
        layout.addWidget(self.status_bar)

        self._conectar_acciones()

    def _envolver_scroll(self, pagina: QWidget) -> QScrollArea:
        scroll = QScrollArea()
        scroll.setObjectName("ScrollArea")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(pagina)
        return scroll

    def _conectar_acciones(self) -> None:
        barra = self.dashboard.action_bar
        barra.btn_iniciar.clicked.connect(self._iniciar)
        barra.btn_detener.clicked.connect(self._detener)
        self.dashboard.activity_log.descargar.connect(self._descargar_log)
        self.dashboard.documents_card.cambio.connect(self._actualizar_estado_entradas)
        self._actualizar_estado_entradas()

    # ------------------------------------------------------------------
    # Navegación
    # ------------------------------------------------------------------
    def _cambiar_pagina(self, indice: int) -> None:
        self.stack.setCurrentIndex(indice)
        if indice == 1:
            self.pagina_resultados.refrescar()

    # ------------------------------------------------------------------
    # Registro / estado
    # ------------------------------------------------------------------
    def _on_log(self, nivel: str, mensaje: str) -> None:
        self._historial.append((datetime.now().strftime("%H:%M:%S"), nivel, mensaje))
        self.dashboard.activity_log.agregar(nivel, mensaje)

    # ------------------------------------------------------------------
    # Actualizaciones
    # ------------------------------------------------------------------
    def _buscar_actualizaciones(self) -> None:
        if self._update_worker is not None and self._update_worker.isRunning():
            return
        self.title_bar.btn_actualizar.setEnabled(False)
        self._on_log("INFO", f"Buscando actualizaciones (versión {__version__})...")
        self._update_worker = UpdateCheckWorker(self)
        self._update_worker.resultado.connect(self._on_actualizacion_consultada)
        self._update_worker.finished.connect(self._actualizacion_terminada)
        self._update_worker.start()

    def _on_actualizacion_consultada(self, resultado: object) -> None:
        datos = resultado if isinstance(resultado, dict) else {}
        if not datos.get("ok"):
            mensaje = str(datos.get("error", "No se pudo consultar GitHub."))
            self._on_log("ERROR", f"No se pudo buscar actualizaciones: {mensaje}")
            QMessageBox.warning(self, "Actualizaciones", mensaje)
            return

        update = datos.get("data", {})
        if not update.get("available"):
            self._on_log("INFO", "La aplicación ya está actualizada.")
            QMessageBox.information(
                self,
                "Actualizaciones",
                f"Ya tienes la versión {__version__} instalada.",
            )
            return

        version = update["version"]
        respuesta = QMessageBox.question(
            self,
            "Nueva versión disponible",
            f"Está disponible la versión {version}.\n\n"
            "La aplicación se cerrará, instalará la actualización y se abrirá de nuevo.\n\n"
            "¿Deseas actualizar ahora?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if respuesta != QMessageBox.StandardButton.Yes:
            self._on_log("INFO", "Actualización cancelada por el usuario.")
            return

        try:
            launch_update(update)
        except (OSError, RuntimeError) as exc:
            self._on_log("ERROR", f"No se pudo iniciar la actualización: {exc}")
            QMessageBox.critical(self, "Actualizaciones", str(exc))
            return
        self._on_log("INFO", f"Actualización a {version} iniciada.")
        self.close()

    def _actualizacion_terminada(self) -> None:
        self.title_bar.btn_actualizar.setEnabled(True)
        self._update_worker = None

    def _tick(self) -> None:
        if self._inicio_global:
            self.status_bar.set_tiempo(_formatear_duracion(time.monotonic() - self._inicio_global))
        if self._etapa_activa and self._inicio_etapa:
            tarjeta = self.dashboard.source_cards.get(self._etapa_activa)
            if tarjeta:
                tarjeta.set_tiempo(_formatear_duracion(time.monotonic() - self._inicio_etapa))

    # ------------------------------------------------------------------
    # Proceso principal
    # ------------------------------------------------------------------
    def _faltantes(self) -> list:
        """Nombres de los documentos que aún no están seleccionados o no existen."""
        seleccion = self.dashboard.documents_card.rutas()
        faltantes = []
        for documento in documentos():
            ruta = seleccion.get(documento.id, "")
            if not ruta or not os.path.isfile(ruta):
                faltantes.append(documento.nombre)
        return faltantes

    def _actualizar_estado_entradas(self) -> None:
        if self.worker is not None and self.worker.isRunning():
            return
        faltantes = self._faltantes()
        if not faltantes:
            self.dashboard.status_chip.set_estado("pending")
            self.dashboard.status_chip.set_texto("Listo para iniciar")
        else:
            self.dashboard.status_chip.set_estado("pending")
            self.dashboard.status_chip.set_texto(f"Faltan {len(faltantes)} archivos")

    def _iniciar(self) -> None:
        if self.worker is not None and self.worker.isRunning():
            return
        faltantes = self._faltantes()
        if faltantes:
            self._on_log(
                "ERROR",
                "Faltan documentos por cargar: " + ", ".join(faltantes) + ".",
            )
            self.dashboard.status_chip.set_estado("error")
            self.dashboard.status_chip.set_texto("Faltan archivos")
            return

        self.dashboard.reiniciar_tarjetas()
        self.dashboard.action_bar.set_en_ejecucion(True)
        self.dashboard.status_chip.set_estado("running")
        self.dashboard.status_chip.set_texto("En proceso")
        self._historial.clear()
        self.dashboard.activity_log.limpiar()

        self._inicio_global = time.monotonic()
        self._inicio_etapa = 0.0
        self._etapa_activa = None
        self.timer.start()

        self._on_log("INFO", "Proceso iniciado con los documentos cargados.")

        self.worker = PipelineWorker(
            self.dashboard.documents_card.rutas(),
            demo=False,
        )
        self.worker.etapa_actualizada.connect(self._on_etapa)
        self.worker.progreso_global.connect(self._on_progreso)
        self.worker.progreso_contrato.connect(self._on_progreso_contrato)
        self.worker.finalizado.connect(self._on_finalizado)
        self.worker.finished.connect(self._worker_terminado)
        self.worker.start()

    def _on_etapa(self, etapa_id: str, estado: str, pct: int, detalle: str) -> None:
        tarjeta = self.dashboard.source_cards.get(etapa_id)
        if tarjeta is None:
            return
        if estado == "running":
            if self._etapa_activa and self._etapa_activa != etapa_id:
                anterior = self.dashboard.source_cards.get(self._etapa_activa)
                if anterior:
                    anterior.set_tiempo(_formatear_duracion(time.monotonic() - self._inicio_etapa))
            self._etapa_activa = etapa_id
            self._inicio_etapa = time.monotonic()
            tarjeta.set_estado("running")
            tarjeta.set_progreso(pct)
            nombre = next((e.nombre for e in ETAPAS if e.id == etapa_id), etapa_id)
            self.dashboard.status_chip.set_texto(f"En proceso · {nombre}")
        elif estado == "done":
            tarjeta.set_estado("done", detalle)
            tarjeta.set_tiempo(_formatear_duracion(time.monotonic() - self._inicio_etapa))
            if self._etapa_activa == etapa_id:
                self._etapa_activa = None
        elif estado == "error":
            tarjeta.set_estado("error", detalle)
            tarjeta.set_tiempo(_formatear_duracion(time.monotonic() - self._inicio_etapa))
            if self._etapa_activa == etapa_id:
                self._etapa_activa = None
        else:
            tarjeta.set_estado(estado)

    def _on_progreso(self, completadas: int, total: int) -> None:
        self.status_bar.set_progreso(completadas, total)
        self.dashboard.sources_head.set_hint(f"{completadas} de {total} completadas")

    def _on_progreso_contrato(self, hechos: int, total: int, detalle: str) -> None:
        transcurrido = time.monotonic() - self._inicio_global if self._inicio_global else 0
        promedio = transcurrido / hechos if hechos else 0
        texto = f"Promedio por consulta: {promedio:.1f} s" if hechos else "Promedio por consulta: calculando…"
        self.dashboard.set_progreso_contratos(hechos, total, texto)
        self._on_log("INFO", detalle)

    def _on_finalizado(self, exito: bool, mensaje: str) -> None:
        self.timer.stop()
        self._etapa_activa = None
        self.dashboard.action_bar.set_en_ejecucion(False)
        self.dashboard.status_chip.set_estado("done" if exito else "error")
        self.dashboard.status_chip.set_texto("Completado" if exito else "Error")
        if self._inicio_global:
            self.status_bar.set_tiempo(_formatear_duracion(time.monotonic() - self._inicio_global))
        self._on_log("INFO" if exito else "ERROR", mensaje)
        if exito:
            self.pagina_resultados.refrescar()

    def _worker_terminado(self) -> None:
        self.worker = None

    def _detener(self) -> None:
        if self.worker is not None and self.worker.isRunning():
            self.worker.requestInterruption()
            self.worker.continuar("")
            self._on_log("WARNING", "Detención solicitada por el usuario…")

    # ------------------------------------------------------------------
    # Registro completo
    # ------------------------------------------------------------------
    def _descargar_log(self) -> None:
        ruta, _ = QFileDialog.getSaveFileName(
            self,
            "Guardar registro de actividad",
            os.path.join(BASE_DIR, f"registro_actividad_{datetime.now():%Y%m%d_%H%M%S}.txt"),
            "Texto (*.txt);;Todos los archivos (*.*)",
        )
        if not ruta:
            return
        try:
            with open(ruta, "w", encoding="utf-8") as fh:
                for hora, nivel, mensaje in self._historial:
                    fh.write(f"{hora} | {nivel:<8} | {mensaje}\n")
        except OSError as exc:
            self._on_log("ERROR", f"No se pudo guardar el registro: {exc}")
            return
        self._on_log("INFO", f"Registro guardado en {ruta}")

    # ------------------------------------------------------------------
    def closeEvent(self, event):  # noqa: N802, D102
        for hilo in (self.worker,):
            if hilo is not None and hilo.isRunning():
                hilo.requestInterruption()
                if hasattr(hilo, "continuar"):
                    hilo.continuar("")
                if not hilo.wait(3000):
                    hilo.terminate()
                    hilo.wait(1000)
        event.accept()
