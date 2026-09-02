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

from utils.logger import configurar_logger

logger = configurar_logger("main")

from uisard_extractor import UISARDExtractor
from conciliacion_datos import generar_consolidado
from alfresco_extractor import AlfrescoExtractor
from utils.limpieza import limpiar
from config import REPORTES_DIR, RESULTADOS_DIR, preparar_directorios

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def getenv(clave: str, requerido: bool = False) -> str:
    """Lee una variable de entorno. Si es requerida y falta, aborta con un aviso claro."""
    valor = os.getenv(clave, "").strip()
    if requerido and not valor:
        logger.error("Falta la variable requerida '%s' en el archivo .env", clave)
        sys.exit(1)
    return valor


def construir_salidas(base_dir: str) -> dict:
    carpeta = str(RESULTADOS_DIR)
    preparar_directorios()
    return {
        "carpeta": carpeta,
        "reportes": str(REPORTES_DIR),
        "csv": os.path.join(carpeta, "conciliacion_datos.csv"),
        "verificacion": os.path.join(carpeta, "contratos_unificados.csv"),
    }


# ----------------------------------------------------------------------
# BLOQUE PROPIO: Financiero UIS -> matriz -> CSV
# ----------------------------------------------------------------------
def paso_login_financiero(fecha_inicio: date, fecha_fin: date) -> None:
    """Descarga el Excel y omite únicamente la pausa final de cierre."""
    import uis_login_p1

    original_input = builtins.input

    def input_del_flujo(prompt=""):
        if str(prompt) == "":
            print("[main] Pausa final omitida; cerrando navegador automáticamente.")
            return ""
        return original_input(prompt)

    builtins.input = input_del_flujo
    try:
        print("[MAIN] Paso 1/6: login y descarga del reporte financiero")
        uis_login_p1.main(fecha_inicio=fecha_inicio, fecha_fin=fecha_fin)
    finally:
        builtins.input = original_input


def ejecutar_bloque_propio(args) -> None:
    import extraccion_p21
    import seguimiento_p2

    if args.skip_financiero:
        logger.info("--skip-financiero: se omite el bloque propio.")
        return

    paso_login_financiero(args.fecha_inicio, args.fecha_fin)
    print("[MAIN] Paso 2/6: actualización de la matriz de seguimiento")
    seguimiento_p2.main()
    print("[MAIN] Paso 3/6: extracción del CSV normalizado")
    extraccion_p21.main()


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

    extractor = UISARDExtractor(
        url=getenv("UISARD_URL", True),
        usuario=getenv("UISARD_USER", True),
        contrasena=getenv("UISARD_PASS", True),
        fecha_inicio=args.fecha_inicio.strftime("%Y-%m-%d"),
        fecha_fin=args.fecha_fin.strftime("%Y-%m-%d"),
    )
    # Descarga los reportes por serie a archivos/reportes_demo/ (alimenta la FASE 2).
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

    from unificar_expedientes import _buscar_csv_propio, unir_consolidados

    ruta_base = _buscar_csv_propio()
    if args.skip_financiero and not ruta_base:
        logger.info("--skip-financiero sin CSV propio: se usa el consolidado UISARD directo.")
        return salidas["csv"]

    resultado = unir_consolidados(ruta_base, df_uisard, salidas["verificacion"])
    if resultado.get("encontrado"):
        logger.info(
            "Unión lista: %d contratos | %d con expediente UISARD | %d sin UISARD",
            resultado["total"], resultado["con_uisard"], resultado["sin_uisard"],
        )
        return resultado["ruta"]

    logger.warning("No hay CSV del bloque propio; se verifica el consolidado UISARD directo.")
    return salidas["csv"]


# ----------------------------------------------------------------------
#  FASE 4 — Notificación a ordenadores sin registros en UISARD
# ----------------------------------------------------------------------
def fase_notificacion(args, salidas: dict, ruta_unificado: Optional[str] = None) -> None:
    logger.info("=" * 60)
    logger.info("FASE 4: Notificación a ordenadores sin registros en UISARD")
    logger.info("=" * 60)

    if args.no_notificar:
        logger.info("--no-notificar: se omite la notificación.")
        return

    from notificar_uisard import notificar_no_uisard

    ruta_csv = args.ruta_unificado or ruta_unificado or os.path.join(
        salidas["carpeta"], "contratos_unificados.csv"
    )
    resumen = notificar_no_uisard(ruta_csv, enviar=args.enviar_correos)
    logger.info(
        "Notificación: %d registros, %d sin UISARD, %d correos generados.",
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

    extractor = AlfrescoExtractor(
        url=alf_url,
        usuario=alf_user,
        contrasena=alf_pass,
        rapido=not args.lento,
        descargar_zip=not args.no_zip,
    )
    resultados = extractor.ejecutar_verificacion_csv(ruta_csv)
    pasos = resultados.get("pasos", [])
    resumen = resultados.get("resumen", [])
    if not resumen:
        logger.error("No se obtuvieron resultados de la verificación Alfresco.")
        sys.exit(1)

    ruta_pasos = os.path.join(salidas["carpeta"], "verificacion_alfresco_pasos.csv")
    ruta_resumen = os.path.join(salidas["carpeta"], "verificacion_alfresco.csv")
    pd.DataFrame(pasos).to_csv(ruta_pasos, index=False, encoding="utf-8-sig")
    pd.DataFrame(resumen).to_csv(ruta_resumen, index=False, encoding="utf-8-sig")

    encontrados = sum(1 for r in resumen if r.get("MOTIVO") == "")
    total = len(resumen)
    logger.info(
        "Verificación finalizada: %d registros | %d encontrados | %d no encontrados",
        total, encontrados, total - encontrados,
    )

    reintento = resultados.get("reintento", [])
    if reintento:
        logger.info(
            "FASE 1 (búsqueda) no encontró %d expedientes; se escribieron a: %s",
            len(reintento), resultados.get("ruta_reintento", ""),
        )
    no_encontrados = resultados.get("pendientes", [])
    if no_encontrados:
        logger.info(
            "Tras la ruta manual quedan %d pendientes: %s",
            len(no_encontrados), resultados.get("ruta_pendientes", ""),
        )

    if ruta_pasos:
        logger.info("Detalle por paso: %s", ruta_pasos)
    logger.info("Resumen: %s", ruta_resumen)


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
    return parser.parse_args()


def main():
    args = parsear_argumentos()
    if args.fecha_inicio > args.fecha_fin:
        logger.error("La fecha inicial no puede ser posterior a la fecha final.")
        sys.exit(2)
    salidas = construir_salidas(BASE_DIR)

    logger.info("Inicio de ejecución: %s", datetime.now().isoformat())

    try:
        # Primero se ejecuta el bloque propio.
        ejecutar_bloque_propio(args)

        # Después se ejecuta el bloque de la compañera.
        logger.info("Inicio del bloque UISARD/Alfresco")
        fase_uisard(args)
        df = fase_conciliacion(args, salidas)
        logger.info("Consolidado listo (%d filas): %s", len(df), salidas["csv"])
        csv_verificacion = fase_unificacion(args, salidas, df)
        fase_alfresco(args, salidas, csv_verificacion)
        fase_notificacion(args, salidas, csv_verificacion)
        logger.info("Proceso completo: bloque propio y bloque UISARD/Alfresco finalizados.")

    except KeyboardInterrupt:
        logger.info("Proceso interrumpido por el usuario.")
        sys.exit(0)
    except SystemExit:
        raise
    except Exception as exc:
        logger.critical("Error fatal en el proceso: %s", exc, exc_info=True)
        sys.exit(1)
    finally:
         # Purga automática de archivos antiguos (logs, diagnósticos y reportes).
        try:
            limpiar(BASE_DIR, serie=True)
        except Exception as exc:
            logger.warning("Fallo durante la limpieza automática: %s", exc)


if __name__ == "__main__":
    main()
