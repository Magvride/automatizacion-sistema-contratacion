import argparse
import sys
import os
import random
import tempfile
import time
import shutil
import pandas as pd
from datetime import datetime, timedelta
from typing import Optional

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException,
    NoSuchElementException,
    ElementClickInterceptedException,
    WebDriverException,
)

from utils.logger import configurar_logger
from config import REPORTES_DIR, RESULTADOS_DIR

logger = configurar_logger("uisard")


class UISARDExtractor:
    """Extrae reportes de la plataforma UISARD en formato Excel."""

    RUTAS_NAVEGACION = {
        "gestion_documental": (
            By.XPATH,
            "//aside//button[.//mat-icon[text()='folder_shared']]",
        ),
        "sistema_reportes": (
            By.XPATH,
            "//mat-tree-node[.//mat-label[@title='Sistema de reportes']]",
        ),
    }

    COLUMNAS_OBJETIVO = [
        "Nombre Expediente",
        "Número de Contrato",
        "Unidad Académico-Administrativa",
    ]

    def __init__(
        self,
        url: str,
        usuario: str,
        contrasena: str,
        fecha_inicio: str,
        fecha_fin: str,
        download_dir: Optional[str] = None,
    ):
        self.url = url
        self.usuario = usuario
        self.contrasena = contrasena
        self.fecha_inicio = fecha_inicio
        self.fecha_fin = fecha_fin
        # Descarga del navegador a una carpeta temporal del sistema (se limpia sola).
        self.download_dir = download_dir or tempfile.mkdtemp(prefix="uisard_dl_")
        self.runtime_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs"
        )
        os.makedirs(self.runtime_dir, exist_ok=True)
        self.reportes_dir = str(REPORTES_DIR)
        os.makedirs(self.reportes_dir, exist_ok=True)
        self.driver: Optional[webdriver.Chrome] = None
        self._workbook: Optional[pd.ExcelWriter] = None

    def _human_pause(self, min_ms: int = 300, max_ms: int = 1200):
        return random.uniform(min_ms, max_ms) / 1000

    def _human_click(self, element):
        time.sleep(self._human_pause(150, 500))
        ActionChains(self.driver).move_to_element(element).pause(
            self._human_pause(100, 400)
        ).click().perform()
        time.sleep(self._human_pause(400, 1200))

    # ------------------------------------------------------------------
    #  Ciclo de vida del driver
    # ------------------------------------------------------------------
    def _iniciar_driver(self) -> webdriver.Chrome:
        opts = Options()
        prefs = {
            "download.default_directory": self.download_dir,
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "plugins.always_open_pdf_externally": True,
        }
        opts.add_experimental_option("prefs", prefs)
        opts.add_argument("--start-maximized")
        opts.add_argument("--disable-blink-features=AutomationControlled")
        opts.add_argument("--no-sandbox")
        opts.add_argument("--disable-dev-shm-usage")

        driver = webdriver.Chrome(options=opts)
        driver.implicitly_wait(5)
        logger.info("Driver Chrome iniciado correctamente.")
        return driver

    def cerrar(self):
        if self.driver:
            self.driver.quit()
            logger.info("Driver cerrado.")

    # ------------------------------------------------------------------
    #  Autenticación
    # ------------------------------------------------------------------
    def autenticar(self):
        logger.info("Navegando a página de login UISARD: %s", self.url)
        self.driver.get(self.url)
        wait = WebDriverWait(self.driver, 20)

        try:
            campo_usuario = wait.until(
                EC.presence_of_element_located(
                    (
                        By.CSS_SELECTOR,
                        "input[formcontrolname='username'], input[name='username'], input[type='text']",
                    )
                )
            )
            campo_usuario.clear()
            campo_usuario.send_keys(self.usuario)
            time.sleep(self._human_pause())

            campo_contrasena = self.driver.find_element(
                By.CSS_SELECTOR,
                "input[formcontrolname='password'], input[name='password'], input[type='password']",
            )
            campo_contrasena.clear()
            campo_contrasena.send_keys(self.contrasena)
            time.sleep(self._human_pause())

            btn_login = self.driver.find_element(
                By.CSS_SELECTOR, "button[type='submit'], button.btn-primary"
            )
            self._human_click(btn_login)
            wait.until(EC.url_changes(self.url))
            logger.info("Autenticación exitosa para usuario: %s", self.usuario)
        except (TimeoutException, NoSuchElementException) as exc:
            logger.error("Fallo en autenticación: %s", exc)

            raise

    def _cerrar_cookies(self):
        wait = WebDriverWait(self.driver, 10)
        try:
            btn_aceptar = wait.until(
                EC.element_to_be_clickable(
                    (
                        By.XPATH,
                        "//mat-dialog-container//button[.//span[contains(text(),'Aceptar todas')]]",
                    )
                )
            )
            self._human_click(btn_aceptar)
            logger.info("Cookies aceptadas.")
        except TimeoutException:
            logger.info("No se encontró modal de cookies (ya cerrado o no apareció).")

    def seleccionar_rol_analista(self):
        wait = WebDriverWait(self.driver, 15)
        try:
            btn_dropdown = wait.until(
                EC.element_to_be_clickable(
                    (By.CSS_SELECTOR, "button.mat-mdc-menu-trigger")
                )
            )
            rol_actual = btn_dropdown.find_element(
                By.CSS_SELECTOR, "span.text"
            ).text.strip()
            logger.info("Rol actual detectado: '%s'", rol_actual)

            if "analista" in rol_actual.lower():
                logger.info(
                    "Ya se tiene el rol 'Analista de Contratación'. Se omite cambio."
                )
                return

            self._human_click(btn_dropdown)
            logger.debug("Menú de rol abierto.")

            selectores_rol = [
                "//app-select-role-panel//button[@title='Analista de contratación']",
                "//button[@class='btn menu-option truncate' and @title='Analista de contratación']",
                "//button[contains(@title,'Analista de contratación')]",
            ]

            opcion = None
            for selector in selectores_rol:
                try:
                    opcion = wait.until(
                        EC.element_to_be_clickable((By.XPATH, selector))
                    )
                    break
                except TimeoutException:
                    continue

            if opcion is None:
                logger.error(
                    "No se encontró la opción 'Analista de Contratación' en el menú."
                )

                return

            self._human_click(opcion)
            logger.info("Rol 'Analista de Contratación' seleccionado.")

        except (TimeoutException, NoSuchElementException) as exc:
            logger.error("Error seleccionando rol: %s", exc)

    # ------------------------------------------------------------------
    #  Navegación
    # ------------------------------------------------------------------
    def _click_menu(self, clave: str):
        wait = WebDriverWait(self.driver, 15)
        try:
            locator = self.RUTAS_NAVEGACION[clave]
            elem = wait.until(EC.element_to_be_clickable(locator))
            self._human_click(elem)
            logger.debug("Menú '%s' clickeado.", clave)
        except (TimeoutException, ElementClickInterceptedException) as exc:
            logger.error("Error navegando a '%s': %s", clave, exc)

            raise

    def navegar_a_sistema_reportes(self):
        self._click_menu("gestion_documental")
        self._click_menu("sistema_reportes")
        logger.info("Navegación hasta Sistema de Reportes completada.")

    # ------------------------------------------------------------------
    #  Configuración de filtros y descarga
    # ------------------------------------------------------------------
    def _formato_fecha_ui(self, fecha_iso: str) -> str:
        dt = datetime.strptime(fecha_iso, "%Y-%m-%d")
        return dt.strftime("%d/%m/%Y")

    def _seleccionar_tipo_reporte(self):
        wait = WebDriverWait(self.driver, 15)
        try:
            select_tipo = wait.until(
                EC.element_to_be_clickable(
                    (By.CSS_SELECTOR, "mat-select[formcontrolname='reportType']")
                )
            )
            self._human_click(select_tipo)

            opcion = wait.until(
                EC.element_to_be_clickable(
                    (By.XPATH, "//mat-option[.//span[contains(text(),'Expedientes')]]")
                )
            )
            self._human_click(opcion)
            logger.info("Tipo de reporte: Expedientes seleccionado.")
        except (TimeoutException, NoSuchElementException) as exc:
            logger.error("Error seleccionando tipo de reporte: %s", exc)

    def _aplicar_filtros(self):
        wait = WebDriverWait(self.driver, 15)
        try:
            btn_calendario = wait.until(
                EC.element_to_be_clickable(
                    (By.CSS_SELECTOR, "mat-datepicker-toggle button")
                )
            )
            self._human_click(btn_calendario)

            self._seleccionar_dia_calendario(self.fecha_inicio)
            time.sleep(self._human_pause(300, 700))
            self._seleccionar_dia_calendario(self.fecha_fin)
            time.sleep(self._human_pause(500, 1000))

            logger.info(
                "Fechas aplicadas: %s - %s",
                self._formato_fecha_ui(self.fecha_inicio),
                self._formato_fecha_ui(self.fecha_fin),
            )
        except (TimeoutException, NoSuchElementException) as exc:
            logger.error("Error aplicando fechas: %s", exc)

            raise

    def _seleccionar_dia_calendario(self, fecha_iso: str):
        wait = WebDriverWait(self.driver, 10)
        dt = datetime.strptime(fecha_iso, "%Y-%m-%d")
        dia = dt.day

        boton_dia = wait.until(
            EC.element_to_be_clickable(
                (
                    By.XPATH,
                    f"//mat-datepicker-content//button[.//span[contains(@class,'mat-calendar-body-cell-content') and normalize-space(text())='{dia}']]",
                )
            )
        )
        self._human_click(boton_dia)

    def _descargar_reporte(self, serie: str) -> Optional[str]:
        wait = WebDriverWait(self.driver, 15)
        try:
            select_serie = wait.until(
                EC.element_to_be_clickable(
                    (By.CSS_SELECTOR, "mat-select[formcontrolname='serie']")
                )
            )
            self._human_click(select_serie)

            opcion = wait.until(
                EC.element_to_be_clickable(
                    (
                        By.XPATH,
                        f"//mat-option[contains(translate(., 'abcdefghijklmnopqrstuvwxyzáéíóú', 'ABCDEFGHIJKLMNOPQRSTUVWXYZÁÉÍÓÚ'), '{serie.upper()}')]",
                    )
                )
            )
            self._human_click(opcion)
            logger.info("Serie '%s' seleccionada.", serie)

            self._aplicar_filtros()

            btn_generar = wait.until(
                EC.element_to_be_clickable(
                    (By.XPATH, "//button[.//span[contains(text(),'Generar reporte')]]")
                )
            )
            self._human_click(btn_generar)
            logger.info("Reporte '%s' en proceso de generación...", serie)

            return self._esperar_descarga(serie)
        except (TimeoutException, NoSuchElementException) as exc:
            logger.error("Error descargando serie '%s': %s", serie, exc)

            return None

    def _esperar_descarga(self, serie: str, timeout: int = 30) -> Optional[str]:
        extensiones = (".xlsx", ".xls", ".csv")
        archivos_previos = set(os.listdir(self.download_dir))
        chrome_default = os.path.join(os.path.expanduser("~"), "Downloads")
        archivos_previos_default = (
            set(os.listdir(chrome_default)) if os.path.isdir(chrome_default) else set()
        )
        inicio = time.time()

        logger.info("Buscando descarga para '%s' en: %s", serie, self.download_dir)

        while time.time() - inicio < timeout:
            archivos_actuales = set(os.listdir(self.download_dir))
            nuevos = archivos_actuales - archivos_previos
            for nombre in nuevos:
                if any(
                    nombre.endswith(ext) for ext in extensiones
                ) and not nombre.endswith(".crdownload"):
                    ruta_origen = os.path.join(self.download_dir, nombre)
                    nombre_serie = self._nombre_archivo_serie(serie, nombre)
                    ruta_destino = os.path.join(self.reportes_dir, nombre_serie)
                    shutil.copy2(ruta_origen, ruta_destino)
                    logger.info("Reporte '%s' guardado en: %s", serie, ruta_destino)
                    return ruta_destino

            if os.path.isdir(chrome_default):
                archivos_default = set(os.listdir(chrome_default))
                nuevos_default = archivos_default - archivos_previos_default
                for nombre in nuevos_default:
                    if any(
                        nombre.endswith(ext) for ext in extensiones
                    ) and not nombre.endswith(".crdownload"):
                        ruta_origen = os.path.join(chrome_default, nombre)
                        nombre_serie = self._nombre_archivo_serie(serie, nombre)
                        ruta_destino = os.path.join(self.reportes_dir, nombre_serie)
                        shutil.copy2(ruta_origen, ruta_destino)
                        logger.info(
                            "Reporte '%s' copiado desde Downloads a: %s",
                            serie,
                            ruta_destino,
                        )
                        return ruta_destino

            time.sleep(2)

        logger.warning(
            "Serie '%s': sin datos en el rango de fechas (no se generó descarga).",
            serie,
        )
        return None

    def _nombre_archivo_serie(self, serie: str, nombre_original: str) -> str:
        prefijos = {
            "Contratos": "contrato",
            "Convenios": "convenio",
            "Proyectos": "proyecto",
        }
        prefijo = prefijos.get(serie, serie.lower())
        fecha_str = datetime.now().strftime("%d-%m-%Y")
        ext = os.path.splitext(nombre_original)[1]
        return f"{prefijo}_reporte_{fecha_str}{ext}"

    # ------------------------------------------------------------------
    #  Lectura y consolidación
    # ------------------------------------------------------------------
    def _leer_excel(self, ruta: str, serie: str) -> pd.DataFrame:
        try:
            df = pd.read_excel(ruta, engine="openpyxl")
            df["Serie"] = serie
            logger.info(
                "Leído '%s': %d filas, %d columnas.", serie, len(df), len(df.columns)
            )
            logger.info("Columnas '%s': %s", serie, list(df.columns))
            return df
        except Exception as exc:
            logger.error("Error leyendo Excel %s: %s", ruta, exc)
            return pd.DataFrame()

    def extraer_todas_series(self) -> pd.DataFrame:
        series = ["Contratos", "Convenios", "Proyectos"]
        dataframes = []

        for serie in series:
            ruta = self._descargar_reporte(serie)
            if ruta:
                df = self._leer_excel(ruta, serie)
                if not df.empty:
                    dataframes.append(df)
            else:
                logger.warning("No se pudo descargar la serie '%s'.", serie)

        if not dataframes:
            logger.error("No se descargó ningún reporte.")
            return pd.DataFrame()

        consolidado = pd.concat(dataframes, ignore_index=True)
        columnas_disponibles = [
            c for c in self.COLUMNAS_OBJETIVO if c in consolidado.columns
        ]
        logger.info("Columnas objetivo disponibles: %s", columnas_disponibles)
        logger.info("Total filas antes del filtro: %d", len(consolidado))

        resultado = consolidado[columnas_disponibles].copy()
        if "Nombre Expediente" in resultado.columns:
            antes = len(resultado)
            resultado.dropna(subset=["Nombre Expediente"], inplace=True)
            logger.info(
                "dropna(Nombre Expediente): %d → %d filas", antes, len(resultado)
            )
        resultado.reset_index(drop=True, inplace=True)

        return resultado

    # ------------------------------------------------------------------
    #  Utilidades
    # ------------------------------------------------------------------
    #  Diagnóstico
    # ------------------------------------------------------------------
    def __html_diagnostico(self, nombre: str):
        carpeta = os.path.join(self.runtime_dir, "diagnostico")
        os.makedirs(carpeta, exist_ok=True)
        ruta = os.path.join(carpeta, f"{nombre}_{int(time.time())}.html")
        try:
            with open(ruta, "w", encoding="utf-8") as f:
                f.write(self.driver.page_source)
            logger.info("HTML de diagnóstico guardado: %s", ruta)
        except Exception:
            logger.warning("No se pudo guardar HTML de diagnóstico.")

    # ------------------------------------------------------------------

    def ejecutar_extraccion(self) -> pd.DataFrame:
        try:
            self.driver = self._iniciar_driver()
            self.autenticar()
            self._cerrar_cookies()

            self.seleccionar_rol_analista()

            self.navegar_a_sistema_reportes()
            self._seleccionar_tipo_reporte()
            return self.extraer_todas_series()
        except Exception as exc:
            logger.critical(
                "Fallo en la fase de extracción UISARD: %s", exc, exc_info=True
            )
            return pd.DataFrame()
        finally:
            self.cerrar()


def parsear_argumentos() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Automatización de extracción UISARD y verificación en Alfresco."
    )
    parser.add_argument(
        "--reporte-nuevas",
        type=str,
        default=None,
        help="Ruta al Excel de reporte de nuevas versiones para conciliación.",
    )
    parser.add_argument(
        "--skip-uisard",
        action="store_true",
        help="Omitir fase de extracción UISARD (usar consolidado previo).",
    )
    parser.add_argument(
        "--skip-alfresco",
        action="store_true",
        help="Omitir fase de verificación en Alfresco.",
    )
    parser.add_argument(
        "--ruta-consolidado",
        type=str,
        default=None,
        help="Ruta a consolidado UISARD previo (requiere --skip-uisard).",
    )
    return parser.parse_args()


def construir_salidas(base_dir: str) -> dict:
    carpeta = str(RESULTADOS_DIR)
    os.makedirs(carpeta, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return {
        "carpeta": carpeta,
        "consolidado": os.path.join(carpeta, f"consolidado_uisard_{ts}.xlsx"),
        "listos_cecop": os.path.join(carpeta, "expedientes_listos_cecop.xlsx"),
        "faltantes": os.path.join(carpeta, "reporte_faltantes_notificar.xlsx"),
        "notificaciones_dir": os.path.join(carpeta, "notificaciones"),
    }


def fase_uisard(args, salidas: dict) -> pd.DataFrame:
    logger.info("=" * 60)
    logger.info("FASE 1: Extracción de datos desde UISARD")
    logger.info("=" * 60)

    if args.skip_uisard:
        ruta = args.ruta_consolidado or salidas["consolidado"]
        logger.info("Omitiendo extracción. Cargando consolidado previo: %s", ruta)
        return pd.read_excel(ruta, engine="openpyxl")

    ayer = datetime.now() - timedelta(days=1)
    fecha_inicio = ayer.strftime("%Y-%m-%d")
    fecha_fin = ayer.strftime("%Y-%m-%d")

    extractor = UISARDExtractor(
        url=os.getenv("UISARD_URL", "https://gestion.uis.edu.co/auth/#/auth/login"),
        usuario=os.getenv("UISARD_USER", "mariamos_no_encontrada"),
        contrasena=os.getenv("UISARD_PASS", "lmHVKW9T"),
        fecha_inicio=fecha_inicio,
        fecha_fin=fecha_fin,
    )

    df = extractor.ejecutar_extraccion()

    if df.empty:
        logger.warning("No se obtuvieron datos de UISARD.")
        return df

    df.to_excel(salidas["consolidado"], index=False)
    logger.info("Consolidado guardado en: %s", salidas["consolidado"])
    return df


def main():
    args = parsear_argumentos()
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    salidas = construir_salidas(base_dir)

    logger.info("Inicio de ejecución: %s", datetime.now().isoformat())

    try:
        df_uisard = fase_uisard(args, salidas)
        if df_uisard.empty:
            logger.error("No hay datos de UISARD. Proceso terminado.")
            sys.exit(1)

        logger.info("Proceso completado exitosamente.")

    except KeyboardInterrupt:
        logger.info("Proceso interrumpido por el usuario.")
        sys.exit(0)
    except Exception as exc:
        logger.critical("Error fatal en el proceso: %s", exc, exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    print("Este script forma parte del flujo. Ejecuta: python main.py")
    sys.exit(0)
