# -*- coding: utf-8 -*-
"""Puente entre el módulo ``logging`` del backend y las señales Qt.

Los módulos del flujo (``main``, ``uisard_extractor``, ``alfresco_extractor``...)
escriben con ``logging``. Al arrancar la interfaz se **reemplazan** sus handlers
por uno que:

* reenvía cada registro a la ventana mediante :class:`LogBridge` (señal segura
  entre hilos), y
* escribe el mismo registro en un archivo ``logs/ejecucion_*.log``.

También se redirigen ``stdout``/``stderr`` para que los ``print()`` del backend
aparezcan en el registro de actividad.
"""

import logging
import os
import sys
from datetime import datetime

from PyQt6.QtCore import QObject, pyqtSignal

# Nombres de los loggers que usa el backend.
LOGGERS_BACKEND = (
    "main",
    "uisard",
    "conciliacion",
    "alfresco",
    "notificacion",
    "unificacion",
    "limpieza",
    "uisard_alfresco",
    "onedrive",
    "app",
)


class LogBridge(QObject):
    """Objeto Qt que transporta registros de log hacia la interfaz."""

    registro = pyqtSignal(str, str)  # (nivel, mensaje)


class QtLogHandler(logging.Handler):
    """Handler que escribe a archivo y emite el registro a la interfaz."""

    def __init__(self, bridge: LogBridge, log_dir: str, level: int = logging.INFO) -> None:
        super().__init__(level=level)
        self._bridge = bridge
        os.makedirs(log_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self._archivo = os.path.join(log_dir, f"ejecucion_{timestamp}.log")
        self._fh = open(self._archivo, "a", encoding="utf-8")
        self._fmt_archivo = logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(module)s:%(lineno)d | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        self._fmt_gui = logging.Formatter("%(message)s")

    def emit(self, record: logging.LogRecord) -> None:  # noqa: D102
        try:
            self._fh.write(self._fmt_archivo.format(record) + "\n")
            self._fh.flush()
        except OSError:
            pass
        try:
            self._bridge.registro.emit(record.levelname, self._fmt_gui.format(record))
        except Exception:  # pragma: no cover - defensivo
            pass

    def close(self) -> None:  # noqa: D102
        try:
            self._fh.close()
        except OSError:
            pass
        super().close()


class _WriterQt:
    """Sustituto de ``sys.stdout``/``sys.stderr`` que emite líneas a la GUI."""

    def __init__(self, bridge: LogBridge, nivel: str) -> None:
        self._bridge = bridge
        self._nivel = nivel
        self._buf = ""

    def write(self, texto: str) -> int:
        if not texto:
            return 0
        self._buf += texto
        while "\n" in self._buf:
            linea, self._buf = self._buf.split("\n", 1)
            if linea.strip():
                self._bridge.registro.emit(self._nivel, linea)
        return len(texto)

    def flush(self) -> None:
        if self._buf.strip():
            self._bridge.registro.emit(self._nivel, self._buf)
        self._buf = ""

    def isatty(self) -> bool:
        return False


def instalar_handler(bridge: LogBridge, log_dir: str | None = None) -> QtLogHandler:
    """Reemplaza los handlers del backend por el handler Qt.

    Debe llamarse **antes** de importar/ejecutar el backend para que
    ``configurar_logger`` no añada sus propios handlers de consola.
    """
    if log_dir is None:
        from desktop.paths import BASE_DIR

        log_dir = os.path.join(BASE_DIR, "logs")

    handler = QtLogHandler(bridge, log_dir)
    for nombre in LOGGERS_BACKEND:
        logger = logging.getLogger(nombre)
        logger.handlers = [handler]
        logger.setLevel(logging.DEBUG)
        logger.propagate = False

    sys.stdout = _WriterQt(bridge, "STDOUT")
    sys.stderr = _WriterQt(bridge, "STDERR")
    return handler
