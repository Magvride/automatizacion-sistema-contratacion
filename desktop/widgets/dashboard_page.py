# -*- coding: utf-8 -*-
"""Página principal: panel de ejecución con fuentes, acciones y registro."""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QVBoxLayout,
    QWidget,
)

from desktop.core.pipeline import ETAPAS
from desktop.widgets.action_bar import ActionBar
from desktop.widgets.activity_log import ActivityLog
from desktop.widgets.components import Card, CardHead, StatusChip
from desktop.widgets.documents_card import DocumentsCard
from desktop.widgets.source_card import SourceCard


class DashboardPage(QWidget):
    """Contenido de la sección ``Panel de ejecución``."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Content")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 22, 26, 22)
        layout.setSpacing(16)

        layout.addWidget(self._crear_encabezado())

        self.documents_card = DocumentsCard()
        layout.addWidget(self.documents_card)

        layout.addWidget(self._crear_fuentes())

        progreso = Card()
        progreso_layout = QVBoxLayout(progreso)
        progreso_layout.setContentsMargins(18, 14, 18, 14)
        fila = QHBoxLayout()
        self.lbl_contratos = QLabel("Contratos: 0/0")
        self.lbl_contratos.setObjectName("CardTitle")
        self.lbl_promedio = QLabel("Promedio por consulta: calculando…")
        self.lbl_promedio.setObjectName("PageSubtitle")
        fila.addWidget(self.lbl_contratos)
        fila.addStretch(1)
        fila.addWidget(self.lbl_promedio)
        self.barra_contratos = QProgressBar()
        self.barra_contratos.setRange(0, 100)
        self.barra_contratos.setValue(0)
        self.barra_contratos.setTextVisible(False)
        progreso_layout.addLayout(fila)
        progreso_layout.addWidget(self.barra_contratos)
        layout.addWidget(progreso)

        self.action_bar = ActionBar()
        layout.addWidget(self.action_bar)

        self.activity_log = ActivityLog()
        layout.addWidget(self.activity_log)
        layout.addStretch(1)

    # ------------------------------------------------------------------
    def _crear_encabezado(self) -> QWidget:
        head = QWidget()
        fila = QHBoxLayout(head)
        fila.setContentsMargins(0, 0, 0, 0)

        titulos = QWidget()
        columna = QVBoxLayout(titulos)
        columna.setContentsMargins(0, 0, 0, 0)
        columna.setSpacing(4)
        self.titulo = QLabel("Panel de ejecución")
        self.titulo.setObjectName("PageTitle")
        subtitulo = QLabel(
            "Carga el Excel de contratos y ejecuta las verificaciones automáticamente."
        )
        subtitulo.setObjectName("PageSubtitle")
        columna.addWidget(self.titulo)
        columna.addWidget(subtitulo)

        self.status_chip = StatusChip("En espera")
        fila.addWidget(titulos)
        fila.addStretch(1)
        fila.addWidget(self.status_chip, alignment=Qt.AlignmentFlag.AlignTop)
        return head

    def _crear_fuentes(self) -> Card:
        card = Card()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.sources_head = CardHead("Fuentes de datos", f"0 de {len(ETAPAS)} completadas")
        layout.addWidget(self.sources_head)

        cuerpo = QWidget()
        grid = QGridLayout(cuerpo)
        grid.setContentsMargins(18, 16, 18, 16)
        grid.setSpacing(10)

        self.source_cards: dict[str, SourceCard] = {}
        for indice, etapa in enumerate(ETAPAS):
            tarjeta = SourceCard(etapa)
            grid.addWidget(tarjeta, indice // 2, indice % 2)
            self.source_cards[etapa.id] = tarjeta

        layout.addWidget(cuerpo)
        return card

    # ------------------------------------------------------------------
    def reiniciar_tarjetas(self) -> None:
        for tarjeta in self.source_cards.values():
            tarjeta.reset()
        self.sources_head.set_hint(f"0 de {len(ETAPAS)} completadas")
        self.status_chip.set_estado("pending")
        self.status_chip.set_texto("En espera")
        self.set_progreso_contratos(0, 0, "Promedio por consulta: calculando…")

    def set_progreso_contratos(self, hechos: int, total: int, promedio: str = "") -> None:
        total = max(int(total), 0)
        hechos = max(0, min(int(hechos), total)) if total else 0
        self.lbl_contratos.setText(f"Contratos verificados: {hechos}/{total}")
        self.barra_contratos.setValue(int(hechos * 100 / total) if total else 0)
        if promedio:
            self.lbl_promedio.setText(promedio)
