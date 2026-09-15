# -*- coding: utf-8 -*-
"""Punto de entrada de la aplicación de escritorio (PyQt6)."""

import sys
import logging
import traceback

from desktop import paths  # noqa: F401  (configura sys.path antes del backend)
from desktop.paths import icono_app


def _excepcion_no_controlada(tipo, valor, traza) -> None:
    """Registra errores de callbacks Qt sin cerrar silenciosamente la GUI."""
    detalle = "".join(traceback.format_exception(tipo, valor, traza))
    logging.getLogger("app").critical("Excepción no controlada en la interfaz:\n%s", detalle)

    # PyQt llama a sys.excepthook para errores ocurridos dentro de señales.
    # Mostrar el error aquí evita que la aplicación desaparezca sin contexto.
    try:
        from PyQt6.QtWidgets import QMessageBox

        QMessageBox.critical(
            None,
            "Error de la aplicación",
            f"La operación no pudo completarse:\n\n{valor}\n\n"
            "El detalle quedó guardado en la carpeta logs.",
        )
    except Exception:
        # El hook no debe generar una segunda excepción.
        pass


def main() -> int:
    sys.excepthook = _excepcion_no_controlada
    from PyQt6.QtGui import QFont, QIcon
    from PyQt6.QtWidgets import QApplication

    from desktop import theme
    from desktop.widgets.main_window import MainWindow

    app = QApplication(sys.argv)
    app.setApplicationName("Contrataciones ETL")
    app.setApplicationDisplayName("Sistema Automatizado de Contrataciones")
    app.setOrganizationName("UIS")
    app.setWindowIcon(QIcon(icono_app()))
    app.setFont(QFont(theme.FUENTE_UI, 10))
    app.setStyleSheet(theme.hoja_estilos())

    ventana = MainWindow()
    ventana.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
