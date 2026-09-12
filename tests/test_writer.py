# -*- coding: utf-8 -*-
"""Tests del writer de verificación (``src/alfresco_mcp/writer.py``)."""

import pandas as pd

from alfresco_mcp.writer import COLUMNAS_06, COLUMNAS_07, escribir_verificacion


def _resultado(nombre, encontrado):
    return {
        "verificacion": {
            "NOMBRE EXPEDIENTE": nombre,
            "UAA": "UAA1",
            "SERIE": "S1",
            "SUB-SERIE": "SS1",
            "alfresco": "SI" if encontrado else "NO",
            "cantidad_archivos": 3 if encontrado else 0,
            "MOTIVO": "" if encontrado else "carpeta_no_encontrada",
            "EXPEDIENTE_ENCONTRADO": "SI" if encontrado else "NO",
            "DESCRIPCION": "",
        }
    }


def test_escribir_verificacion(tmp_path):
    ruta_06 = str(tmp_path / "06_Verificacion_Alfresco.csv")
    ruta_07 = str(tmp_path / "07_Expedientes_Faltantes.csv")

    resumen = escribir_verificacion(
        [_resultado("0020_A", True), _resultado("0020_B", False)],
        ruta_06, ruta_07,
    )

    assert resumen["total"] == 2
    assert resumen["encontrados"] == 1
    assert resumen["no_encontrados"] == 1

    df6 = pd.read_csv(ruta_06, encoding="utf-8-sig", dtype=str).fillna("")
    assert list(df6.columns) == COLUMNAS_06
    assert len(df6) == 2

    df7 = pd.read_csv(ruta_07, encoding="utf-8-sig", dtype=str).fillna("")
    assert list(df7.columns) == COLUMNAS_07
    assert "DESCRIPCION" not in df7.columns
    assert len(df7) == 1
    assert df7.iloc[0]["NOMBRE EXPEDIENTE"] == "0020_B"
