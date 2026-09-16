# -*- coding: utf-8 -*-
"""Tarjeta de carga manual de los documentos de entrada."""

import os

from PyQt6.QtCore import QSize, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from desktop import icons, theme
from desktop.core.documentos import documentos
from desktop.widgets.components import Card, CardHead


def _separador() -> QFrame:
    sep = QFrame()
    sep.setObjectName("DocSeparator")
    sep.setFixedHeight(1)
    return sep


class _FilaDocumento(QWidget):
    """Fila con nombre, ruta seleccionada y botón para elegir el archivo."""

    cambio = pyqtSignal()

    def __init__(self, documento, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.documento = documento
        self._ruta = ""

        fila = QHBoxLayout(self)
        fila.setContentsMargins(0, 8, 0, 8)
        fila.setSpacing(10)

        self.icono = QLabel()
        self.icono.setFixedSize(26, 26)
        self.icono.setAlignment(Qt.AlignmentFlag.AlignCenter)

        textos = QWidget()
        columna = QVBoxLayout(textos)
        columna.setContentsMargins(0, 0, 0, 0)
        columna.setSpacing(1)
        self.lbl_nombre = QLabel(documento.nombre)
        self.lbl_nombre.setObjectName("DocName")
        self.lbl_ruta = QLabel("Sin seleccionar")
        self.lbl_ruta.setObjectName("DocPath")
        columna.addWidget(self.lbl_nombre)
        columna.addWidget(self.lbl_ruta)

        self.btn_seleccionar = QPushButton("Seleccionar…")
        self.btn_seleccionar.setObjectName("SmallButton")
        self.btn_seleccionar.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_seleccionar.clicked.connect(self._elegir)

        self.btn_limpiar = QPushButton()
        self.btn_limpiar.setObjectName("GhostButton")
        self.btn_limpiar.setIcon(icons.svg_icon(icons.TRASH, 14, theme.INK_FAINT))
        self.btn_limpiar.setIconSize(QSize(14, 14))
        self.btn_limpiar.setToolTip("Quitar selección")
        self.btn_limpiar.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_limpiar.clicked.connect(self._limpiar)
        self.btn_limpiar.setVisible(False)

        fila.addWidget(self.icono)
        fila.addWidget(textos, 1)
        fila.addWidget(self.btn_limpiar)
        fila.addWidget(self.btn_seleccionar)

        self._pintar()

    # ------------------------------------------------------------------
    def _pintar(self) -> None:
        seleccionado = bool(self._ruta)
        color = theme.OK if seleccionado else theme.INK_FAINT
        fondo = theme.OK_SOFT if seleccionado else "#F1F3F5"
        self.icono.setPixmap(icons.svg_pixmap(icons.FILE, 14, color))
        self.icono.setStyleSheet(f"background:{fondo}; border-radius:7px;")

    def _elegir(self) -> None:
        ruta, _ = QFileDialog.getOpenFileName(
            self,
            f"Selecciona: {self.documento.nombre}",
            self._ruta or str(self.documento.carpeta),
            self.documento.filtro,
        )
        if ruta:
            self.set_ruta(ruta)
            self.cambio.emit()

    def _limpiar(self) -> None:
        self.set_ruta("")
        self.cambio.emit()

    def set_ruta(self, ruta: str) -> None:
        self._ruta = ruta
        if ruta:
            self.lbl_ruta.setText(os.path.basename(ruta))
            self.lbl_ruta.setObjectName("DocPathOk")
            self.lbl_ruta.setToolTip(ruta)
        else:
            self.lbl_ruta.setText("Sin seleccionar")
            self.lbl_ruta.setObjectName("DocPath")
            self.lbl_ruta.setToolTip("")
        self.lbl_ruta.style().unpolish(self.lbl_ruta)
        self.lbl_ruta.style().polish(self.lbl_ruta)
        self.btn_limpiar.setVisible(bool(ruta))
        self._pintar()

    def ruta(self) -> str:
        return self._ruta


class DocumentsCard(Card):
    """Selección de los archivos de entrada y de la matriz de seguimiento."""

    cambio = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(
            CardHead("Documentos de entrada", f"{len(documentos())} archivos Excel")
        )

        cuerpo = QWidget()
        cuerpo_layout = QVBoxLayout(cuerpo)
        cuerpo_layout.setContentsMargins(18, 6, 18, 14)
        cuerpo_layout.setSpacing(0)

        self._filas: dict[str, _FilaDocumento] = {}
        for indice, documento in enumerate(documentos()):
            if indice:
                cuerpo_layout.addWidget(_separador())
            fila = _FilaDocumento(documento)
            fila.cambio.connect(self.cambio.emit)
            cuerpo_layout.addWidget(fila)
            self._filas[documento.id] = fila

        nota = QLabel(
            "El diccionario de contratos se carga automáticamente. "
            "Los correos de apoyo del Excel de ordenadores se usan como copia (CC) "
            "en los avisos de la última fase."
        )
        nota.setObjectName("DocNote")
        nota.setWordWrap(True)
        cuerpo_layout.addWidget(nota)

        layout.addWidget(cuerpo)
        self._preseleccionar_ordenadores()

    # ------------------------------------------------------------------
    def rutas(self) -> dict:
        return {doc_id: fila.ruta() for doc_id, fila in self._filas.items()}

    def set_ruta(self, doc_id: str, ruta: str) -> None:
        fila = self._filas.get(doc_id)
        if fila:
            fila.set_ruta(ruta)

    def _preseleccionar_ordenadores(self) -> None:
        try:
            from config import ruta_ordenadores

            ruta = ruta_ordenadores()
        except Exception:
            return
        if ruta and ruta.is_file():
            self.set_ruta("ordenadores", str(ruta))
