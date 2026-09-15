# -*- coding: utf-8 -*-
"""Pruebas de persistencia segura de credenciales de Alfresco."""

import sys
import types

import config


def test_guardar_y_cargar_credenciales_alfresco(tmp_path, monkeypatch):
    almacen = {}
    fake_keyring = types.SimpleNamespace(
        set_password=lambda servicio, usuario, clave: almacen.__setitem__((servicio, usuario), clave),
        get_password=lambda servicio, usuario: almacen.get((servicio, usuario)),
        delete_password=lambda servicio, usuario: almacen.pop((servicio, usuario), None),
    )
    monkeypatch.setitem(sys.modules, "keyring", fake_keyring)
    monkeypatch.setattr(config, "ARCHIVO_CONFIG_RUTAS", tmp_path / "config_rutas.json")
    for nombre in (
        "ALFRESCO_URL", "ALFRESCO_SHARE_URL", "ALFRESCO_USER", "ALFRESCO_SHARE_USER",
        "ALFRESCO_PASS", "ALFRESCO_SHARE_PASS",
    ):
        monkeypatch.delenv(nombre, raising=False)

    config.guardar_credenciales_alfresco(
        "https://alfresco.test/share/page", "cliente", "secreto",
    )
    datos = config.credenciales_alfresco()

    assert datos["url"] == "https://alfresco.test/share/page"
    assert datos["usuario"] == "cliente"
    assert datos["contrasena"] == "secreto"
