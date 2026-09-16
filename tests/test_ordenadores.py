# -*- coding: utf-8 -*-
"""Tests de la carga del mapa de ordenadores (``src/ordenadores.py``)."""

import pandas as pd

from ordenadores import (
    cargar_correos_ordenadores,
    cargar_correos_apoyo,
    cargar_mapa_ordenadores,
    extraer_correos,
    normalizar_nombre,
)


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


def test_extraer_correos():
    assert extraer_correos("a@uis.edu.co, b@uis.edu.co") == ["a@uis.edu.co", "b@uis.edu.co"]
    assert extraer_correos("ESCUELA X <esc@uis.edu.co>\notra@uis.edu.co") == [
        "esc@uis.edu.co", "otra@uis.edu.co",
    ]
    assert extraer_correos(None) == []


def test_cargar_mapa_ordenadores_con_apoyos_sep(tmp_path):
    ruta = tmp_path / "Ordenadores_SEP.xlsx"
    filas = [
        ["CONSULTA DE ORDENADORES DE GASTO ACTIVOS", None, None, None],
        ["ORDENADORES DE GASTO", "CORREO", "PERSONAL DE APOYO", "CORREOS DE APOYO"],
        ["Juan Pérez", "juan@uis.edu.co", "Secretaria X",
         "ESCUELA X <apoyo1@uis.edu.co>\napoyo2@uis.edu.co"],
        ["María Gómez", "maria@uis.edu.co", "Secretaria Y", ""],
    ]
    pd.DataFrame(filas).to_excel(ruta, index=False, header=False)

    mapa = cargar_mapa_ordenadores(str(ruta))

    assert mapa["JUAN PEREZ"]["correo"] == "juan@uis.edu.co"
    assert mapa["JUAN PEREZ"]["apoyos"] == ["apoyo1@uis.edu.co", "apoyo2@uis.edu.co"]
    assert mapa["MARIA GOMEZ"]["apoyos"] == []

    apoyos = cargar_correos_apoyo(str(ruta))
    assert apoyos == {"JUAN PEREZ": "apoyo1@uis.edu.co; apoyo2@uis.edu.co"}

    # Compatibilidad: el mapa simple de correos sigue igual.
    assert cargar_correos_ordenadores(str(ruta)) == {
        "JUAN PEREZ": "juan@uis.edu.co",
        "MARIA GOMEZ": "maria@uis.edu.co",
    }
