# -*- coding: utf-8 -*-
"""Tests de los borradores de correo (``src/auditoria_documental/correos.py``)."""

import openpyxl

from auditoria_documental.correos import (
    cargar_plantillas,
    construir_mensajes,
    escribir_borradores,
    escribir_borradores_excel,
    renderizar,
)


def _workbook_correos(tmp_path):
    ruta = tmp_path / "Matriz_Documentos_por_Clase.xlsx"
    libro = openpyxl.Workbook()
    hoja = libro.active
    hoja.title = "CORREOS"
    filas = [
        ["PROFORMAS DE CORREO", None],
        ["Campos entre llaves dobles", None],
        [None, None],
        ["CAMPOS DE COMBINACIÓN", None],
        ["{{CONTRATO}}", "Columna CONTRATO"],
        [None, None],
        ["1. SOLICITUD DE DOCUMENTACIÓN FALTANTE", None],
        ["Cuándo se envía", "Cuando el ESTADO es Incompleto."],
        ["Para", "Supervisor del contrato ({{SUPERVISOR}})."],
        ["Asunto", "Solicitud de documentación faltante. Contrato {{CONTRATO}}"],
        ["Cuerpo", "Cordial saludo, {{SUPERVISOR}}.\nFaltantes: {{LISTADO_FALTANTES}}. Completitud: {{PORCENTAJE}}. Enlace: {{ENLACE_CARPETA}}."],
        [None, None],
        ["3. CARPETA NO LOCALIZADA O NO DESCARGADA", None],
        ["Cuándo se envía", "Cuando la carpeta no se encuentra."],
        ["Para", "Auxiliar del equipo."],
        ["Asunto", "Carpeta no localizada en Alfresco. Contrato {{CONTRATO}}"],
        ["Cuerpo", "No fue posible localizar la carpeta del contrato {{CONTRATO}} ({{CLASE}})."],
        [None, None],
        ["4. EXPEDIENTE COMPLETO Y CONFORME", None],
        ["Cuándo se envía", "Cuando el ESTADO es Completo."],
        ["Para", "Supervisor del contrato."],
        ["Asunto", "Expediente completo. Contrato {{CONTRATO}}"],
        ["Cuerpo", "El expediente del contrato {{CONTRATO}} está completo."],
    ]
    for fila in filas:
        hoja.append(fila)
    libro.save(ruta)
    return str(ruta)


def _contrato_incompleto():
    return {
        "contrato": "20-2026000003",
        "cod": "20",
        "estado_alfresco": "ENCONTRADA",
        "node_id": "n1",
        "supervisor": "JUAN PEREZ",
        "correo_ordenador": "juan@uis.edu.co",
        "filas": [
            {"ID_DOC": "D190", "DOCUMENTO": "Informe oportunidad", "FORMATO": "FCO.55",
             "ESTADO": "ENCONTRADO", "ARCHIVO": "FCO.55.pdf"},
            {"ID_DOC": "D027", "DOCUMENTO": "Solicitud cotizaciones", "FORMATO": "FCO.57",
             "ESTADO": "FALTANTE", "ARCHIVO": ""},
        ],
    }


def _contrato_no_encontrado():
    return {
        "contrato": "20-2026009999",
        "cod": "20",
        "estado_alfresco": "NO SE EVIDENCIA",
        "filas": [],
    }


def test_renderizar():
    assert renderizar("Hola {{SUPERVISOR}}, {{NO_EXISTE}}!", {"SUPERVISOR": "JUAN"}) == "Hola JUAN, !"


def test_cargar_plantillas(tmp_path):
    plantillas = cargar_plantillas(_workbook_correos(tmp_path))
    assert len(plantillas) == 3
    assert plantillas[0]["titulo"] == "SOLICITUD DE DOCUMENTACIÓN FALTANTE"
    assert plantillas[0]["asunto"] == "Solicitud de documentación faltante. Contrato {{CONTRATO}}"
    assert "{{LISTADO_FALTANTES}}" in plantillas[0]["cuerpo"]


def test_construir_mensajes_selecciona_plantilla(tmp_path):
    plantillas = cargar_plantillas(_workbook_correos(tmp_path))
    mensajes = construir_mensajes(
        [_contrato_incompleto(), _contrato_no_encontrado()],
        plantillas,
        fecha_revision="2026-08-31",
    )
    assert len(mensajes) == 2

    faltante = mensajes[0]
    assert faltante["tipo"] == "SOLICITUD DE DOCUMENTACIÓN FALTANTE"
    assert "20-2026000003" in faltante["asunto"]
    assert "JUAN PEREZ" in faltante["cuerpo"]
    assert "FCO.57 Solicitud cotizaciones" in faltante["cuerpo"]
    assert "50.0%" in faltante["cuerpo"]

    no_loc = mensajes[1]
    assert no_loc["tipo"] == "CARPETA NO LOCALIZADA O NO DESCARGADA"


def test_escribir_borradores(tmp_path):
    plantillas = cargar_plantillas(_workbook_correos(tmp_path))
    mensajes = construir_mensajes([_contrato_incompleto()], plantillas)
    ruta = str(tmp_path / "10_Correos_Auditoria.txt")

    escribir_borradores(mensajes, ruta)

    with open(ruta, encoding="utf-8") as archivo:
        contenido = archivo.read()
    assert "PARA: JUAN PEREZ" in contenido
    assert "ASUNTO: Solicitud de documentación faltante. Contrato 20-2026000003" in contenido


def test_escribir_borradores_excel_para_power_automate(tmp_path):
    mensajes = [{
        "para": "JUAN PEREZ",
        "contrato": "20-2026000003",
        "correo": "juan@uis.edu.co",
        "asunto": "Solicitud de documentación faltante",
        "cuerpo": "Cordial saludo. Faltan documentos del contrato 20-2026000003.",
    }]
    ruta = str(tmp_path / "10_Correos_Auditoria.xlsx")

    escribir_borradores_excel(mensajes, ruta)

    libro = openpyxl.load_workbook(ruta)
    hoja = libro["Correos"]
    assert [celda.value for celda in hoja[1]] == ["CORREO", "ASUNTO", "CUERPO"]
    assert hoja.cell(row=2, column=1).value == "juan@uis.edu.co"
    assert hoja.cell(row=2, column=2).value == (
        "Cordial saludo, JUAN PEREZ. Documentación pendiente del contrato 20-2026000003"
    )
    assert "No se verificó" in hoja.cell(row=2, column=3).value
    assert "20-2026000003" in hoja.cell(row=2, column=3).value
    assert "verificación automática" not in hoja.cell(row=2, column=3).value.lower()
    assert hoja.tables["CorreosPowerAutomate"].ref == "A1:C2"
