import argparse
import csv
import os
import re
import sys
import tempfile
import time
import random
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
from config import RESULTADOS_DIR

logger = configurar_logger("alfresco")


class AlfrescoExtractor:
    """Extrae el atributo title del menú de repositorio en Alfresco Share."""

    ELEMENTO_TITLE = (By.XPATH, "//*[@id='HEADER_REPOSITORY']")
    CONSTANTE_TITLE_ESPERADA = "Repositório"

    # Navegación por el árbol del repositorio (YUI TreeView / ygtv-*)
    REPOSITORIO_MENU = (By.XPATH, "//a[@href='/share/page/repository']")
    RAIZ_REPO_NOMBRE = "REPOSITORIO_UIS_0002"
    TRAZA = (By.CSS_SELECTOR, "span.ygtvlabel")

    def __init__(
        self,
        url: str,
        usuario: str,
        contrasena: str,
        download_dir: Optional[str] = None,
        rapido: bool = True,
        timeout_busqueda: int = 8,
    ):
        self.url = url
        self.usuario = usuario
        self.contrasena = contrasena
        # Descarga del navegador a una carpeta temporal del sistema (se limpia sola).
        self.download_dir = download_dir or tempfile.mkdtemp(prefix="alfresco_dl_")
        self.rapido = rapido
        self.timeout_busqueda = timeout_busqueda
        self.runtime_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
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
            self._capturar_pantalla("error_login")
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
            self._guardar_html_diagnostico("error_expandir_nodo")
            self._capturar_pantalla("error_expandir_nodo")
            raise

        return self._contenedor_hijos(self._bajar_por_ruta(ruta))

    def _entrar_nodo(self, ruta: list):
        """Entra/selecciona el nodo ruta[-1] haciendo clic en su etiqueta."""
        item = self._bajar_por_ruta(ruta)
        etiqueta = item.find_element(By.XPATH, ".//span[contains(@class,'ygtvlabel')]")
        self._human_click(etiqueta)

    def _existe_documento(self, objetivo: str) -> bool:
        """True si en la biblioteca de documentos hay un ítem cuyo nombre coincide."""
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
                    return True
        except StaleElementReferenceException:
            return False
        return False

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
    ) -> bool:
        """Busca el expediente dentro de la biblioteca de la subserie actual (AJAX).

        La biblioteca pagina los resultados (paginador YUI: 'N - M de TOTAL'); como
        el expediente puede estar en cualquier página, recorre todas hasta
        encontrarlo o agotar las páginas. ``startswith`` permite que el nombre del
        CSV (0270_2026000733_9701) coincida con la carpeta_archivo completa
        (0270_2026000733_9701_9703).
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
                WebDriverWait(self.driver, timeout).until(
                    lambda _d: self._existe_documento(objetivo)
                )
                return True
            except TimeoutException:
                pass

            actual = self._pagina_actual() or pagina
            if actual >= total_paginas:
                break
            if not self._ir_a_pagina_siguiente(actual + 1):
                break

        return False

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
        """Devuelve la fila de resultado de búsqueda que coincide con ``objetivo``.

        Confirma que el nombre del resultado contenga el objetivo y, si se
        pasan ``uaa``/``serie``, que la ruta del resultado los incluya (evita
        falsos positivos de carpetas homónimas en otra UAA).
        """
        try:
            filas = self.driver.find_elements(
                By.CSS_SELECTOR, "tr.alfresco-search-AlfSearchResult"
            )
            if not filas:
                filas = self.driver.find_elements(
                    By.XPATH, "//div[contains(@class,'alfresco-search-AlfSearchResult')]"
                )
            for fila in filas:
                texto = self._normalizar_texto(fila.text)
                if objetivo not in texto:
                    continue
                if uaa and uaa not in texto:
                    continue
                if serie and serie not in texto:
                    continue
                return fila
        except StaleElementReferenceException:
            return None
        return None

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

    def _carpeta_tiene_contenido(self, timeout: int = 12) -> bool:
        """True si la carpeta abierta muestra al menos un fichero (h3.filename)."""
        wait = WebDriverWait(self.driver, timeout)
        try:
            return wait.until(
                lambda _d: len(
                    _d.find_elements(By.XPATH, "//h3[contains(@class,'filename')]")
                ) > 0
            )
        except TimeoutException:
            return False

    def _buscar_expediente_por_busqueda(
        self, expediente: str, uaa: Optional[str] = None, serie: Optional[str] = None,
        timeout: int = 15,
    ) -> bool:
        """Fast path: busca el expediente en el buscador global de Alfresco.

        1) Escribe el nombre en la caja de búsqueda del header y pulsa Enter.
        2) Espera al resultado (fila alfresco-search-AlfSearchResult) y lo cruzase
           con la UAA/SERIE del CSV.
        3) Abre la carpeta resultante y comprueba que tiene ficheros dentro.
        """
        objetivo = self._normalizar_texto(expediente)
        wait = WebDriverWait(self.driver, timeout)
        try:
            caja = wait.until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, "input#HEADER_SEARCHBOX_FORM_FIELD, input.alfresco-header-SearchBox-text")
                )
            )
        except TimeoutException:
            logger.warning("Fast path: caja de búsqueda del header no disponible.")
            return False

        try:
            caja.clear()
            caja.send_keys(objetivo)
            time.sleep(self._human_pause(250, 600))
            caja.send_keys(Keys.RETURN)
        except (ElementNotInteractableException, StaleElementReferenceException, WebDriverException) as exc:
            logger.warning("Fast path: no se pudo escribir en la caja: %s", exc)
            return False

        try:
            fila = wait.until(lambda _d: self._hay_resultado_busqueda(objetivo, uaa, serie))
        except TimeoutException:
            logger.warning("Fast path: sin resultados para '%s'.", expediente)
            return False

        if fila is None:
            return False
        if not self._abrir_resultado(fila):
            return False
        return self._carpeta_tiene_contenido()

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
                self._guardar_html_diagnostico("no_encontro_raiz")
                self._capturar_pantalla("no_encontro_raiz")
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
                self._guardar_html_diagnostico("no_encontro_uaa")
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
            self._guardar_html_diagnostico("no_encontro_serie")
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
            self._guardar_html_diagnostico("no_encontro_subserie")
            return None, None, False

        self._entrar_nodo([R, uaa, serie_label, subserie_label])
        logger.info("Sub-serie '%s' alcanzada y seleccionada. Ruta completa OK.", subserie_label)

        self._serie_label = serie_label
        self._subserie_label = subserie_label
        self._subserie_actual = (uaa, serie, subserie)
        return serie_label, subserie_label, True

    def navegar_ruta(self, uaa: str, serie: str, subserie: str, expediente: Optional[str] = None) -> bool:
        """Busca secuencialmente Repositorio -> UAA -> SERIE -> SUB-SERIE en el árbol.

        Si se proporciona ``expediente``, tras entrar en la subserie lo busca dentro
        de la biblioteca de documentos y registra el hallazgo en
        ``self.expediente_encontrado``.

        Registra en self._ultima_traza cada nivel con su valor y si se localizó.
        Devuelve True si llega y entra en la subserie; False en caso contrario.
        """
        logger.info(
            "Buscando ruta UAA='%s' | SERIE='%s' | SUB-SERIE='%s'",
            uaa, serie, subserie,
        )
        self._ultima_traza = []

        # 0) Fast path: buscador global del header. Si aparece la carpeta, la abre
        #    y se considera ENCONTRADO sin bajar por el árbol (ruta más larga).
        if expediente:
            if self._buscar_expediente_por_busqueda(expediente, uaa=uaa, serie=serie):
                self.expediente_encontrado = True
                self._traza("BUSQUEDA", expediente, True)
                logger.info("Fast path: expediente '%s' localizado vía buscador global.", expediente)
                return True
            logger.warning(
                "Fast path sin éxito para '%s'; se restaura el árbol y se usa la ruta oficial.",
                expediente,
            )
            self._reset_navegacion()
            self.navegar_al_repositorio()

        # 1-4) Navegación con caché de ruta ya entrada (REPO -> UAA -> SERIE -> SUB-SERIE)
        serie_label, subserie_label, encontrado = self._navegar_hasta_subserie(
            uaa, serie, subserie
        )
        if not encontrado:
            return False

        # 5) EXPEDIENTE dentro de la sub-serie
        self.expediente_encontrado = False
        if expediente:
            self.expediente_encontrado = self._buscar_expediente(expediente)
            self._traza("EXPEDIENTE", expediente, self.expediente_encontrado)
            if self.expediente_encontrado:
                logger.info("EXPEDIENTE '%s' encontrado dentro de la subserie '%s'.", expediente, subserie_label)
            else:
                logger.warning("EXPEDIENTE '%s' no encontrado dentro de la subserie '%s'.", expediente, subserie_label)
                self._guardar_html_diagnostico("no_encontro_expediente")
                self._capturar_pantalla("no_encontro_expediente")

        return True

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
            self._guardar_html_diagnostico("post_login")
            self.navegar_al_repositorio()
            self._guardar_html_diagnostico("post_repositorio")
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

    def verificar_expedientes_desde_csv(
        self,
        ruta_csv: str,
        ruta_pasos: Optional[str] = None,
        ruta_resumen: Optional[str] = None,
    ) -> dict:
        """Recorre el CSV (NOMBRE EXPEDIENTE, UAA, SERIE) y navega a cada ruta.

        Si se indican ``ruta_pasos`` y ``ruta_resumen``, los resultados se
        escriben en disco de forma incremental (tras cada registro), de modo
        que pueden monitorearse mientras corre y no se pierden si se interrumpe.
        """
        try:
            df = pd.read_csv(ruta_csv, encoding="utf-8-sig")
        except Exception as exc:
            logger.error("No se pudo leer el CSV '%s': %s", ruta_csv, exc)
            return {"pasos": [], "resumen": []}

        logger.info("CSV cargado: %d filas. Columnas: %s", len(df), list(df.columns))

        # Agrupa las filas por ruta para que los expedientes de una misma subserie
        # queden consecutivos y se reutilice la navegación ya expandida del árbol.
        claves = ["UAA", "SERIE"]
        if "SUBSERIE" in df.columns:
            claves.append("SUBSERIE")
        if "NOMBRE EXPEDIENTE" in df.columns and "NOMBRE EXPEDIENTE" not in claves:
            claves.append("NOMBRE EXPEDIENTE")
        df = df.sort_values(claves, kind="mergesort").reset_index(drop=True)
        logger.info("CSV reordenado por ruta (UAA -> SERIE -> SUB-SERIE) para reutilizar nodos.")

        pasos = []  # filas apiladas: una por nivel recorrido de cada registro
        resumen = []  # una fila por registro

        # Encabezados fijos para la escritura incremental.
        encabezados_pasos = ["NOMBRE EXPEDIENTE", "UAA", "SERIE", "SUB-SERIE", "NIVEL", "VALOR", "ENCONTRADO"]
        encabezados_resumen = ["NOMBRE EXPEDIENTE", "UAA", "SERIE", "SUB-SERIE", "MOTIVO", "EXPEDIENTE_ENCONTRADO"]
        # En una re-ejecución se empieza de cero (sin acumular registros viejos).
        if ruta_pasos and os.path.isfile(ruta_pasos):
            os.remove(ruta_pasos)
        if ruta_resumen and os.path.isfile(ruta_resumen):
            os.remove(ruta_resumen)

        self._subserie_actual = None  # limpiar caché de ruta
        self._expandidos = set()  # limpiar caché de nodos expandidos
        self.navegar_al_repositorio()

        for idx, fila in df.iterrows():
            nombre = self._celda_csv(fila, "NOMBRE EXPEDIENTE")
            uaa = self._celda_csv(fila, "UAA")
            serie = self._celda_csv(fila, "SERIE")
            subserie = self._celda_csv(fila, "SUBSERIE") or self._celda_csv(fila, "NOMBRE EXPEDIENTE")

            if not nombre or not uaa:
                logger.debug("Fila %d ignorada (nombre/uaa vacío).", idx)
                continue

            try:
                encontrado = self.navegar_ruta(uaa, serie, subserie, expediente=nombre)
            except Exception as exc:
                logger.error("Excepción navegando '%s': %s", nombre, exc)
                self._guardar_html_diagnostico("error_navegacion")
                self._capturar_pantalla("error_navegacion")
                encontrado = False
                self.expediente_encontrado = False
                self._ultima_traza = [t for t in self._ultima_traza] or [{
                    "NIVEL": "NAVEGACION", "VALOR": subserie, "ENCONTRADO": False,
                }]

            exp_found = self.expediente_encontrado and encontrado
            if exp_found:
                motivo = ""
            elif not encontrado:
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
                "MOTIVO": motivo,
                "EXPEDIENTE_ENCONTRADO": "SI" if exp_found else "NO",
            }
            resumen.append(fila_resumen)

            # Escritura incremental: los resultados quedan visibles en disco.
            if ruta_pasos and ruta_resumen:
                self._append_csv(ruta_pasos, encabezados_pasos, filas_paso)
                self._append_csv(ruta_resumen, encabezados_resumen, [fila_resumen])
            logger.info(
                "[%d/%d] '%s' -> %s",
                idx + 1, len(df), nombre,
                "ENCONTRADO" if exp_found else (
                    "SUB-SERIE OK / EXP NO" if encontrado else "NO ENCONTRADO"
                ),
            )

        logger.info("Verificación CSV finalizada: %d registros, %d pasos apilados.", len(resumen), len(pasos))
        return {"pasos": pasos, "resumen": resumen}

    def ejecutar_verificacion_csv(
        self,
        ruta_csv: str,
        ruta_pasos: Optional[str] = None,
        ruta_resumen: Optional[str] = None,
    ) -> dict:
        if not ruta_pasos or not ruta_resumen:
            carpeta = str(RESULTADOS_DIR)
            ruta_pasos = ruta_pasos or os.path.join(carpeta, "verificacion_alfresco_pasos.csv")
            ruta_resumen = ruta_resumen or os.path.join(carpeta, "verificacion_alfresco.csv")
        logger.info("Salida incremental: pasos=%s | resumen=%s", ruta_pasos, ruta_resumen)
        try:
            self.driver = self._iniciar_driver()
            self.autenticar()
            self._guardar_html_diagnostico("post_login")
            return self.verificar_expedientes_desde_csv(ruta_csv, ruta_pasos, ruta_resumen)
        except Exception as exc:
            logger.critical("Fallo en la verificación Alfresco desde CSV: %s", exc, exc_info=True)
            return {"pasos": [], "resumen": []}
        finally:
            self.cerrar()

    # ------------------------------------------------------------------
    #  Utilidades
    # ------------------------------------------------------------------
    def _guardar_html_diagnostico(self, nombre: str):
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
    #  Orquestación
    # ------------------------------------------------------------------
    def ejecutar_extraccion(self) -> Optional[str]:
        try:
            self.driver = self._iniciar_driver()
            self.autenticar()
            self._guardar_html_diagnostico("post_login")
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
            "para verificar todas las rutas (ej. archivos/resultados/conciliacion_datos.csv)."
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

    base_dir = os.path.dirname(os.path.abspath(__file__))

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
            ruta_csv = str(RESULTADOS_DIR / "conciliacion_datos.csv")
            logger.info("Sin --csv: se usa el inicio por defecto %s", ruta_csv)

        if not os.path.isfile(ruta_csv):
            logger.error("No existe el CSV de conciliación: %s", ruta_csv)
            sys.exit(1)

        logger.info("Modo verificación por lotes desde CSV: %s", ruta_csv)
        resultados = extractor.ejecutar_verificacion_csv(ruta_csv)
        pasos = resultados.get("pasos", [])
        resumen = resultados.get("resumen", [])
        if not resumen:
            logger.error("No se obtuvieron resultados del CSV.")
            sys.exit(1)

        output_dir = str(RESULTADOS_DIR)
        os.makedirs(output_dir, exist_ok=True)
        ruta_pasos = os.path.join(output_dir, "verificacion_alfresco_pasos.csv")
        ruta_resumen = os.path.join(output_dir, "verificacion_alfresco.csv")
        pd.DataFrame(pasos).to_csv(ruta_pasos, index=False, encoding="utf-8-sig")
        pd.DataFrame(resumen).to_csv(ruta_resumen, index=False, encoding="utf-8-sig")

        encontrados = sum(1 for r in resumen if r["MOTIVO"] == "")
        total = len(resumen)
        print(f"REGISTROS={total} SUBSERIE_OK={encontrados} NO_ENCONTRADOS={total - encontrados}")
        print(f"PASOS_CSV={ruta_pasos}")
        print(f"RESUMEN_CSV={ruta_resumen}")
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
