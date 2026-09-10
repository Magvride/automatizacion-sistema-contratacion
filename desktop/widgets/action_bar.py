# -*- coding: utf-8 -*-
"""Barra de acciones: iniciar, detener, continuar y subir a OneDrive."""

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
        self.btn_continuar = self._boton(
            "Continuar", "OutlineButton", icons.CONTINUE, theme.INK
        )
        self.btn_continuar.setEnabled(False)
        self.btn_onedrive = self._boton(
            "Subir a OneDrive", "SecondaryButton", icons.UPLOAD, "#FFFFFF"
        )

        fila.addWidget(self.btn_iniciar)
        fila.addWidget(self.btn_detener)
        fila.addWidget(self.btn_continuar)
        fila.addStretch(1)
        fila.addWidget(self.btn_onedrive)

        nota = QWidget()
        nota_layout = QHBoxLayout(nota)
        nota_layout.setContentsMargins(0, 0, 0, 0)
        nota_layout.setSpacing(6)
        icono = QLabel()
        icono.setPixmap(icons.svg_pixmap(icons.CLOCK, 13, theme.INK_FAINT))
        texto = QLabel("Carga manual de reportes · verificación automática")
        texto.setObjectName("ScheduleNote")
        nota_layout.addWidget(icono)
        nota_layout.addWidget(texto)
        fila.addWidget(nota)

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
        self.btn_continuar.setEnabled(en_ejecucion)
        self.btn_onedrive.setEnabled(not en_ejecucion)
