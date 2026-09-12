# -*- coding: utf-8 -*-
"""
Servicio **Auditoría Documental Automatizada**.

Es el punto de entrada único del servicio: recibe los contratos, consulta el
repositorio documental (Alfresco) y genera todos los entregables.

Entregables (en ``carpeta_salida``):
    06_Verificacion_Alfresco.csv     resultado por expediente
    07_Expedientes_Faltantes.csv     solo los no encontrados
    Auditoria_Contratos.xlsx         informe Excel (resumen, etapas, diagnóstico)
    10_Correos_Auditoria.txt         borradores de correo
    Informe_Auditoria_Contrato.html  informe visual: qué tiene y qué le falta
"""

import os

from utils.logger import configurar_logger
from .correos import generar_borradores
from .informe_html import generar_informe

logger = configurar_logger("servicio_auditoria")

NOMBRE = "Auditoría Documental Automatizada"
DESCRIPCION = (
    "Revisa automáticamente cada expediente en el repositorio documental, "
    "confirma qué documentos obligatorios contiene y cuáles faltan según el tipo "
    "de contrato, y genera el informe detallado con los borradores de notificación."
)

SALIDAS = {
    "verificacion": "06_Verificacion_Alfresco.csv",
    "faltantes": "07_Expedientes_Faltantes.csv",
    "auditoria": "Auditoria_Contratos.xlsx",
    "correos": "10_Correos_Auditoria.txt",
    "informe": "Informe_Auditoria_Contrato.html",
}


def ejecutar_servicio(
    contratos,
    gateway,
    carpeta_salida: str,
    ruta_diccionario: str = "",
    periodo: str = "",
    fecha_revision: str = "",
    fecha_limite: str = "",
    on_progreso=None,
    on_resultado=None,
) -> dict:
    """Ejecuta el servicio completo y devuelve un resumen con las rutas.

    ``contratos`` puede ser un DataFrame o una lista de dicts con ``contrato``.
    ``gateway`` es el acceso al repositorio (REST o simulado).
    """
    from alfresco_mcp.motor import ejecutar_auditoria

    os.makedirs(carpeta_salida, exist_ok=True)
    resultados = []

    def _recoger(resultado):
        resultados.append(resultado)
        if on_resultado:
            on_resultado(resultado)

    resumen = ejecutar_auditoria(
        contratos,
        gateway,
        ruta_diccionario=ruta_diccionario,
        ruta_06=os.path.join(carpeta_salida, SALIDAS["verificacion"]),
        ruta_07=os.path.join(carpeta_salida, SALIDAS["faltantes"]),
        ruta_09=os.path.join(carpeta_salida, SALIDAS["auditoria"]),
        periodo=periodo,
        fecha_revision=fecha_revision,
        on_progreso=on_progreso,
        on_resultado=_recoger,
    )

    ruta_correos = os.path.join(carpeta_salida, SALIDAS["correos"])
    generar_borradores(
        resultados,
        ruta_correos,
        ruta_diccionario=ruta_diccionario,
        fecha_revision=fecha_revision,
        fecha_limite=fecha_limite,
    )

    ruta_informe = os.path.join(carpeta_salida, SALIDAS["informe"])
    generar_informe(
        resultados,
        ruta_informe,
        periodo=periodo,
        fecha_revision=fecha_revision,
    )

    return {
        **resumen,
        "ruta_correos": ruta_correos,
        "ruta_informe": ruta_informe,
        "resultados": resultados,
    }
