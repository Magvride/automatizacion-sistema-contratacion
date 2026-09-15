# -*- coding: utf-8 -*-
"""Páginas auxiliares: fuentes, historial de ejecuciones y configuración."""

import os
from datetime import datetime

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from desktop import icons, theme
from desktop.core.documentos import documentos
from desktop.paths import BASE_DIR
from desktop.widgets.components import Card


def _boton(texto: str, object_name: str = "OutlineButton") -> QPushButton:
    boton = QPushButton(texto)
    boton.setObjectName(object_name)
    boton.setCursor(Qt.CursorShape.PointingHandCursor)
    return boton


class SourcesPage(QWidget):
    """Descripción de los documentos de entrada del flujo."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Content")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 22, 26, 22)
        layout.setSpacing(16)

        titulo = QLabel("Documentos de entrada")
        titulo.setObjectName("PageTitle")
        layout.addWidget(titulo)

        for documento in documentos():
            card = Card()
            fila = QHBoxLayout(card)
            fila.setContentsMargins(18, 16, 18, 16)
            fila.setSpacing(12)

            icono = QLabel()
            icono.setPixmap(icons.svg_pixmap(icons.FILE, 20, theme.ACCENT))
            icono.setFixedWidth(24)

            textos = QWidget()
            columna = QVBoxLayout(textos)
            columna.setContentsMargins(0, 0, 0, 0)
            columna.setSpacing(2)
            nombre = QLabel(documento.nombre)
            nombre.setObjectName("CardTitle")
            descripcion = QLabel(documento.descripcion)
            descripcion.setObjectName("PageSubtitle")
            columna.addWidget(nombre)
            columna.addWidget(descripcion)

            fila.addWidget(icono, alignment=Qt.AlignmentFlag.AlignTop)
            fila.addWidget(textos, 1)
            layout.addWidget(card)

        layout.addStretch(1)


class HistoryPage(QWidget):
    """Lista de archivos de log generados por las ejecuciones."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Content")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 22, 26, 22)
        layout.setSpacing(12)

        cabecera = QHBoxLayout()
        titulo = QLabel("Historial de ejecuciones")
        titulo.setObjectName("PageTitle")
        self.btn_refrescar = _boton("Actualizar")
        self.btn_abrir = _boton("Abrir carpeta")
        self.btn_refrescar.clicked.connect(self.refrescar)
        self.btn_abrir.clicked.connect(self._abrir_carpeta)
        cabecera.addWidget(titulo)
        cabecera.addStretch(1)
        cabecera.addWidget(self.btn_refrescar)
        cabecera.addWidget(self.btn_abrir)
        layout.addLayout(cabecera)

        self.lista = QListWidget()
        self.lista.setObjectName("HistoryList")
        self.lista.itemDoubleClicked.connect(self._abrir_item)
        layout.addWidget(self.lista, 1)

        self.refrescar()

    @property
    def _carpeta_logs(self) -> str:
        return os.path.join(BASE_DIR, "logs")

    def refrescar(self) -> None:
        self.lista.clear()
        carpeta = self._carpeta_logs
        if not os.path.isdir(carpeta):
            return
        archivos = [
            os.path.join(carpeta, n)
            for n in os.listdir(carpeta)
            if n.lower().endswith(".log")
        ]
        archivos.sort(key=os.path.getmtime, reverse=True)
        for ruta in archivos[:200]:
            mtime = datetime.fromtimestamp(os.path.getmtime(ruta)).strftime("%Y-%m-%d %H:%M")
            tamano = os.path.getsize(ruta) / 1024
            item = QListWidgetItem(f"{os.path.basename(ruta)}   ·   {mtime}   ·   {tamano:.0f} KB")
            item.setData(Qt.ItemDataRole.UserRole, ruta)
            self.lista.addItem(item)

    def _abrir_item(self, item: QListWidgetItem) -> None:
        ruta = item.data(Qt.ItemDataRole.UserRole)
        if ruta and os.path.isfile(ruta):
            try:
                os.startfile(ruta)  # noqa: S606 - Windows
            except OSError as exc:
                QMessageBox.warning(self, "No se pudo abrir el registro", str(exc))

    def _abrir_carpeta(self) -> None:
        carpeta = self._carpeta_logs
        try:
            os.makedirs(carpeta, exist_ok=True)
            os.startfile(carpeta)  # noqa: S606 - Windows
        except OSError as exc:
            QMessageBox.warning(self, "No se pudo abrir la carpeta", str(exc))


class ConfigPage(QWidget):
    """Configuración de las rutas manuales y credenciales de Alfresco."""

    actualizado = pyqtSignal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Content")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 22, 26, 22)
        layout.setSpacing(12)

        titulo = QLabel("Configuración")
        titulo.setObjectName("PageTitle")
        layout.addWidget(titulo)

        credenciales = Card()
        cred_layout = QVBoxLayout(credenciales)
        cred_layout.setContentsMargins(18, 14, 18, 14)
        cred_layout.setSpacing(8)
        cred_titulo = QLabel("Credenciales de Alfresco")
        cred_titulo.setObjectName("CardTitle")
        cred_layout.addWidget(cred_titulo)
        cred_info = QLabel(
            "Se guardan una sola vez: la contraseña se almacena en el Administrador "
            "de credenciales de Windows y no en un archivo de texto."
        )
        cred_info.setObjectName("PageSubtitle")
        cred_info.setWordWrap(True)
        cred_layout.addWidget(cred_info)

        formulario = QFormLayout()
        self._alfresco_url = QLineEdit()
        self._alfresco_usuario = QLineEdit()
        self._alfresco_contrasena = QLineEdit()
        self._alfresco_contrasena.setEchoMode(QLineEdit.EchoMode.Password)
        self._alfresco_contrasena.setPlaceholderText("Dejar vacío para conservar la guardada")
        formulario.addRow("URL", self._alfresco_url)
        formulario.addRow("Usuario", self._alfresco_usuario)
        formulario.addRow("Contraseña", self._alfresco_contrasena)
        cred_layout.addLayout(formulario)

        cred_acciones = QHBoxLayout()
        btn_guardar = _boton("Guardar credenciales", "PrimaryButton")
        btn_guardar.clicked.connect(self._guardar_alfresco)
        self._lbl_credenciales = QLabel()
        self._lbl_credenciales.setWordWrap(True)
        cred_acciones.addWidget(btn_guardar)
        cred_acciones.addWidget(self._lbl_credenciales, 1)
        cred_layout.addLayout(cred_acciones)
        layout.addWidget(credenciales)

        layout.addStretch(1)
        self.refrescar()

    def _fila_ruta(self, layout: QVBoxLayout, etiqueta: str, slot) -> QLabel:
        card = Card()
        fila = QHBoxLayout(card)
        fila.setContentsMargins(18, 14, 18, 14)
        fila.setSpacing(12)

        textos = QWidget()
        columna = QVBoxLayout(textos)
        columna.setContentsMargins(0, 0, 0, 0)
        columna.setSpacing(2)
        lbl_etiqueta = QLabel(etiqueta)
        lbl_etiqueta.setObjectName("CardTitle")
        valor = QLabel("—")
        valor.setObjectName("ConfigValue")
        valor.setWordWrap(True)
        columna.addWidget(lbl_etiqueta)
        columna.addWidget(valor)

        boton = _boton("Cambiar…")
        boton.clicked.connect(slot)

        fila.addWidget(textos, 1)
        fila.addWidget(boton)
        layout.addWidget(card)
        return valor

    # ------------------------------------------------------------------
    def refrescar(self) -> None:
        try:
            from config import credenciales_alfresco
        except Exception as exc:  # noqa: BLE001
            self._lbl_credenciales.setText(f"No disponible: {exc}")
            return

        try:
            datos = credenciales_alfresco()
            self._alfresco_url.setText(datos["url"])
            self._alfresco_usuario.setText(datos["usuario"])
            self._lbl_credenciales.setText(
                "Credenciales guardadas" if datos["contrasena"] else "Falta guardar la contraseña"
            )
        except Exception as exc:  # noqa: BLE001
            self._lbl_credenciales.setText(f"No disponible: {exc}")

    def _guardar_alfresco(self) -> None:
        try:
            from config import guardar_credenciales_alfresco

            guardar_credenciales_alfresco(
                self._alfresco_url.text(),
                self._alfresco_usuario.text(),
                self._alfresco_contrasena.text(),
            )
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Credenciales de Alfresco", str(exc))
            return

        self._alfresco_contrasena.clear()
        self._lbl_credenciales.setText("Credenciales guardadas correctamente")
        self.actualizado.emit("Credenciales de Alfresco guardadas de forma segura.")
