# -*- coding: utf-8 -*-
"""
Carga del diccionario de documentos obligatorios.

Lee ``Diccionario_Documentos.xlsx`` (hojas ``Diccionario`` y ``Matriz_Etapas``)
y ofrece:

* ``cargar_diccionario(ruta)`` — registros normalizados del diccionario y etapas.
* ``obligatorios_por_clase(registros, clase)`` — solo ``OBLIGATORIEDAD=Obligatorio``
  de una clase (``20``, ``18 PN``, ``18 PJ``, ``270``…).
* ``clase_de_contrato(contrato, contratista)`` — deduce la clase a partir del
  prefijo del contrato y, para ``18``, si el contratista es persona natural o
  jurídica.

El archivo Excel no vive en este repositorio: es un insumo que debe aportar el
equipo de contratación. Si falta, se lanza ``FileNotFoundError`` con un mensaje
claro para que el flujo lo reporte en lugar de fallar en silencio.
"""

import os
import re
import unicodedata

import openpyxl

from config import MATRIZ_MANUAL_DIR
from utils.logger import configurar_logger

logger = configurar_logger("diccionario")

# Nombres aceptados para la hoja con el catálogo de documentos (una fila por
# documento y clase). Se admite tanto el formato del diccionario histórico
# ("Diccionario") como el de la matriz entregada ("CATALOGO_PLANO").
HOJAS_CATALOGO = ("Diccionario", "CATALOGO_PLANO")

# Nombres aceptados para la hoja de etapas/matriz de aplicabilidad.
HOJAS_MATRIZ = ("Matriz_Etapas", "MATRIZ")

# Nombres de archivo que se autodetectan dentro de 00_Datos_Raw.
NOMBRES_DICCIONARIO = (
    "Diccionario_Documentos.xlsx",
    "Matriz_Documentos_por_Clase.xlsx",
)
PATRON_DICCIONARIO = "Matriz_Documentos_por_Clase*.xlsx"

# Clases soportadas (prefijo de contrato -> etiqueta de clase).
CLASES_POR_PREFIJO = {
    "20": "20",
    "19": "19",
    "298": "298",
    "450": "450",
    "270": "270",
    "18": "18",  # se especializa a 18 PN / 18 PJ
}

# Patrones que identifican persona jurídica (según diccionario_config.json).
_PATRONES_PERSONA_JURIDICA = ("SAS", "LTDA", "S.A", "S.A.S")

# Encabezados canónicos del diccionario y sus alias normalizados.
_CABECERAS = {
    "ID_DOC": "ID_DOC",
    "IDDOC": "ID_DOC",
    "CLASE": "CLASE",
    "CODIGO_CLASE": "CODIGO_CLASE",
    "CODIGOCLASE": "CODIGO_CLASE",
    "DOCUMENTO": "DOCUMENTO",
    "CODIGO_FORMATO": "CODIGO_FORMATO",
    "CODIGOFORMATO": "CODIGO_FORMATO",
    "ETAPA": "ETAPA",
    "CARDINALIDAD": "CARDINALIDAD",
    "OBLIGATORIEDAD": "OBLIGATORIEDAD",
    "ALIAS": "ALIAS",
}

# Orden de las etapas para la hoja "Cruce_por_Etapa".
ETAPAS_ORDEN = [
    "Precontractual - selección",
    "Precontractual - idoneidad",
    "Precontractual - presupuestal",
    "Contractual / perfeccionamiento",
    "Ejecución y pagos",
    "Cierre y liquidación",
    "Novedades",
]


def _sin_acentos(texto: str) -> str:
    return "".join(
        c
        for c in unicodedata.normalize("NFKD", str(texto))
        if not unicodedata.combining(c)
    )


def _clave_cabecera(valor) -> str:
    """Normaliza un encabezado: mayúsculas, sin acentos, espacios ni guiones."""
    if valor is None:
        return ""
    limpio = _sin_acentos(valor).upper()
    return re.sub(r"[^A-Z0-9]", "", limpio)


def _normalizar_valor(valor) -> str:
    if valor is None:
        return ""
    return str(valor).strip()


def _es_persona_juridica(contratista) -> bool:
    """True si el nombre del contratista corresponde a persona jurídica."""
    texto = str(contratista or "").upper()
    return any(patron in texto for patron in _PATRONES_PERSONA_JURIDICA)


def clase_de_contrato(contrato, contratista: str = "") -> str:
    """Deduce la clase del contrato (``20``, ``18 PN``, ``18 PJ``…).

    El prefijo del contrato (antes de ``-``) identifica la clase; para ``18`` se
    infiere persona natural/jurídica a partir del nombre del contratista.
    """
    texto = str(contrato or "").strip()
    prefijo = texto.split("-")[0].strip() if "-" in texto else texto
    prefijo = re.sub(r"\D", "", prefijo) or prefijo
    # El contrato puede venir con ceros a la izquierda ("0450"); el diccionario
    # usa la clase sin ellos ("450").
    prefijo = prefijo.lstrip("0") or "0"
    if prefijo == "18":
        return "18 PJ" if _es_persona_juridica(contratista) else "18 PN"
    return CLASES_POR_PREFIJO.get(prefijo, prefijo)


def _leer_hoja(libro, nombre_hoja: str) -> list:
    """Lee una hoja como lista de dicts usando la fila de encabezados canónicos."""
    if nombre_hoja not in libro.sheetnames:
        return []
    hoja = libro[nombre_hoja]

    filas = list(hoja.iter_rows(values_only=True))
    if not filas:
        return []

    fila_cabecera = None
    indices = {}
    for i, fila in enumerate(filas):
        mapa = {}
        for j, celda in enumerate(fila):
            clave = _CABECERAS.get(_clave_cabecera(celda))
            if clave:
                mapa[clave] = j
        # Una cabecera válida del diccionario reconoce al menos ID_DOC/DOCUMENTO.
        if "ID_DOC" in mapa or "DOCUMENTO" in mapa or "CODIGO_CLASE" in mapa:
            fila_cabecera = i
            indices = mapa
            break

    if fila_cabecera is None:
        logger.warning("La hoja '%s' no tiene encabezados reconocibles.", nombre_hoja)
        return []

    registros = []
    for fila in filas[fila_cabecera + 1:]:
        if not any(_normalizar_valor(c) for c in fila):
            continue
        registro = {
            clave: (fila[idx] if idx < len(fila) else "")
            for clave, idx in indices.items()
        }
        registro = {k: _normalizar_valor(v) for k, v in registro.items()}
        if registro.get("ID_DOC") or registro.get("DOCUMENTO"):
            registros.append(registro)
    return registros


def _leer_primera_hoja(libro, nombres) -> list:
    """Devuelve los registros de la primera hoja existente de ``nombres``."""
    for nombre in nombres:
        if nombre in libro.sheetnames:
            registros = _leer_hoja(libro, nombre)
            if registros:
                return registros
    return []


def buscar_diccionario(ruta: str = "") -> str:
    """Resuelve la ruta del diccionario de documentos.

    Prioridad: ruta explícita → ``Diccionario_Documentos.xlsx`` →
    ``Matriz_Documentos_por_Clase*.xlsx``, todas dentro de ``00_Datos_Raw``.
    Devuelve "" si no encuentra ninguna.
    """
    if ruta and os.path.isfile(ruta):
        return str(ruta)

    candidatos = [MATRIZ_MANUAL_DIR / nombre for nombre in NOMBRES_DICCIONARIO]
    candidatos.extend(sorted(MATRIZ_MANUAL_DIR.glob(PATRON_DICCIONARIO)))
    for candidato in candidatos:
        if candidato.is_file():
            return str(candidato)
    return ""


def _abrir_libro(ruta: str, intentos: int = 3):
    """Abre el Excel con reintentos ante bloqueos (abierto en Excel/OneDrive)."""
    import time

    ultimo = None
    for intento in range(1, intentos + 1):
        try:
            return openpyxl.load_workbook(ruta, data_only=True, read_only=True)
        except PermissionError as exc:
            ultimo = exc
            logger.warning(
                "No se pudo abrir '%s' (intento %d/%d): archivo bloqueado.",
                ruta, intento, intentos,
            )
            if intento < intentos:
                time.sleep(0.8 * intento)
    raise PermissionError(
        f"No se pudo leer el diccionario '{ruta}' porque está abierto o bloqueado "
        "(por ejemplo, abierto en Excel o sincronizándose en OneDrive). "
        "Ciérralo e inténtalo de nuevo."
    ) from ultimo


def cargar_diccionario(ruta: str = "") -> dict:
    """Carga el diccionario y las etapas desde el Excel de documentos.

    Acepta las hojas ``Diccionario``/``CATALOGO_PLANO`` (catálogo) y
    ``Matriz_Etapas``/``MATRIZ`` (etapas). Si ``ruta`` es vacía, autodetecta el
    archivo en ``00_Datos_Raw``. Devuelve
    ``{"diccionario": [...], "etapas": [...], "ruta": ruta}``.
    Lanza ``FileNotFoundError`` si no hay archivo.
    """
    ruta = buscar_diccionario(ruta)
    if not ruta:
        raise FileNotFoundError(
            "No se encontró el diccionario de documentos en "
            f"'{MATRIZ_MANUAL_DIR}' (se espera 'Diccionario_Documentos.xlsx' o "
            "'Matriz_Documentos_por_Clase*.xlsx'). Es un insumo obligatorio."
        )

    libro = _abrir_libro(ruta)
    try:
        diccionario = _leer_primera_hoja(libro, HOJAS_CATALOGO)
        etapas = _leer_primera_hoja(libro, HOJAS_MATRIZ)
    finally:
        libro.close()

    logger.info(
        "Diccionario cargado desde %s: %d documentos, %d filas de etapas.",
        ruta,
        len(diccionario),
        len(etapas),
    )
    return {"diccionario": diccionario, "etapas": etapas, "ruta": ruta}


def obligatorios_por_clase(registros: list, clase: str) -> list:
    """Filtra los documentos obligatorios de una clase (``20``, ``18 PN``…)."""
    clase_norm = _clave_cabecera(clase)
    resultado = []
    for registro in registros or []:
        if _clave_cabecera(registro.get("CODIGO_CLASE", "")) != clase_norm:
            continue
        obligatoriedad = _clave_cabecera(registro.get("OBLIGATORIEDAD", ""))
        if obligatoriedad.startswith("OBLIGATORIO"):
            resultado.append(registro)
    return resultado


def ordenar_etapas(etapas) -> list:
    """Ordena una colección de etapas según el orden estándar del diccionario."""
    vistas = list(dict.fromkeys(str(e).strip() for e in (etapas or []) if str(e).strip()))

    def _indice(etapa: str) -> int:
        for i, conocida in enumerate(ETAPAS_ORDEN):
            if _clave_cabecera(conocida) == _clave_cabecera(etapa):
                return i
        return len(ETAPAS_ORDEN)

    return sorted(vistas, key=_indice)
