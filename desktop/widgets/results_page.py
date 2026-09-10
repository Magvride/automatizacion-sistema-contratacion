# -*- coding: utf-8 -*-
"""Página de resultados: lista los archivos generados, los previsualiza y permite
descargarlos o exportarlos a Excel."""

import csv
import os
import shutil
from datetime import datetime

from PyQt6.QtCore import Qt, QSize
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from desktop import icons, theme
from desktop.paths import BASE_DIR
from desktop.widgets.components import Card, CardHead

# Número máximo de filas que se cargan en la vista previa.
MAX_PREVIEW_FILAS = 1000


def _boton(texto: str, object_name: str = "SmallButton") -> QPushButton:
    boton = QPushButton(texto)
    boton.setObjectName(object_name)
    boton.setCursor(Qt.CursorShape.PointingHandCursor)
    return boton


class ResultsPage(QWidget):
    """Muestra los archivos de ``archivos/05_Datos_filtrados`` y los permite descargar."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Content")
        self._ruta_actual = ""

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 22, 26, 22)
        layout.setSpacing(12)

        titulo = QLabel("Resultados")
        titulo.setObjectName("PageTitle")
        layout.addWidget(titulo)

        subtitulo = QLabel(
            "Consulta, previsualiza y descarga los archivos generados por el proceso."
        )
        subtitulo.setObjectName("PageSubtitle")
        layout.addWidget(subtitulo)

        layout.addLayout(self._crear_cabecera())
        layout.addWidget(self._crear_cuerpo(), 1)

        nota = QLabel(
            "Los archivos se guardan en la carpeta de trabajo del proceso. "
            "Usa «Descargar» para copiarlos a la ubicación que prefieras."
        )
        nota.setObjectName("DocNote")
        nota.setWordWrap(True)
        layout.addWidget(nota)

        self.refrescar()

    # ------------------------------------------------------------------
    def _crear_cabecera(self) -> QHBoxLayout:
        fila = QHBoxLayout()
        fila.addStretch(1)
        self.btn_refrescar = _boton("Actualizar")
        self.btn_abrir_carpeta = _boton("Abrir carpeta")
        self.btn_refrescar.clicked.connect(self.refrescar)
        self.btn_abrir_carpeta.clicked.connect(self._abrir_carpeta)
        fila.addWidget(self.btn_refrescar)
        fila.addWidget(self.btn_abrir_carpeta)
        return fila

    def _crear_cuerpo(self) -> QSplitter:
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setMinimumHeight(460)
        splitter.setChildrenCollapsible(False)

        # --- Izquierda: lista de archivos ---
        izquierda = Card()
        izq_layout = QVBoxLayout(izquierda)
        izq_layout.setContentsMargins(0, 0, 0, 0)
        izq_layout.setSpacing(0)
        self.head = CardHead("Archivos generados", "0")
        izq_layout.addWidget(self.head)
        self.lista = QListWidget()
        self.lista.setObjectName("HistoryList")
        self.lista.itemSelectionChanged.connect(self._on_seleccion)
        self.lista.itemDoubleClicked.connect(self._abrir_item)
        izq_layout.addWidget(self.lista, 1)

        # --- Derecha: vista previa ---
        derecha = Card()
        der_layout = QVBoxLayout(derecha)
        der_layout.setContentsMargins(0, 0, 0, 0)
        der_layout.setSpacing(0)
        self.head_preview = CardHead("Vista previa", "Selecciona un archivo")
        der_layout.addWidget(self.head_preview)

        self.stack = QStackedWidget()

        self.tabla = QTableWidget()
        self.tabla.setObjectName("ResultsTable")
        self.tabla.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tabla.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tabla.setAlternatingRowColors(True)
        self.tabla.verticalHeader().setVisible(False)
        self.stack.addWidget(self.tabla)

        self.texto = QPlainTextEdit()
        self.texto.setObjectName("PreviewText")
        self.texto.setReadOnly(True)
        self.stack.addWidget(self.texto)

        der_layout.addWidget(self.stack, 1)
        der_layout.addWidget(self._crear_acciones())

        splitter.addWidget(izquierda)
        splitter.addWidget(derecha)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([320, 640])
        return splitter

    def _crear_acciones(self) -> QWidget:
        contenedor = QWidget()
        fila = QHBoxLayout(contenedor)
        fila.setContentsMargins(14, 10, 14, 12)
        fila.setSpacing(8)

        self.btn_abrir = _boton("Abrir")
        self.btn_descargar = _boton("Descargar", "PrimaryButton")
        self.btn_exportar = _boton("Exportar a Excel")
        self.btn_abrir.clicked.connect(self._abrir_actual)
        self.btn_descargar.clicked.connect(self._descargar)
        self.btn_exportar.clicked.connect(self._exportar_excel)

        fila.addWidget(self.btn_abrir)
        fila.addWidget(self.btn_exportar)
        fila.addStretch(1)
        fila.addWidget(self.btn_descargar)
        self._actualizar_botones()
        return contenedor

    # ------------------------------------------------------------------
    @property
    def _carpeta(self) -> str:
        try:
            from config import RESULTADOS_DIR

            return str(RESULTADOS_DIR)
        except Exception:  # noqa: BLE001
            return os.path.join(BASE_DIR, "archivos", "05_Datos_filtrados")

    def refrescar(self) -> None:
        seleccionada = self._ruta_actual
        self.lista.clear()
        carpeta = self._carpeta
        if not os.path.isdir(carpeta):
            self.head.set_hint("0")
            self._ruta_actual = ""
            self._limpiar_preview()
            self._actualizar_botones()
            return

        archivos = [
            os.path.join(carpeta, n)
            for n in os.listdir(carpeta)
            if os.path.isfile(os.path.join(carpeta, n))
        ]
        archivos.sort(key=os.path.getmtime, reverse=True)
        for ruta in archivos:
            mtime = datetime.fromtimestamp(os.path.getmtime(ruta)).strftime("%Y-%m-%d %H:%M")
            tamano = os.path.getsize(ruta) / 1024
            item = QListWidgetItem(
                f"{os.path.basename(ruta)}   ·   {mtime}   ·   {tamano:.0f} KB"
            )
            item.setData(Qt.ItemDataRole.UserRole, ruta)
            self.lista.addItem(item)

        self.head.set_hint(str(len(archivos)))
        self._ruta_actual = ""
        self._limpiar_preview()
        self._actualizar_botones()

        for indice in range(self.lista.count()):
            item = self.lista.item(indice)
            if item.data(Qt.ItemDataRole.UserRole) == seleccionada:
                item.setSelected(True)
                break

    # ------------------------------------------------------------------
    def _ruta_seleccionada(self) -> str:
        item = self.lista.currentItem()
        if item is None:
            return ""
        return item.data(Qt.ItemDataRole.UserRole) or ""

    def _on_seleccion(self) -> None:
        ruta = self._ruta_seleccionada()
        self._ruta_actual = ruta
        if not ruta:
            self._limpiar_preview()
        else:
            self._previsualizar(ruta)
        self._actualizar_botones()

    def _actualizar_botones(self) -> None:
        ruta = self._ruta_seleccionada()
        hay = bool(ruta) and os.path.isfile(ruta)
        self.btn_abrir.setEnabled(hay)
        self.btn_descargar.setEnabled(hay)
        self.btn_exportar.setEnabled(hay and ruta.lower().endswith(".csv"))

    def _limpiar_preview(self) -> None:
        self.tabla.clear()
        self.tabla.setRowCount(0)
        self.tabla.setColumnCount(0)
        self.texto.setPlainText("")
        self.stack.setCurrentWidget(self.tabla)
        self.head_preview.set_hint("Selecciona un archivo")

    def _previsualizar(self, ruta: str) -> None:
        self.head_preview.set_hint(os.path.basename(ruta))
        extension = os.path.splitext(ruta)[1].lower()
        try:
            if extension == ".csv":
                self._previsualizar_csv(ruta)
            elif extension in (".xlsx", ".xls"):
                self._previsualizar_excel(ruta)
            elif extension in (".txt", ".log"):
                with open(ruta, "r", encoding="utf-8-sig", errors="replace") as fh:
                    self.texto.setPlainText(fh.read())
                self.stack.setCurrentWidget(self.texto)
            else:
                self._limpiar_preview()
                self.head_preview.set_hint("Sin vista previa disponible")
        except Exception as exc:  # noqa: BLE001
            self._limpiar_preview()
            self.head_preview.set_hint(f"No se pudo previsualizar: {exc}")

    def _previsualizar_csv(self, ruta: str) -> None:
        with open(ruta, "r", encoding="utf-8-sig", newline="") as fh:
            muestra = fh.read(8192)
            fh.seek(0)
            try:
                dialecto = csv.Sniffer().sniff(muestra, delimiters=",;\t|")
                separador = dialecto.delimiter
            except csv.Error:
                separador = ","
            filas = []
            for i, fila in enumerate(csv.reader(fh, delimiter=separador)):
                filas.append(fila)
                if i >= MAX_PREVIEW_FILAS:
                    break
        self._llenar_tabla(filas)

    def _previsualizar_excel(self, ruta: str) -> None:
        import pandas as pd

        df = pd.read_excel(ruta, dtype=str, nrows=MAX_PREVIEW_FILAS).fillna("")
        encabezados = [str(c) for c in df.columns]
        filas = [encabezados] + df.astype(str).values.tolist()
        self._llenar_tabla(filas)

    def _llenar_tabla(self, filas: list) -> None:
        self.tabla.clear()
        if not filas:
            self.tabla.setRowCount(0)
            self.tabla.setColumnCount(0)
            self.stack.setCurrentWidget(self.tabla)
            return
        encabezados = filas[0]
        datos = filas[1:]
        self.tabla.setColumnCount(len(encabezados))
        self.tabla.setHorizontalHeaderLabels([str(c) for c in encabezados])
        self.tabla.setRowCount(len(datos))
        for f, fila in enumerate(datos):
            for c in range(len(encabezados)):
                valor = fila[c] if c < len(fila) else ""
                self.tabla.setItem(f, c, QTableWidgetItem(str(valor)))
        self.tabla.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.tabla.resizeColumnsToContents()
        self.stack.setCurrentWidget(self.tabla)

    # ------------------------------------------------------------------
    def _abrir_item(self, item: QListWidgetItem) -> None:
        ruta = item.data(Qt.ItemDataRole.UserRole)
        if ruta and os.path.isfile(ruta):
            os.startfile(ruta)  # noqa: S606 - Windows

    def _abrir_actual(self) -> None:
        ruta = self._ruta_seleccionada()
        if ruta and os.path.isfile(ruta):
            os.startfile(ruta)  # noqa: S606 - Windows

    def _abrir_carpeta(self) -> None:
        carpeta = self._carpeta
        os.makedirs(carpeta, exist_ok=True)
        os.startfile(carpeta)  # noqa: S606 - Windows

    def _descargar(self) -> None:
        ruta = self._ruta_seleccionada()
        if not ruta or not os.path.isfile(ruta):
            return
        destino, _ = QFileDialog.getSaveFileName(
            self,
            "Guardar archivo de resultados",
            os.path.join(os.path.expanduser("~"), os.path.basename(ruta)),
            "Todos los archivos (*.*)",
        )
        if not destino:
            return
        try:
            shutil.copy2(ruta, destino)
        except OSError as exc:
            self.head_preview.set_hint(f"No se pudo guardar: {exc}")
            return
        self.head_preview.set_hint(f"Guardado en {destino}")

    def _exportar_excel(self) -> None:
        ruta = self._ruta_seleccionada()
        if not ruta or not ruta.lower().endswith(".csv"):
            return
        nombre = os.path.splitext(os.path.basename(ruta))[0] + ".xlsx"
        destino, _ = QFileDialog.getSaveFileName(
            self,
            "Exportar a Excel",
            os.path.join(os.path.expanduser("~"), nombre),
            "Excel (*.xlsx)",
        )
        if not destino:
            return
        try:
            import pandas as pd

            pd.read_csv(ruta, encoding="utf-8-sig", dtype=str).fillna("").to_excel(
                destino, index=False
            )
        except Exception as exc:  # noqa: BLE001
            self.head_preview.set_hint(f"No se pudo exportar: {exc}")
            return
        self.head_preview.set_hint(f"Excel generado en {destino}")
