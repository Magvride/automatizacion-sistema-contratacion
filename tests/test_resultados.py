# -*- coding: utf-8 -*-
"""Tests de compatibilidad de ``_estado()`` (flujo legado y flujo sin UISARD)."""

from resultados import _estado


def test_estado_flujo_legado_con_uisard():
    assert _estado("NO", "SI") == "NO ESTA EN UISARD"
    assert _estado("SI", "SI") == "EN UISARD - CON ARCHIVOS"
    assert _estado("SI", "NO") == "EN UISARD - SIN ARCHIVOS"
    assert _estado("SI", "") == "EN UISARD - PENDIENTE"


def test_estado_flujo_sin_uisard():
    assert _estado("", "SI") == "EN ALFRESCO - CON ARCHIVOS"
    assert _estado("", "NO") == "EN ALFRESCO - SIN ARCHIVOS"
    assert _estado("", "") == "PENDIENTE"
