# -*- coding: utf-8 -*-
"""Test de la limpieza de salidas (``src/utils/limpieza.py``)."""

import utils.limpieza as lim


def test_limpiar_salidas_conserva_entregables(tmp_path, monkeypatch):
    interno = tmp_path / "_interno"
    interno.mkdir()
    (interno / "02_Consolidado_General.csv").write_text("x", encoding="utf-8")
    (interno / "06_Verificacion_Alfresco.csv").write_text("x", encoding="utf-8")

    resultados = tmp_path / "resultados"
    resultados.mkdir()
    (resultados / "Auditoria_Contratos.xlsx").write_bytes(b"x")
    (resultados / "Informe_Auditoria_Contrato.html").write_text("x", encoding="utf-8")
    (resultados / "viejo_sobrante.csv").write_text("x", encoding="utf-8")

    monkeypatch.setattr(lim, "INTERNO_DIR", interno)
    monkeypatch.setattr(lim, "RESULTADOS_DIR", resultados)

    resumen = lim.limpiar_salidas()

    assert list(interno.iterdir()) == []
    nombres = {p.name for p in resultados.iterdir()}
    assert nombres == {"Auditoria_Contratos.xlsx", "Informe_Auditoria_Contrato.html"}
    assert resumen["eliminados"] == 3
