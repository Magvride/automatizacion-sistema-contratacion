# -*- coding: utf-8 -*-
"""Tests de la migración de la GUI desktop al backend MCP (sin PyQt)."""

from desktop.core.documentos import documentos
from desktop.core.pipeline import ETAPAS, EtlPipeline


def test_etapas_migradas():
    assert [etapa.id for etapa in ETAPAS] == [
        "base",
        "consolidar",
        "alfresco",
        "notificacion",
    ]


def test_documentos_migrados():
    assert [doc.id for doc in documentos()] == ["nuevas_versiones", "diccionario"]


def test_pipeline_tiene_metodo_por_etapa():
    for etapa in ETAPAS:
        assert hasattr(EtlPipeline, f"_{etapa.id}"), etapa.id


def test_args_usan_backend_mcp():
    pipeline = EtlPipeline(
        {},
        on_etapa=lambda *a: None,
        on_progreso=lambda *a: None,
    )
    args = pipeline._args()
    assert args.backend_alfresco == "mcp"
    assert hasattr(args, "ruta_diccionario")
