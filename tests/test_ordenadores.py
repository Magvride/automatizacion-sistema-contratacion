# -*- coding: utf-8 -*-
"""Tests de la carga del mapa de ordenadores (``src/ordenadores.py``)."""

import pandas as pd

from ordenadores import cargar_correos_ordenadores, normalizar_nombre


def test_normalizar_nombre():
    assert normalizar_nombre("Juan Pérez") == "JUAN PEREZ"
    assert normalizar_nombre("  MARÍA   GÓMEZ ") == "MARIA GOMEZ"
    assert normalizar_nombre(None) == ""


def test_cargar_correos_ordenadores_con_titulo_previo(tmp_path):
    ruta = tmp_path / "Ordenadores_Agosto.xlsx"
    filas = [
        ["REPORTE DE ORDENADORES", None, None],
        [None, None, None],
        ["ORDENADORES DE GASTO", "CORREO", "OTRA"],
        ["Juan Pérez", "juan@uis.edu.co", "x"],
        ["MARÍA GÓMEZ", "maria@uis.edu.co", "y"],
        [None, None, None],
    ]
    pd.DataFrame(filas).to_excel(ruta, index=False, header=False)

    correos = cargar_correos_ordenadores(str(ruta))

    assert correos["JUAN PEREZ"] == "juan@uis.edu.co"
    assert correos["MARIA GOMEZ"] == "maria@uis.edu.co"
    assert len(correos) == 2


def test_cargar_correos_ordenadores_sin_columnas(tmp_path):
    ruta = tmp_path / "Ordenadores_Sin.xlsx"
    pd.DataFrame([["a", "b"], ["c", "d"]]).to_excel(ruta, index=False, header=False)
    assert cargar_correos_ordenadores(str(ruta)) == {}


def test_cargar_correos_ordenadores_archivo_inexistente(tmp_path):
    assert cargar_correos_ordenadores(str(tmp_path / "no_existe.xlsx")) == {}
