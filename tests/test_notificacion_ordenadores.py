# -*- coding: utf-8 -*-
"""Tests de la notificación a ordenadores (``src/auditoria_documental/notificacion.py``)."""

from auditoria_documental import notificacion


def _resultados():
    return [
        {"contrato": "20-A", "estado_alfresco": "NO SE EVIDENCIA",
         "correo_ordenador": "juan@uis.edu.co", "ordenador": "JUAN PEREZ"},
        {"contrato": "20-B", "estado_alfresco": "NO SE EVIDENCIA",
         "correo_ordenador": "juan@uis.edu.co", "ordenador": "JUAN PEREZ"},
        {"contrato": "20-C", "estado_alfresco": "NO SE EVIDENCIA",
         "correo_ordenador": "", "ordenador": "MARIA GOMEZ"},
        {"contrato": "20-D", "estado_alfresco": "ENCONTRADA",
         "correo_ordenador": "pedro@uis.edu.co", "ordenador": "PEDRO"},
    ]


def test_destinatarios_agrupa_sin_carpeta_con_correo():
    destinos = notificacion.destinatarios(_resultados())
    assert len(destinos) == 1
    assert destinos[0]["correo"] == "juan@uis.edu.co"
    assert destinos[0]["contratos"] == ["20-A", "20-B"]


def test_resumen():
    resumen = notificacion.resumen(_resultados())
    assert resumen == {"sin_carpeta": 3, "con_correo": 2, "sin_correo": 1, "destinatarios": 1}


def test_construir_mensajes():
    mensajes = notificacion.construir_mensajes(_resultados())
    assert len(mensajes) == 1
    assert mensajes[0]["para"] == "juan@uis.edu.co"
    assert "20-A" in mensajes[0]["cuerpo"] and "20-B" in mensajes[0]["cuerpo"]
    assert "JUAN PEREZ" in mensajes[0]["cuerpo"]


def test_enviar_sin_autorizacion_no_envia():
    llamadas = []

    def spy(smtp, mensaje):
        llamadas.append(mensaje["para"])
        return True

    resumen = notificacion.enviar(_resultados(), autorizado=False, enviar_fn=spy)

    assert resumen["autorizado"] is False
    assert resumen["enviados"] == 0
    assert llamadas == []


def test_enviar_con_autorizacion_envia():
    llamadas = []

    def spy(smtp, mensaje):
        llamadas.append(mensaje["para"])
        return True

    resumen = notificacion.enviar(
        _resultados(),
        autorizado=True,
        smtp={"user": "u", "from": "f@uis.edu.co"},
        enviar_fn=spy,
    )

    assert resumen["autorizado"] is True
    assert resumen["enviados"] == 1
    assert llamadas == ["juan@uis.edu.co"]


def test_enviar_sin_smtp_configurado():
    resumen = notificacion.enviar(_resultados(), autorizado=True, smtp={"user": "", "from": ""})
    assert resumen["autorizado"] is True
    assert resumen["enviados"] == 0
    assert "SMTP" in resumen["detalle"]


def test_resultados_desde_excel(tmp_path):
    import openpyxl

    ruta = tmp_path / "Auditoria_Contratos.xlsx"
    libro = openpyxl.Workbook()
    hoja = libro.active
    hoja.title = "DIAGNOSTICO"
    hoja.append(["CONTRATO", "CARPETA ENCONTRADA", "SUPERVISOR / DESTINATARIO", "CORREO ORDENADOR"])
    hoja.append(["20-A", "No encontrada", "JUAN PEREZ", "juan@uis.edu.co"])
    hoja.append(["20-B", "Encontrada", "MARIA GOMEZ", "maria@uis.edu.co"])
    libro.save(ruta)

    resultados = notificacion.resultados_desde_excel(str(ruta))

    assert len(resultados) == 2
    assert resultados[0]["contrato"] == "20-A"
    assert resultados[0]["estado_alfresco"] == "NO SE EVIDENCIA"
    assert resultados[0]["correo_ordenador"] == "juan@uis.edu.co"
    assert resultados[1]["estado_alfresco"] == "ENCONTRADA"
    assert len(notificacion.destinatarios(resultados)) == 1
