# -*- coding: utf-8 -*-
"""Tests del verificador de Alfresco (``src/alfresco_mcp/verifier.py``)."""

from alfresco_mcp.gateway import AlfrescoGateway
from alfresco_mcp.verifier import (
    MOTIVO_CARPETA,
    MOTIVO_EXPEDIENTE,
    elegir_carpeta,
    numero_y_pad,
    verificar_contrato,
)


class FakeGateway(AlfrescoGateway):
    def __init__(self, carpetas=None, archivos=None, total=None):
        self._carpetas = carpetas or []
        self._archivos = archivos or []
        self._total = total if total is not None else len(self._archivos)

    def buscar_carpetas(self, numero, max_items=10):
        return list(self._carpetas)

    def listar_archivos(self, node_id, max_items=100):
        return {"archivos": list(self._archivos), "total": self._total}

    def obtener_nodo(self, node_id):
        return None

    def descargar(self, node_id, destino):
        return destino


def _docs():
    return [
        {"ID_DOC": "D190", "DOCUMENTO": "Informe de oportunidad",
         "CODIGO_FORMATO": "FCO.55", "ETAPA": "Precontractual - selección",
         "ALIAS": "FCO.55 Informe Oportunidad"},
        {"ID_DOC": "D027", "DOCUMENTO": "Solicitud de cotizaciones",
         "CODIGO_FORMATO": "FCO.57", "ETAPA": "Precontractual - selección",
         "ALIAS": "FCO.57 Solicitud Cotizaciones"},
    ]


def test_numero_y_pad():
    assert numero_y_pad("20-2026000003") == ("2026000003", "0020")
    assert numero_y_pad("270-2026000050") == ("2026000050", "0270")
    assert numero_y_pad("18-2026001182") == ("2026001182", "0018")
    assert numero_y_pad("") == ("", "")


def test_elegir_carpeta_estricto_y_laxo():
    estricto, ok = elegir_carpeta(
        [{"id": "a", "nombre": "0020_2026000003_9707"}], "2026000003", "0020"
    )
    assert ok is True and estricto["id"] == "a"

    lax, ok = elegir_carpeta(
        [{"id": "b", "nombre": "20_2026000068"}], "2026000068", "0020"
    )
    assert ok is False and lax["id"] == "b"

    vacio, ok = elegir_carpeta([{"id": "c", "nombre": "otra"}], "2026000068", "0020")
    assert vacio is None and ok is False


def test_verificar_contrato_encontrado():
    gateway = FakeGateway(
        carpetas=[{"id": "n1", "nombre": "0020_2026000003_9707", "es_carpeta": True}],
        archivos=[
            {"NOMBRE": "FCO.55_Informe.pdf", "ID": "d1",
             "FECHA_CREACION": "2026-01-29", "FECHA_MODIFICACION": "2026-01-29"},
        ],
    )
    res = verificar_contrato({"contrato": "20-2026000003"}, gateway, _docs())

    assert res["estado_alfresco"] == "ENCONTRADA"
    assert res["carpeta"] == "0020_2026000003_9707"
    assert res["node_id"] == "n1"
    assert res["cantidad_archivos"] == 1
    assert res["encontrados"] == 1 and res["faltantes"] == 1
    assert res["etapas"]["Precontractual - selección"] == (1, 2)

    ver = res["verificacion"]
    assert ver["NOMBRE EXPEDIENTE"] == "0020_2026000003_9707"
    assert ver["alfresco"] == "SI"
    assert ver["MOTIVO"] == ""
    assert ver["EXPEDIENTE_ENCONTRADO"] == "SI"

    fila = next(f for f in res["filas"] if f["ID_DOC"] == "D190")
    assert fila["ESTADO"] == "ENCONTRADO"
    assert fila["FECHA CREACIÓN/CARGA"] == "2026-01-29"


def test_verificar_contrato_carpeta_no_encontrada():
    gateway = FakeGateway(carpetas=[], archivos=[])
    res = verificar_contrato({"contrato": "20-2026009999"}, gateway, _docs())

    assert res["estado_alfresco"] == "NO SE EVIDENCIA"
    assert res["verificacion"]["MOTIVO"] == MOTIVO_CARPETA
    assert res["verificacion"]["alfresco"] == "NO"
    assert res["cantidad_archivos"] == 0
    assert res["faltantes"] == 2


def test_verificar_contrato_carpeta_sin_archivos():
    gateway = FakeGateway(
        carpetas=[{"id": "n2", "nombre": "0020_2026000004_9707", "es_carpeta": True}],
        archivos=[],
        total=0,
    )
    res = verificar_contrato({"contrato": "20-2026000004"}, gateway, _docs())

    assert res["verificacion"]["MOTIVO"] == MOTIVO_EXPEDIENTE
    assert res["verificacion"]["alfresco"] == "NO"


def test_verificar_contrato_pad_laxo_deja_descripcion():
    gateway = FakeGateway(
        carpetas=[{"id": "n3", "nombre": "20_2026000068", "es_carpeta": True}],
        archivos=[{"NOMBRE": "x.pdf", "ID": "d", "FECHA_CREACION": "", "FECHA_MODIFICACION": ""}],
    )
    res = verificar_contrato({"contrato": "20-2026000068"}, gateway, _docs())

    assert res["estado_alfresco"] == "ENCONTRADA"
    assert "pad estricto" in res["verificacion"]["DESCRIPCION"]


def test_verificar_contrato_regla_cierre_18():
    docs = [
        {"ID_DOC": "D226", "DOCUMENTO": "Acta de finalización", "CODIGO_FORMATO": "FCO.66",
         "ETAPA": "Cierre y liquidación", "ALIAS": "FCO.66 Acta Finalizacion"},
    ]
    gateway = FakeGateway(
        carpetas=[{"id": "n4", "nombre": "0018_2026001515_7810", "es_carpeta": True}],
        archivos=[{"NOMBRE": "FCO.74_Acta_Pago_Final.pdf", "ID": "d",
                   "FECHA_CREACION": "", "FECHA_MODIFICACION": ""}],
    )
    res = verificar_contrato(
        {"contrato": "18-2026001515", "contratista": "ACME LTDA"},
        gateway, docs, es_tipo_18=True,
    )
    assert res["filas"][0]["ESTADO"] == "NO APLICA"
    assert res["esperados"] == 0
