# -*- coding: utf-8 -*-
"""Barra mínima de acciones del proceso."""

from PyQt6.QtCore import QSize, Qt
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from desktop import icons, theme
from desktop.widgets.components import Card


class ActionBar(Card):
    """Botones de control del proceso."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 14, 18, 14)

        fila = QHBoxLayout()
        fila.setSpacing(10)

        self.btn_iniciar = self._boton(
            "Iniciar proceso", "PrimaryButton", icons.PLAY, "#FFFFFF"
        )
        self.btn_detener = self._boton(
            "Detener", "OutlineButton", icons.STOP, theme.INK
        )
        self.btn_detener.setEnabled(False)

        fila.addWidget(self.btn_iniciar)
        fila.addWidget(self.btn_detener)
        fila.addStretch(1)

        layout.addLayout(fila)

    def _boton(self, texto: str, object_name: str, svg: str, color: str) -> QPushButton:
        boton = QPushButton(texto)
        boton.setObjectName(object_name)
        boton.setIcon(icons.svg_icon(svg, 14, color))
        boton.setIconSize(QSize(14, 14))
        boton.setCursor(Qt.CursorShape.PointingHandCursor)
        return boton

    def set_en_ejecucion(self, en_ejecucion: bool) -> None:
        self.btn_iniciar.setEnabled(not en_ejecucion)
        self.btn_detener.setEnabled(en_ejecucion)
