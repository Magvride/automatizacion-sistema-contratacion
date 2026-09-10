import argparse
import csv
import os
import re
import shutil
import sys
import tempfile
import time
import random
import zipfile
from typing import Optional

import pandas as pd

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException,
    NoSuchElementException,
    ElementClickInterceptedException,
    StaleElementReferenceException,
    ElementNotInteractableException,
    WebDriverException,
)

from utils.logger import configurar_logger
from config import RESULTADOS_DIR, EXHIBITOS_VERIFICADOS_DIR
from resultados import construir_resultados, guardar_resultados
from dashboard import generar_dashboard, generar_estado_vivo

logger = configurar_logger("alfresco")


class AlfrescoExtractor:
    """Extrae el atributo title del menú de repositorio en Alfresco Share."""

    ELEMENTO_TITLE = (By.XPATH, "//*[@id='HEADER_REPOSITORY']")
    CONSTANTE_TITLE_ESPERADA = "Repositório"

    # Navegación por el árbol del repositorio (YUI TreeView / ygtv-*)
    REPOSITORIO_MENU = (By.XPATH, "//a[@href='/share/page/repository']")
    RAIZ_REPO_NOMBRE = "REPOSITORIO_UIS_0002"
    TRAZA = (By.CSS_SELECTOR, "span.ygtvlabel")
    # Un expediente "coherente" es un nombre real con forma Numero_Sufijo (p.ej. 2025000159_9702).
    REAL_EXPEDIENTE_RE = re.compile(r"^\d+_\d+")

    def __init__(
        self,
        url: str,
        usuario: str,
        contrasena: str,
        download_dir: Optional[str] = None,
        rapido: bool = True,
        timeout_busqueda: int = 6,
        descargar_zip: bool = True,
    ):
        self.url = url
        self.usuario = usuario
        self.contrasena = contrasena
        # Descarga del navegador a una carpeta temporal del sistema (se limpia sola).
        self.download_dir = download_dir or tempfile.mkdtemp(prefix="alfresco_dl_")
        self.rapido = rapido
        self.timeout_busqueda = timeout_busqueda
        # Corroboración por ZIP: desactivable para correr rápido (--no-zip).
        self.zip_verificacion = descargar_zip
        # Carpeta donde se guardan los ZIPS de los expedientes corroborados.
        self.archivo_dir = str(EXHIBITOS_VERIFICADOS_DIR)
        self.runtime_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
        os.makedirs(self.runtime_dir, exist_ok=True)
        self.driver: Optional[webdriver.Chrome] = None
        self.title: Optional[str] = None
        self._ultima_traza: list = []
        self.expediente_encontrado: bool = False
        # Caché de la subserie actualmente entrada: evita re-descender el árbol
        # cuando el siguiente expediente comparte la misma ruta (UAA, SERIE, SUB-SERIE).
        self._subserie_actual: Optional[tuple] = None
        self._serie_label: Optional[str] = None
        self._subserie_label: Optional[str] = None
        self._doms_guardados: int = 0
        # Número de archivos contenidos en el último ZIP corroborado.
        # Es la prueba de hallazgo del expediente (>= 1 archivo).
        self._cantidad_archivos: int = 0
        # Nodos ya expandidos con hijos cargados: evita re-descender/re-expandir
        # cuando se pasa de una subserie a otra de la misma UAA/serie.
        self._expandidos: set = set()

    # ------------------------------------------------------------------
    #  Utilidades de interacción
    # ------------------------------------------------------------------
    def _human_pause(self, min_ms: int = 300, max_ms: int = 500):
        if self.rapido:
            return 0.0
        return random.uniform(min_ms, max_ms) / 1000

    def _human_click(self, element):
        if self.rapido:
            ActionChains(self.driver).move_to_element(element).click().perform()
            return
        time.sleep(self._human_pause(150, 200))
        ActionChains(self.driver).move_to_element(element).pause(
            self._human_pause(100, 400)
        ).click().perform()
        time.sleep(self._human_pause(400, 500))

    # ------------------------------------------------------------------
    #  Ciclo de vida del driver
    # ------------------------------------------------------------------
    def _iniciar_driver(self) -> webdriver.Chrome:
        opts = Options()
        opts.add_experimental_option(
            "prefs",
            {
                "download.default_directory": self.download_dir,
                "download.prompt_for_download": False,
                "download.directory_upgrade": True,
            },
        )
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
        logger.info("Navegando a página de login Alfresco Share: %s", self.url)
        self.driver.get(self.url)
        wait = WebDriverWait(self.driver, 20)

        try:
            campo_usuario = wait.until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, "input#username, input[name='username'], input[type='text']")
                )
            )
            campo_usuario.clear()
            campo_usuario.send_keys(self.usuario)
            time.sleep(self._human_pause())

            campo_contrasena = self.driver.find_element(
                By.CSS_SELECTOR, "input#password, input[name='password'], input[type='password']"
            )
            campo_contrasena.clear()
            campo_contrasena.send_keys(self.contrasena)
            time.sleep(self._human_pause())

            btn_enviar = wait.until(
                EC.element_to_be_clickable(
                    (
                        By.XPATH,
                        "//button[@id='page_x002e_components_x002e_slingshot-login_x0023_default-submit-button']"
                        " | //button[contains(normalize-space(.), 'Iniciar sesión')]",
                    )
                )
            )
            self._human_click(btn_enviar)

            wait.until(
                EC.presence_of_element_located(self.ELEMENTO_TITLE)
            )
            logger.info("Autenticación exitosa para usuario: %s", self.usuario)
        except (TimeoutException, NoSuchElementException) as exc:
            logger.error("Fallo en autenticación: %s", exc)
            raise

    # ------------------------------------------------------------------
    #  Extracción del atributo title
    # ------------------------------------------------------------------
    def extraer_title(self) -> Optional[str]:
        wait = WebDriverWait(self.driver, 20)
        try:
            elemento = wait.until(
                EC.presence_of_element_located(self.ELEMENTO_TITLE)
            )
            self.title = elemento.get_attribute("title")
            logger.info(
                "Atributo title extraído: '%s' (esperado: '%s')",
                self.title,
                self.CONSTANTE_TITLE_ESPERADA,
            )
            return self.title
        except (TimeoutException, NoSuchElementException) as exc:
            logger.error("No se encontró HEADER_REPOSITORY: %s", exc)
            return None

    # ------------------------------------------------------------------
    #  Navegación por el árbol del repositorio
    #  Estructura: REPOSITORIO_UIS_0002 -> UAA -> SERIE -> NOMBRE EXPEDIENTE
    # ------------------------------------------------------------------
    def navegar_al_repositorio(self, timeout: int = 30, recargar: bool = False):
        """Llega al repositorio y espera a que cargue el árbol de carpetas.

        Primero intenta clicar el menú 'Repositorio'; si no es posible (o no
        navega), hace GET directo a la URL /share/page/repository.
        Con recargar=True fuerza la recarga de la página (árbol en estado limpio).
        """
        repo_url = self.url.rstrip("/") + "/repository"
        wait = WebDriverWait(self.driver, 20)
        try:
            link = wait.until(EC.element_to_be_clickable(self.REPOSITORIO_MENU))
            self._human_click(link)
            logger.info("Menú 'Repositorio' clickeado. Espere a que cargue la vista del repositorio.")
        except (TimeoutException, NoSuchElementException, ElementClickInterceptedException) as exc:
            logger.warning("No se pudo clicar el menú 'Repositorio' (%s). Navegando a %s", exc, repo_url)

        if recargar or "/repository" not in self.driver.current_url:
            logger.info("Navegando directamente al repositorio: %s", repo_url)
            self.driver.get(repo_url)

        try:
            WebDriverWait(self.driver, timeout).until(
                lambda _d: _d.find_elements(By.XPATH, (
                    f"//span[contains(@class,'ygtvlabel') and "
                    f"normalize-space(text())='{self.RAIZ_REPO_NOMBRE}']"
                ))
            )
            logger.info("Árbol del repositorio cargado (raíz '%s').", self.RAIZ_REPO_NOMBRE)
        except TimeoutException:
            logger.warning(
                "Tras navegar a '%s' no se detectó la raíz '%s' del árbol.",
                repo_url, self.RAIZ_REPO_NOMBRE,
            )
      

    def _normalizar_texto(self, texto: str) -> str:
        if not texto:
            return ""
        return re.sub(r"\s+", " ", texto.replace("\u00a0", " ")).strip()

    def _span_por_texto(self, scope, texto: str):
        """Devuelve el span.ygtvlabel cuyo texto coincide exactamente con texto."""
        objetivo = self._normalizar_texto(texto)
        try:
            for etiqueta in scope.find_elements(By.XPATH, ".//span[contains(@class,'ygtvlabel')]"):
                if self._normalizar_texto(etiqueta.text) == objetivo:
                    return etiqueta
        except StaleElementReferenceException:
            return None
        return None

    def _item_por_texto(self, scope, texto: str):
        """Devuelve el div.ygtvitem que contiene la etiqueta texto (consulta fresca)."""
        etiqueta = self._span_por_texto(scope, texto)
        if etiqueta is None:
            return None
        return etiqueta.find_element(By.XPATH, ".//ancestor::div[contains(@class,'ygtvitem')][1]")

    def _contenedor_hijos(self, item):
        return item.find_element(By.XPATH, "./div[contains(@class,'ygtvchildren')]")

    def _bajar_por_ruta(self, ruta: list, esperar: bool = False, timeout: int = 12):
        """Baja por la ruta de etiquetas re-anclando desde self.driver (consulta fresca).

        Devuelve el div.ygtvitem del último nivel de ``ruta`` o None si falta.
        ``ruta`` es una lista de etiquetas desde la raíz: [RAIZ, uaa, serie, subserie].
        """
        scope = self.driver
        item = None
        for i, texto in enumerate(ruta):
            if esperar:
                item = self._localizar_item_por_texto(scope, texto, timeout=timeout)
            else:
                item = self._item_por_texto(scope, texto)
            if item is None:
                return None
            if i < len(ruta) - 1:
                try:
                    scope = self._contenedor_hijos(item)
                except NoSuchElementException:
                    return None
        return item

    def _hijos_cargados(self, ruta: list) -> bool:
        """True si el nodo ruta[-1] ya tiene hijos renderizados (chequeo fresco)."""
        item = self._bajar_por_ruta(ruta)
        if item is None:
            return False
        try:
            hijos = self._contenedor_hijos(item)
            return len(hijos.find_elements(By.XPATH, "./div[contains(@class,'ygtvitem')]")) > 0
        except (NoSuchElementException, StaleElementReferenceException):
            return False

    def _localizar_item_por_texto(self, scope, texto: str, timeout: int = 12):
        """Espera y devuelve el div.ygtvitem cuya etiqueta coincide con texto."""
        wait = WebDriverWait(self.driver, timeout)
        try:
            return wait.until(lambda _d: self._item_por_texto(scope, texto))
        except TimeoutException:
            return None

    def _expandir_nodo(self, ruta: list, pre_wait: int = 0, timeout: int = 15):
        """Expande el nodo ruta[-1] y devuelve su contenedor de hijos (div.ygtvchildren).

        pre_wait>0: espera ese tiempo por si los hijos cargan de forma eager (la raíz
        lista todas las UAA sin clic). Si no cargan, clica el toggle (carga lazy).
        """
        if pre_wait:
            try:
                WebDriverWait(self.driver, pre_wait).until(
                    lambda _d: self._hijos_cargados(ruta)
                )
                logger.info("Nodo '%s' cargó sus hijos de forma eager.", ruta[-1])
                return self._contenedor_hijos(self._bajar_por_ruta(ruta))
            except TimeoutException:
                pass

        if self._hijos_cargados(ruta):
            logger.info("Nodo '%s' ya tenía hijos cargados (no se clica el toggle).", ruta[-1])
            return self._contenedor_hijos(self._bajar_por_ruta(ruta))

        item = self._bajar_por_ruta(ruta)
        if item is None:
            raise NoSuchElementException(f"No se encontró el nodo '{ruta[-1]}'")
        toggle = item.find_element(By.XPATH, ".//a[contains(@class,'ygtvspacer')]")
        self._human_click(toggle)

        try:
            WebDriverWait(self.driver, timeout).until(
                lambda _d: self._hijos_cargados(ruta)
            )
        except TimeoutException as exc:
            logger.error("No se expandió el nodo '%s' a tiempo: %s", ruta[-1], exc)

            raise

        return self._contenedor_hijos(self._bajar_por_ruta(ruta))

    def _entrar_nodo(self, ruta: list):
        """Entra/selecciona el nodo ruta[-1] haciendo clic en su etiqueta."""
        item = self._bajar_por_ruta(ruta)
        etiqueta = item.find_element(By.XPATH, ".//span[contains(@class,'ygtvlabel')]")
        self._human_click(etiqueta)

    def _existe_documento(self, objetivo: str):
        """True si en la biblioteca de documentos hay un ítem cuyo nombre coincide.

        Devuelve el elemento (enlace/etiqueta) encontrado para poder abrirlo, o None.
        """
        selectores = [
            "//h3[contains(@class,'filename')]//a[contains(@class,'filter-change')]",
            "//a[contains(@class,'filter-change')]",
            "//a[contains(@class,'item-name')]",
            "//a[contains(@class,'filename')]",
            "//span[contains(@class,'item-name')]",
            "//span[contains(@class,'filename')]",
            "//td[contains(@class,'name')]//a",
        ]
        try:
            elementos = []
            for sel in selectores:
                elementos.extend(self.driver.find_elements(By.XPATH, sel))
            for etiqueta in elementos:
                texto = self._normalizar_texto(etiqueta.text)
                if texto == objetivo or (objetivo and texto.startswith(objetivo)):
                    return etiqueta
        except StaleElementReferenceException:
            return None
        return None

    def _pagina_actual(self) -> Optional[int]:
        """Número de página mostrado por el paginador YUI (.yui-pg-current-page)."""
        try:
            el = self.driver.find_element(By.CSS_SELECTOR, ".yui-pg-current-page")
            return int(self._normalizar_texto(el.text))
        except (NoSuchElementException, ValueError):
            return None

    def _total_paginas(self, timeout: int = 5) -> Optional[int]:
        """Número de páginas totales a partir del texto 'N - M de TOTAL' del paginador."""
        wait = WebDriverWait(self.driver, timeout)
        try:
            el = wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".yui-pg-current"))
            )
            texto = self._normalizar_texto(el.text)
            m = re.search(r"(\d+)\s*[-–]\s*(\d+)\s+de\s+(\d+)", texto)
            if not m:
                # Variante en inglés: '1 - 50 of 373'
                m = re.search(r"(\d+)\s*[-–]\s*(\d+)\s+of\s+(\d+)", texto)
            if not m:
                return None
            total = int(m.group(3))
            inicio = int(m.group(1))
            fin = int(m.group(2))
            page_size = fin - inicio + 1
            if page_size <= 0:
                return None
            return -(-total // page_size)  # ceil(total / page_size)
        except (TimeoutException, NoSuchElementException):
            return None

    def _ir_a_pagina_siguiente(self, esperada: int, timeout: int = 10) -> bool:
        """Clica el botón '>>' del paginador y espera a que cargue la página ``esperada``."""
        wait = WebDriverWait(self.driver, timeout)
        try:
            next_btn = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, ".yui-pg-next")))
            self._human_click(next_btn)
            wait.until(lambda _d: self._pagina_actual() == esperada)
            return True
        except (TimeoutException, NoSuchElementException, ElementClickInterceptedException):
            return False

    def _buscar_expediente(
        self, expediente: str, timeout: Optional[int] = None, max_paginas: int = 200
    ):
        """Busca el expediente dentro de la biblioteca de la subserie actual (AJAX).

        La biblioteca pagina los resultados (paginador YUI: 'N - M de TOTAL'); como
        el expediente puede estar en cualquier página, recorre todas hasta
        encontrarlo o agotar las páginas. ``startswith`` permite que el nombre del
        CSV (0270_2026000733_9701) coincida con la carpeta_archivo completa
        (0270_2026000733_9701_9703).

        Devuelve el elemento del documento encontrado (para abrirlo) o None.
        """
        if timeout is None:
            timeout = self.timeout_busqueda
        objetivo = self._normalizar_texto(expediente)

        total_paginas = self._total_paginas()
        if total_paginas is None:
            total_paginas = 1
        total_paginas = min(total_paginas, max_paginas)
        if total_paginas > 1:
            logger.info("Expediente '%s': %d páginas en la subserie.", expediente, total_paginas)

        pagina = self._pagina_actual() or 1
        for _ in range(total_paginas - pagina + 1):
            try:
                return WebDriverWait(self.driver, timeout).until(
                    lambda _d: self._existe_documento(objetivo)
                )
            except TimeoutException:
                pass

            actual = self._pagina_actual() or pagina
            if actual >= total_paginas:
                break
            if not self._ir_a_pagina_siguiente(actual + 1):
                break

        return None

    # ------------------------------------------------------------------
    #  Fast path: búsqueda global (caja del header) antes de bajar el árbol
    # ------------------------------------------------------------------
    def _reset_navegacion(self):
        """Limpia las cachés de navegación del árbol (ruta y nodos expandidos)."""
        self._subserie_actual = None
        self._expandidos = set()
        self._serie_label = None
        self._subserie_label = None

    def _hay_resultado_busqueda(self, objetivo: str, uaa: Optional[str] = None,
                                serie: Optional[str] = None):
        """Devuelve la fila de resultado de búsqueda que mejor coincide con ``objetivo``.

        Orden de preferencia (evitar falsos positivos y no perder casos reales):
          1) Nombre + UAA + SERIE   -> ruta exacta.
          2) Nombre + UAA           -> confianza alta.
          3) Nombre solo            -> nombre casi único; se acepta y se alerta.
        Devuelve la fila con mayor confianza, o None si ninguna menciona el objetivo.
        """
        objetivo = self._normalizar_texto(objetivo)
        try:
            filas = self.driver.find_elements(
                By.CSS_SELECTOR, "tr.alfresco-search-AlfSearchResult"
            )
            if not filas:
                filas = self.driver.find_elements(
                    By.XPATH, "//div[contains(@class,'alfresco-search-AlfSearchResult')]"
                )
        except StaleElementReferenceException:
            logger.warning("Búsqueda '%s': estado inestable al leer resultados.", objetivo)
            return None

        coincidentes = []  # (confianza, fila, texto)
        for fila in filas:
            try:
                texto = self._normalizar_texto(fila.text)
            except StaleElementReferenceException:
                logger.warning("Búsqueda '%s': resultado caducó al leer su texto.", objetivo)
                continue
            if not objetivo or objetivo not in texto:
                continue
            if uaa and uaa in texto:
                if serie and serie in texto:
                    coincidentes.append((3, fila, texto))
                else:
                    coincidentes.append((2, fila, texto))
            else:
                coincidentes.append((1, fila, texto))

        if not coincidentes:
            return None

        coincidentes.sort(key=lambda m: m[0], reverse=True)
        nivel, fila_mejor, texto_mejor = coincidentes[0]
        if nivel < 3:
            distintos = {self._normalizar_texto(c[2]) for c in coincidentes}
            if len(distintos) > 1:
                logger.warning(
                    "Búsqueda '%s': %d candidatos sin confirmar ruta (nivel %d) -> %s. "
                    "Revisar posible homónimo.",
                    objetivo, len(distintos), nivel, ", ".join(sorted(distintos)),
                )
            else:
                logger.warning(
                    "Búsqueda '%s': resultado no confirma UAA/SERIE (nivel %d) -> '%s'. "
                    "Se acepta por ser nombre único.",
                    objetivo, nivel, texto_mejor,
                )
        return fila_mejor

    def _abrir_resultado(self, fila):
        """Clica el enlace del resultado para abrir la carpeta/expediente."""
        try:
            link = fila.find_element(By.CSS_SELECTOR, "a.alfresco-navigation-_HtmlAnchorMixin")
        except NoSuchElementException:
            try:
                link = fila.find_element(By.XPATH, ".//a[contains(@class,'_HtmlAnchorMixin')]")
            except NoSuchElementException:
                try:
                    link = fila.find_element(By.XPATH, ".//a[@href]")
                except NoSuchElementException:
                    logger.warning("Fast path: resultado sin enlace para abrir.")
                    return False
        self._human_click(link)
        return True

    def _carpeta_tiene_contenido(self, timeout: int = 8) -> bool:
        """True si la carpeta abierta muestra ficheros O subcarpetas."""
        wait = WebDriverWait(self.driver, timeout)
        selectores = [
            "//h3[contains(@class,'filename')]",
            "//tr[contains(@class,'yui-dt-rec')]",
            "//tr[contains(@class,'yui-dt-even')]",
            "//tr[contains(@class,'yui-dt-odd')]",
            "//div[contains(@class,'doclist')]//td[contains(@class,'name')]//a",
            "//a[contains(@class,'filter-change')]",
            "//a[contains(@class,'item-name')]",
        ]
        try:
            return wait.until(
                lambda _d: any(_d.find_elements(By.XPATH, s) for s in selectores)
            )
        except TimeoutException:
            return False

    def _guardar_dom_diagnostico(self, prefijo: str):
        """Vuelca el HTML actual a logs/diagnostico/ (máx. 10 por corrida)."""
        if self.driver is None:
            return
        if self._doms_guardados >= 10:
            return
        try:
            html = self.driver.page_source
        except (WebDriverException, StaleElementReferenceException) as exc:
            logger.warning("No se pudo capturar el DOM para diagnóstico: %s", exc)
            return
        carpeta = os.path.join(self.runtime_dir, "diagnostico")
        os.makedirs(carpeta, exist_ok=True)
        nombre = f"alfresco_{prefijo}_{int(time.time() * 1000)}.html"
        ruta = os.path.join(carpeta, nombre)
        try:
            with open(ruta, "w", encoding="utf-8") as f:
                f.write(html)
            logger.info("DOM de diagnóstico guardado: %s", ruta)
        except OSError as exc:
            logger.warning("No se pudo guardar DOM de diagnóstico: %s", exc)
        self._doms_guardados += 1

    # ------------------------------------------------------------------
    #  Corroboración: dentro de la carpeta del expediente, usar la lista de
    #  documentos para descargar todo como ZIP (Selecionar -> Tudo ->
    #  Itens selecionados -> Baixar como zip) y guardarlo.
    # ------------------------------------------------------------------
    def _cerrar_menu(self):
        """Cierra el menú desplegable si quedó abierto (restaura el estado)."""
        try:
            ActionChains(self.driver).send_keys(Keys.ESCAPE).perform()
        except Exception:
            pass

    def _esperar_elemento(self, xpath: str, timeout: int = 12):
        """Espera y devuelve el primer elemento visible que cumple ``xpath`` (o None)."""
        wait = WebDriverWait(self.driver, timeout)
        try:
            return wait.until(EC.visibility_of_element_located((By.XPATH, xpath)))
        except TimeoutException:
            return None

    def _esperar_archivo_zip(self, antes: set, objetivo: str, timeout: int = 60) -> Optional[str]:
        """Espera a que termine y aparezca el ZIP de la descarga (prefiere el del expediente)."""
        fin = time.time() + timeout
        while time.time() < fin:
            try:
                actual = set(os.listdir(self.download_dir))
            except OSError:
                time.sleep(1)
                continue
            nuevos = [f for f in actual if f not in antes]
            if any(f.lower().endswith(".crdownload") for f in nuevos):
                time.sleep(1)
                continue
            zips = [f for f in nuevos if f.lower().endswith(".zip")]
            if zips:
                candidato = next((f for f in zips if objetivo in f), None)
                if candidato is None:
                    candidato = max(zips, key=lambda f: os.path.getmtime(os.path.join(self.download_dir, f)))
                return os.path.join(self.download_dir, candidato)
            time.sleep(1)
        return None

    def _guardar_y_extraer(self, ruta_zip: str, objetivo: str) -> bool:
        """Mueve el ZIP a <destino>/<expediente>/ y lo descomprime."""
        try:
            carpeta = os.path.join(self.archivo_dir, objetivo)
            os.makedirs(carpeta, exist_ok=True)
            destino_zip = os.path.join(carpeta, os.path.basename(ruta_zip))
            shutil.move(ruta_zip, destino_zip)
            with zipfile.ZipFile(destino_zip) as z:
                z.extractall(carpeta)
            n_items = sum(len(files) for _, _, files in os.walk(carpeta))
            self._cantidad_archivos = n_items
            logger.info(
                "Corroboración ZIP de '%s': %d ítems -> %s",
                objetivo, n_items, carpeta,
            )
            return True
        except (OSError, zipfile.BadZipFile) as exc:
            logger.warning("Corroboración ZIP fallida al guardar/extraer '%s': %s", objetivo, exc)
            return False

    def _descargar_zip_en_carpeta(self, expediente: str) -> bool:
        """Dentro de la carpeta abierta, selecciona todo y descarga el ZIP."""
        objetivo = self._normalizar_texto(expediente)
        self._cantidad_archivos = 0
        try:
            os.makedirs(self.download_dir, exist_ok=True)
            antes = set(os.listdir(self.download_dir))
        except OSError:
            antes = set()

        boton_select = self._esperar_elemento(
            "//button[contains(@id,'fileSelect-button')]", timeout=15
        )
        if boton_select is None:
            logger.warning("Corroboración ZIP: sin botón 'Selecionar' en '%s'.", expediente)
            self._guardar_dom_diagnostico("sin_boton_selecionar")
            return False
        self._human_click(boton_select)

        opc_todo = self._esperar_elemento("//span[contains(@class,'selectAll')]", timeout=8)
        if opc_todo is None:
            logger.warning("Corroboración ZIP: sin opción 'Tudo' para '%s'.", expediente)
            self._cerrar_menu()
            return False
        self._human_click(opc_todo)

        boton_items = self._esperar_elemento(
            "//button[contains(@id,'selectedItems-button')]", timeout=8
        )
        if boton_items is None:
            logger.warning("Corroboración ZIP: sin botón 'Itens selecionados' para '%s'.", expediente)
            self._guardar_dom_diagnostico("sin_boton_items")
            return False
        self._human_click(boton_items)

        opc_zip = self._esperar_elemento("//span[contains(@class,'onActionDownload')]", timeout=8)
        if opc_zip is None:
            logger.warning("Corroboración ZIP: sin opción 'Baixar como zip' para '%s'.", expediente)
            self._cerrar_menu()
            return False
        self._human_click(opc_zip)

        ruta_zip = self._esperar_archivo_zip(antes, objetivo)
        if ruta_zip is None:
            logger.warning("Corroboración ZIP: no llegó el archivo para '%s'.", expediente)
            return False
        return self._guardar_y_extraer(ruta_zip, objetivo)

    def _escribir_busqueda(self, caja, objetivo: str) -> bool:
        """Escribe el término en la caja de búsqueda de forma robusta (JS como respaldo)."""
        try:
            caja.clear()
            caja.send_keys(objetivo)
        except (ElementNotInteractableException, StaleElementReferenceException, WebDriverException) as exc:
            logger.warning("Fast path: no se pudo escribir en la caja: %s", exc)
            return False
        time.sleep(0.2)
        try:
            if objetivo not in (caja.get_attribute("value") or ""):
                self.driver.execute_script(
                    "arguments[0].value = arguments[1];"
                    "arguments[0].dispatchEvent(new Event('input',{bubbles:true}));"
                    "arguments[0].dispatchEvent(new Event('change',{bubbles:true}));"
                    "arguments[0].dispatchEvent(new Event('keydown',{key:'Enter',bubbles:true}));",
                    caja, objetivo,
                )
                time.sleep(0.15)
        except (StaleElementReferenceException, WebDriverException):
            pass
        return True

    def _disparar_busqueda(self, caja, icono) -> bool:
        """Dispara la búsqueda: clic en el icono de búsqueda o Enter."""
        try:
            if icono is not None:
                self._human_click(icono)
            else:
                caja.send_keys(Keys.RETURN)
            return True
        except (ElementNotInteractableException, StaleElementReferenceException, WebDriverException) as exc:
            logger.warning("Fast path: no se pudo disparar la búsqueda: %s", exc)
            return False

    def _candidatos_buscador(self) -> list:
        """Devuelve los buscadores disponibles en orden de preferencia.

        Orden: (1) caja estándar del header, (2) buscador dedicado de la página
        de resultados (combobox searchTerm + icono blanco).
        """
        candidatos = []
        # 1) Caja estándar del header (siempre presente en la barra superior).
        try:
            caja = WebDriverWait(self.driver, 1.0).until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, "input#HEADER_SEARCHBOX_FORM_FIELD, input.alfresco-header-SearchBox-text")
                )
            )
            candidatos.append((caja, None, "header"))
        except TimeoutException:
            pass
        # 2) Buscador dedicado de la página de resultados (disparo distinto).
        try:
            caja = WebDriverWait(self.driver, 0.8).until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, "input[name='searchTerm']")
                )
            )
            icono = None
            try:
                icono = WebDriverWait(self.driver, 1.5).until(
                    EC.element_to_be_clickable(
                        (By.XPATH, "//span[contains(@class,'alf-white-search-icon')]")
                    )
                )
            except TimeoutException:
                pass
            candidatos.append((caja, icono, "searchTerm"))
        except TimeoutException:
            pass
        return candidatos

    def _buscar_expediente_por_busqueda(
        self, expediente: str, uaa: Optional[str] = None, serie: Optional[str] = None,
        timeout: int = 6, intentos: int = 2,
    ) -> bool:
        """Fast path: busca el expediente probando los buscadores en orden.

        1) Primero la caja del header (Enter); si no lo trae, luego el buscador
           dedicado de la página de resultados (combobox searchTerm + icono).
           Escribi el término de forma robusta (JS de respaldo si se pierde).
        2) Espera el resultado con timeout corto; si un buscador no lo trae, prueba
           el siguiente; si ninguno lo devuelve, no reintenta (ahorra tiempo) y cae
           a la ruta manual del árbol.
        3) Abre la carpeta y, si está activada la corroboración, descarga el ZIP.
        """
        objetivo = self._normalizar_texto(expediente)
        for intento in range(intentos):
            if intento > 0:
                logger.info("Fast path: reintento %d para '%s'.", intento + 1, expediente)
                self.navegar_al_repositorio()
            candidatos = self._candidatos_buscador()
            if not candidatos:
                logger.warning("Fast path: sin caja de búsqueda (intento %d).", intento + 1)
                if intento == intentos - 1:
                    self._guardar_dom_diagnostico("buscador_no_disponible")
                continue
            encontrado = False
            for caja, icono, etiqueta in candidatos:
                logger.info("Fast path: buscando '%s' en '%s'.", expediente, etiqueta)
                if not self._escribir_busqueda(caja, objetivo):
                    continue
                if not self._disparar_busqueda(caja, icono):
                    continue
                try:
                    fila = WebDriverWait(self.driver, timeout).until(
                        lambda _d: self._hay_resultado_busqueda(objetivo, uaa, serie)
                    )
                except TimeoutException:
                    continue
                if fila is None:
                    continue
                if not self._abrir_resultado(fila):
                    logger.warning("Fast path: no se pudo abrir el resultado de '%s'.", expediente)
                    continue
                if not self._carpeta_tiene_contenido():
                    logger.warning("Fast path: resultado '%s' sin contenido visible.", expediente)
                    continue
                if self.zip_verificacion:
                    if self._descargar_zip_en_carpeta(expediente) and self._cantidad_archivos >= 1:
                        return True
                    logger.warning(
                        "Fast path: '%s' no corroborado por ZIP (n=%d).",
                        expediente, self._cantidad_archivos,
                    )
                    encontrado = False
                    break
                self._cantidad_archivos = 0
                logger.warning(
                    "Fast path: '%s' verificado por contenido (ZIP desactivado).", expediente,
                )
                encontrado = True
                break
            if encontrado:
                return True
            self._guardar_dom_diagnostico("sin_resultados")
            return False
        return False

    def _candidatos_serie(self, uaa: str, serie: str) -> list:
        """Etiquetas probables de la SERIE en el árbol.

        La serie se guarda con el código de la UAA como prefijo:
        UAA '1110_RECTORIA' + serie 'C10_CONVENIOS' -> carpeta '1110_C10_CONVENIOS'.
        """
        codigo = re.match(r"^(\d+)", uaa).group(1) if re.match(r"^(\d+)", uaa) else uaa
        prefijo = f"{codigo}_{serie}"
        candidatos = []
        if not serie.startswith(f"{codigo}_"):
            candidatos.append(prefijo)
        if serie not in candidatos:
            candidatos.append(serie)
        return candidatos

    def _candidatos_subserie(self, uaa: str, subserie: str) -> list:
        """Etiquetas probables de la SUB-SERIE en el árbol.

        La subserie se guarda con el código de la UAA como prefijo, igual que
        la serie: UAA '1110_RECTORIA' + subserie 'C10.11_...' -> '1110_C10.11_...'.
        """
        codigo = re.match(r"^(\d+)", uaa).group(1) if re.match(r"^(\d+)", uaa) else uaa
        prefijo = f"{codigo}_{subserie}"
        candidatos = []
        if not subserie.startswith(f"{codigo}_"):
            candidatos.append(prefijo)
        if subserie not in candidatos:
            candidatos.append(subserie)
        return candidatos

    def _navegar_hasta_subserie(self, uaa: str, serie: str, subserie: str):
        """Navega Repositorio -> UAA -> SERIE -> SUB-SERIE y entra/selecciona la subserie.

        Si la subserie pedida coincide con ``self._subserie_actual`` (algo habitual
        en el modo lote, donde varios expedientes comparten ruta), reutiliza los
        nodos ya expandidos y no vuelve a descender el árbol.

        Devuelve ``(serie_label, subserie_label, encontrado)``.
        """
        R = self.RAIZ_REPO_NOMBRE

        # 0) Reutilizar la subserie ya entrada (evita re-descender el árbol).
        if self._subserie_actual == (uaa, serie, subserie):
            logger.info("Ruta ya entrada: reutilizando subserie '%s'.", self._subserie_label)
            self._traza("REPOSITORIO", R, True)
            self._traza("UAA", uaa, True)
            self._traza("SERIE", self._serie_label, True)
            self._traza("SUB-SERIE", self._subserie_label, True)
            return self._serie_label, self._subserie_label, True

        # 1) Repositorio (raíz)
        if (R,) not in self._expandidos:
            item_raiz = self._bajar_por_ruta([R], esperar=True, timeout=25)
            self._traza("REPOSITORIO", R, item_raiz is not None)
            if item_raiz is None:
                logger.error("No se encontró el nodo raíz '%s'.", R)
                return None, None, False
            logger.info("Repositorio '%s' OK. Expandiendo...", R)
            self._expandir_nodo([R], pre_wait=10, timeout=20)
            self._expandidos.add((R,))
        else:
            self._traza("REPOSITORIO", R, True)

        # 2) UAA
        if (R, uaa) not in self._expandidos:
            item_uaa = self._bajar_por_ruta([R, uaa], esperar=True, timeout=12)
            self._traza("UAA", uaa, item_uaa is not None)
            if item_uaa is None:
                logger.warning("UAA '%s' no encontrada bajo la raíz.", uaa)
        
                return None, None, False
            logger.info("UAA '%s' OK. Expandiendo...", uaa)
            self._expandir_nodo([R, uaa])
            self._expandidos.add((R, uaa))
        else:
            self._traza("UAA", uaa, True)

        # 3) SERIE (buscada como {codigo_uaa}_{serie})
        serie_label = None
        for candidato in self._candidatos_serie(uaa, serie):
            item_serie = self._bajar_por_ruta([R, uaa, candidato], esperar=True, timeout=8)
            if item_serie is not None:
                serie_label = candidato
                break
        self._traza("SERIE", serie_label or serie, serie_label is not None)
        if serie_label is None:
            logger.warning("SERIE '%s' no encontrada bajo UAA '%s'.", serie, uaa)
        
            return None, None, False
        if (R, uaa, serie_label) not in self._expandidos:
            logger.info("SERIE '%s' OK. Expandiendo...", serie_label)
            self._expandir_nodo([R, uaa, serie_label])
            self._expandidos.add((R, uaa, serie_label))

        # 4) SUB-SERIE (buscada como {codigo_uaa}_{subserie})
        subserie_label = None
        for candidato in self._candidatos_subserie(uaa, subserie):
            item_sub = self._bajar_por_ruta([R, uaa, serie_label, candidato], esperar=True, timeout=10)
            if item_sub is not None:
                subserie_label = candidato
                break
        self._traza("SUB-SERIE", subserie_label or subserie, subserie_label is not None)
        if subserie_label is None:
            logger.warning("SUB-SERIE '%s' no encontrada bajo SERIE '%s'.", subserie, serie_label)
        
            return None, None, False

        self._entrar_nodo([R, uaa, serie_label, subserie_label])
        logger.info("Sub-serie '%s' alcanzada y seleccionada. Ruta completa OK.", subserie_label)

        self._serie_label = serie_label
        self._subserie_label = subserie_label
        self._subserie_actual = (uaa, serie, subserie)
        return serie_label, subserie_label, True

    def _navegar_arbol(self, uaa: str, serie: str, subserie: str, expediente: Optional[str] = None) -> bool:
        """Ruta manual: Repositorio -> UAA -> SERIE -> SUB-SERIE y busca el expediente.

        Sin fast path. Registra cada nivel en ``self._ultima_traza`` y el hallazgo
        del expediente en ``self.expediente_encontrado``. Devuelve True si llega y
        entra a la subserie (aunque el expediente no esté dentro).
        """
        logger.info(
            "Ruta manual UAA='%s' | SERIE='%s' | SUB-SERIE='%s'",
            uaa, serie, subserie,
        )
        self._ultima_traza = []

        serie_label, subserie_label, encontrado = self._navegar_hasta_subserie(
            uaa, serie, subserie
        )
        if not encontrado:
            return False

        self.expediente_encontrado = False
        if expediente:
            elemento = self._buscar_expediente(expediente)
            if elemento is not None:
                self._human_click(elemento)
                if self.zip_verificacion:
                    self.expediente_encontrado = (
                        self._descargar_zip_en_carpeta(expediente)
                        and self._cantidad_archivos >= 1
                    )
                else:
                    self._cantidad_archivos = 0
                    self.expediente_encontrado = True
            self._traza("EXPEDIENTE", expediente, self.expediente_encontrado)
            if self.expediente_encontrado:
                logger.info("EXPEDIENTE '%s' encontrado dentro de la subserie '%s'.", expediente, subserie_label)
            else:
                logger.warning("EXPEDIENTE '%s' no encontrado dentro de la subserie '%s'.", expediente, subserie_label)
        return True

    def navegar_ruta(self, uaa: str, serie: str, subserie: str, expediente: Optional[str] = None) -> bool:
        """Verifica un registro: fast path (buscadores) y, como último recurso, la ruta manual.

        Devuelve True si llega/entra en la subserie; el hallazgo del expediente queda
        en ``self.expediente_encontrado``. Registra la traza en ``self._ultima_traza``.
        """
        logger.info(
            "Buscando ruta UAA='%s' | SERIE='%s' | SUB-SERIE='%s'",
            uaa, serie, subserie,
        )
        self._ultima_traza = []
        if expediente:
            if self._buscar_expediente_por_busqueda(expediente, uaa=uaa, serie=serie):
                self.expediente_encontrado = True
                self._traza("BUSQUEDA", expediente, True)
                logger.info("Fast path: expediente '%s' localizado vía buscador global.", expediente)
                return True
            logger.warning(
                "Fast path sin éxito para '%s'; se usa la ruta manual del árbol.",
                expediente,
            )
            self._reset_navegacion()
            self.navegar_al_repositorio()
        return self._navegar_arbol(uaa, serie, subserie, expediente)

    def _traza(self, nivel: str, valor: str, encontrado: bool):
        self._ultima_traza.append({
            "NIVEL": nivel,
            "VALOR": valor,
            "ENCONTRADO": encontrado,
        })
        logger.info("Traza: %s | %s | %s", nivel, valor, "OK" if encontrado else "NO")

    def ejecutar_navegacion_ruta(self, uaa: str, serie: str, nombre_expediente: str) -> bool:
        try:
            self.driver = self._iniciar_driver()
            self.autenticar()
          
            self.navegar_al_repositorio()

            return self.navegar_ruta(uaa, serie, nombre_expediente)
        except Exception as exc:
            logger.critical("Fallo en la navegación de ruta Alfresco: %s", exc, exc_info=True)
            return False
        finally:
            self.cerrar()

    # ------------------------------------------------------------------
    #  Verificación por lotes desde un CSV (conciliación de datos)
    # ------------------------------------------------------------------
    def _append_csv(self, ruta: str, encabezados: list, filas: list):
        """Añade ``filas`` a un CSV creando la cabecera la primera vez.

        Permite que los resultados se vean en disco mientras el script corre,
        de modo que una interrupción a mitad de la ejecución no pierda
        los registros ya verificados.
        """
        if not filas:
            return
        carpeta = os.path.dirname(ruta) or "."
        os.makedirs(carpeta, exist_ok=True)
        es_nuevo = not os.path.isfile(ruta)
        try:
            with open(ruta, "a", newline="", encoding="utf-8-sig") as f:
                escritor = csv.DictWriter(f, fieldnames=encabezados, lineterminator="\n")
                if es_nuevo:
                    escritor.writeheader()
                for fila in filas:
                    escritor.writerow({
                        c: ("" if fila.get(c) is None else str(fila.get(c, "")))
                        for c in encabezados
                    })
        except OSError as exc:
            logger.warning("No se pudo escribir en %s: %s", ruta, exc)

    def _celda_csv(self, fila, columna: str) -> str:
        try:
            valor = fila[columna]
        except KeyError:
            return ""
        if pd.isna(valor):
            return ""
        return str(valor).strip()

    def _ruta_csv_aux(self, ruta_resumen: Optional[str], nombre: str) -> str:
        """Deriva una ruta CSV auxiliar en la misma carpeta que el resumen."""
        if ruta_resumen:
            carpeta = os.path.dirname(ruta_resumen)
        else:
            carpeta = str(RESULTADOS_DIR)
        os.makedirs(carpeta, exist_ok=True)
        return os.path.join(carpeta, nombre)

    def _es_expediente_coherente(self, nombre: str) -> bool:
        """True si el nombre parece un expediente real (Numero_Sufijo)."""
        return bool(nombre and self.REAL_EXPEDIENTE_RE.match(nombre))

    def _describir_anomalia(self, nombre: str, exp_found: bool) -> str:
        """Describe qué puede estar pasando cuando el nombre no es un expediente coherente."""
        if self._es_expediente_coherente(nombre):
            return ""
        base = (
            "El nombre no corresponde a un expediente real (formato de carpeta de "
            "prueba/obsoleta)"
        )
        if exp_found:
            return (
                base + ". En Alfresco existe una carpeta que coincide literalmente con "
                "ese nombre; posible registro que debería depurarse del reporte."
            )
        return base + ". No se encontró en Alfresco; posible registro que debería depurarse del reporte."

    def _registrar_resultado(self, nombre, uaa, serie, subserie, encontrado_ruta, pasos, resumen):
        """Calcula el motivo y apila en ``resumen``/``pasos``.

        Devuelve (fila_resumen, filas_paso, exp_found).
        """
        exp_found = self.expediente_encontrado and encontrado_ruta
        if exp_found:
            motivo = ""
        elif not encontrado_ruta:
            motivo = "carpeta_no_encontrada"
        else:
            motivo = "expediente_no_encontrado"

        filas_paso = []
        for paso in self._ultima_traza:
            fila_paso = {
                "NOMBRE EXPEDIENTE": nombre,
                "UAA": uaa,
                "SERIE": serie,
                "SUB-SERIE": subserie,
                **paso,
            }
            pasos.append(fila_paso)
            filas_paso.append(fila_paso)

        fila_resumen = {
            "NOMBRE EXPEDIENTE": nombre,
            "UAA": uaa,
            "SERIE": serie,
            "SUB-SERIE": subserie,
            "alfresco": "SI" if exp_found else "NO",
            "cantidad_archivos": self._cantidad_archivos,
            "MOTIVO": motivo,
            "EXPEDIENTE_ENCONTRADO": "SI" if exp_found else "NO",
            "DESCRIPCION": self._describir_anomalia(nombre, exp_found),
        }
        resumen.append(fila_resumen)
        return fila_resumen, filas_paso, exp_found

    def _leer_consolidado(self, ruta_consolidado) -> pd.DataFrame:
        """Carga el consolidado 02 (o devuelve vacío si no existe/falla)."""
        if not ruta_consolidado or not os.path.isfile(ruta_consolidado):
            return pd.DataFrame()
        try:
            return pd.read_csv(ruta_consolidado, encoding="utf-8-sig", dtype=str).fillna("")
        except Exception as exc:  # noqa: BLE001
            logger.warning("No se pudo leer el consolidado para las salidas en vivo: %s", exc)
            return pd.DataFrame()

    def _actualizar_salidas(
        self,
        resumen,
        ruta_consolidado=None,
        ruta_resultados=None,
        ruta_dashboard=None,
    ):
        """Refresca 03_Resultado_Final.xlsx y el dashboard con lo verificado hasta ahora.

        Se llama tras cada expediente para poder seguir el avance en vivo. Los
        errores de escritura (p. ej. el Excel abierto) no detienen el flujo.
        """
        consolidado = self._leer_consolidado(ruta_consolidado)
        try:
            df = construir_resultados(consolidado, resumen)
        except Exception as exc:  # noqa: BLE001
            logger.warning("No se pudo construir el reporte de resultados: %s", exc)
            return

        if ruta_resultados:
            try:
                guardar_resultados(df, ruta_resultados)
            except PermissionError:
                logger.debug("03_Resultado_Final.xlsx está abierto; se omite la actualización en vivo.")
            except Exception as exc:  # noqa: BLE001
                logger.warning("No se pudo actualizar 03_Resultado_Final en vivo: %s", exc)

        if ruta_dashboard:
            try:
                generar_dashboard(df, ruta_dashboard)
            except Exception as exc:  # noqa: BLE001
                logger.warning("No se pudo actualizar el dashboard en vivo: %s", exc)

    def _volcar_estado_vivo(
        self,
        ruta_vivo,
        expediente,
        indice,
        total,
        fase,
        resumen,
        estado="BUSCANDO",
    ):
        """Refresca el panel en tiempo real con el expediente que se está buscando."""
        if not ruta_vivo:
            return
        try:
            generar_estado_vivo(
                expediente=expediente,
                indice=indice,
                total=total,
                fase=fase,
                resumen=resumen,
                ruta=ruta_vivo,
                estado=estado,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("No se pudo actualizar el dashboard en vivo: %s", exc)

    def verificar_expedientes_desde_csv(
        self,
        ruta_csv: str,
        ruta_pasos: Optional[str] = None,
        ruta_resumen: Optional[str] = None,
        ruta_consolidado: Optional[str] = None,
        ruta_resultados: Optional[str] = None,
        ruta_dashboard: Optional[str] = None,
        ruta_vivo: Optional[str] = None,
    ) -> dict:
        """Verifica en dos fases: primero búsqueda (header + searchTerm), luego ruta manual.

        Fase 1 (búsqueda): recorre el CSV y busca cada expediente en los buscadores.
        Los que la búsqueda no encuentra se guardan en ``reintento`` (en memoria).
        Fase 2 (ruta manual): re-itera sobre ese subconjunto usando el árbol
        (Repositorio -> UAA -> SERIE -> SUB-SERIE -> expediente).

        La prueba de hallazgo es el ZIP corroborado con >= 1 archivo (columna
        ``cantidad_archivos``). Genera solo dos salidas: ``06_Verificacion_Alfresco.csv``
        (todos los registros) y ``07_Expedientes_Faltantes.csv`` (los no encontrados).
        """
        try:
            df = pd.read_csv(ruta_csv, encoding="utf-8-sig")
        except Exception as exc:
            logger.error("No se pudo leer el CSV '%s': %s", ruta_csv, exc)
            return {"pasos": [], "resumen": []}

        logger.info("CSV cargado: %d filas. Columnas: %s", len(df), list(df.columns))

        claves = ["UAA", "SERIE"]
        if "SUBSERIE" in df.columns:
            claves.append("SUBSERIE")
        if "NOMBRE EXPEDIENTE" in df.columns and "NOMBRE EXPEDIENTE" not in claves:
            claves.append("NOMBRE EXPEDIENTE")
        df = df.sort_values(claves, kind="mergesort").reset_index(drop=True)
        logger.info("CSV reordenado por ruta (UAA -> SERIE -> SUB-SERIE).")

        pasos = []
        resumen = []
        encabezados_resumen = [
            "NOMBRE EXPEDIENTE", "UAA", "SERIE", "SUB-SERIE",
            "alfresco", "cantidad_archivos",
            "MOTIVO", "EXPEDIENTE_ENCONTRADO", "DESCRIPCION",
        ]
        if ruta_resumen and os.path.isfile(ruta_resumen):
            os.remove(ruta_resumen)

        self._subserie_actual = None
        self._expandidos = set()
        self.navegar_al_repositorio()

        # --- FASE 1: búsqueda en los buscadores (header + searchTerm) ---
        reintento = []
        for idx, fila in df.iterrows():
            nombre = self._celda_csv(fila, "NOMBRE EXPEDIENTE")
            uaa = self._celda_csv(fila, "UAA")
            serie = self._celda_csv(fila, "SERIE")
            subserie = self._celda_csv(fila, "SUBSERIE") or self._celda_csv(fila, "NOMBRE EXPEDIENTE")

            if not nombre or not uaa:
                logger.debug("Fila %d ignorada (nombre/uaa vacío).", idx)
                continue

            self._volcar_estado_vivo(
                ruta_vivo, nombre, idx + 1, len(df), "BÚSQUEDA", resumen, "BUSCANDO"
            )
            try:
                encontrado = self._buscar_expediente_por_busqueda(nombre, uaa=uaa, serie=serie)
            except Exception as exc:
                logger.error("Excepción buscando '%s': %s", nombre, exc)
                encontrado = False
                self._cantidad_archivos = 0
                self._ultima_traza = [{"NIVEL": "BUSQUEDA", "VALOR": nombre, "ENCONTRADO": False}]

            if encontrado:
                self.expediente_encontrado = True
                self._traza("BUSQUEDA", nombre, True)
                logger.info("Fast path: '%s' localizado vía buscador global.", nombre)
                self._registrar_resultado(nombre, uaa, serie, subserie, True, pasos, resumen)
                self._actualizar_salidas(resumen, ruta_consolidado, ruta_resultados, ruta_dashboard)
                self._volcar_estado_vivo(
                    ruta_vivo, nombre, idx + 1, len(df), "BÚSQUEDA", resumen, "ENCONTRADO"
                )
                logger.info("[%d/%d] (búsqueda) '%s' -> ENCONTRADO", idx + 1, len(df), nombre)
            else:
                self.expediente_encontrado = False
                self._ultima_traza = []
                reintento.append({
                    "NOMBRE EXPEDIENTE": nombre, "UAA": uaa, "SERIE": serie, "SUB-SERIE": subserie,
                })
                self._volcar_estado_vivo(
                    ruta_vivo, nombre, idx + 1, len(df), "BÚSQUEDA", resumen, "REINTENTO"
                )
                logger.info("[%d/%d] (búsqueda) '%s' -> NO ENCONTRADO (pasa a reintento)", idx + 1, len(df), nombre)

        if reintento:
            logger.info("FASE 1: %d no encontrados -> reintento.", len(reintento))
        else:
            logger.info("FASE 1: todos encontrados por búsqueda (sin reintento).")

        # --- FASE 2: ruta manual del árbol sobre los no encontrados ---
        if reintento:
            self._subserie_actual = None
            self._expandidos = set()
            self.navegar_al_repositorio()
            for j, item in enumerate(reintento):
                nombre = item["NOMBRE EXPEDIENTE"]
                uaa = item["UAA"]
                serie = item["SERIE"]
                subserie = item["SUB-SERIE"]
                self._volcar_estado_vivo(
                    ruta_vivo, nombre, len(df) - len(reintento) + j + 1, len(df),
                    "RUTA MANUAL", resumen, "BUSCANDO",
                )
                try:
                    encontrado = self._navegar_arbol(uaa, serie, subserie, nombre)
                except Exception as exc:
                    logger.error("Excepción en ruta manual '%s': %s", nombre, exc)
                    encontrado = False
                    self.expediente_encontrado = False
                    self._cantidad_archivos = 0
                    self._ultima_traza = [{"NIVEL": "NAVEGACION", "VALOR": subserie, "ENCONTRADO": False}]
                _, _, exp_found = self._registrar_resultado(
                    nombre, uaa, serie, subserie, encontrado, pasos, resumen,
                )
                self._actualizar_salidas(resumen, ruta_consolidado, ruta_resultados, ruta_dashboard)
                self._volcar_estado_vivo(
                    ruta_vivo, nombre, len(df) - len(reintento) + j + 1, len(df),
                    "RUTA MANUAL", resumen, "LISTO",
                )
                logger.info(
                    "[reintento %d/%d] '%s' -> %s",
                    j + 1, len(reintento), nombre,
                    "ENCONTRADO" if exp_found else (
                        "SUB-SERIE OK / EXP NO" if encontrado else "NO ENCONTRADO"
                    ),
                )

        # --- Resumen final + pendientes definitivos ---
        ruta_pendientes = self._ruta_csv_aux(ruta_resumen, "07_Expedientes_Faltantes.csv")
        finales_no = [
            {k: v for k, v in r.items() if k != "DESCRIPCION"}
            for r in resumen if r["EXPEDIENTE_ENCONTRADO"] == "NO"
        ]
        pd.DataFrame(resumen, columns=encabezados_resumen).to_csv(
            ruta_resumen, index=False, encoding="utf-8-sig"
        )
        pd.DataFrame(finales_no).to_csv(ruta_pendientes, index=False, encoding="utf-8-sig")

        logger.info(
            "Verificación finalizada (2 fases): %d registros | %d encontrados | %d no encontrados. "
            "Pendientes: %s",
            len(resumen), len(resumen) - len(finales_no), len(finales_no), ruta_pendientes,
        )
        return {
            "pasos": pasos,
            "resumen": resumen,
            "reintento": reintento,
            "pendientes": finales_no,
            "ruta_resumen": ruta_resumen,
            "ruta_pendientes": ruta_pendientes,
        }

    def ejecutar_verificacion_csv(
        self,
        ruta_csv: str,
        ruta_pasos: Optional[str] = None,
        ruta_resumen: Optional[str] = None,
        ruta_consolidado: Optional[str] = None,
        ruta_resultados: Optional[str] = None,
        ruta_dashboard: Optional[str] = None,
        ruta_vivo: Optional[str] = None,
    ) -> dict:
        if not ruta_resumen:
            ruta_resumen = os.path.join(str(RESULTADOS_DIR), "06_Verificacion_Alfresco.csv")
        logger.info(
            "Salida: resumen=%s | pendientes=%s",
            ruta_resumen,
            os.path.join(os.path.dirname(ruta_resumen) or ".", "07_Expedientes_Faltantes.csv"),
        )
        try:
            self.driver = self._iniciar_driver()
            self.autenticar()

            return self.verificar_expedientes_desde_csv(
                ruta_csv, ruta_pasos, ruta_resumen,
                ruta_consolidado, ruta_resultados, ruta_dashboard, ruta_vivo,
            )
        except Exception as exc:
            logger.critical("Fallo en la verificación Alfresco desde CSV: %s", exc, exc_info=True)
            return {"pasos": [], "resumen": []}
        finally:
            self.cerrar()

    # ------------------------------------------------------------------
    #  Utilidades
    # ------------------------------------------------------------------
    



    # ------------------------------------------------------------------
    #  Orquestación
    # ------------------------------------------------------------------
    def ejecutar_extraccion(self) -> Optional[str]:
        try:
            self.driver = self._iniciar_driver()
            self.autenticar()
           
            return self.extraer_title()
        except Exception as exc:
            logger.critical("Fallo en la fase de extracción Alfresco: %s", exc, exc_info=True)
            return None
        finally:
            self.cerrar()


def parsear_argumentos() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extrae el atributo title del menú Repositório en Alfresco Share."
    )
    parser.add_argument(
        "--url",
        type=str,
        default=os.getenv("ALFRESCO_SHARE_URL", "https://gesdoc.uis.edu.co/share/page"),
        help="URL de la página de login de Alfresco Share.",
    )
    parser.add_argument(
        "--usuario",
        type=str,
        default=os.getenv("ALFRESCO_SHARE_USER", "consulta_contratos"),
        help="Usuario de acceso.",
    )
    parser.add_argument(
        "--contrasena",
        type=str,
        default=os.getenv("ALFRESCO_SHARE_PASS", ""),
        help="Contraseña de acceso.",
    )
    parser.add_argument(
        "--uaa",
        type=str,
        default=None,
        help="Unidad Académico-Administrativa a buscar en el árbol (ej. 1110_RECTORIA).",
    )
    parser.add_argument(
        "--serie",
        type=str,
        default=None,
        help="Serie a buscar bajo la UAA (ej. 1110_C09_CONTRATOS).",
    )
    parser.add_argument(
        "--expediente",
        type=str,
        default=None,
        help="Nombre del expediente a entrar (PASO. ...).",
    )
    parser.add_argument(
        "--csv",
        type=str,
        default=None,
        help=(
            "Ruta a un CSV con columnas 'NOMBRE EXPEDIENTE', 'UAA' y 'SERIE' "
            "para verificar todas las rutas (ej. archivos/05_Datos_filtrados/01_Contratos_en_UISARD.csv)."
        ),
    )
    parser.add_argument(
        "--solo-title",
        action="store_true",
        help="Solo extrae el atributo title del menú Repositorio (modo antiguo).",
    )
    parser.add_argument(
        "--lento",
        action="store_true",
        help="Desactiva el modo rápido (pausas human-like y timeouts largos).",
    )
    return parser.parse_args()


def main():
    args = parsear_argumentos()
    logger.info("Inicio de ejecución: %s", time.strftime("%Y-%m-%d %H:%M:%S"))

    extractor = AlfrescoExtractor(
        url=args.url,
        usuario=args.usuario,
        contrasena=args.contrasena,
        rapido=not args.lento,
    )

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    try:
        if args.solo_title:
            title = extractor.ejecutar_extraccion()
            if title is None:
                logger.error("No se pudo extraer el atributo title.")
                sys.exit(1)
            logger.info("VALOR_TITLE=%s", title)
            print(f"VALOR_TITLE={title}")
            return

        if args.csv:
            ruta_csv = args.csv
        elif all([args.uaa, args.serie, args.expediente]):
            logger.info("Modo verificación de ruta (UAA -> SERIE -> NOMBRE EXPEDIENTE).")
            encontrado = extractor.ejecutar_navegacion_ruta(
                uaa=args.uaa,
                serie=args.serie,
                nombre_expediente=args.expediente,
            )
            logger.info("RUTA_ENCONTRADA=%s", encontrado)
            print(f"RUTA_ENCONTRADA={encontrado}")
            sys.exit(0 if encontrado else 1)
        else:
            ruta_csv = str(RESULTADOS_DIR / "01_Contratos_en_UISARD.csv")
            logger.info("Sin --csv: se usa el inicio por defecto %s", ruta_csv)

        if not os.path.isfile(ruta_csv):
            logger.error("No existe el CSV de conciliación: %s", ruta_csv)
            sys.exit(1)

        logger.info("Modo verificación por lotes desde CSV: %s", ruta_csv)
        resultados = extractor.ejecutar_verificacion_csv(ruta_csv)
        resumen = resultados.get("resumen", [])
        if not resumen:
            logger.error("No se obtuvieron resultados del CSV.")
            sys.exit(1)

        ruta_resumen = resultados.get("ruta_resumen") or str(RESULTADOS_DIR / "06_Verificacion_Alfresco.csv")
        ruta_pendientes = resultados.get("ruta_pendientes") or str(RESULTADOS_DIR / "07_Expedientes_Faltantes.csv")

        encontrados = sum(1 for r in resumen if r["MOTIVO"] == "")
        total = len(resumen)
        print(f"REGISTROS={total} SUBSERIE_OK={encontrados} NO_ENCONTRADOS={total - encontrados}")
        print(f"RESUMEN_CSV={ruta_resumen}")
        print(f"PENDIENTES_CSV={ruta_pendientes}")
        sys.exit(0 if encontrados > 0 else 1)
    except KeyboardInterrupt:
        logger.info("Proceso interrumpido por el usuario.")
        sys.exit(0)
    except Exception as exc:
        logger.critical("Error fatal en el proceso: %s", exc, exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    print("Este script forma parte del flujo. Ejecuta: python main.py")
    sys.exit(0)
