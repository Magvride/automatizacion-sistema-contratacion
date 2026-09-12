# -*- coding: utf-8 -*-
"""
Coincidencia documento esperado ↔ archivo real de Alfresco.

Reimplementa las reglas documentadas del proyecto de referencia
(``documentacion_contratos/docs/METODOLOGIA.md`` §3.3 y
``LECCIONES_APRENDIDAS.md`` §3):

* ``normalize`` ignora acentos, mayúsculas, espacios y signos (incluye ``()`` y
  números de versión como ``(32)``).
* Si el documento tiene **código de formato** (FCO/FTH/FFI) se exige el código
  exacto (``FCO.55`` → ``fco55``) o el **alias completo**; nunca un token suelto
  genérico (evita que ``Acta_Inicio`` (FCO.60) matchee ``Acta finalización``
  (FCO.66)).
* Sin código de formato se usan tokens distintivos (≥2 si la frase es
  multi-token) con *stemming* simple (``cotizaciones`` ≈ ``cotizacion``).
* Equivalencias de negocio: ``Seguridad Social`` ↔ ``Parafiscales`` y
  ``ARL`` ↔ ``Estándares/Constancia``.
* Regla de cierre: si existe ``FCO.74`` (acta de pago final) en un contrato tipo
  18, ``FCO.66``/``FCO.67`` se marcan ``NO APLICA`` (no ``FALTANTE``).

Módulo puro: no depende de Alfresco ni de Excel, por lo que es testeable de
forma aislada.
"""

import re
import unicodedata

# Formatos que llevan código numérico asociado (se exige el código exacto).
PREFIJOS_FORMATO = ("fco", "fth", "ffi")

# Palabras vacías que no cuentan como tokens distintivos.
STOPWORDS = {
    "de", "del", "la", "el", "los", "las", "y", "e", "o", "u", "a", "al",
    "para", "por", "con", "en", "un", "una", "ante", "segun", "sus", "su",
}

# Estados posibles de un documento esperado.
ENCONTRADO = "ENCONTRADO"
FALTANTE = "FALTANTE"
NO_APLICA = "NO APLICA"

# Formatos de cierre que quedan eximidos cuando hay acta de pago final.
_FORMATOS_CIERRE = {"fco66", "fco67"}
_FORMATO_PAGO_FINAL = "fco74"

# Familias de equivalencia: si el documento pertenece a la familia, basta con que
# el archivo contenga alguno de los patrones equivalentes.
_FAMILIA_PATRONES = {
    "parafiscales": ("parafiscal", "seguridadsocial", "seguridad"),
    "arl": ("arl", "estandar", "constancia", "riesgoslaborales"),
}

_CODIGO_RE = re.compile(r"(fco|fth|ffi)\.?\s*(\d+)", re.IGNORECASE)


def _sin_acentos(texto: str) -> str:
    """Quita los diacríticos (á→a, ñ→n) conservando el resto de caracteres."""
    return "".join(
        c
        for c in unicodedata.normalize("NFKD", str(texto))
        if not unicodedata.combining(c)
    )


def _tokens(texto) -> list:
    """Tokeniza en minúsculas, sin acentos y sin signos."""
    if texto is None:
        return []
    limpio = _sin_acentos(texto).lower()
    return [tok for tok in re.split(r"[^a-z0-9]+", limpio) if tok]


def normalize(texto) -> str:
    """Normaliza un texto a su forma comparable (sin acentos/espacios/signos).

    ``"Informe_Oportunidad_Conveniencia (32).pdf"`` → ``"informeoportunidadconveniencia32pdf"``.
    """
    if texto is None:
        return ""
    return "".join(_tokens(texto))


def _tokens_distintivos(texto) -> list:
    """Tokens relevantes para comparar (≥3 caracteres y no vacíos)."""
    return [tok for tok in _tokens(texto) if len(tok) >= 3 and tok not in STOPWORDS]


def _stem(token: str) -> str:
    """Stemming simple de plural en español (``cotizaciones`` → ``cotizacion``)."""
    if len(token) > 4 and token.endswith("es"):
        return token[:-2]
    if len(token) > 3 and token.endswith("s"):
        return token[:-1]
    return token


def _codigos_formato(codigo_formato) -> set:
    """Extrae los códigos ``fcoNN``/``fthNN``/``ffiNN`` de un campo de formato.

    Soporta formatos múltiples como ``"FCO.62/69/74"`` → ``{fco62, fco69, fco74}``.
    """
    if not codigo_formato:
        return set()
    return {
        f"{m.group(1).lower()}{m.group(2)}"
        for m in _CODIGO_RE.finditer(str(codigo_formato))
    }


def _lista_alias(documento) -> list:
    """Separa el campo ALIAS (varios alias por coma/punto y coma/barra)."""
    alias = documento.get("ALIAS", "") if isinstance(documento, dict) else ""
    if not alias:
        return []
    return [parte.strip() for parte in re.split(r"[;,|]", str(alias)) if parte.strip()]


def _frases(documento) -> list:
    """Frases candidatas del documento: su nombre y sus alias."""
    frases = []
    if isinstance(documento, dict):
        nombre = documento.get("DOCUMENTO", "")
        if nombre:
            frases.append(nombre)
        frases.extend(_lista_alias(documento))
    return frases


def _frases_fuertes(file_norm: str, file_stems: set, frases: list) -> bool:
    """Coincidencia estricta: exige ≥2 tokens distintivos presentes (o el código).

    Se usa para documentos con código de formato, donde un token suelto genérico
    (``acta``, ``evaluacion``) no debe dar por encontrado el documento.
    """
    for frase in frases:
        tokens = _tokens_distintivos(frase)
        if len(tokens) < 2:
            continue
        if all(_stem(tok) in file_stems for tok in tokens):
            return True
    return False


def _frases_laxas(file_norm: str, file_stems: set, frases: list) -> bool:
    """Coincidencia para documentos sin formato: un token distintivo basta."""
    for frase in frases:
        tokens = _tokens_distintivos(frase)
        if not tokens:
            continue
        if len(tokens) == 1:
            if _stem(tokens[0]) in file_stems:
                return True
        elif all(_stem(tok) in file_stems for tok in tokens):
            return True
    return False


def _familia_equivalencia(documento) -> set:
    """Familias de equivalencia a las que pertenece el documento.

    Se compara por tokens completos (no por subcadena) para evitar falsos
    positivos como ``"persona / RL"`` o ``"Cedula RL"`` conteniendo ``arl``.
    """
    tokens = set()
    for frase in _frases(documento):
        tokens.update(_tokens(frase))
    stems = {_stem(tok) for tok in tokens}

    familias = set()
    if "parafiscal" in stems:
        familias.add("parafiscales")
    if "seguridad" in tokens and "social" in tokens:
        familias.add("parafiscales")
    if "arl" in tokens:
        familias.add("arl")
    if "riesgos" in tokens and "laborales" in tokens:
        familias.add("arl")
    return familias


def _equivalencia(file_norm: str, documento) -> bool:
    """True si el archivo satisface una equivalencia de negocio del documento."""
    for familia in _familia_equivalencia(documento):
        if any(patron in file_norm for patron in _FAMILIA_PATRONES[familia]):
            return True
    return False


def _match_archivo(nombre_archivo: str, documento) -> bool:
    """True si ``nombre_archivo`` satisface el documento esperado."""
    file_norm = normalize(nombre_archivo)
    if not file_norm:
        return False
    file_stems = {_stem(tok) for tok in _tokens(nombre_archivo)}
    frases = _frases(documento)
    codigos = _codigos_formato(documento.get("CODIGO_FORMATO", ""))

    if codigos:
        if any(codigo in file_norm for codigo in codigos):
            return True
        if _frases_fuertes(file_norm, file_stems, frases):
            return True
        return _equivalencia(file_norm, documento)

    if _frases_laxas(file_norm, file_stems, frases):
        return True
    return _equivalencia(file_norm, documento)


def match_documento(archivos: list, documento) -> list:
    """Devuelve la lista de archivos que satisfacen el documento esperado.

    ``archivos`` puede ser una lista de nombres (str) o de dicts con clave
    ``NOMBRE``. El orden se conserva.
    """
    coincidencias = []
    for archivo in archivos or []:
        nombre = archivo.get("NOMBRE", "") if isinstance(archivo, dict) else archivo
        if _match_archivo(nombre, documento):
            coincidencias.append(nombre)
    return coincidencias


def hay_pago_final(archivos: list) -> bool:
    """True si algún archivo corresponde al acta de pago final (``FCO.74``)."""
    for archivo in archivos or []:
        nombre = archivo.get("NOMBRE", "") if isinstance(archivo, dict) else archivo
        if _FORMATO_PAGO_FINAL in normalize(nombre):
            return True
    return False


def evaluar_contrato(archivos: list, documentos: list, es_tipo_18: bool = False) -> dict:
    """Evalúa un contrato: estado de cada documento obligatorio y conteos.

    ``documentos`` es una lista de dicts con al menos ``ID_DOC``, ``DOCUMENTO``,
    ``CODIGO_FORMATO``, ``ETAPA`` y ``ALIAS``. Devuelve ``{filas, esperados,
    encontrados, faltantes, no_aplica}`` donde ``filas`` son dicts listos para la
    hoja granular (``ESTADO``/``ARCHIVO`` incluidos).

    Regla de cierre: en contratos tipo 18, si hay ``FCO.74`` los documentos
    ``FCO.66``/``FCO.67`` quedan ``NO APLICA`` (no cuentan como faltantes).
    """
    pago_final = es_tipo_18 and hay_pago_final(archivos)

    filas = []
    encontrados = 0
    faltantes = 0
    no_aplica = 0

    for documento in documentos or []:
        codigos = _codigos_formato(documento.get("CODIGO_FORMATO", ""))
        if pago_final and codigos & _FORMATOS_CIERRE:
            estado = NO_APLICA
            archivo_txt = ""
            no_aplica += 1
        else:
            coincidencias = match_documento(archivos, documento)
            if coincidencias:
                estado = ENCONTRADO
                archivo_txt = " | ".join(coincidencias)
                encontrados += 1
            else:
                estado = FALTANTE
                archivo_txt = ""
                faltantes += 1

        filas.append(
            {
                "ID_DOC": documento.get("ID_DOC", ""),
                "DOCUMENTO": documento.get("DOCUMENTO", ""),
                "FORMATO": documento.get("CODIGO_FORMATO", ""),
                "ETAPA": documento.get("ETAPA", ""),
                "ALIAS": documento.get("ALIAS", ""),
                "ESTADO": estado,
                "ARCHIVO": archivo_txt,
            }
        )

    return {
        "filas": filas,
        "esperados": len(documentos or []) - no_aplica,
        "encontrados": encontrados,
        "faltantes": faltantes,
        "no_aplica": no_aplica,
    }
