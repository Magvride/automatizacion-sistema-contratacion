# -*- coding: utf-8 -*-
"""Paleta de colores y hoja de estilos (QSS) que replica el mockup HTML."""

# --- Colores base (equivalentes a las variables CSS del mockup) ---
BG = "#EAEEF1"
PANEL = "#FFFFFF"
INK = "#1A2233"
INK_SOFT = "#616B7A"
INK_FAINT = "#929CAA"
LINE = "#DFE4E9"
LINE_STRONG = "#C7CED6"

ACCENT = "#145C56"
ACCENT_SOFT = "#E4EEEC"
ACCENT_DARK = "#0E413D"
ACCENT_MINT = "#5FD9C7"

INFO = "#2F6FED"
INFO_SOFT = "#E9F0FE"
WARN = "#C98A2C"
WARN_SOFT = "#FBF1E1"
OK = "#2F9E68"
OK_SOFT = "#E7F5EE"
ERR = "#D6484B"
ERR_SOFT = "#FBE9E9"

SIDEBAR = ACCENT_DARK
SIDEBAR_TEXT = "#B9D6D1"
SIDEBAR_TEXT_STRONG = "#FFFFFF"
SIDEBAR_MUTED = "#8FB5AF"
SIDEBAR_FOOTER = "#6E9C95"

# Estado -> (fondo, texto, punto)
COLORES_ESTADO = {
    "pending": ("#F1F3F5", INK_FAINT, INK_FAINT),
    "running": (INFO_SOFT, "#1F51B8", INFO),
    "done": (OK_SOFT, "#1F7A4C", OK),
    "error": (ERR_SOFT, "#A83236", ERR),
}

FUENTE_UI = "Segoe UI"
FUENTE_TITULO = "Segoe UI Semibold"
FUENTE_MONO = "Consolas"

RADIUS = 10


def hoja_estilos() -> str:
    """Construye la QSS global de la aplicación."""
    return f"""
    * {{
        font-family: "{FUENTE_UI}";
        outline: none;
    }}

    QWidget {{
        color: {INK};
    }}

    #Root {{
        background: {BG};
        border: 1px solid rgba(10, 15, 25, 0.08);
    }}

    /* ---------------- Barra de título ---------------- */
    #TitleBar {{
        background: {SIDEBAR};
        min-height: 40px;
        max-height: 40px;
    }}
    #TitleBarText {{
        color: #DCEAE7;
        font-size: 12px;
        letter-spacing: 0.3px;
    }}
    #TitleBarIcon {{
        color: #DCEAE7;
    }}
    #WinButton {{
        background: rgba(255, 255, 255, 0.16);
        border: none;
        border-radius: 6px;
        color: #DCEAE7;
        font-size: 13px;
        min-width: 26px;
        max-width: 26px;
        min-height: 20px;
        max-height: 20px;
    }}
    #WinButton:hover {{
        background: rgba(255, 255, 255, 0.30);
    }}
    #UpdateButton {{
        background: rgba(255, 255, 255, 0.16);
        border: none;
        border-radius: 6px;
        color: #DCEAE7;
        font-size: 12px;
        min-width: 166px;
        max-width: 166px;
        min-height: 26px;
        max-height: 26px;
        padding: 0 8px;
    }}
    #UpdateButton:hover {{
        background: rgba(255, 255, 255, 0.30);
    }}
    #UpdateButton:disabled {{
        color: #A9C5C0;
    }}
    #WinClose {{
        background: rgba(255, 255, 255, 0.16);
        border: none;
        border-radius: 6px;
        color: #DCEAE7;
        font-size: 13px;
        min-width: 26px;
        max-width: 26px;
        min-height: 20px;
        max-height: 20px;
    }}
    #WinClose:hover {{
        background: {ERR};
        color: #FFFFFF;
    }}

    /* ---------------- Sidebar ---------------- */
    #Sidebar {{
        background: {SIDEBAR};
        min-width: 208px;
        max-width: 208px;
    }}
    #Brand {{
        color: {SIDEBAR_TEXT_STRONG};
        font-family: "{FUENTE_TITULO}";
        font-size: 15px;
        font-weight: 600;
    }}
    #BrandSub {{
        color: {SIDEBAR_MUTED};
        font-size: 11px;
    }}
    #NavItem {{
        background: transparent;
        border: none;
        border-radius: 7px;
        color: {SIDEBAR_TEXT};
        font-size: 13px;
        text-align: left;
        padding: 9px 10px;
    }}
    #NavItem:hover {{
        background: rgba(255, 255, 255, 0.06);
        color: #E8F3F1;
    }}
    #NavItem:checked {{
        background: rgba(255, 255, 255, 0.10);
        color: {SIDEBAR_TEXT_STRONG};
    }}
    #NavFooter {{
        color: {SIDEBAR_FOOTER};
        font-size: 10.5px;
        border-top: 1px solid rgba(255, 255, 255, 0.08);
        padding-top: 10px;
    }}
    #NavFooter b {{
        color: #A9CFC9;
    }}

    /* ---------------- Contenido ---------------- */
    #Content {{
        background: {BG};
    }}
    #ScrollArea {{
        background: {BG};
        border: none;
    }}
    #ScrollArea > QWidget > QWidget {{
        background: {BG};
    }}
    QScrollBar:vertical {{
        background: transparent;
        width: 8px;
        margin: 0;
    }}
    QScrollBar::handle:vertical {{
        background: {LINE_STRONG};
        border-radius: 4px;
        min-height: 30px;
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0;
    }}

    #PageTitle {{
        font-family: "{FUENTE_TITULO}";
        font-size: 19px;
        font-weight: 600;
        color: {INK};
    }}
    #PageSubtitle {{
        color: {INK_SOFT};
        font-size: 12.5px;
    }}
    #StatusChip {{
        background: {PANEL};
        border: 1px solid {LINE};
        border-radius: 20px;
    }}
    #StatusChipText {{
        color: {INK_SOFT};
        font-size: 12px;
    }}

    /* ---------------- Tarjetas ---------------- */
    #Card {{
        background: {PANEL};
        border: 1px solid {LINE};
        border-radius: {RADIUS}px;
    }}
    #CardHead {{
        border-bottom: 1px solid {LINE};
    }}
    #CardTitle {{
        font-family: "{FUENTE_TITULO}";
        font-size: 13px;
        font-weight: 600;
        color: {INK};
    }}
    #CardHint {{
        color: {INK_FAINT};
        font-size: 11.5px;
    }}

    /* ---------------- Campos ---------------- */
    #FieldLabel {{
        color: {INK_SOFT};
        font-size: 11.5px;
        font-weight: 500;
    }}
    #DateInput {{
        font-family: "{FUENTE_MONO}";
        font-size: 13px;
        padding: 8px 10px;
        border: 1px solid {LINE_STRONG};
        border-radius: 7px;
        background: #FBFCFD;
        color: {INK};
        min-width: 150px;
        max-width: 150px;
    }}
    #DateInput:focus {{
        border: 1px solid {ACCENT};
        background: #FFFFFF;
    }}
    #FormatNote {{
        color: {INK_FAINT};
        font-size: 11.5px;
    }}

    /* ---------------- Tarjetas de fuentes ---------------- */
    #SourceCard {{
        background: #FCFDFD;
        border: 1px solid {LINE};
        border-radius: 9px;
    }}
    #SourceName {{
        font-size: 13px;
        font-weight: 500;
        color: {INK};
    }}
    #SourceIcon {{
        border-radius: 7px;
    }}
    #SourceMeta {{
        font-family: "{FUENTE_MONO}";
        font-size: 11px;
        color: {INK_FAINT};
    }}
    #ProgressTrack {{
        background: #EDEFF2;
        border-radius: 3px;
        min-height: 5px;
        max-height: 5px;
    }}
    #ProgressFill {{
        border-radius: 3px;
        min-height: 5px;
        max-height: 5px;
    }}

    /* ---------------- Insignias (pills) ---------------- */
    #Pill {{
        border-radius: 10px;
        font-size: 10.5px;
        font-weight: 500;
    }}
    #Pill[estado="done"] {{ background: {OK_SOFT}; }}
    #Pill[estado="running"] {{ background: {INFO_SOFT}; }}
    #Pill[estado="pending"] {{ background: #F1F3F5; }}
    #Pill[estado="error"] {{ background: {ERR_SOFT}; }}
    #PillText[estado="done"] {{ color: #1F7A4C; }}
    #PillText[estado="running"] {{ color: #1F51B8; }}
    #PillText[estado="pending"] {{ color: {INK_FAINT}; }}
    #PillText[estado="error"] {{ color: #A83236; }}

    /* ---------------- Botones ---------------- */
    QPushButton#PrimaryButton {{
        background: {ACCENT};
        color: #FFFFFF;
        border: 1px solid transparent;
        border-radius: 8px;
        font-size: 13px;
        font-weight: 500;
        padding: 10px 16px;
    }}
    QPushButton#PrimaryButton:hover {{ background: {ACCENT_DARK}; }}
    QPushButton#PrimaryButton:disabled {{ background: #A9BEBB; color: #EDF3F2; }}

    QPushButton#OutlineButton {{
        background: {PANEL};
        color: {INK};
        border: 1px solid {LINE_STRONG};
        border-radius: 8px;
        font-size: 13px;
        font-weight: 500;
        padding: 10px 16px;
    }}
    QPushButton#OutlineButton:hover {{ background: #F3F5F7; }}
    QPushButton#OutlineButton:disabled {{
        color: {INK_FAINT};
        background: #F5F6F8;
        border: 1px solid {LINE};
    }}

    QPushButton#SecondaryButton {{
        background: {INFO};
        color: #FFFFFF;
        border: 1px solid transparent;
        border-radius: 8px;
        font-size: 13px;
        font-weight: 500;
        padding: 10px 16px;
    }}
    QPushButton#SecondaryButton:hover {{ background: #2456C4; }}
    QPushButton#SecondaryButton:disabled {{ background: #9DB7EE; color: #EEF3FE; }}

    #ScheduleNote {{
        color: {INK_FAINT};
        font-size: 11.5px;
    }}

    QPushButton#SmallButton {{
        background: {PANEL};
        color: {INK};
        border: 1px solid {LINE_STRONG};
        border-radius: 6px;
        font-size: 12px;
        font-weight: 500;
        padding: 6px 12px;
    }}
    QPushButton#SmallButton:hover {{ background: #F3F5F7; }}
    QPushButton#SmallButton:disabled {{ color: {INK_FAINT}; background: #F5F6F8; }}

    QPushButton#GhostButton {{
        background: transparent;
        border: none;
        border-radius: 6px;
        min-width: 24px;
        max-width: 24px;
        min-height: 24px;
        max-height: 24px;
    }}
    QPushButton#GhostButton:hover {{ background: #F1F3F5; }}

    #DocName {{
        font-size: 12.5px;
        font-weight: 600;
        color: {INK};
    }}
    #DocPath {{
        color: {INK_FAINT};
        font-family: "{FUENTE_MONO}";
        font-size: 11px;
    }}
    #DocPathOk {{
        color: {OK};
        font-family: "{FUENTE_MONO}";
        font-size: 11px;
    }}
    #DocSeparator {{
        background: #F0F2F4;
        max-height: 1px;
        min-height: 1px;
    }}
    #DocNote {{
        color: {INK_FAINT};
        font-size: 11.5px;
    }}

    /* ---------------- Registro de actividad ---------------- */
    #LogToggle {{
        background: {PANEL};
        border: none;
        border-radius: {RADIUS}px;
    }}
    #LogTitle {{
        font-family: "{FUENTE_TITULO}";
        font-size: 13px;
        font-weight: 600;
        color: {INK};
    }}
    #LogCount {{
        background: #F1F3F5;
        color: {INK_SOFT};
        border-radius: 10px;
        font-family: "{FUENTE_MONO}";
        font-size: 11px;
        padding: 2px 8px;
    }}
    #IconButton {{
        background: {PANEL};
        border: 1px solid {LINE_STRONG};
        border-radius: 6px;
        min-width: 26px;
        max-width: 26px;
        min-height: 26px;
        max-height: 26px;
    }}
    #IconButton:hover {{ background: #F3F5F7; }}
    #LogBody {{
        background: {PANEL};
        border-top: 1px solid {LINE};
    }}
    #LogBody QWidget {{
        background: {PANEL};
        color: {INK};
    }}
    #LogEntry {{
        background: {PANEL};
        color: {INK};
    }}
    #LogEntryTime {{
        font-family: "{FUENTE_MONO}";
        color: {INK_FAINT};
        font-size: 12px;
    }}
    #LogEntryText {{
        color: {INK};
        font-size: 12px;
    }}
    #LogEntrySub {{
        color: {INK_FAINT};
        font-size: 11px;
    }}
    #LogSeparator {{
        background: #F0F2F4;
        max-height: 1px;
        min-height: 1px;
    }}

    /* ---------------- Diálogos del sistema ---------------- */
    QDialog {{
        background: {PANEL};
        color: {INK};
    }}
    QMessageBox {{
        background: {PANEL};
        color: {INK};
    }}
    QMessageBox QLabel {{
        background: transparent;
        color: {INK};
    }}
    QMessageBox QPushButton {{
        background: {ACCENT};
        color: #FFFFFF;
        border: 1px solid {ACCENT_DARK};
        border-radius: 6px;
        min-width: 76px;
        min-height: 28px;
        padding: 4px 12px;
    }}
    QMessageBox QPushButton:hover {{
        background: {ACCENT_DARK};
    }}
    QDialog QLabel, QDialog QCheckBox, QDialog QRadioButton {{
        color: {INK};
    }}

    /* ---------------- Barra de estado ---------------- */
    #StatusBar {{
        background: #F4F6F7;
        border-top: 1px solid {LINE_STRONG};
    }}
    #StatusBarItem {{
        color: {INK_SOFT};
        font-size: 11.5px;
    }}
    #GlobalTrack {{
        background: #E2E6E9;
        border-radius: 3px;
        min-height: 5px;
        max-height: 5px;
    }}
    #GlobalFill {{
        background: {ACCENT};
        border-radius: 3px;
        min-height: 5px;
        max-height: 5px;
    }}

    /* ---------------- Páginas auxiliares ---------------- */
    #ConfigLabel {{
        color: {INK_SOFT};
        font-size: 12px;
    }}
    #ConfigValue {{
        color: {INK};
        font-family: "{FUENTE_MONO}";
        font-size: 11.5px;
    }}
    QListWidget#HistoryList {{
        background: {PANEL};
        border: 1px solid {LINE};
        border-radius: {RADIUS}px;
        font-family: "{FUENTE_MONO}";
        font-size: 12px;
        padding: 4px;
    }}
    QListWidget#HistoryList::item {{
        padding: 8px 10px;
        border-bottom: 1px solid #F0F2F4;
    }}
    QListWidget#HistoryList::item:selected {{
        background: {ACCENT_SOFT};
        color: {ACCENT_DARK};
    }}

    QTableWidget#ResultsTable {{
        background: {PANEL};
        border: none;
        gridline-color: #EEF1F3;
        font-size: 12px;
    }}
    QTableWidget#ResultsTable::item {{
        padding: 5px 8px;
    }}
    QTableWidget#ResultsTable::item:selected {{
        background: {ACCENT_SOFT};
        color: {ACCENT_DARK};
    }}
    QHeaderView::section {{
        background: #F4F6F7;
        color: {INK_SOFT};
        border: none;
        border-right: 1px solid {LINE};
        border-bottom: 1px solid {LINE};
        padding: 6px 8px;
        font-weight: 600;
    }}
    QPlainTextEdit#PreviewText {{
        background: {PANEL};
        border: none;
        font-family: "{FUENTE_MONO}";
        font-size: 12px;
        color: {INK};
        padding: 6px;
    }}
    """
