# -*- coding: utf-8 -*-
"""Tests de la consolidación sin UISARD (``src/consolidar.py``)."""

import pandas as pd

from consolidar import COLUMNAS_CONSOLIDADO, construir_consolidado


def _escribir_normalizados(tmp_path, filas):
    ruta = tmp_path / "contratos_normalizados.csv"
    pd.DataFrame(filas).to_csv(ruta, index=False, encoding="utf-8-sig")
    return str(ruta)


def test_construir_consolidado_basico(tmp_path):
    ruta = _escribir_normalizados(
        tmp_path,
        [
            {
                "contrato": "20-2026000003",
                "centro_costo": "CC1",
                "ordenador": "JUAN PEREZ",
                "correo_ordenador": "",
                "uisard": "",
            },
            {
                "contrato": "18-2026001182",
                "centro_costo": "CC2",
                "ordenador": "MARIA GOMEZ",
                "correo_ordenador": "",
                "uisard": "",
            },
        ],
    )
    salida = str(tmp_path / "02_Consolidado_General.csv")

    res = construir_consolidado(ruta, salida, correos={"JUAN PEREZ": "juan@uis.edu.co"})

    assert res["encontrado"] is True
    assert res["total"] == 2
    assert res["con_correo"] == 1

    df = pd.read_csv(salida, encoding="utf-8-sig", dtype=str).fillna("")
    assert list(df.columns) == COLUMNAS_CONSOLIDADO
    assert set(df["origen"]) == {"NUEVAS VERSIONES"}
    assert (df["uisard"] == "").all()
    for col in ("NOMBRE EXPEDIENTE", "UAA", "SERIE", "SUBSERIE", "alfresco", "cantidad_archivos"):
        assert (df[col] == "").all(), col

    fila = df[df["contrato"] == "20-2026000003"].iloc[0]
    assert fila["correo_ordenador"] == "juan@uis.edu.co"


def test_construir_consolidado_con_apoyos(tmp_path):
    ruta = _escribir_normalizados(
        tmp_path,
        [{"contrato": "20-2026000003", "centro_costo": "CC1", "ordenador": "JUAN PEREZ"}],
    )
    salida = str(tmp_path / "02_Consolidado_General.csv")

    res = construir_consolidado(
        ruta,
        salida,
        correos={"JUAN PEREZ": "juan@uis.edu.co"},
        apoyos={"JUAN PEREZ": "apoyo1@uis.edu.co; apoyo2@uis.edu.co"},
    )

    assert res["encontrado"] is True
    df = pd.read_csv(salida, encoding="utf-8-sig", dtype=str).fillna("")
    assert "correos_apoyo" in df.columns
    assert df.iloc[0]["correos_apoyo"] == "apoyo1@uis.edu.co; apoyo2@uis.edu.co"


def test_construir_consolidado_sin_columna_correo(tmp_path):
    ruta = _escribir_normalizados(
        tmp_path,
        [{"contrato": "20-2026000003", "centro_costo": "CC1", "ordenador": "JUAN PEREZ"}],
    )
    salida = str(tmp_path / "02_Consolidado_General.csv")

    res = construir_consolidado(ruta, salida, correos={"JUAN PEREZ": "juan@uis.edu.co"})

    assert res["encontrado"] is True
    df = pd.read_csv(salida, encoding="utf-8-sig", dtype=str).fillna("")
    assert df.iloc[0]["correo_ordenador"] == "juan@uis.edu.co"


def test_construir_consolidado_archivo_faltante(tmp_path):
    salida = str(tmp_path / "02_Consolidado_General.csv")
    res = construir_consolidado(str(tmp_path / "no_existe.csv"), salida, correos={})
    assert res["encontrado"] is False
    assert res["total"] == 0
    assert not (tmp_path / "02_Consolidado_General.csv").exists()


def test_construir_consolidado_sin_columna_contrato(tmp_path):
    ruta = tmp_path / "contratos_normalizados.csv"
    pd.DataFrame([{"otra": "x"}]).to_csv(ruta, index=False, encoding="utf-8-sig")
    salida = str(tmp_path / "02_Consolidado_General.csv")

    res = construir_consolidado(str(ruta), salida, correos={})

    assert res["encontrado"] is False
    assert not (tmp_path / "02_Consolidado_General.csv").exists()
