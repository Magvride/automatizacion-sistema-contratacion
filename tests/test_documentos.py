# -*- coding: utf-8 -*-
"""Tests de la carga de documentos de entrada (``desktop/core/documentos.py``)."""

from pathlib import Path

import desktop.core.documentos as docs
from desktop.core.documentos import DocumentoEntrada


def test_filtro_incluye_xls():
    documento = DocumentoEntrada(
        "nuevas_versiones", "Nuevas", "", Path("."),
        "contratos_{fecha}{ext}", "contratos_*", (".xlsx", ".xls"),
    )
    assert "*.xlsx" in documento.filtro
    assert "*.xls" in documento.filtro


def test_preparar_entradas_convierte_xls(tmp_path, monkeypatch):
    contratos_dir = tmp_path / "contratos"
    raw_dir = tmp_path / "raw"
    monkeypatch.setattr(
        docs,
        "_DOCUMENTOS",
        (
            DocumentoEntrada(
                "nuevas_versiones", "Nuevas", "", contratos_dir,
                "contratos_{fecha}{ext}", "contratos_*", (".xlsx", ".xls"),
            ),
            DocumentoEntrada(
                "diccionario", "Diccionario", "", raw_dir,
                "Diccionario_Documentos.xlsx", "Diccionario_Documentos.xlsx", (".xlsx",),
            ),
        ),
    )

    origen_xls = tmp_path / "reporte.xls"
    origen_xls.write_bytes(b"\xd0\xcf\x11\xe0 dummy xls")
    origen_dic = tmp_path / "Diccionario_Documentos.xlsx"
    origen_dic.write_bytes(b"dummy xlsx")

    llamadas = []

    def fake_convertir(origen, destino):
        llamadas.append((origen, str(destino)))
        Path(destino).write_bytes(b"xlsx convertido")

    monkeypatch.setattr(docs, "_convertir_xls_a_xlsx", fake_convertir)

    copiados = docs.preparar_entradas(
        {"nuevas_versiones": str(origen_xls), "diccionario": str(origen_dic)}
    )

    assert llamadas, "se debió convertir el .xls"
    assert llamadas[0][1].endswith(".xlsx")

    destinos = [Path(c) for c in copiados]
    nuevas = next(d for d in destinos if d.parent == contratos_dir)
    assert nuevas.suffix == ".xlsx"
    assert nuevas.name.startswith("contratos_")

    diccionario = next(d for d in destinos if d.parent == raw_dir)
    assert diccionario.name == "Diccionario_Documentos.xlsx"
    assert diccionario.read_bytes() == b"dummy xlsx"


def test_preparar_entradas_no_borra_origen_igual_al_destino(tmp_path, monkeypatch):
    """El archivo seleccionado no debe borrarse si ya está en la carpeta destino."""
    destino = tmp_path / "Diccionario_Documentos.xlsx"
    destino.write_bytes(b"contenido")
    nv = tmp_path / "reporte.xlsx"
    nv.write_bytes(b"xlsx")

    monkeypatch.setattr(
        docs,
        "_DOCUMENTOS",
        (
            DocumentoEntrada(
                "nuevas_versiones", "N", "", tmp_path,
                "contratos_{fecha}{ext}", "contratos_*", (".xlsx", ".xls"),
            ),
            DocumentoEntrada(
                "diccionario", "D", "", tmp_path,
                "Diccionario_Documentos.xlsx", "Diccionario_Documentos.xlsx", (".xlsx",),
            ),
        ),
    )

    copiados = docs.preparar_entradas(
        {"nuevas_versiones": str(nv), "diccionario": str(destino)}
    )

    assert destino.is_file()
    assert destino.read_bytes() == b"contenido"
    assert any(Path(c).name == "Diccionario_Documentos.xlsx" for c in copiados)
