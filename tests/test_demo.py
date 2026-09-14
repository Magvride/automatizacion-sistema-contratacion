# -*- coding: utf-8 -*-
"""Tests del modo demo (``src/alfresco_mcp/demo.py``)."""

from alfresco_mcp.demo import GatewayDemo, carpetas_demo, nombre_archivo


def _diccionario():
    return [
        {"ID_DOC": "D1", "CODIGO_CLASE": "20", "DOCUMENTO": "Informe",
         "CODIGO_FORMATO": "FCO.55", "OBLIGATORIEDAD": "Obligatorio", "ETAPA": "E"},
        {"ID_DOC": "D2", "CODIGO_CLASE": "20", "DOCUMENTO": "Camara",
         "CODIGO_FORMATO": "", "OBLIGATORIEDAD": "Obligatorio", "ETAPA": "E"},
        {"ID_DOC": "D3", "CODIGO_CLASE": "18 PJ", "DOCUMENTO": "Minuta",
         "CODIGO_FORMATO": "", "OBLIGATORIEDAD": "Obligatorio", "ETAPA": "E"},
        {"ID_DOC": "D4", "CODIGO_CLASE": "20", "DOCUMENTO": "Opcional",
         "CODIGO_FORMATO": "", "OBLIGATORIEDAD": "Condicional", "ETAPA": "E"},
    ]


def test_nombre_archivo():
    assert nombre_archivo({"CODIGO_FORMATO": "FCO.55", "DOCUMENTO": "Informe"}) == "FCO.55 Informe.pdf"
    assert nombre_archivo({"CODIGO_FORMATO": "", "DOCUMENTO": "Camara"}) == "Camara.pdf"


def test_carpetas_demo():
    carpetas = carpetas_demo(_diccionario())
    assert "2026000003" in carpetas
    assert "2026001515" in carpetas
    # El contrato 18 PJ recibe todos sus obligatorios + FCO.74.
    assert "FCO.74 Acta de pago final.pdf" in carpetas["2026001515"]["archivos"]
    # El contrato 20 recibe un subconjunto (parcial).
    assert len(carpetas["2026000003"]["archivos"]) <= 2


def test_gateway_demo():
    carpetas = {
        "2026000003": {
            "carpeta": {"id": "nA", "nombre": "0020_2026000003_9707", "es_carpeta": True},
            "archivos": ["a.pdf", "b.pdf"],
        }
    }
    gateway = GatewayDemo(carpetas)
    assert gateway.buscar_carpetas("2026000003")[0]["id"] == "nA"
    assert gateway.buscar_carpetas("9999") == []
    listado = gateway.listar_archivos("nA")
    assert listado["total"] == 2
    assert listado["archivos"][0]["NOMBRE"] == "a.pdf"
    assert gateway.listar_archivos("nX")["total"] == 0
