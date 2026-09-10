# -*- coding: utf-8 -*-
"""Runtime hook de PyInstaller: activa los navegadores de Playwright empaquetados."""

import os
import sys

if getattr(sys, "frozen", False):
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(sys.executable)))
    carpeta = os.path.join(base, "playwright_browsers")
    if os.path.isdir(carpeta):
        os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", carpeta)
