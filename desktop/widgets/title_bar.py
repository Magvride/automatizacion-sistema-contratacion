# -*- coding: utf-8 -*-
"""Barra de título personalizada con controles de ventana y arrastre."""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QWidget,
)

from desktop import icons, theme


class TitleBar(QFrame):
    """Cabecera verde de la ventana (ventana sin marco nativo)."""

    def __init__(self, ventana: QWidget, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("TitleBar")
        self._ventana = ventana
        self._arrastrando = False
        self._offset = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 0, 10, 0)
        layout.setSpacing(8)

        icono = QLabel()
        icono.setObjectName("TitleBarIcon")
        icono.setPixmap(icons.svg_pixmap(icons.SYNC, 14, "#DCEAE7"))
        titulo = QLabel("Sistema Automatizado de Contrataciones")
        titulo.setObjectName("TitleBarText")
        layout.addWidget(icono)
        layout.addWidget(titulo)
        layout.addStretch(1)

        self.btn_minimizar = self._boton(icons.MINIMIZE, "Minimizar", self._minimizar)
        self.btn_maximizar = self._boton(icons.MAXIMIZE, "Maximizar", self._alternar_max)
        self.btn_cerrar = self._boton(icons.CLOSE, "Cerrar", self._cerrar, cierre=True)
        layout.addWidget(self.btn_minimizar)
        layout.addWidget(self.btn_maximizar)
        layout.addWidget(self.btn_cerrar)

        self.setMouseTracking(True)

    # ------------------------------------------------------------------
    def _boton(self, svg: str, tip: str, slot, cierre: bool = False) -> QPushButton:
        boton = QPushButton()
        boton.setObjectName("WinClose" if cierre else "WinButton")
        boton.setIcon(icons.svg_icon(svg, 12, "#DCEAE7"))
        boton.setToolTip(tip)
        boton.setCursor(Qt.CursorShape.PointingHandCursor)
        boton.setFlat(True)
        boton.clicked.connect(slot)
        return boton

    def _minimizar(self) -> None:
        self._ventana.showMinimized()

    def _cerrar(self) -> None:
        self._ventana.close()

    def _alternar_max(self) -> None:
        if self._ventana.isMaximized():
            self._ventana.showNormal()
        else:
            self._ventana.showMaximized()
        self.actualizar_icono_max()

    def actualizar_icono_max(self) -> None:
        svg = icons.RESTORE if self._ventana.isMaximized() else icons.MAXIMIZE
        self.btn_maximizar.setIcon(icons.svg_icon(svg, 12, "#DCEAE7"))

    # ------------------------------------------------------------------
    # Arrastre de la ventana sin marco
    # ------------------------------------------------------------------
    def mousePressEvent(self, event):  # noqa: N802, D102
        if event.button() == Qt.MouseButton.LeftButton:
            self._arrastrando = True
            self._offset = event.globalPosition().toPoint() - self._ventana.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):  # noqa: N802, D102
        if self._arrastrando and self._offset is not None and not self._ventana.isMaximized():
            self._ventana.move(event.globalPosition().toPoint() - self._offset)
            event.accept()

    def mouseReleaseEvent(self, event):  # noqa: N802, D102
        self._arrastrando = False
        self._offset = None
        event.accept()

    def mouseDoubleClickEvent(self, event):  # noqa: N802, D102
        self._alternar_max()
        event.accept()
