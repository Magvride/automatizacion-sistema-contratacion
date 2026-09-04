# -*- coding: utf-8 -*-
"""
Notificación a ordenadores de gasto con contratos NO registrados en UISARD.

Lee ``archivos/resultados/contratos_unificados.csv`` (o el CSV que indique ``main.py``),
busca los registros cuya columna ``uisard`` es ``NO``, agrupa por ``correo_ordenador`` y
arma un correo por destinatario con la plantilla configurable.

Modo simulación (por defecto): no envía correos. Arma los mensajes, los escribe a un
archivo de borradores (``borradores_correos_uisard.txt``) y los registra en log.
Para enviar de verdad use ``--enviar-correos`` (o llame con ``enviar=True``).

La plantilla se lee de ``NOTIFICAR_PLANTILLA`` en el .env; admite los campos
{ordenador}, {contrato} y {centro_costo}. Por defecto:

   Señor {ordenador}, no ha subido los contratos {contrato} del centro de costo {centro_costo}.
"""

import os
import re
from pathlib import Path

import pandas as pd

from utils.logger import configurar_logger

logger = configurar_logger("notificacion")

from config import RESULTADOS_DIR

# Columnas que necesita el módulo.
COLUMNA_UISARD = "uisard"
COLUMNA_ORDENADOR = "ordenador"
COLUMNA_CORREO = "correo_ordenador"
COLUMNA_CONTRATO = "contrato"
COLUMNA_CENTRO = "centro_costo"

PLANTILLA_POR_DEFECTO = (
    "Señor {ordenador}, no ha subido los contratos {contrato} "
    "del centro de costo {centro_costo}."
)

ASUNTO_POR_DEFECTO = "Contratos no registrados en UISARD"


def _variable(nombre: str, predeterminado: str = "") -> str:
    return os.getenv(nombre, predeterminado).strip()


def _permiso_envio() -> bool:
    """True si se permite el envío real (por entorno)."""
    return _variable("NOTIFICAR_ENVIAR", "0") in ("1", "true", "True", "yes", "si", "sí")


def _celda(fila, columna: str) -> str:
    try:
        valor = fila[columna]
    except KeyError:
        return ""
    if pd.isna(valor):
        return ""
    return str(valor).strip()


def _normalizar_correo(correo: str) -> str:
    """Devuelve el primer correo válido (limpiando la lista 'a@x, b@y')."""
    for parte in re.split(r"[,;]", correo):
        parte = parte.strip()
        if "@" in parte:
            return parte
    return ""


def _formatear_plantilla(plantilla: str, fila) -> str:
    """Rellena la plantilla con los campos de una fila."""
    campos = {
        "ordenador": _celda(fila, COLUMNA_ORDENADOR),
        "contrato": _celda(fila, COLUMNA_CONTRATO),
        "centro_costo": _celda(fila, COLUMNA_CENTRO),
    }
    match_llaves = re.compile(r"{(\w+)}")

    def reemplazo(m):
        return campos.get(m.group(1), m.group(0))

    return match_llaves.sub(reemplazo, plantilla)


def _construir_cuerpo(plantilla: str, filas: list) -> str:
    """Arma el cuerpo del correo con un saludo y una lista de contratos.

    Si hay un solo contrato, usa la plantilla tal cual. Con varios, el saludo
    aparece una sola vez y los contratos se listan a continuación.
    """
    lineas = [_formatear_plantilla(plantilla, fila) for fila in filas]

    if len(lineas) == 1:
        return lineas[0]

    # Separar el saludo ("Señor X,") del resto para no repetirlo.
    saludo_match = re.match(r"^(Se[ñn]or[^,]*),", lineas[0])
    if not saludo_match:
        return "\n".join(lineas)

    saludo = saludo_match.group(1) + ","
    partes = []
    for linea in lineas:
        _, despues = linea.split(",", 1)
        partes.append("  - " + despues.strip())
    return saludo + "\n" + "\n".join(partes)


def _construir_mensajes(df: pd.DataFrame, plantilla: str) -> list:
    """Agrupa los contratos por correo y devuelve una lista de mensajes."""
    mensajes = []
    agrupados = {}

    for _, fila in df.iterrows():
        correo = _normalizar_correo(_celda(fila, COLUMNA_CORREO))
        if not correo:
            logger.info("Sin correo para %s; se salta.", _celda(fila, COLUMNA_ORDENADOR))
            continue

        agrupados.setdefault(correo, {"filas": [], "ordenadores": set()})
        agrupados[correo]["filas"].append(fila)
        ordenador = _celda(fila, COLUMNA_ORDENADOR)
        if ordenador:
            agrupados[correo]["ordenadores"].add(ordenador)

    for correo, data in sorted(agrupados.items()):
        cuerpo = _construir_cuerpo(plantilla, data["filas"])
        asunto = ASUNTO_POR_DEFECTO
        mensajes.append({
            "para": correo,
            "ordenadores": sorted(data["ordenadores"]),
            "asunto": asunto,
            "cuerpo": cuerpo,
        })

    return mensajes


def _enviar(smtp: dict, msj: dict) -> bool:
    """Envía un mensaje real vía SMTP (Outlook/Exchange)."""
    import smtplib
    from email.message import EmailMessage

    mensaje = EmailMessage()
    mensaje["From"] = smtp["from"]
    mensaje["To"] = msj["para"]
    mensaje["Subject"] = msj["asunto"]
    mensaje.set_content(msj["cuerpo"], charset="utf-8")

    try:
        with smtplib.SMTP(smtp["host"], smtp["port"], timeout=30) as servidor:
            servidor.ehlo()
            if smtp.get("tls", True):
                servidor.starttls()
                servidor.ehlo()
            if smtp["user"]:
                servidor.login(smtp["user"], smtp["pass"])
            servidor.send_message(mensaje)
        return True
    except Exception as exc:  # noqa: BLE001
        logger.error("No se pudo enviar a %s: %s", msj["para"], exc)
        return False


def _guardar_borradores(msj_list: list, ruta: Path) -> None:
    """Escribe los mensajes a un archivo de borradores legible."""
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with open(ruta, "w", encoding="utf-8") as f:
        for msj in msj_list:
            f.write("=" * 60 + "\n")
            f.write(f"PARA: {msj['para']}\n")
            f.write(f"ASUNTO: {msj['asunto']}\n")
            f.write("-" * 60 + "\n")
            f.write(msj["cuerpo"] + "\n\n")
    logger.info("Borradores guardados en: %s", ruta)


def notificar_no_uisard(ruta_csv=None, plantilla=None, enviar=False, borradores=None) -> dict:
    """Genera y (opcionalmente) envía correos de contratos no registrados en UISARD.

    Devuelve un resumen: total registros revisados, sin_uisard, con_correo,
    sin_correo, y mensajes construidos.
    """
    ruta_csv = str(ruta_csv or (RESULTADOS_DIR / "contratos_unificados.csv"))
    plantilla = plantilla or _variable("NOTIFICAR_PLANTILLA", PLANTILLA_POR_DEFECTO)
    enviar = enviar or _permiso_envio()
    borradores = borradores or (RESULTADOS_DIR / "borradores_correos_uisard.txt")

    if not os.path.isfile(ruta_csv):
        logger.warning("No existe %s; no se puede notificar.", ruta_csv)
        return {"total": 0, "sin_uisard": 0, "con_correo": 0, "sin_correo": 0, "mensajes": 0}

    df = pd.read_csv(ruta_csv, encoding="utf-8-sig", dtype=str).fillna("")

    if COLUMNA_UISARD not in df.columns:
        logger.warning("El CSV %s no tiene la columna '%s'.", ruta_csv, COLUMNA_UISARD)
        return {"total": len(df), "sin_uisard": 0, "con_correo": 0, "sin_correo": 0, "mensajes": 0}

    total = len(df)
    sin_uisard = df[df[COLUMNA_UISARD].astype(str).str.strip().str.upper() == "NO"]

    mensajes = _construir_mensajes(sin_uisard, plantilla)

    con_correo = len(mensajes)
    sin_correo = len(sin_uisard) - sin_uisard.apply(
        lambda r: bool(_normalizar_correo(_celda(r, COLUMNA_CORREO))), axis=1
    ).sum()

    logger.info(
        "Notificación: %d registros | %d sin UISARD | %d con correo | %d sin correo",
        total, len(sin_uisard), con_correo, sin_correo,
    )

    if mensajes:
        _guardar_borradores(mensajes, Path(borradores))

    if enviar:
        smtp = {
            "host": _variable("SMTP_HOST", "smtp.uis.edu.co"),
            "port": int(_variable("SMTP_PORT", "587") or 587),
            "user": _variable("SMTP_USER"),
            "pass": _variable("SMTP_PASS"),
            "from": _variable("SMTP_FROM", _variable("SMTP_USER")),
            "tls": _variable("SMTP_TLS", "1") not in ("0", "false", "False"),
        }
        if not smtp["user"] or not smtp["from"]:
            logger.error("Faltan SMTP_USER/SMTP_FROM en .env para enviar correos.")
            enviados = 0
        else:
            enviados = 0
            for msj in mensajes:
                if _enviar(smtp, msj):
                    enviados += 1
            logger.info("Enviados %d/%d correos.", enviados, len(mensajes))
    else:
        logger.info("Modo simulación: no se enviaron correos. Use --enviar-correos para enviar.")

    return {
        "total": total,
        "sin_uisard": len(sin_uisard),
        "con_correo": con_correo,
        "sin_correo": int(sin_correo),
        "mensajes": len(mensajes),
    }


if __name__ == "__main__":
    print("Este script forma parte del flujo. Ejecuta: python main.py")
    import sys
    sys.exit(0)
