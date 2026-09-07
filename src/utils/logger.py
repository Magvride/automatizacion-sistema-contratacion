import logging
import os
import sys
from datetime import datetime

_log_dir = None
_archivo_log = None
_file_handler = None


def _directorio_logs() -> str:
    if getattr(sys, "frozen", False):
        return os.path.join(os.path.dirname(os.path.abspath(sys.executable)), "logs")
    return os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "logs"
    )


def _obtener_file_handler():
    """Crea un único FileHandler compartido por toda la ejecución.

    Así, vayan main, uisard, conciliacion, alfresco o limpieza, todos los
    módulos escriben en el mismo archivo log de esa corrida.
    """
    global _log_dir, _archivo_log, _file_handler
    if _file_handler is not None:
        return _file_handler

    _log_dir = _directorio_logs()
    os.makedirs(_log_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    _archivo_log = os.path.join(_log_dir, f"ejecucion_{timestamp}.log")

    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(module)s:%(lineno)d | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    _file_handler = logging.FileHandler(_archivo_log, encoding="utf-8")
    _file_handler.setLevel(logging.DEBUG)
    _file_handler.setFormatter(fmt)
    return _file_handler


def configurar_logger(nombre: str = "uisard_alfresco") -> logging.Logger:
    logger = logging.getLogger(nombre)
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)
    logger.addHandler(_obtener_file_handler())
    logger.propagate = False

    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(_file_handler.formatter)
    logger.addHandler(ch)
    return logger
