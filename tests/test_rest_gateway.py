# -*- coding: utf-8 -*-
"""Tests del gateway REST de Alfresco (``src/alfresco_mcp/rest_gateway.py``)."""

from alfresco_mcp.rest_gateway import RestAlfrescoGateway


class FakeResponse:
    def __init__(self, status_code=200, payload=None, content=b""):
        self.status_code = status_code
        self._payload = payload if payload is not None else {}
        self.content = content

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class FakeSession:
    def __init__(self, get_map=None, post_map=None):
        self.get_map = get_map or {}
        self.post_map = post_map or {}
        self.llamadas = []
        self.cerrada = False

    def get(self, url, params=None, **kwargs):
        self.llamadas.append(("GET", url, params))
        return self.get_map.get(url, FakeResponse(404))

    def post(self, url, json=None, **kwargs):
        self.llamadas.append(("POST", url, json))
        return self.post_map.get(url, FakeResponse(404))

    def close(self):
        self.cerrada = True


def test_recorta_sufijo_share():
    gateway = RestAlfrescoGateway("https://gesdoc.uis.edu.co/share/page", "u", "p")
    assert gateway.base == "https://gesdoc.uis.edu.co"
    assert gateway.api.endswith("/public/alfresco/versions/1")


def test_buscar_carpetas():
    gateway = RestAlfrescoGateway("https://x", "u", "p", session=FakeSession())
    url = f"{gateway.search_api}/search"
    gateway.session.post_map[url] = FakeResponse(
        200,
        {
            "list": {
                "entries": [
                    {"entry": {"id": "a", "name": "0020_2026000003_9707",
                               "isFolder": True, "nodeType": "td:carpeta"}}
                ]
            }
        },
    )
    candidatas = gateway.buscar_carpetas("2026000003")
    assert candidatas == [
        {"id": "a", "nombre": "0020_2026000003_9707", "es_carpeta": True, "tipo": "td:carpeta"}
    ]


def test_listar_archivos_pagina_y_total():
    gateway = RestAlfrescoGateway("https://x", "u", "p", session=FakeSession())
    url = f"{gateway.api}/nodes/n1/children"
    gateway.session.get_map[url] = FakeResponse(
        200,
        {
            "list": {
                "entries": [
                    {"entry": {"id": "d1", "name": "f1.pdf",
                               "createdAt": "2026-01-01", "modifiedAt": "2026-01-02"}}
                ],
                "pagination": {"count": 7},
            }
        },
    )
    listado = gateway.listar_archivos("n1", max_items=100)
    assert listado["total"] == 7
    assert listado["archivos"][0]["NOMBRE"] == "f1.pdf"
    assert listado["archivos"][0]["FECHA_CREACION"] == "2026-01-01"


def test_obtener_nodo_404():
    gateway = RestAlfrescoGateway("https://x", "u", "p", session=FakeSession())
    assert gateway.obtener_nodo("nope") is None


def test_descargar(tmp_path):
    gateway = RestAlfrescoGateway("https://x", "u", "p", session=FakeSession())
    url = f"{gateway.api}/nodes/n1/content"
    gateway.session.get_map[url] = FakeResponse(200, content=b"PDFDATA")
    destino = str(tmp_path / "doc.pdf")
    gateway.descargar("n1", destino)
    with open(destino, "rb") as archivo:
        assert archivo.read() == b"PDFDATA"


def test_auth_por_ticket():
    session = FakeSession()
    session.post_map[f"https://x/alfresco/api/-default-/public/authentication/versions/1/tickets"] = (
        FakeResponse(200, {"entry": {"id": "TICKET123"}})
    )
    session.post_map["https://x/alfresco/api/-default-/public/search/versions/1/search"] = (
        FakeResponse(200, {"list": {"entries": []}})
    )
    gateway = RestAlfrescoGateway("https://x", "u", "p", session=session, auth_method="ticket")
    gateway.buscar_carpetas("2026000003")

    primera = session.llamadas[0]
    assert primera[0] == "POST"
    assert primera[1].endswith("/authentication/versions/1/tickets")


def test_cerrar_cierra_sesion():
    session = FakeSession()
    gateway = RestAlfrescoGateway("https://x", "u", "p", session=session)
    gateway.cerrar()
    assert session.cerrada is True
