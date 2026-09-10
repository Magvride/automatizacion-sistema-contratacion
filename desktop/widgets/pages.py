# -*- coding: utf-8 -*-
"""Páginas auxiliares: fuentes, historial de ejecuciones y configuración."""

import os
from datetime import datetime

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
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
            os.startfile(ruta)  # noqa: S606 - Windows

    def _abrir_carpeta(self) -> None:
        carpeta = self._carpeta_logs
        os.makedirs(carpeta, exist_ok=True)
        os.startfile(carpeta)  # noqa: S606 - Windows


class ConfigPage(QWidget):
    """Configuración de las rutas manuales (matriz, ordenadores, OneDrive)."""

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

        self._lbl_matriz = self._fila_ruta(layout, "Matriz manual", self._elegir_matriz)
        self._lbl_ordenadores = self._fila_ruta(layout, "Ordenadores", self._elegir_ordenadores)
        self._lbl_onedrive = self._fila_ruta(layout, "Carpeta OneDrive", self._elegir_onedrive)

        boton = _boton("Restablecer valores por defecto")
        boton.clicked.connect(self._restablecer)
        layout.addWidget(boton, alignment=Qt.AlignmentFlag.AlignLeft)

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
            from config import (
                ruta_matriz_manual,
                ruta_onedrive_destino,
                ruta_ordenadores,
            )
        except Exception as exc:  # noqa: BLE001
            self._lbl_matriz.setText(f"No disponible ({exc})")
            self._lbl_ordenadores.setText("—")
            self._lbl_onedrive.setText("—")
            return

        self._lbl_matriz.setText(str(ruta_matriz_manual()))
        self._lbl_ordenadores.setText(str(ruta_ordenadores()))
        self._lbl_onedrive.setText(str(ruta_onedrive_destino()))

    def _elegir_matriz(self) -> None:
        from config import configurar_rutas, ruta_matriz_manual, ruta_ordenadores

        ruta, _ = QFileDialog.getOpenFileName(
            self, "Selecciona la matriz manual", str(ruta_matriz_manual().parent),
            "Excel (*.xlsx)",
        )
        if ruta:
            configurar_rutas(matriz_manual=ruta, ordenadores=str(ruta_ordenadores()))
            self.refrescar()
            self.actualizado.emit(f"Matriz manual actualizada: {ruta}")

    def _elegir_ordenadores(self) -> None:
        from config import configurar_rutas, ruta_matriz_manual, ruta_ordenadores

        ruta, _ = QFileDialog.getOpenFileName(
            self, "Selecciona el archivo de ordenadores", str(ruta_ordenadores().parent),
            "Excel (*.xlsx)",
        )
        if ruta:
            configurar_rutas(matriz_manual=str(ruta_matriz_manual()), ordenadores=ruta)
            self.refrescar()
            self.actualizado.emit(f"Archivo de ordenadores actualizado: {ruta}")

    def _elegir_onedrive(self) -> None:
        from config import (
            configurar_rutas,
            ruta_matriz_manual,
            ruta_onedrive_destino,
            ruta_ordenadores,
        )

        ruta = QFileDialog.getExistingDirectory(
            self, "Selecciona la carpeta destino en OneDrive", str(ruta_onedrive_destino().parent)
        )
        if ruta:
            configurar_rutas(
                matriz_manual=str(ruta_matriz_manual()),
                ordenadores=str(ruta_ordenadores()),
                onedrive_destino=ruta,
            )
            self.refrescar()
            self.actualizado.emit(f"Carpeta OneDrive actualizada: {ruta}")

    def _restablecer(self) -> None:
        from config import restablecer_rutas

        restablecer_rutas()
        self.refrescar()
        self.actualizado.emit("Rutas restablecidas a los valores por defecto.")
