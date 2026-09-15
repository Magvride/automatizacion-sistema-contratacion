# -*- coding: utf-8 -*-
"""Test del servicio «Auditoría Documental Automatizada»."""

import openpyxl

from alfresco_mcp.demo import GatewayDemo, carpetas_demo
from auditoria_documental.diccionario import cargar_diccionario
from auditoria_documental.servicio import SALIDAS, ejecutar_servicio


def _diccionario(tmp_path):
    ruta = tmp_path / "Diccionario_Documentos.xlsx"
    libro = openpyxl.Workbook()
    hoja = libro.active
    hoja.title = "Diccionario"
    hoja.append(["ID_DOC", "CLASE", "CODIGO_CLASE", "DOCUMENTO", "CODIGO_FORMATO",
                 "ETAPA", "CARDINALIDAD", "OBLIGATORIEDAD", "ALIAS"])
    hoja.append(["D1", "ORDEN DE COMPRA", "20", "Informe de oportunidad", "FCO.55",
                 "Precontractual - selección", "Única", "Obligatorio", "FCO.55 Informe"])
    hoja.append(["D2", "ORDEN DE COMPRA", "20", "Cámara de comercio", "",
                 "Precontractual - idoneidad", "Única", "Obligatorio", "Camara Comercio"])
    libro.save(ruta)
    return str(ruta)


def test_ejecutar_servicio_genera_todas_las_salidas(tmp_path):
    ruta_diccionario = _diccionario(tmp_path)
    diccionario = cargar_diccionario(ruta_diccionario)["diccionario"]
    gateway = GatewayDemo(carpetas_demo(diccionario))
    salida = tmp_path / "salida"

    resumen = ejecutar_servicio(
        [{"contrato": "20-2026000003", "ordenador": "JUAN PEREZ"}],
        gateway,
        str(salida),
        ruta_diccionario=ruta_diccionario,
        periodo="TEST",
        fecha_revision="2026-08-31",
    )

    assert resumen["total"] == 1
    assert resumen["encontradas"] == 1
    for clave in ("verificacion", "faltantes", "auditoria", "correos", "correos_excel", "informe"):
        assert (salida / SALIDAS[clave]).is_file(), clave

    assert resumen["ruta_informe"].endswith("Informe_Auditoria_Contrato.html")
    with open(resumen["ruta_informe"], encoding="utf-8") as archivo:
        assert "Documentos faltantes" in archivo.read()
