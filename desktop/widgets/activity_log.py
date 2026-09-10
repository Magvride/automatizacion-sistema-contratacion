# -*- coding: utf-8 -*-
"""Sección colapsable de registro de actividad en tiempo real."""

from datetime import datetime

from PyQt6.QtCore import QSize, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QTransform
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from desktop import icons, theme
from desktop.widgets.components import Card

_NIVELES = {
    "ok": (theme.OK, theme.OK_SOFT, icons.CHECK),
    "info": (theme.INFO, theme.INFO_SOFT, icons.DOT),
    "warn": (theme.WARN, theme.WARN_SOFT, icons.ALERT),
    "err": (theme.ERR, theme.ERR_SOFT, icons.CLOSE),
}


def _clasificar(nivel: str, mensaje: str) -> str:
    nivel = (nivel or "").upper()
    if nivel in ("ERROR", "CRITICAL"):
        return "err"
    if nivel in ("WARNING", "STDERR"):
        return "warn"
    texto = mensaje.lower()
    if any(p in texto for p in ("completado", "finalizado", "finalizada", "correctamente", "éxito")):
        return "ok"
    return "info"


class _ClickableFrame(QFrame):
    """Marco que emite ``clicked`` al pulsarlo con el botón izquierdo."""

    clicked = pyqtSignal()

    def mousePressEvent(self, event):  # noqa: N802, D102
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


class ActivityLog(Card):
    """Lista de eventos con marca de tiempo; colapsada por defecto."""

    descargar = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._abierto = False
        self._eventos = 0
        self._max_entradas = 500
        self._widgets: list[tuple[QWidget, QWidget]] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        layout.addWidget(self._crear_toggle())
        layout.addWidget(self._crear_cuerpo())

    # ------------------------------------------------------------------
    def _crear_toggle(self) -> QFrame:
        toggle = _ClickableFrame()
        toggle.setObjectName("LogToggle")
        toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        toggle.clicked.connect(self.alternar)

        fila = QHBoxLayout(toggle)
        fila.setContentsMargins(18, 12, 18, 12)
        fila.setSpacing(9)

        titulo = QLabel("Registro de actividad")
        titulo.setObjectName("LogTitle")
        self.lbl_conteo = QLabel("0 eventos")
        self.lbl_conteo.setObjectName("LogCount")

        self.btn_descargar = QPushButton()
        self.btn_descargar.setObjectName("IconButton")
        self.btn_descargar.setIcon(icons.svg_icon(icons.DOWNLOAD, 13, theme.INK_SOFT))
        self.btn_descargar.setIconSize(QSize(13, 13))
        self.btn_descargar.setToolTip("Descargar registro completo")
        self.btn_descargar.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_descargar.clicked.connect(self.descargar.emit)

        self.lbl_chevron = QLabel()
        self.lbl_chevron.setPixmap(icons.svg_pixmap(icons.CHEVRON, 16, theme.INK_FAINT))

        fila.addWidget(titulo)
        fila.addWidget(self.lbl_conteo)
        fila.addStretch(1)
        fila.addWidget(self.btn_descargar)
        fila.addWidget(self.lbl_chevron)
        return toggle

    def _crear_cuerpo(self) -> QScrollArea:
        self.scroll = QScrollArea()
        self.scroll.setObjectName("LogBody")
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setFixedHeight(260)

        contenedor = QWidget()
        self._contenedor_layout = QVBoxLayout(contenedor)
        self._contenedor_layout.setContentsMargins(0, 0, 0, 0)
        self._contenedor_layout.setSpacing(0)
        self._contenedor_layout.addStretch(1)
        self.scroll.setWidget(contenedor)
        self.scroll.setVisible(False)
        return self.scroll

    # ------------------------------------------------------------------
    def alternar(self) -> None:
        self._abierto = not self._abierto
        self.scroll.setVisible(self._abierto)
        rotada = (
            QTransform().rotate(180) if self._abierto else QTransform()
        )
        self.lbl_chevron.setPixmap(
            icons.svg_pixmap(icons.CHEVRON, 16, theme.INK_FAINT).transformed(rotada)
        )

    def agregar(self, nivel: str, mensaje: str, sub: str = "") -> None:
        tipo = _clasificar(nivel, mensaje)
        color, fondo, svg = _NIVELES[tipo]
        hora = datetime.now().strftime("%H:%M:%S")

        entrada = QFrame()
        fila = QHBoxLayout(entrada)
        fila.setContentsMargins(18, 10, 18, 10)
        fila.setSpacing(10)

        lbl_hora = QLabel(hora)
        lbl_hora.setObjectName("LogEntryTime")
        lbl_hora.setFixedWidth(66)

        lbl_punto = QLabel()
        lbl_punto.setFixedSize(16, 16)
        lbl_punto.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_punto.setPixmap(icons.svg_pixmap(svg, 10, color))
        lbl_punto.setStyleSheet(f"background:{fondo}; border-radius:8px;")

        textos = QWidget()
        textos_layout = QVBoxLayout(textos)
        textos_layout.setContentsMargins(0, 0, 0, 0)
        textos_layout.setSpacing(1)
        lbl_texto = QLabel(mensaje)
        lbl_texto.setObjectName("LogEntryText")
        lbl_texto.setWordWrap(True)
        textos_layout.addWidget(lbl_texto)
        if sub:
            lbl_sub = QLabel(sub)
            lbl_sub.setObjectName("LogEntrySub")
            lbl_sub.setWordWrap(True)
            textos_layout.addWidget(lbl_sub)

        fila.addWidget(lbl_hora)
        fila.addWidget(lbl_punto, alignment=Qt.AlignmentFlag.AlignTop)
        fila.addWidget(textos, 1)

        separador = QFrame()
        separador.setObjectName("LogSeparator")

        # Inserta antes del stretch final.
        indice = self._contenedor_layout.count() - 1
        self._contenedor_layout.insertWidget(indice, entrada)
        self._contenedor_layout.insertWidget(indice + 1, separador)
        self._widgets.append((entrada, separador))

        self._eventos += 1
        self.lbl_conteo.setText(f"{self._eventos} eventos")
        self._podar()
        QTimer.singleShot(0, self._desplazar_abajo)

    def _podar(self) -> None:
        while len(self._widgets) > self._max_entradas:
            entrada, separador = self._widgets.pop(0)
            entrada.deleteLater()
            separador.deleteLater()

    def _desplazar_abajo(self) -> None:
        barra = self.scroll.verticalScrollBar()
        barra.setValue(barra.maximum())

    def limpiar(self) -> None:
        for entrada, separador in self._widgets:
            entrada.deleteLater()
            separador.deleteLater()
        self._widgets.clear()
        self._eventos = 0
        self.lbl_conteo.setText("0 eventos")

    def total(self) -> int:
        return self._eventos
