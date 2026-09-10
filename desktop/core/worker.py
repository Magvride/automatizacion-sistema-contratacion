# -*- coding: utf-8 -*-
"""Hilos de trabajo (``QThread``) para ejecutar el ETL sin bloquear la interfaz."""

import builtins
import logging
import threading

from PyQt6.QtCore import QThread, pyqtSignal

from desktop.core.pipeline import EtlPipeline, Interrumpido

logger = logging.getLogger("app")


class PipelineWorker(QThread):
    """Ejecuta :class:`EtlPipeline` en segundo plano y emite su progreso.

    Señales
    -------
    etapa_actualizada(id, estado, pct, detalle)
        Cambio de estado de una fuente (``pending``/``running``/``done``/``error``).
    progreso_global(completadas, total)
        Número de etapas completadas.
    pausa_requerida(prompt)
        El backend espera una confirmación manual (p. ej. captcha).
    finalizado(exito, mensaje)
        El proceso terminó (con o sin error).
    """

    etapa_actualizada = pyqtSignal(str, str, int, str)
    progreso_global = pyqtSignal(int, int)
    pausa_requerida = pyqtSignal(str)
    finalizado = pyqtSignal(bool, str)

    def __init__(self, documentos: dict, parent=None) -> None:
        super().__init__(parent)
        self.documentos = documentos
        self._evento_input = threading.Event()
        self._texto_input = ""
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # API para la interfaz
    # ------------------------------------------------------------------
    def continuar(self, texto: str = "") -> None:
        """Desbloquea una espera de ``input()`` del backend."""
        with self._lock:
            self._texto_input = texto
        self._evento_input.set()

    # ------------------------------------------------------------------
    # Hilo
    # ------------------------------------------------------------------
    def _input_desde_gui(self, prompt: str = "") -> str:
        if prompt:
            self.pausa_requerida.emit(str(prompt))
        while not self._evento_input.wait(0.1):
            if self.isInterruptionRequested():
                raise KeyboardInterrupt
        with self._lock:
            texto = self._texto_input
            self._texto_input = ""
        self._evento_input.clear()
        return texto

    def run(self) -> None:  # noqa: D102
        original_input = builtins.input
        builtins.input = self._input_desde_gui
        pipeline = EtlPipeline(
            self.documentos,
            on_etapa=lambda *args: self.etapa_actualizada.emit(*args),
            on_progreso=lambda *args: self.progreso_global.emit(*args),
            cancelado=self.isInterruptionRequested,
        )
        try:
            pipeline.ejecutar()
        except Interrumpido:
            logger.warning("Proceso detenido por el usuario.")
            self.finalizado.emit(False, "Proceso detenido por el usuario.")
        except Exception as exc:  # noqa: BLE001
            logger.error("El proceso terminó con error: %s", exc)
            self.finalizado.emit(False, str(exc))
        else:
            self.finalizado.emit(True, "Proceso finalizado correctamente.")
        finally:
            builtins.input = original_input


class OneDriveWorker(QThread):
    """Copia la matriz actualizada a OneDrive sin congelar la interfaz."""

    finalizado = pyqtSignal(bool, str)

    def run(self) -> None:  # noqa: D102
        try:
            from onedrive_subida import subir_a_onedrive

            destino = subir_a_onedrive()
        except Exception as exc:  # noqa: BLE001
            logger.error("Error al subir a OneDrive: %s", exc)
            self.finalizado.emit(False, str(exc))
        else:
            logger.info("Matriz copiada a OneDrive: %s", destino)
            self.finalizado.emit(True, f"Matriz copiada a {destino}")
