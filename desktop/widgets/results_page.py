# -*- coding: utf-8 -*-
"""Página de resultados: los entregables de la auditoría.

Sustituye la vista previa (poco útil) por dos tarjetas con botones para **abrir**
o **descargar** cada entregable:

* ``Auditoria_Contratos.xlsx`` — Excel con el diagnóstico por contrato.
* ``Informe_Auditoria_Contrato.html`` — informe visual (el PDF se guarda desde
  el botón interno del propio informe).
"""

import os
import shutil
import logging

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from desktop import icons
from desktop.paths import BASE_DIR
from desktop.widgets.components import Card, CardHead, repolish

logger = logging.getLogger("app")

ENTREGABLES = (
    {
        "titulo": "Auditoría de contratos",
        "descripcion": (
            "Excel con el diagnóstico por contrato: documentos hallados, "
            "faltantes, valor, fechas, ordenador y estado."
        ),
        "archivo": "Auditoria_Contratos.xlsx",
        "texto_abrir": "Abrir",
        "texto_descargar": "Descargar Excel",
        "icono": icons.DATABASE,
    },
    {
        "titulo": "Informe de auditoría",
        "descripcion": (
            "Informe visual en HTML (módulos con/sin carpeta y faltantes). "
            "Incluye un botón interno para guardarlo en PDF."
        ),
        "archivo": "Informe_Auditoria_Contrato.html",
        "texto_abrir": "Abrir en navegador",
        "texto_descargar": "Descargar HTML",
        "icono": icons.RESULTS,
    },
    {
        "titulo": "Correos para Power Automate",
        "descripcion": (
            "Excel con una tabla lista para automatizar el envío: destinatario, "
            "asunto y cuerpo completo del correo."
        ),
        "archivo": "10_Correos_Auditoria.xlsx",
        "texto_abrir": "Abrir",
        "texto_descargar": "Descargar Excel",
        "icono": icons.FILE,
    },
)


class _EntregableCard(Card):
    """Tarjeta de un entregable con botones de abrir/descargar."""

    def __init__(self, spec: dict, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.spec = spec
        self.ruta = ""

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(CardHead(spec["titulo"]))

        cuerpo = QWidget()
        cuerpo_layout = QVBoxLayout(cuerpo)
        cuerpo_layout.setContentsMargins(18, 12, 18, 16)
        cuerpo_layout.setSpacing(8)

        descripcion = QLabel(spec["descripcion"])
        descripcion.setObjectName("PageSubtitle")
        descripcion.setWordWrap(True)

        self.lbl_estado = QLabel("No generado")
        self.lbl_estado.setObjectName("DocPath")

        botones = QHBoxLayout()
        botones.setSpacing(8)
        self.btn_abrir = QPushButton(spec["texto_abrir"])
        self.btn_abrir.setObjectName("PrimaryButton")
        self.btn_descargar = QPushButton(spec["texto_descargar"])
        self.btn_descargar.setObjectName("OutlineButton")
        self.btn_abrir.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_descargar.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_abrir.clicked.connect(self._abrir)
        self.btn_descargar.clicked.connect(self._descargar)
        botones.addWidget(self.btn_abrir)
        botones.addWidget(self.btn_descargar)
        botones.addStretch(1)

        cuerpo_layout.addWidget(descripcion)
        cuerpo_layout.addWidget(self.lbl_estado)
        cuerpo_layout.addLayout(botones)
        layout.addWidget(cuerpo)

    def actualizar(self, carpeta: str) -> None:
        self.ruta = os.path.join(carpeta, self.spec["archivo"])
        existe = os.path.isfile(self.ruta)
        if existe:
            try:
                import datetime as _dt

                fh = _dt.datetime.fromtimestamp(os.path.getmtime(self.ruta))
                estado = f"generado · {fh.strftime('%Y-%m-%d %H:%M')}"
            except OSError:
                estado = "generado"
        else:
            estado = "no generado"
        self.lbl_estado.setText(f"{self.spec['archivo']} · {estado}")
        self.lbl_estado.setObjectName("DocPathOk" if existe else "DocPath")
        repolish(self.lbl_estado)
        self.btn_abrir.setEnabled(existe)
        self.btn_descargar.setEnabled(existe)

    def _abrir(self) -> None:
        if self.ruta and os.path.isfile(self.ruta):
            try:
                os.startfile(self.ruta)  # noqa: S606 - Windows
            except OSError as exc:
                logger.error("No se pudo abrir el entregable %s: %s", self.ruta, exc, exc_info=True)
                QMessageBox.critical(self, "Abrir entregable", f"No se pudo abrir el archivo:\n{exc}")

    def _descargar(self) -> None:
        if not self.ruta or not os.path.isfile(self.ruta):
            return
        destino, _ = QFileDialog.getSaveFileName(
            self,
            "Guardar entregable",
            os.path.join(os.path.expanduser("~"), self.spec["archivo"]),
            "Todos los archivos (*.*)",
        )
        if destino:
            try:
                shutil.copy2(self.ruta, destino)
            except OSError as exc:
                logger.error("No se pudo descargar el entregable %s: %s", self.ruta, exc, exc_info=True)
                QMessageBox.critical(self, "Descargar entregable", f"No se pudo guardar el archivo:\n{exc}")


class ResultsPage(QWidget):
    """Muestra los entregables con botones para abrirlos o descargarlos."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Content")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 22, 26, 22)
        layout.setSpacing(12)

        titulo = QLabel("Resultados")
        titulo.setObjectName("PageTitle")
        subtitulo = QLabel("Abre o descarga los entregables de la auditoría.")
        subtitulo.setObjectName("PageSubtitle")

        cabecera = QHBoxLayout()
        cabecera.addWidget(titulo)
        cabecera.addStretch(1)
        self.btn_refrescar = QPushButton("Actualizar")
        self.btn_refrescar.setObjectName("SmallButton")
        self.btn_refrescar.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_refrescar.clicked.connect(self.refrescar)
        cabecera.addWidget(self.btn_refrescar)

        layout.addLayout(cabecera)
        layout.addWidget(subtitulo)

        self._cards = []
        for spec in ENTREGABLES:
            card = _EntregableCard(spec)
            self._cards.append(card)
            layout.addWidget(card)

        layout.addStretch(1)
        self.refrescar()

    @property
    def _carpeta(self) -> str:
        try:
            from config import RESULTADOS_DIR

            return str(RESULTADOS_DIR)
        except Exception:  # noqa: BLE001
            return os.path.join(BASE_DIR, "archivos", "05_Datos_filtrados")

    def refrescar(self) -> None:
        for card in self._cards:
            card.actualizar(self._carpeta)
