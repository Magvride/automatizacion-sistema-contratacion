# -*- coding: utf-8 -*-
"""Página de resultados: los dos entregables de la auditoría.

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
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMessageBox,
    QPlainTextEdit,
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
        estado = "generado" if existe else "no generado"
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


class _DialogoEnvio(QDialog):
    """Diálogo de autorización previa al envío masivo de correos."""

    def __init__(self, mensajes: list, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.mensajes = mensajes
        self.setWindowTitle("Autorizar envío de correos")
        self.setMinimumSize(760, 620)

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        aviso = QLabel(
            f"Se prepararon <b>{len(mensajes)}</b> correo(s) para envío masivo. "
            "Antes de autorizar, revisa el reporte de verificación en Alfresco y "
            "confirma que los destinatarios y el contenido de cada borrador sean correctos."
        )
        aviso.setWordWrap(True)
        layout.addWidget(aviso)

        lista = QListWidget()
        for mensaje in mensajes:
            lista.addItem(
                f"{mensaje['para']}  —  {mensaje['ordenador']}  —  "
                f"{len(mensaje['contratos'])} contrato(s)"
            )
        lista.setMinimumHeight(115)
        layout.addWidget(lista)

        detalle = QLabel(
            "Borrador seleccionado. Este es el asunto y el mensaje exactos que se enviarán."
        )
        detalle.setWordWrap(True)
        layout.addWidget(detalle)

        self.vista_mensaje = QPlainTextEdit()
        self.vista_mensaje.setReadOnly(True)
        self.vista_mensaje.setPlaceholderText("Selecciona un destinatario para ver su borrador.")
        layout.addWidget(self.vista_mensaje, 1)

        lista.currentRowChanged.connect(self._mostrar_mensaje)
        if mensajes:
            lista.setCurrentRow(0)

        self.chk_autorizo = QCheckBox(
            "He revisado el reporte de Alfresco y autorizo el envío masivo de estos correos."
        )
        layout.addWidget(self.chk_autorizo)

        botones = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.btn_enviar = botones.button(QDialogButtonBox.StandardButton.Ok)
        self.btn_enviar.setText("Enviar")
        self.btn_enviar.setEnabled(False)
        self.chk_autorizo.toggled.connect(self.btn_enviar.setEnabled)
        botones.accepted.connect(self.accept)
        botones.rejected.connect(self.reject)
        layout.addWidget(botones)

    def _mostrar_mensaje(self, indice: int) -> None:
        if indice < 0 or indice >= len(self.mensajes):
            self.vista_mensaje.clear()
            return
        mensaje = self.mensajes[indice]
        contratos = "\n".join(f"- {contrato}" for contrato in mensaje["contratos"])
        self.vista_mensaje.setPlainText(
            f"PARA: {mensaje['para']}\n"
            f"ORDENADOR: {mensaje['ordenador']}\n"
            f"CONTRATOS: {contratos}\n"
            f"ASUNTO: {mensaje['asunto']}\n\n"
            f"{mensaje['cuerpo']}"
        )


class _NotificacionCard(Card):
    """Notificación a ordenadores de contratos sin carpeta (con autorización)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.ruta = ""

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(CardHead("Notificar a ordenadores", "requiere autorización"))

        cuerpo = QWidget()
        cuerpo_layout = QVBoxLayout(cuerpo)
        cuerpo_layout.setContentsMargins(18, 12, 18, 16)
        cuerpo_layout.setSpacing(8)

        descripcion = QLabel(
            "Envía un correo a los ordenadores de los contratos que no tienen "
            "carpeta en Alfresco. Primero revisa el reporte y los borradores; el "
            "envío masivo requiere autorización explícita."
        )
        descripcion.setObjectName("PageSubtitle")
        descripcion.setWordWrap(True)

        self.lbl_resumen = QLabel("—")
        self.lbl_resumen.setObjectName("DocPath")

        self.btn_preparar = QPushButton("Preparar envío…")
        self.btn_preparar.setObjectName("PrimaryButton")
        self.btn_preparar.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_preparar.clicked.connect(self._preparar)

        cuerpo_layout.addWidget(descripcion)
        cuerpo_layout.addWidget(self.lbl_resumen)
        cuerpo_layout.addWidget(self.btn_preparar, alignment=Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(cuerpo)

    def actualizar(self, carpeta: str) -> None:
        self.ruta = os.path.join(carpeta, "Auditoria_Contratos.xlsx")
        if not os.path.isfile(self.ruta):
            self.lbl_resumen.setText("Primero genera la auditoría.")
            self.btn_preparar.setEnabled(False)
            return
        try:
            from auditoria_documental.notificacion import resultados_desde_excel, resumen

            info = resumen(resultados_desde_excel(self.ruta))
        except Exception as exc:  # noqa: BLE001
            self.lbl_resumen.setText(f"No se pudo leer la auditoría: {exc}")
            self.btn_preparar.setEnabled(False)
            return
        self.lbl_resumen.setText(
            f"{info['sin_carpeta']} sin carpeta · {info['con_correo']} con correo · "
            f"{info['sin_correo']} sin correo · {info['destinatarios']} destinatario(s)"
        )
        self.btn_preparar.setEnabled(info["destinatarios"] > 0)

    def _preparar(self) -> None:
        if not self.ruta or not os.path.isfile(self.ruta):
            return
        try:
            from auditoria_documental import notificacion

            resultados = notificacion.resultados_desde_excel(self.ruta)
            mensajes = notificacion.construir_mensajes(resultados)
        except Exception as exc:  # noqa: BLE001
            logger.error("No se pudieron preparar los correos: %s", exc, exc_info=True)
            QMessageBox.critical(
                self,
                "Preparar envío",
                f"No se pudieron preparar los correos:\n\n{exc}",
            )
            return
        if not mensajes:
            QMessageBox.information(
                self, "Sin correos",
                "No hay contratos sin carpeta con correo de ordenador.",
            )
            return

        dialogo = _DialogoEnvio(mensajes, self)
        if dialogo.exec() != QDialog.DialogCode.Accepted or not dialogo.chk_autorizo.isChecked():
            return

        try:
            resumen_envio = notificacion.enviar(resultados, autorizado=True, mensajes=mensajes)
        except Exception as exc:  # noqa: BLE001
            logger.error("No se pudieron enviar los correos: %s", exc, exc_info=True)
            QMessageBox.critical(self, "Envío de correos", f"No se pudieron enviar los correos:\n\n{exc}")
            return
        QMessageBox.information(self, "Envío de correos", resumen_envio["detalle"])


class ResultsPage(QWidget):
    """Muestra los dos entregables con botones para abrirlos o descargarlos."""

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

        self.card_notificacion = _NotificacionCard()
        self._cards.append(self.card_notificacion)
        layout.addWidget(self.card_notificacion)

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
