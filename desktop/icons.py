# -*- coding: utf-8 -*-
"""Iconos vectoriales embebidos (SVG) renderizados con ``QtSvg``.

Cada icono usa ``currentColor`` como color de trazo/relleno para poder teñirlo
en tiempo de ejecución sin necesidad de archivos externos.
"""

from PyQt6.QtCore import QByteArray, Qt
from PyQt6.QtGui import QIcon, QPainter, QPixmap
from PyQt6.QtSvg import QSvgRenderer

# --- Iconos de navegación ---
PANEL = (
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">'
    '<rect x="3" y="3" width="7" height="9" rx="1.5"/>'
    '<rect x="14" y="3" width="7" height="5" rx="1.5"/>'
    '<rect x="14" y="12" width="7" height="9" rx="1.5"/>'
    '<rect x="3" y="16" width="7" height="5" rx="1.5"/></svg>'
)
DATABASE = (
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">'
    '<ellipse cx="12" cy="5" rx="8" ry="3"/>'
    '<path d="M4 5v14c0 1.7 3.6 3 8 3s8-1.3 8-3V5"/>'
    '<path d="M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3"/></svg>'
)
HISTORY = (
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">'
    '<path d="M3 3v5h5"/><path d="M3.05 13a9 9 0 1 0 2.13-6.36L3 8"/>'
    '<path d="M12 7v5l4 2"/></svg>'
)
RESULTS = (
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">'
    '<rect x="3" y="4" width="18" height="16" rx="2"/>'
    '<path d="M3 9h18"/><path d="M9 9v11"/><path d="M15 13h3"/></svg>'
)
GEAR = (
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">'
    '<circle cx="12" cy="12" r="3"/>'
    '<path d="M19.4 15a1.7 1.7 0 0 0 .34 1.87l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.7 1.7 0 0 0-1.87-.34 1.7 1.7 0 0 0-1.03 1.56V21a2 2 0 1 1-4 0v-.09A1.7 1.7 0 0 0 9 19.4a1.7 1.7 0 0 0-1.87.34l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.7 1.7 0 0 0 4.6 15a1.7 1.7 0 0 0-1.56-1.03H3a2 2 0 1 1 0-4h.09A1.7 1.7 0 0 0 4.6 9a1.7 1.7 0 0 0-.34-1.87l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06A1.7 1.7 0 0 0 9 4.6a1.7 1.7 0 0 0 1.03-1.56V3a2 2 0 1 1 4 0v.09A1.7 1.7 0 0 0 15 4.6a1.7 1.7 0 0 0 1.87-.34l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06A1.7 1.7 0 0 0 19.4 9c.36.51.9.87 1.56 1.03H21a2 2 0 1 1 0 4h-.09a1.7 1.7 0 0 0-1.51 1z"/></svg>'
)

# --- Acciones ---
PLAY = '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z"/></svg>'
STOP = '<svg viewBox="0 0 24 24" fill="currentColor"><rect x="6" y="6" width="12" height="12" rx="2"/></svg>'
CONTINUE = (
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">'
    '<path d="M5 3l14 9-14 9V3z"/></svg>'
)
UPLOAD = (
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">'
    '<path d="M12 3v13"/><path d="M7 8l5-5 5 5"/><path d="M4 19h16"/></svg>'
)
DOWNLOAD = (
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">'
    '<path d="M12 3v13"/><path d="M7 11l5 5 5-5"/><path d="M4 19h16"/></svg>'
)

# --- Estados / varios ---
CHECK = (
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">'
    '<path d="M20 6L9 17l-5-5"/></svg>'
)
CLOCK = (
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">'
    '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></svg>'
)
DOT = '<svg viewBox="0 0 24 24" fill="currentColor"><circle cx="12" cy="12" r="6"/></svg>'
ALERT = (
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">'
    '<path d="M12 8v5"/><circle cx="12" cy="16.5" r="0.6" fill="currentColor"/>'
    '<path d="M10.3 4.6l-8 14A1 1 0 0 0 3 20h18a1 1 0 0 0 .87-1.4l-8-14a1 1 0 0 0-1.74 0z"/></svg>'
)
CLOSE = (
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4">'
    '<path d="M6 6l12 12"/><path d="M18 6L6 18"/></svg>'
)
CHEVRON = (
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">'
    '<path d="M6 9l6 6 6-6"/></svg>'
)
MINIMIZE = (
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4">'
    '<path d="M5 12h14"/></svg>'
)
MAXIMIZE = (
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">'
    '<rect x="5" y="5" width="14" height="14" rx="1.5"/></svg>'
)
RESTORE = (
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">'
    '<rect x="4" y="8" width="12" height="12" rx="1.5"/>'
    '<path d="M8 8V6a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2h-2"/></svg>'
)
SYNC = (
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">'
    '<path d="M3 12a9 9 0 1 0 9-9"/><path d="M3 3v6h6"/></svg>'
)
FILE = (
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">'
    '<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/>'
    '<path d="M14 3v5h5"/></svg>'
)
TRASH = (
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">'
    '<path d="M4 7h16"/><path d="M9 7V5a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2"/>'
    '<path d="M6 7l1 13a1 1 0 0 0 1 1h8a1 1 0 0 0 1-1l1-13"/></svg>'
)


def _teñir(svg: str, color: str | None) -> str:
    if color:
        return svg.replace("currentColor", color)
    return svg


def svg_pixmap(svg: str, tamano: int = 16, color: str | None = None) -> QPixmap:
    """Renderiza un SVG a ``QPixmap`` del tamaño indicado."""
    renderer = QSvgRenderer(QByteArray(_teñir(svg, color).encode("utf-8")))
    pixmap = QPixmap(tamano, tamano)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    renderer.render(painter)
    painter.end()
    return pixmap


def svg_icon(svg: str, tamano: int = 16, color: str | None = None) -> QIcon:
    """Renderiza un SVG a ``QIcon``."""
    return QIcon(svg_pixmap(svg, tamano, color))
