# -*- coding: utf-8 -*-
"""Configuración de pytest: expone ``src/`` en el path como hace ``main.py``."""

import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(RAIZ, "src")

for ruta in (RAIZ, SRC):
    if ruta not in sys.path:
        sys.path.insert(0, ruta)
