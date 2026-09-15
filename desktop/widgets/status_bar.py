# -*- coding: utf-8 -*-
"""Barra de estado inferior: progreso global, tiempo y destino."""

from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QWidget


class _BarraGlobal(QFrame):
    """Barra de progreso global (pista + relleno)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("GlobalTrack")
        self.setFixedSize(120, 5)
        self._fill = QFrame(self)
        self._fill.setObjectName("GlobalFill")
        self._completadas = 0
        self._total = 4
        self._recolocar()

    def set_progreso(self, completadas: int, total: int) -> None:
        self._completadas = completadas
        self._total = max(total, 1)
        self._recolocar()

    def _recolocar(self) -> None:
        pct = max(0.0, min(1.0, self._completadas / self._total))
        self._fill.setGeometry(0, 0, int(self.width() * pct), self.height())

    def resizeEvent(self, event):  # noqa: N802, D102
        super().resizeEvent(event)
        self._recolocar()


class StatusBar(QFrame):
    """Franja inferior con el resumen del proceso."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("StatusBar")
        self._completadas = 0
        self._total = 4

        layout = QHBoxLayout(self)
        layout.setContentsMargins(26, 9, 26, 9)
        layout.setSpacing(22)

        # Progreso global
        item1 = QWidget()
        fila1 = QHBoxLayout(item1)
        fila1.setContentsMargins(0, 0, 0, 0)
        fila1.setSpacing(7)
        lbl = QLabel("Progreso global")
        lbl.setObjectName("StatusBarItem")
        self.barra = _BarraGlobal()
        self.lbl_fuentes = QLabel("0/4 fuentes")
        self.lbl_fuentes.setObjectName("StatusBarItem")
        fila1.addWidget(lbl)
        fila1.addWidget(self.barra)
        fila1.addWidget(self.lbl_fuentes)

        self.lbl_tiempo = QLabel("Tiempo transcurrido: 00:00:00")
        self.lbl_tiempo.setObjectName("StatusBarItem")

        layout.addWidget(item1)
        layout.addWidget(self.lbl_tiempo)
        layout.addStretch(1)

    # ------------------------------------------------------------------
    def set_progreso(self, completadas: int, total: int) -> None:
        self._completadas = completadas
        self._total = total
        self.barra.set_progreso(completadas, total)
        self.lbl_fuentes.setText(f"{completadas}/{total} fuentes")

    def set_tiempo(self, texto: str) -> None:
        self.lbl_tiempo.setText(f"Tiempo transcurrido: {texto}")

    def set_destino(self, texto: str) -> None:
        return None
