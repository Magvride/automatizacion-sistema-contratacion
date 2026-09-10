# -*- coding: utf-8 -*-
"""Punto de entrada de la aplicación de escritorio (PyQt6)."""

import sys

from desktop import paths  # noqa: F401  (configura sys.path antes del backend)
from desktop.paths import icono_app


def main() -> int:
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
