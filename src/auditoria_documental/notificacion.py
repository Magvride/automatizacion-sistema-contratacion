# -*- coding: utf-8 -*-
"""
Notificación a los ordenadores de gasto de los contratos **sin carpeta** en Alfresco.

Selecciona los contratos cuyo expediente no fue encontrado en Alfresco, agrupa
por correo del ordenador y arma un correo por destinatario.

**Autorización previa:** el envío masivo es una acción sensible. La función
``enviar`` **no envía nada** si ``autorizado`` no es ``True``; así el envío
siempre pasa por una confirmación explícita (por ejemplo, un diálogo en la GUI).
"""

import os
import re
import smtplib
from email.message import EmailMessage

from utils.logger import configurar_logger

logger = configurar_logger("notificacion")

ASUNTO_POR_DEFECTO = "Expedientes pendientes de cargar en el repositorio (Alfresco)"
PLANTILLA_POR_DEFECTO = (
    "Cordial saludo, {ordenador}.\n\n"
    "Le informamos que los siguientes contratos a su cargo tienen pendientes en "
    "el repositorio documental (Alfresco):\n\n"
    "{contratos}\n\n"
    "Le solicitamos gestionar la creación o el cargue del expediente.\n\n"
    "División de Contratación\nUniversidad Industrial de Santander"
)


def _variable(nombre: str, predeterminado: str = "") -> str:
    return os.getenv(nombre, predeterminado).strip()


def _render(texto: str, valores: dict) -> str:
    return re.sub(r"\{(\w+)\}", lambda m: str(valores.get(m.group(1), m.group(0))), texto)


def correo_valido(valor) -> str:
    """Devuelve el primer correo válido de una celda (limpia listas 'a@x, b@y')."""
    for parte in re.split(r"[,;]", str(valor or "")):
        parte = parte.strip()
        if "@" in parte:
            return parte
    return ""


def _pendientes(resultados) -> list:
    return [
        r for r in (resultados or [])
        if str(r.get("estado_alfresco", "")).upper() != "ENCONTRADA"
        or str(r.get("faltantes", "0")).strip() not in ("", "0")
    ]


def destinatarios(resultados) -> list:
    """Agrupa por correo del ordenador los contratos sin carpeta con correo."""
    grupos = {}
    for resultado in _pendientes(resultados):
        correo = correo_valido(resultado.get("correo_ordenador", ""))
        if not correo:
            continue
        ordenador = str(resultado.get("ordenador", "") or resultado.get("supervisor", "")).strip()
        grupo = grupos.setdefault(correo, {"correo": correo, "ordenador": ordenador, "contratos": []})
        if not grupo["ordenador"] and ordenador:
            grupo["ordenador"] = ordenador
        faltantes = str(resultado.get("listado_faltantes", "")).strip()
        contrato = str(resultado.get("contrato", ""))
        grupo["contratos"].append(f"{contrato} ({faltantes})" if faltantes else contrato)
    return [grupos[clave] for clave in sorted(grupos)]


def resumen(resultados) -> dict:
    """Cuenta cuántos contratos sin carpeta tienen y no tienen correo."""
    sin = _pendientes(resultados)
    con_correo = sum(1 for r in sin if correo_valido(r.get("correo_ordenador", "")))
    return {
        "sin_carpeta": len(sin),
        "con_correo": con_correo,
        "sin_correo": len(sin) - con_correo,
        "destinatarios": len(destinatarios(resultados)),
    }


def resultados_desde_excel(ruta: str) -> list:
    """Lee la hoja ``DIAGNOSTICO`` de ``Auditoria_Contratos.xlsx``.

    Devuelve los contratos en el formato que consume este módulo
    (``contrato``, ``estado_alfresco``, ``correo_ordenador``, ``ordenador``).
    """
    import openpyxl

    if not ruta or not os.path.isfile(ruta):
        return []

    libro = openpyxl.load_workbook(ruta, data_only=True, read_only=True)
    try:
        hoja = libro["DIAGNOSTICO"] if "DIAGNOSTICO" in libro.sheetnames else libro.active
        filas = list(hoja.iter_rows(values_only=True))
    finally:
        libro.close()

    indices = None
    inicio = 0
    for i, fila in enumerate(filas[:12]):
        claves = {str(c).strip().upper() for c in fila if c is not None}
        if "CONTRATO" in claves:
            indices = {str(c).strip().upper(): j for j, c in enumerate(fila) if c is not None}
            inicio = i + 1
            break
    if not indices:
        return []

    def valor(fila, nombre):
        j = indices.get(nombre)
        if j is None or j >= len(fila) or fila[j] is None:
            return ""
        return str(fila[j]).strip()

    resultados = []
    for fila in filas[inicio:]:
        contrato = valor(fila, "CONTRATO")
        if not contrato:
            continue
        encontrada = valor(fila, "CARPETA ENCONTRADA").upper().startswith("ENCONTRADA")
        resultados.append(
            {
                "contrato": contrato,
                "estado_alfresco": "ENCONTRADA" if encontrada else "NO SE EVIDENCIA",
                "correo_ordenador": valor(fila, "CORREO ORDENADOR"),
                "ordenador": valor(fila, "SUPERVISOR / DESTINATARIO"),
                "faltantes": valor(fila, "DOCS FALTANTES"),
                "listado_faltantes": valor(fila, "LISTADO DE FALTANTES"),
            }
        )
    return resultados


def construir_mensajes(resultados, asunto: str = "", plantilla: str = "") -> list:
    """Construye un correo por ordenador con la lista de sus contratos sin carpeta."""
    asunto = asunto or _variable("NOTIFICAR_ASUNTO", ASUNTO_POR_DEFECTO)
    plantilla = plantilla or _variable("NOTIFICAR_PLANTILLA", PLANTILLA_POR_DEFECTO)

    mensajes = []
    for destino in destinatarios(resultados):
        contratos = destino["contratos"]
        valores = {
            "ordenador": destino["ordenador"],
            "contratos": "\n".join(f"  - {c}" for c in contratos),
            "contrato": ", ".join(contratos),
        }
        mensajes.append(
            {
                "para": destino["correo"],
                "ordenador": destino["ordenador"],
                "contratos": contratos,
                "asunto": _render(asunto, valores),
                "cuerpo": _render(plantilla, valores),
            }
        )
    return mensajes


def _smtp_config() -> dict:
    return {
        "host": _variable("SMTP_HOST", "smtp.uis.edu.co"),
        "port": int(_variable("SMTP_PORT", "587") or 587),
        "user": _variable("SMTP_USER"),
        "pass": _variable("SMTP_PASS"),
        "from": _variable("SMTP_FROM", _variable("SMTP_USER")),
        "tls": _variable("SMTP_TLS", "1") not in ("0", "false", "False"),
    }


def _enviar_smtp(smtp: dict, mensaje: dict) -> bool:
    email = EmailMessage()
    email["From"] = smtp["from"]
    email["To"] = mensaje["para"]
    email["Subject"] = mensaje["asunto"]
    email.set_content(mensaje["cuerpo"], charset="utf-8")
    try:
        with smtplib.SMTP(smtp["host"], smtp["port"], timeout=30) as servidor:
            servidor.ehlo()
            if smtp.get("tls", True):
                servidor.starttls()
                servidor.ehlo()
            if smtp["user"]:
                servidor.login(smtp["user"], smtp["pass"])
            servidor.send_message(email)
        return True
    except Exception as exc:  # noqa: BLE001
        logger.error("No se pudo enviar a %s: %s", mensaje["para"], exc)
        return False


def enviar(
    resultados,
    autorizado: bool = False,
    mensajes: list = None,
    smtp: dict = None,
    enviar_fn=None,
) -> dict:
    """Envía los correos **solo si** ``autorizado`` es ``True``.

    Devuelve un resumen. Si no está autorizado, no envía nada.
    ``enviar_fn(smtp, mensaje)`` es inyectable para pruebas.
    """
    if mensajes is None:
        mensajes = construir_mensajes(resultados)

    if not autorizado:
        logger.warning("Envío cancelado: se requiere autorización explícita.")
        return {
            "autorizado": False,
            "total": len(mensajes),
            "enviados": 0,
            "detalle": "Se requiere autorización explícita antes del envío masivo.",
        }

    if not mensajes:
        return {"autorizado": True, "total": 0, "enviados": 0, "detalle": "No hay correos por enviar."}

    smtp = smtp or _smtp_config()
    if not smtp.get("user") or not smtp.get("from"):
        return {
            "autorizado": True,
            "total": len(mensajes),
            "enviados": 0,
            "detalle": "Faltan SMTP_USER/SMTP_FROM en .env para enviar.",
        }

    enviar_fn = enviar_fn or _enviar_smtp
    enviados = sum(1 for mensaje in mensajes if enviar_fn(smtp, mensaje))
    logger.info("Enviados %d/%d correos.", enviados, len(mensajes))
    return {
        "autorizado": True,
        "total": len(mensajes),
        "enviados": enviados,
        "detalle": f"Enviados {enviados}/{len(mensajes)}.",
    }
