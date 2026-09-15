# -*- coding: utf-8 -*-
"""Barra lateral de navegación."""

from PyQt6.QtCore import QSize, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from desktop import icons, theme
from desktop import __version__

ITEMS = (
    ("Panel de ejecución", icons.PANEL),
    ("Resultados", icons.RESULTS),
    ("Documentos de entrada", icons.DATABASE),
    ("Configuración", icons.GEAR),
)


class Sidebar(QFrame):
    """Navegación principal; emite el índice de la página seleccionada."""

    navegacion = pyqtSignal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Sidebar")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 20, 12, 12)
        layout.setSpacing(2)

        # --- Marca ---
        marca = QWidget()
        marca_layout = QVBoxLayout(marca)
        marca_layout.setContentsMargins(10, 0, 10, 18)
        marca_layout.setSpacing(3)
        titulo = QLabel("Contrataciones ETL")
        titulo.setObjectName("Brand")
        subtitulo = QLabel("Automatización de descargas")
        subtitulo.setObjectName("BrandSub")
        marca_layout.addWidget(titulo)
        marca_layout.addWidget(subtitulo)
        layout.addWidget(marca)

        # --- Navegación ---
        self._grupo = QButtonGroup(self)
        self._grupo.setExclusive(True)
        for indice, (texto, svg) in enumerate(ITEMS):
            boton = QPushButton(texto)
            boton.setObjectName("NavItem")
            boton.setCheckable(True)
            boton.setCursor(Qt.CursorShape.PointingHandCursor)
            boton.setIcon(icons.svg_icon(svg, 15, theme.SIDEBAR_TEXT))
            boton.setIconSize(QSize(15, 15))
            boton.clicked.connect(lambda _checked, i=indice: self.navegacion.emit(i))
            self._grupo.addButton(boton, indice)
            layout.addWidget(boton)
        self._grupo.button(0).setChecked(True)

        layout.addStretch(1)

        # --- Pie ---
        pie = QLabel(
            f"<b>v{__version__}</b><br>Extracción manual de reportes.<br>"
            "Conciliación, verificación y notificación automatizadas."
        )
        pie.setObjectName("NavFooter")
        pie.setWordWrap(True)
        layout.addWidget(pie)

    def seleccionar(self, indice: int) -> None:
        boton = self._grupo.button(indice)
        if boton:
            boton.setChecked(True)
