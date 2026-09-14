# -*- coding: utf-8 -*-
"""Test del enriquecimiento del consolidado 02 en el flujo MCP (``main.py``)."""

import pandas as pd

from main import _consolidado_enriquecido


def test_consolidado_enriquecido_por_contrato():
    cons = pd.DataFrame(
        [
            {"contrato": "20-2026000003", "NOMBRE EXPEDIENTE": "", "alfresco": "",
             "cantidad_archivos": ""},
            {"contrato": "20-2026009999", "NOMBRE EXPEDIENTE": "", "alfresco": "",
             "cantidad_archivos": ""},
        ],
        dtype=str,
    )
    resultados = [
        {"contrato": "20-2026000003", "carpeta": "0020_2026000003_9707",
         "estado_alfresco": "ENCONTRADA", "cantidad_archivos": 5},
        {"contrato": "20-2026009999", "carpeta": "0020_2026009999",
         "estado_alfresco": "NO SE EVIDENCIA", "cantidad_archivos": 0},
    ]

    salida = _consolidado_enriquecido(cons, resultados)

    assert salida.iloc[0]["NOMBRE EXPEDIENTE"] == "0020_2026000003_9707"
    assert salida.iloc[0]["alfresco"] == "SI"
    assert salida.iloc[0]["cantidad_archivos"] == "5"
    assert salida.iloc[1]["alfresco"] == "NO"
