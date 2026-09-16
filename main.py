# -*- coding: utf-8 -*-
"""Orquestador único del flujo propio y del flujo UISARD/Alfresco."""

import argparse
import builtins
import os
import sys
import traceback
from datetime import date, datetime, timedelta
from typing import Optional

import pandas as pd

from dotenv import load_dotenv
load_dotenv()

if not getattr(sys, "frozen", False):
    _SRC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "src")
    if _SRC_DIR not in sys.path:
        sys.path.insert(0, _SRC_DIR)

from src.utils.logger import configurar_logger

logger = configurar_logger("main")

from src.conciliacion_datos import generar_consolidado
from src.utils.limpieza import limpiar, limpiar_salidas
from src.config import (
    INTERNO_DIR,
    MATRIZ_MANUAL_DIR,
    REPORTES_DIR,
    RESULTADOS_DIR,
    credenciales_alfresco,
    preparar_directorios,
)

if getattr(sys, "frozen", False):
    BASE_DIR = os.path.dirname(os.path.abspath(sys.executable))
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def getenv(clave: str, requerido: bool = False) -> str:
    """Lee una variable de entorno. Si es requerida y falta, aborta con un aviso claro."""
    valor = os.getenv(clave, "").strip()
    if requerido and not valor:
        logger.error("Falta la variable requerida '%s' en el archivo .env", clave)
        sys.exit(1)
    return valor


def construir_salidas(base_dir: str) -> dict:
    """Rutas de trabajo. Al cliente se entregan auditoría, informe y correos.

    El resto (consolidado, verificación, resultados y borradores) se guarda en
    ``archivos/_interno`` para no ensuciar la carpeta de resultados.
    """
    carpeta = str(RESULTADOS_DIR)
    interno = str(INTERNO_DIR)
    preparar_directorios()
    return {
        "carpeta": carpeta,
        "interno": interno,
        "reportes": str(REPORTES_DIR),
        "csv": os.path.join(interno, "01_Contratos_en_UISARD.csv"),
        "verificacion": os.path.join(interno, "02_Consolidado_General.csv"),
        "resultados": os.path.join(interno, "03_Resultado_Final.xlsx"),
        "dashboard": os.path.join(interno, "04_Tablero_Resumen.html"),
        "dashboard_vivo": os.path.join(interno, "05_Tablero_en_Vivo.html"),
        "faltantes": os.path.join(interno, "07_Expedientes_Faltantes.csv"),
        "auditoria": os.path.join(carpeta, "auditoria_contratos.xlsx"),
        "correos_auditoria": os.path.join(interno, "10_Correos_Auditoria.txt"),
        "correos_excel": os.path.join(carpeta, "10_Correos_Auditoria.xlsx"),
        "informe": os.path.join(carpeta, "Informe_Auditoria_Contrato.html"),
    }


# ----------------------------------------------------------------------
# BLOQUE PROPIO: Financiero UIS -> matriz -> CSV
# ----------------------------------------------------------------------
def paso_login_financiero(fecha_inicio: date, fecha_fin: date) -> None:
    """Descarga el Excel y omite únicamente la pausa final de cierre."""
    import src.uis_login_p1

    original_input = builtins.input

    def input_del_flujo(prompt=""):
        if str(prompt) == "":
            print("[main] Pausa final omitida; cerrando navegador automáticamente.")
            return ""
        return original_input(prompt)

    builtins.input = input_del_flujo
    try:
        print("[MAIN] Paso 1/5: login y descarga del reporte financiero")
        src.uis_login_p1.main(fecha_inicio=fecha_inicio, fecha_fin=fecha_fin)
    finally:
        builtins.input = original_input


def ejecutar_bloque_propio(args) -> None:
    logger.info("La matriz y la actualización automática están deshabilitadas; se usa el Excel cargado.")


# ----------------------------------------------------------------------
#  FASE 1 — Extracción UISARD
# ----------------------------------------------------------------------
def fase_uisard(args) -> None:
    logger.info("=" * 60)
    logger.info("FASE 1: Extracción de datos desde UISARD")
    logger.info("=" * 60)

    if args.skip_uisard:
        logger.info("--skip-uisard: se omite la extracción.")
        return

    from src.uisard_extractor import UISARDExtractor

    extractor = UISARDExtractor(
        url=getenv("UISARD_URL", True),
        usuario=getenv("UISARD_USER", True),
        contrasena=getenv("UISARD_PASS", True),
        fecha_inicio=args.fecha_inicio.strftime("%Y-%m-%d"),
        fecha_fin=args.fecha_fin.strftime("%Y-%m-%d"),
        #fecha_inicio="2026-09-08",
        #fecha_fin="2026-09-08"
    )
    # Descarga los reportes por serie a archivos/04_Contratos_Descargados_UISARD/ (alimenta la FASE 2).
    extractor.ejecutar_extraccion()


# ----------------------------------------------------------------------
#  FASE 2 — Conciliación (consolidado)
# ----------------------------------------------------------------------
def fase_conciliacion(args, salidas: dict) -> pd.DataFrame:
    logger.info("=" * 60)
    logger.info("FASE 2: Conciliación de reportes")
    logger.info("=" * 60)

    if args.ruta_consolidado and os.path.isfile(args.ruta_consolidado):
        logger.info("Cargando consolidado externo: %s", args.ruta_consolidado)
        if args.ruta_consolidado.lower().endswith(".csv"):
            df = pd.read_csv(args.ruta_consolidado, encoding="utf-8-sig", dtype=str)
        else:
            df = pd.read_excel(args.ruta_consolidado, engine="openpyxl", dtype=str)
        df = df.fillna("")
        df.to_csv(salidas["csv"], index=False, encoding="utf-8-sig")
        logger.info("Consolidado externo copiado a: %s (%d filas)", salidas["csv"], len(df))
        return df

    if args.skip_uisard and os.path.isfile(salidas["csv"]):
        logger.info("--skip-uisard: reutilizando consolidado previo: %s", salidas["csv"])
        return pd.read_csv(salidas["csv"], encoding="utf-8-sig", dtype=str)

    df = generar_consolidado(salidas["reportes"], salidas["csv"])
    if df.empty:
        logger.error("La conciliación quedó vacía: no hay reportes válidos en %s", salidas["reportes"])
        sys.exit(1)
    return df


# ----------------------------------------------------------------------
#  FASE 2.5 — Unificación por número de contrato
# ----------------------------------------------------------------------
def fase_unificacion(args, salidas: dict, df_uisard: pd.DataFrame) -> str:
    """Une el bloque propio (contratos Financiero) con UISARD por número de contrato.

    Devuelve la ruta del CSV que deberá verificar la FASE 3. Si no hay CSV del
    bloque propio, cae al consolidado UISARD directo.
    """
    logger.info("=" * 60)
    logger.info("FASE 2.5: Unificación por número de contrato")
    logger.info("=" * 60)

    from src.unificar_expedientes import _buscar_csv_propio, unir_consolidados

    ruta_base = _buscar_csv_propio()
    if ruta_base and os.path.isfile(ruta_base):
        resultado = unir_consolidados(ruta_base, df_uisard, salidas["verificacion"])
        if resultado.get("encontrado"):
            logger.info(
                "Unión lista: %d contratos | %d con expediente UISARD | %d sin UISARD",
                resultado["total"], resultado["con_uisard"], resultado["sin_uisard"],
            )
            return resultado["ruta"]

    logger.warning(
        "No hay CSV del bloque propio; el consolidado 02 queda como el consolidado UISARD."
    )
    df_uisard.to_csv(salidas["verificacion"], index=False, encoding="utf-8-sig")
    return salidas["verificacion"]


# ----------------------------------------------------------------------
#  FASE 4 — Notificación a ordenadores sin registros en UISARD
# ----------------------------------------------------------------------
def fase_notificacion(args, salidas: dict, ruta_unificado: Optional[str] = None) -> None:
    logger.info("=" * 60)
    logger.info("FASE 4: Notificación de expedientes no encontrados en Alfresco")
    logger.info("=" * 60)

    if args.no_notificar:
        logger.info("--no-notificar: se omite la notificación.")
        return

    from src.notificar_uisard import notificar_no_uisard

    ruta_csv = args.ruta_unificado or ruta_unificado or salidas.get(
        "resultados", os.path.join(salidas["carpeta"], "03_Resultado_Final.xlsx")
    )
    resumen = notificar_no_uisard(ruta_csv, enviar=args.enviar_correos, columna_no="alfresco")
    logger.info(
        "Notificación: %d registros, %d sin expediente en Alfresco, %d correos generados.",
        resumen["total"], resumen["sin_uisard"], resumen["mensajes"],
    )


# ----------------------------------------------------------------------
#  FASE 3 — Verificación Alfresco
# ----------------------------------------------------------------------
def fase_alfresco(args, salidas: dict, ruta_csv: Optional[str] = None) -> None:
    logger.info("=" * 60)
    logger.info("FASE 3: Verificación en Alfresco")
    logger.info("=" * 60)

    if args.skip_alfresco:
        logger.info("--skip-alfresco: se omite la verificación.")
        return

    ruta_csv = ruta_csv or salidas["csv"]

    if not os.path.isfile(ruta_csv):
        logger.error("No existe el consolidado %s para verificar.", ruta_csv)
        sys.exit(1)

    alf_url = os.getenv("ALFRESCO_SHARE_URL") or os.getenv("ALFRESCO_URL") \
        or "https://gesdoc.uis.edu.co/share/page"
    alf_user = os.getenv("ALFRESCO_SHARE_USER") or os.getenv("ALFRESCO_USER") \
        or "consulta_contratos"
    alf_pass = os.getenv("ALFRESCO_SHARE_PASS", "").strip() or os.getenv("ALFRESCO_PASS", "").strip()
    if not alf_pass:
        logger.error("Falta la contraseña de Alfresco (define ALFRESCO_SHARE_PASS o ALFRESCO_PASS en .env).")
        sys.exit(1)

    from src.alfresco_extractor import AlfrescoExtractor

    extractor = AlfrescoExtractor(
        url=alf_url,
        usuario=alf_user,
        contrasena=alf_pass,
        rapido=not args.lento,
        descargar_zip=not args.no_zip,
    )
    # El reporte maestro 03 y los dashboards se refrescan en vivo tras cada expediente.
    resultados = extractor.ejecutar_verificacion_csv(
        ruta_csv,
        ruta_consolidado=salidas.get("verificacion"),
        ruta_resultados=salidas.get("resultados"),
        ruta_dashboard=salidas.get("dashboard"),
        ruta_vivo=salidas.get("dashboard_vivo"),
    )
    resumen = resultados.get("resumen", [])
    if not resumen:
        logger.error("No se obtuvieron resultados de la verificación Alfresco.")
        sys.exit(1)

    ruta_resumen = resultados.get("ruta_resumen") or os.path.join(
        salidas["carpeta"], "06_Verificacion_Alfresco.csv"
    )
    ruta_pendientes = resultados.get("ruta_pendientes") or os.path.join(
        salidas["carpeta"], "07_Expedientes_Faltantes.csv"
    )

    encontrados = sum(1 for r in resumen if r.get("MOTIVO") == "")
    total = len(resumen)
    logger.info(
        "Verificación finalizada: %d registros | %d encontrados | %d no encontrados",
        total, encontrados, total - encontrados,
    )

    no_encontrados = resultados.get("pendientes", [])
    if no_encontrados:
        logger.info(
            "Expedientes no encontrados (%d): %s",
            len(no_encontrados), ruta_pendientes,
        )
    logger.info("Resumen: %s", ruta_resumen)


# ----------------------------------------------------------------------
#  FASE 2 (MCP) — Consolidación sin UISARD
# ----------------------------------------------------------------------
def fase_consolidacion_mcp(args, salidas: dict) -> pd.DataFrame:
    """Construye el consolidado directamente desde el Excel recibido."""
    from src.consolidar import buscar_nuevas_versiones, construir_consolidado_desde_excel

    ruta_excel = buscar_nuevas_versiones()
    resultado = construir_consolidado_desde_excel(ruta_excel, salidas["verificacion"])
    if not resultado.get("encontrado"):
        logger.error("No se pudo construir el consolidado desde %s.", ruta_excel)
        sys.exit(1)

    df = pd.read_csv(salidas["verificacion"], encoding="utf-8-sig", dtype=str).fillna("")
    logger.info("Consolidado 02 listo (%d filas): %s", len(df), salidas["verificacion"])
    return df


# ----------------------------------------------------------------------
#  FASE 3 (MCP) — Verificación en Alfresco + auditoría documental
# ----------------------------------------------------------------------
def _consolidado_enriquecido(cons: pd.DataFrame, resultados: list) -> pd.DataFrame:
    """Copia el consolidado 02 y rellena nombre/alfresco/archivos por contrato.

    Sin UISARD, el nombre del expediente solo se conoce tras consultar Alfresco,
    así que esta función reemplaza el antiguo cruce por ``NOMBRE EXPEDIENTE``.
    """
    cons = cons.copy()
    mapa = {str(r.get("contrato", "")).strip(): r for r in resultados}
    for idx, fila in cons.iterrows():
        resultado = mapa.get(str(fila.get("contrato", "")).strip())
        if not resultado:
            continue
        cons.at[idx, "NOMBRE EXPEDIENTE"] = resultado.get("carpeta", "")
        cons.at[idx, "alfresco"] = (
            "SI" if resultado.get("estado_alfresco") == "ENCONTRADA" else "NO"
        )
        cons.at[idx, "cantidad_archivos"] = str(resultado.get("cantidad_archivos", ""))
    return cons


def fase_alfresco_mcp(args, salidas: dict, on_progreso=None, on_resultado=None) -> dict:
    """Verifica Alfresco por API REST y genera el Excel de auditoría documental.

    Sustituye a la FASE 3 con Selenium. Usa el gateway REST y el motor de
    auditoría; refresca 03/04 en vivo cada pocos contratos.
    """
    logger.info("=" * 60)
    logger.info("FASE 3 (MCP): Verificación en Alfresco y auditoría documental")
    logger.info("=" * 60)

    if args.skip_alfresco:
        logger.info("--skip-alfresco: se omite la verificación.")
        return {}

    from src.alfresco_mcp.motor import ejecutar_auditoria
    from src.alfresco_mcp.rest_gateway import RestAlfrescoGateway

    ruta_consolidado = salidas["verificacion"]
    if not os.path.isfile(ruta_consolidado):
        logger.error("No existe el consolidado 02 (%s) para verificar.", ruta_consolidado)
        sys.exit(1)
    cons = pd.read_csv(ruta_consolidado, encoding="utf-8-sig", dtype=str).fillna("")
    if cons.empty:
        logger.error("El consolidado 02 está vacío; no hay contratos por verificar.")
        sys.exit(1)

    credenciales = credenciales_alfresco()
    base = credenciales["url"]
    usuario = credenciales["usuario"]
    contrasena = credenciales["contrasena"]
    if not contrasena:
        logger.error("Falta la contraseña de Alfresco (ALFRESCO_SHARE_PASS o ALFRESCO_PASS).")
        sys.exit(1)

    from src.auditoria_documental.diccionario import buscar_diccionario

    ruta_diccionario = buscar_diccionario(getattr(args, "ruta_diccionario", None) or "")
    if not ruta_diccionario:
        logger.error(
            "No se encontró el diccionario de documentos en %s. Defínalo con "
            "--ruta-diccionario o coloque 'Diccionario_Documentos.xlsx' o "
            "'Matriz_Documentos_por_Clase*.xlsx' en esa carpeta.",
            MATRIZ_MANUAL_DIR,
        )
        sys.exit(1)

    interno = salidas.get("interno") or salidas["carpeta"]
    ruta_06 = os.path.join(interno, "06_Verificacion_Alfresco.csv")
    ruta_07 = salidas.get("faltantes") or os.path.join(interno, "07_Expedientes_Faltantes.csv")
    periodo = ""
    fecha_rev = ""
    if getattr(args, "fecha_fin", None):
        try:
            periodo = args.fecha_fin.strftime("%Y-%m")
            fecha_rev = args.fecha_fin.strftime("%Y-%m-%d")
        except Exception:  # noqa: BLE001
            periodo = ""
            fecha_rev = ""
    ruta_09 = salidas.get("auditoria") or os.path.join(salidas["carpeta"], "auditoria_contratos.xlsx")

    gateway = RestAlfrescoGateway(
        base_url=base,
        usuario=usuario,
        contrasena=contrasena,
        verify_ssl=os.getenv("ALFRESCO_VERIFY_SSL", "false").lower() == "true",
        timeout=int(os.getenv("ALFRESCO_TIMEOUT", "30")),
        auth_method=credenciales["auth_method"],
    )

    estado = {"resultados": []}

    def _on_resultado(resultado):
        estado["resultados"].append(resultado)
        if on_resultado:
            on_resultado(resultado)

    try:
        resumen = ejecutar_auditoria(
            cons,
            gateway,
            ruta_diccionario=ruta_diccionario,
            ruta_06=ruta_06,
            ruta_07=ruta_07,
            ruta_09=ruta_09,
            periodo=periodo,
            on_progreso=on_progreso,
            on_resultado=_on_resultado,
        )
    finally:
        gateway.cerrar()

    # Consolidado enriquecido (interno, para trazabilidad; no es entregable).
    try:
        _consolidado_enriquecido(cons, estado["resultados"]).to_csv(
            ruta_consolidado, index=False, encoding="utf-8-sig"
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("No se pudo guardar el consolidado interno: %s", exc)

    # Borradores de correo (interno; no es entregable).
    ruta_correos = salidas.get("correos_auditoria") or os.path.join(
        interno, "10_Correos_Auditoria.txt"
    )
    try:
        from src.auditoria_documental.correos import generar_borradores

        info_correos = generar_borradores(
            estado["resultados"],
            ruta_correos,
            ruta_diccionario=ruta_diccionario,
            fecha_revision=fecha_rev,
            ruta_excel=salidas.get("correos_excel", ""),
        )
        ruta_excel_efectiva = (info_correos or {}).get("ruta_excel", salidas.get("correos_excel", ""))
        if ruta_excel_efectiva != salidas.get("correos_excel", ""):
            logger.warning(
                "El Excel de correos no pudo sobrescribirse (¿abierto?). Última versión en: %s",
                ruta_excel_efectiva,
            )
        else:
            logger.info("Excel de correos para envío: %s", ruta_excel_efectiva)
    except Exception as exc:  # noqa: BLE001
        logger.warning("No se pudieron generar los borradores de correo: %s", exc)

    # Informe HTML (entregable principal del servicio).
    ruta_informe = salidas.get("informe") or os.path.join(
        salidas["carpeta"], "Informe_Auditoria_Contrato.html"
    )
    try:
        from src.auditoria_documental.informe_html import generar_informe

        generar_informe(
            estado["resultados"],
            ruta_informe,
            periodo=periodo,
            fecha_revision=fecha_rev,
        )
        logger.info("Informe HTML de auditoría: %s", ruta_informe)
    except Exception as exc:  # noqa: BLE001
        logger.warning("No se pudo generar el informe HTML: %s", exc)

    logger.info(
        "Auditoría: %d contratos | %d encontradas | %d no encontradas",
        resumen["total"], resumen["encontradas"], resumen["no_encontradas"],
    )
    logger.info("Excel de auditoría documental: %s", resumen["ruta_09"])
    resumen["resultados"] = estado["resultados"]
    return resumen


def fase_merge_alfresco(args, salidas: dict) -> str:
    """Une el resultado de la verificación Alfresco al consolidado 02.

    Lee ``06_Verificacion_Alfresco.csv`` y agrega al consolidado
    ``02_Consolidado_General.csv`` las columnas ``alfresco``
    (SI/NO) y ``cantidad_archivos`` (n.º de archivos del ZIP corroborado), uniendo
    por ``NOMBRE EXPEDIENTE``. Devuelve la ruta del consolidado 02 enriquecido.
    """
    logger.info("=" * 60)
    logger.info("FASE 3.5: Incorporación de resultados Alfresco al consolidado 02")
    logger.info("=" * 60)

    ruta_verificacion = os.path.join(salidas["carpeta"], "06_Verificacion_Alfresco.csv")
    ruta_consolidado = os.path.join(
        salidas["carpeta"], "02_Consolidado_General.csv"
    )

    if not os.path.isfile(ruta_verificacion):
        logger.warning("No existe %s; no se puede enriquecer el consolidado 02.", ruta_verificacion)
        return ruta_consolidado

    ver = pd.read_csv(ruta_verificacion, encoding="utf-8-sig", dtype=str).fillna("")
    if "NOMBRE EXPEDIENTE" not in ver.columns or not {"alfresco", "cantidad_archivos"}.issubset(ver.columns):
        logger.warning(
            "El resumen Alfresco no tiene las columnas 'NOMBRE EXPEDIENTE'/'alfresco'/'cantidad_archivos'."
        )
        return ruta_consolidado

    if not os.path.isfile(ruta_consolidado):
        logger.warning(
            "No existe el consolidado %s; se crea a partir del consolidado base (01).",
            ruta_consolidado,
        )
        base = pd.read_csv(salidas["csv"], encoding="utf-8-sig", dtype=str).fillna("")
        base.to_csv(ruta_consolidado, index=False, encoding="utf-8-sig")

    cons = pd.read_csv(ruta_consolidado, encoding="utf-8-sig", dtype=str).fillna("")

    # Mapa expediente -> resultado de Alfresco.
    mapa = ver.set_index("NOMBRE EXPEDIENTE")[["alfresco", "cantidad_archivos"]]
    cons["alfresco"] = cons["NOMBRE EXPEDIENTE"].map(mapa["alfresco"])
    cons["cantidad_archivos"] = cons["NOMBRE EXPEDIENTE"].map(mapa["cantidad_archivos"])

    tiene_exp = cons["NOMBRE EXPEDIENTE"].astype(str).str.strip() != ""
    # Con expediente pero sin verificación (no estaba en el reporte) -> NO encontrado.
    cons.loc[tiene_exp & cons["alfresco"].isna(), "alfresco"] = "NO"
    # Sin expediente (contrato no registrado en UISARD) -> queda en blanco.
    cons["alfresco"] = cons["alfresco"].fillna("")
    cons["cantidad_archivos"] = cons["cantidad_archivos"].fillna("")

    cons.to_csv(ruta_consolidado, index=False, encoding="utf-8-sig")
    logger.info(
        "Consolidado 02 enriquecido (%d filas): %s | alfresco=SI: %d",
        len(cons), ruta_consolidado,
        int((cons["alfresco"].astype(str).str.upper() == "SI").sum()),
    )
    return ruta_consolidado


# ----------------------------------------------------------------------
#  FASE 3.6 — Reporte maestro final (03_Resultado_Final)
# ----------------------------------------------------------------------
def fase_resultados(args, salidas: dict) -> str:
    """Genera el reporte maestro final ``03_Resultado_Final.xlsx`` y su dashboard.

    Resume, por contrato, si está en UISARD y si el expediente se encontró en
    Alfresco (con el número de archivos). Es el insumo del envío final.
    """
    logger.info("=" * 60)
    logger.info("FASE 3.6: Reporte maestro de resultados y dashboard")
    logger.info("=" * 60)

    from src.resultados import generar_reporte
    from src.dashboard import generar_dashboard

    ruta_consolidado = os.path.join(
        salidas["carpeta"], "02_Consolidado_General.csv"
    )
    ruta_verificacion = os.path.join(salidas["carpeta"], "06_Verificacion_Alfresco.csv")
    ruta_salida = salidas.get("resultados") or os.path.join(
        salidas["carpeta"], "03_Resultado_Final.xlsx"
    )

    if not os.path.isfile(ruta_consolidado):
        logger.warning("No existe %s; no se puede generar el reporte maestro.", ruta_consolidado)
        return ""

    cons = pd.read_csv(ruta_consolidado, encoding="utf-8-sig", dtype=str).fillna("")

    # El estado de Alfresco se toma directo de la verificación (no depende de que
    # el consolidado 02 ya esté enriquecido), para que 03 siempre refleje lo real.
    verificacion = None
    if os.path.isfile(ruta_verificacion):
        verificacion = pd.read_csv(
            ruta_verificacion, encoding="utf-8-sig", dtype=str
        ).fillna("")
    else:
        logger.warning(
            "No existe %s; el reporte maestro quedará sin estado de Alfresco.",
            ruta_verificacion,
        )

    df = generar_reporte(cons, verificacion, ruta=ruta_salida)

    ruta_dashboard = salidas.get("dashboard") or os.path.join(
        salidas["carpeta"], "04_Tablero_Resumen.html"
    )
    generar_dashboard(df, ruta_dashboard)

    if "estado" in df.columns:
        resumen = df["estado"].value_counts().to_dict()
        logger.info("Resumen del reporte maestro: %s", resumen)
    logger.info("Reporte maestro final: %s (%d filas)", ruta_salida, len(df))
    return ruta_salida


def parsear_argumentos() -> argparse.Namespace:
    ayer = date.today() - timedelta(days=1)

    def parsear_fecha(valor: str) -> date:
        try:
            return datetime.strptime(valor, "%Y-%m-%d").date()
        except ValueError as exc:
            raise argparse.ArgumentTypeError(
                f"Fecha inválida '{valor}'. Use el formato YYYY-MM-DD."
            ) from exc

    parser = argparse.ArgumentParser(
        description="Flujo Financiero UIS -> matriz -> CSV -> UISARD -> Alfresco."
    )
    parser.add_argument(
        "--fecha-inicio",
        type=parsear_fecha,
        default=ayer,
        help="Fecha inicial de consulta en ambos sistemas (YYYY-MM-DD). Por defecto: ayer.",
    )
    parser.add_argument(
        "--fecha-fin",
        type=parsear_fecha,
        default=ayer,
        help="Fecha final de consulta en ambos sistemas (YYYY-MM-DD). Por defecto: ayer.",
    )
    parser.add_argument(
        "--skip-financiero",
        action="store_true",
        help="Omitir login, matriz y CSV del bloque propio.",
    )
    parser.add_argument(
        "--reporte-nuevas",
        type=str,
        default=None,
        help="Ruta al Excel de reporte de nuevas versiones (reservado).",
    )
    parser.add_argument(
        "--skip-uisard",
        action="store_true",
        help="Omitir extracción UISARD y reutilizar el consolidado previo.",
    )
    parser.add_argument(
        "--skip-alfresco",
        action="store_true",
        help="Omitir la verificación en Alfresco.",
    )
    parser.add_argument(
        "--ruta-consolidado",
        type=str,
        default=None,
        help="Ruta a un consolidado (CSV/XLSX) para usar como entrada de la FASE 3.",
    )
    parser.add_argument(
        "--lento",
        action="store_true",
        help="Desactiva el modo rápido en Alfresco (pausas human-like).",
    )
    parser.add_argument(
        "--no-zip",
        action="store_true",
        help="Omite la descarga/corroboración por ZIP en Alfresco (verificación más rápida).",
    )
    parser.add_argument(
        "--enviar-correos",
        action="store_true",
        help="Envía correos a los ordenadores con contratos no registrados en UISARD.",
    )
    parser.add_argument(
        "--no-notificar",
        action="store_true",
        help="Omite la FASE 4 (notificación por correo).",
    )
    parser.add_argument(
        "--ruta-unificado",
        type=str,
        default=None,
        help="CSV unificado a leer para notificar (opcional).",
    )
    parser.add_argument(
        "--backend-alfresco",
        choices=["mcp", "selenium"],
        default="mcp",
        help="Motor de Alfresco: 'mcp' (API REST, por defecto) o 'selenium' (legado).",
    )
    parser.add_argument(
        "--ruta-diccionario",
        type=str,
        default=None,
        help="Ruta a Diccionario_Documentos.xlsx (por defecto en 00_Datos_Raw).",
    )
    return parser.parse_args()


def main():
    args = parsear_argumentos()
    if args.fecha_inicio > args.fecha_fin:
        logger.error("La fecha inicial no puede ser posterior a la fecha final.")
        sys.exit(2)
    salidas = construir_salidas(BASE_DIR)

    logger.info("Inicio de ejecución: %s", datetime.now().isoformat())

    try:
        # Modulo 1 ---------------------------------------------------------------------------------------
        """
        Este modelo tiene como objetivo la siguiente serie de pasos 
        paso 1: Ingresar a la plataforma de nuevas versiones y descargar el reporte financiero. Descarga en ./01_Contratos_Descargados
        Paso 2: Ejecuta el main de seguimiento_p2 para actualizar la matriz de seguimiento y exportar el CSV normalizado. guarda en ./02_Matriz_actualizada y ./03_Contratos_Conciliacion
        """
        ejecutar_bloque_propio(args)



        #Modulo 2 ---------------------------------------------------------------------------------------
        """
        Este modelo tiene como objetivo la siguiente serie de pasos
        paso 1: Ejecuta la fase_uisard para extraer los datos de UISARD. guarda en ./04_Contratos_Descargados_UISARD
        Paso 2: Genera una archivo CSV con los datos recopilados en UISARD y los guarda
        
        """
        #Paso 1: Ejecuta la fase_uisard para extraer los datos de UISARD. Hace el login en la plataforma
        logger.info("Inicio del bloque UISARD/Alfresco")
        #Paso 1: Ejecuta la fase_uisard para extraer los datos de UISARD. Hace el login en la plataforma
        backend = getattr(args, "backend_alfresco", "mcp")
        if backend == "mcp":
            logger.info("Backend de Alfresco: MCP/REST — flujo de nuevas versiones (sin UISARD)")
            fase_consolidacion_mcp(args, salidas)
            fase_alfresco_mcp(args, salidas)
        else:
            logger.info("Inicio del bloque UISARD/Alfresco (backend Selenium legado)")
            fase_uisard(args)
            #paso 2: genera un archivo csv con los datos recopilados en UISARD y los guarda en 
            df = fase_conciliacion(args, salidas)
            logger.info("Consolidado listo (%d filas): %s", len(df), salidas["csv"])
            #paso 3: concatena los 3 tipos de contratos extraídos de alfresco y los guarda en un archivo csv
            fase_unificacion(args, salidas, df)

            #Modulo 3 ---------------------------------------------------------------------------------------
            """"
            Este modulo tiene como objetivo la siguiente serie de pasos
            paso 1: Entrar y autenticarse en la plataforma de Alfresco y verificar los contratos que se encuentran en el archivo csv generado en el paso anterior.
            paso 2: notificar a los ordenadores
            """
            #La verificación de Alfresco se hace únicamente sobre el consolidado UISARD (01_...).
            fase_alfresco(args, salidas)

            # Se incorpora el resultado al consolidado 02 (alfresco + cantidad_archivos).
            fase_merge_alfresco(args, salidas)
            # Reporte maestro final (resumen de UISARD + archivos encontrados).
            fase_resultados(args, salidas)
            fase_notificacion(args, salidas)

        logger.info("Proceso completo (backend=%s).", backend)

    except KeyboardInterrupt:
        logger.info("Proceso interrumpido por el usuario.")
        sys.exit(0)
    except SystemExit:
        raise
    except Exception as exc:
        logger.critical("Error fatal en el proceso: %s", exc, exc_info=True)
        sys.exit(1)
    finally:
         # Purga automática de archivos antiguos (logs, diagnósticos y reportes)
         # y de los archivos internos generados en la sesión.
        try:
            limpiar(BASE_DIR, serie=True)
            limpiar_salidas(BASE_DIR)
        except Exception as exc:
            logger.warning("Fallo durante la limpieza automática: %s", exc)


if __name__ == "__main__":
    main()
