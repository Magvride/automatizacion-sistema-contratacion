# -*- coding: utf-8 -*-
"""Componentes básicos: tarjetas, encabezados, insignias y barras de progreso."""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from desktop import icons, theme


def repolish(widget: QWidget) -> None:
    """Fuerza la reevaluación de la QSS tras cambiar una propiedad dinámica."""
    widget.style().unpolish(widget)
    widget.style().polish(widget)


class Card(QFrame):
    """Contenedor blanco con borde y esquinas redondeadas."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Card")


class CardHead(QFrame):
    """Encabezado de tarjeta con título y texto de ayuda."""

    def __init__(self, titulo: str, hint: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("CardHead")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(8)

        self.titulo = QLabel(titulo)
        self.titulo.setObjectName("CardTitle")
        self.hint = QLabel(hint)
        self.hint.setObjectName("CardHint")

        layout.addWidget(self.titulo)
        layout.addStretch(1)
        layout.addWidget(self.hint)

    def set_hint(self, texto: str) -> None:
        self.hint.setText(texto)


class Pill(QFrame):
    """Insignia de estado con punto de color y texto."""

    TEXTOS = {
        "pending": "En cola",
        "running": "En proceso",
        "done": "Completado",
        "error": "Error",
    }

    def __init__(self, estado: str = "pending", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Pill")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(9, 3, 9, 3)
        layout.setSpacing(5)

        self._punto = QLabel()
        self._punto.setFixedSize(6, 6)
        self._texto = QLabel()
        self._texto.setObjectName("PillText")

        layout.addWidget(self._punto)
        layout.addWidget(self._texto)
        self.set_estado(estado)

    def set_estado(self, estado: str, texto: str | None = None) -> None:
        _, _, color_punto = theme.COLORES_ESTADO.get(estado, theme.COLORES_ESTADO["pending"])
        self.setProperty("estado", estado)
        self._texto.setProperty("estado", estado)
        self._texto.setText(texto if texto is not None else self.TEXTOS.get(estado, estado))
        self._punto.setStyleSheet(f"background:{color_punto}; border-radius:3px;")
        repolish(self)
        repolish(self._texto)


class IconBadge(QFrame):
    """Cuadro redondeado con un icono cuyo color depende del estado."""

    ICONOS = {
        "pending": icons.DOT,
        "running": icons.CLOCK,
        "done": icons.CHECK,
        "error": icons.ALERT,
    }

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("SourceIcon")
        self.setFixedSize(26, 26)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._icono = QLabel()
        self._icono.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._icono)
        self.set_estado("pending")

    def set_estado(self, estado: str) -> None:
        fondo, color, _ = theme.COLORES_ESTADO.get(estado, theme.COLORES_ESTADO["pending"])
        svg = self.ICONOS.get(estado, icons.DOT)
        self._icono.setPixmap(icons.svg_pixmap(svg, 14, color))
        self.setStyleSheet(f"#SourceIcon {{ background:{fondo}; border-radius:7px; }}")


class ProgressBar(QFrame):
    """Barra de progreso plana (pista + relleno) con color según estado."""

    COLORES = {
        "pending": theme.INK_FAINT,
        "running": theme.INFO,
        "done": theme.OK,
        "error": theme.ERR,
    }

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ProgressTrack")
        self.setFixedHeight(5)
        self._fill = QFrame(self)
        self._fill.setObjectName("ProgressFill")
        self._valor = 0
        self._estado = "pending"
        self.set_progreso(0, "pending")

    def set_progreso(self, valor: int, estado: str) -> None:
        self._valor = max(0, min(100, int(valor)))
        self._estado = estado
        if estado == "pending":
            color = "rgba(146, 156, 170, 0.30)"
        else:
            color = self.COLORES.get(estado, theme.INK_FAINT)
        self._fill.setStyleSheet(f"#ProgressFill {{ background: {color}; border-radius: 3px; }}")
        self._recolocar()

    def _recolocar(self) -> None:
        ancho = self.width()
        if ancho <= 0:
            return
        pct = 100 if self._estado == "pending" else self._valor
        self._fill.setGeometry(0, 0, int(ancho * pct / 100), self.height())

    def resizeEvent(self, event):  # noqa: N802, D102
        super().resizeEvent(event)
        self._recolocar()


class StatusChip(QFrame):
    """Pastilla blanca del encabezado con punto de estado y texto."""

    def __init__(self, texto: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("StatusChip")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 7, 12, 7)
        layout.setSpacing(7)

        self._dot = QLabel()
        self._dot.setFixedSize(7, 7)
        self._texto = QLabel(texto)
        self._texto.setObjectName("StatusChipText")

        layout.addWidget(self._dot)
        layout.addWidget(self._texto)
        self.set_estado("pending")

    def set_texto(self, texto: str) -> None:
        self._texto.setText(texto)

    def set_estado(self, estado: str) -> None:
        _, _, color = theme.COLORES_ESTADO.get(estado, theme.COLORES_ESTADO["pending"])
        self._dot.setStyleSheet(f"background:{color}; border-radius:3px;")
