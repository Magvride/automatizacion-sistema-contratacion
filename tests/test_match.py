# -*- coding: utf-8 -*-
"""
Tests de las reglas de coincidencia (``src/auditoria_documental/match.py``).

Los casos reproducen los ejemplos documentados en
``documentacion_contratos/.../LECCIONES_APRENDIDAS.md`` §3 y ``METODOLOGIA.md``
§3.3 (falsos positivos de ``acta`` genérico, alias completo sin código FCO,
equivalencias de negocio, stemming y regla de cierre FCO.74).
"""

from auditoria_documental import match
from auditoria_documental.match import (
    ENCONTRADO,
    FALTANTE,
    NO_APLICA,
    evaluar_contrato,
    hay_pago_final,
    match_documento,
    normalize,
)


def _doc(id_doc, documento, formato="", alias="", etapa="Etapa"):
    return {
        "ID_DOC": id_doc,
        "DOCUMENTO": documento,
        "CODIGO_FORMATO": formato,
        "ETAPA": etapa,
        "ALIAS": alias,
    }


def test_normalize_ignora_signos_espacios_y_numeros_de_version():
    assert normalize("Informe_Oportunidad_Conveniencia (32).pdf") == (
        "informeoportunidadconveniencia32pdf"
    )
    assert normalize("  MARÍA  GÓMEZ ") == "mariagomez"
    assert normalize(None) == ""


def test_fco_exige_codigo_exacto():
    doc = _doc("D190", "Informe de oportunidad y conveniencia", "FCO.55", "FCO.55 Informe Oportunidad")
    assert match_documento(["0001_20260119_FCO.55_Informe_Oportunidad_Conveniencia.pdf"], doc)


def test_alias_completo_sin_codigo_fco():
    # Caso documentado: sin FCO.55 en el nombre pero alias completo presente.
    doc = _doc(
        "D190",
        "Informe de oportunidad y conveniencia",
        "FCO.55",
        "FCO.55 Informe Oportunidad, Informe Oportunidad Conveniencia",
    )
    archivo = "0002_20260119_Informe_Oportunidad_Conveniencia (32).pdf"
    assert match_documento([archivo], doc)


def test_no_falso_positivo_acta_inicio_vs_acta_finalizacion():
    # D226 (FCO.66) no debe matchear con el acta de inicio (FCO.60).
    doc = _doc("D226", "Acta de finalización", "FCO.66", "FCO.66 Acta Finalizacion")
    assert match_documento(["0027_20260119_Acta_Inicio.pdf"], doc) == []


def test_no_falso_positivo_evaluacion_generica():
    # FCO.70 no debe matchear por el token genérico 'evaluacion' de un FCO.59.
    doc = _doc("D226", "Evaluación", "FCO.70", "Evaluación")
    assert match_documento(["FCO.59_Evaluacion.pdf"], doc) == []


def test_sin_formato_tokens_multiples():
    doc = _doc("D197", "Certificados de antecedentes")
    assert match_documento(["0008_20260119_Certificados_Antecedentes.pdf"], doc)


def test_sin_formato_stemming_plural():
    doc = _doc("D027", "Solicitud de cotizaciones")
    assert match_documento(["Solicitud_Cotizacion.pdf"], doc)


def test_equivalencia_seguridad_parafiscales():
    doc = _doc("D033", "Seguridad Social")
    assert match_documento(["Parafiscales_2026.pdf"], doc)


def test_equivalencia_arl_estandares():
    doc = _doc("D035", "ARL")
    assert match_documento(["Constancia_Estandares.pdf"], doc)


def test_no_falso_positivo_rl_no_es_arl():
    # "Cedula RL" contiene la subcadena 'arl' pero NO es un documento de ARL.
    doc = _doc("D_x", "Cédula del representante legal", "", "Cedula RL, Cedula Representante Legal")
    assert match_documento(["0018_20260119_Certificado_ARL.pdf"], doc) == []


def test_no_falso_positivo_procuraduria_persona_rl():
    doc = _doc("D_y", "Antecedentes Procuraduría (persona / RL)")
    assert match_documento(["0018_20260119_Certificado_ARL.pdf"], doc) == []


def test_arl_real_sigue_matcheando():
    doc = _doc("D035", "Certificado ARL / afiliación a riesgos laborales")
    assert match_documento(["0018_20260119_Certificado_ARL.pdf"], doc)


def test_match_documento_acepta_dicts_con_nombre():
    doc = _doc("D027", "Solicitud de cotizaciones")
    archivos = [{"NOMBRE": "Solicitud_Cotizacion.pdf", "ID": "x"}]
    assert match_documento(archivos, doc) == ["Solicitud_Cotizacion.pdf"]


def test_hay_pago_final():
    assert hay_pago_final(["FCO.74_Acta_Pago_Final.pdf"])
    assert not hay_pago_final(["FCO.69_Acta_Pago.pdf"])


def test_regla_fco74_exime_cierre():
    docs = [
        _doc("D219", "Acta de pago", "FCO.62/69/74", "FCO.69 Acta Pago"),
        _doc("D226", "Acta de finalización", "FCO.66", "FCO.66 Acta Finalizacion"),
        _doc("D227", "Liquidación", "FCO.67", "FCO.67 Liquidacion"),
    ]
    archivos = ["FCO.69_Acta_Pago.pdf", "FCO.74_Acta_Pago_Final.pdf"]

    res = evaluar_contrato(archivos, docs, es_tipo_18=True)

    estados = {f["ID_DOC"]: f["ESTADO"] for f in res["filas"]}
    assert estados["D226"] == NO_APLICA
    assert estados["D227"] == NO_APLICA
    assert estados["D219"] == ENCONTRADO
    assert res["no_aplica"] == 2
    assert res["esperados"] == 1
    assert res["encontrados"] == 1
    assert res["faltantes"] == 0


def test_evaluar_contrato_conteos_y_faltantes():
    docs = [
        _doc("D190", "Informe de oportunidad y conveniencia", "FCO.55", "FCO.55 Informe Oportunidad"),
        _doc("D027", "Solicitud de cotizaciones", "FCO.57", "FCO.57 Solicitud Cotizaciones"),
    ]
    archivos = ["FCO.55_Informe_Oportunidad.pdf"]

    res = evaluar_contrato(archivos, docs, es_tipo_18=False)

    estados = {f["ID_DOC"]: f["ESTADO"] for f in res["filas"]}
    assert estados["D190"] == ENCONTRADO
    assert estados["D027"] == FALTANTE
    assert res["esperados"] == 2
    assert res["encontrados"] == 1
    assert res["faltantes"] == 1
    assert res["filas"][0]["ARCHIVO"] == "FCO.55_Informe_Oportunidad.pdf"


def test_regla_fco74_no_aplica_sin_tipo_18():
    docs = [_doc("D226", "Acta de finalización", "FCO.66", "FCO.66 Acta Finalizacion")]
    res = evaluar_contrato(["FCO.74_Acta_Pago_Final.pdf"], docs, es_tipo_18=False)
    assert res["filas"][0]["ESTADO"] == FALTANTE
