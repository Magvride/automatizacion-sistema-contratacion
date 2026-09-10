# -*- coding: utf-8 -*-
"""Tarjeta individual de una fuente de datos (etapa del pipeline)."""

from PyQt6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from desktop.core.pipeline import Etapa
from desktop.widgets.components import Card, IconBadge, Pill, ProgressBar


class SourceCard(Card):
    """Muestra el estado, progreso y métricas de una fuente/etapa."""

    def __init__(self, etapa: Etapa, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("SourceCard")
        self.etapa = etapa
        self._pct = 0
        self._estado = "pending"

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        # --- Fila superior: icono + nombre + insignia ---
        fila = QHBoxLayout()
        fila.setSpacing(9)
        self.badge = IconBadge()
        self.nombre = QLabel(etapa.nombre)
        self.nombre.setObjectName("SourceName")
        self.pill = Pill("pending")

        fila.addWidget(self.badge)
        fila.addWidget(self.nombre)
        fila.addStretch(1)
        fila.addWidget(self.pill)
        layout.addLayout(fila)

        # --- Barra de progreso ---
        self.progress = ProgressBar()
        layout.addWidget(self.progress)

        # --- Métricas ---
        meta = QHBoxLayout()
        self.meta_registros = QLabel("—")
        self.meta_registros.setObjectName("SourceMeta")
        self.meta_tiempo = QLabel("—")
        self.meta_tiempo.setObjectName("SourceMeta")
        meta.addWidget(self.meta_registros)
        meta.addStretch(1)
        meta.addWidget(self.meta_tiempo)
        layout.addLayout(meta)

        self.setToolTip(etapa.descripcion)

    # ------------------------------------------------------------------
    def set_estado(self, estado: str, detalle: str = "") -> None:
        self._estado = estado
        self.badge.set_estado(estado)
        self.pill.set_estado(estado)
        if estado == "done":
            self.progress.set_progreso(100, "done")
        elif estado == "pending":
            self.progress.set_progreso(0, "pending")
        else:
            self.progress.set_progreso(self._pct, estado)
        if detalle and estado == "done":
            self.meta_registros.setText(detalle)

    def set_progreso(self, pct: int) -> None:
        self._pct = max(0, min(100, int(pct)))
        self.progress.set_progreso(self._pct, self._estado)

    def set_tiempo(self, texto: str) -> None:
        self.meta_tiempo.setText(texto)

    def reset(self) -> None:
        self._pct = 0
        self.meta_registros.setText("—")
        self.meta_tiempo.setText("—")
        self.set_estado("pending")
