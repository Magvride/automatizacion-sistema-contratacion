import random
from datetime import date, timedelta

from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth

from config import CONTRATOS_DIR, STORAGE_STATE_PATH, variable

USUARIO = variable("UIS_LOGIN_USER", variable("UISARD_USER"))
CLAVE = variable("UIS_LOGIN_PASS", variable("UISARD_PASS"))

LOGIN_URL = (
    "https://www.uis.edu.co/sistemasInformacion/login.seam"
    "?josso_back_to=https://www.uis.edu.co/sistemasInformacion/josso_security_check"
)

# Valores (atributo "value" del <option>) marcados en la captura:
# 298, 49, 20, 450, 18, 374, 19, 270
CLASES_CONTRATO_VALUES = ["3", "6", "7", "8", "12", "13", "15", "16"]

SELECT_CLASES_ID = "formConsultaRegistro:j_id215:selClasesContrato"

# IDs base de los widgets de calendario (sin sufijo PopupButton/InputDate)
CALENDAR_DESDE_BASE = "formConsultaRegistro:j_id119:j_id122"
CALENDAR_HASTA_BASE = "formConsultaRegistro:dteFechaFin:j_id136"

BOTON_CONSULTAR_ID = "formConsultaRegistro:j_id448"

# Carpeta donde se guardará el Excel descargado
DESCARGAS_DIR = CONTRATOS_DIR
PATRON_CONTRATOS = "contratos_*.xlsx"

# Archivo donde persistimos cookies/localStorage de la sesión
# User-Agent de un Chrome de escritorio actual (ajusta la versión si
# quieres que coincida exactamente con tu Chromium de Playwright)
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
)

EXTRA_HEADERS = {
    "Accept-Language": "es-CO,es;q=0.9,en;q=0.8",
}


def human_pause(min_ms: int = 300, max_ms: int = 1200):
    """
    Devuelve una pausa aleatoria en milisegundos, para usar con
    page.wait_for_timeout(human_pause()). Simula el tiempo de reacción
    humano entre acciones en vez de ejecutar todo en milisegundos
    consecutivos.
    """
    return random.randint(min_ms, max_ms)


def human_click(locator, page, timeout: int = 10000):
    """
    Hace hover antes del clic (como haría un humano moviendo el mouse)
    y añade una pausa aleatoria antes y después del clic.
    """
    page.wait_for_timeout(human_pause(150, 500))
    locator.hover(timeout=timeout)
    page.wait_for_timeout(human_pause(100, 400))
    locator.click(timeout=timeout)
    page.wait_for_timeout(human_pause(400, 1200))


def by_id(page, element_id: str):
    """
    Helper para localizar elementos por ID exacto sin lidiar con el
    escapado de ':' en selectores CSS (los IDs de JSF usan ':' como
    separador y eso rompe los selectores CSS tipo '#id').
    Usamos selector de atributo, que no necesita escapar nada.
    """
    return page.locator(f'[id="{element_id}"]')


def crear_contexto(browser):
    """
    Crea el BrowserContext reutilizando storage_state si existe
    (sesión previa guardada), o uno nuevo en caso contrario.
    Aplica User-Agent, headers y viewport realistas.
    """
    kwargs = dict(
        user_agent=USER_AGENT,
        locale="es-CO",
        timezone_id="America/Bogota",
        viewport={"width": 1366, "height": 768},
        extra_http_headers=EXTRA_HEADERS,
        accept_downloads=True,
    )

    sesion_reutilizada = False
    if STORAGE_STATE_PATH.exists():
        print(
            f"[+] Encontré sesión guardada en {STORAGE_STATE_PATH}, reutilizándola..."
        )
        kwargs["storage_state"] = str(STORAGE_STATE_PATH)
        sesion_reutilizada = True
    else:
        print("[+] No hay sesión guardada, se iniciará sesión desde cero.")

    context = browser.new_context(**kwargs)
    return context, sesion_reutilizada


def sesion_sigue_activa(page) -> bool:
    """
    Heurística simple: si al navegar seguimos viendo el formulario de
    login (campo de usuario visible), la sesión guardada ya expiró.
    """
    try:
        campo_usuario = page.locator('input[name="josso_username"]')
        return campo_usuario.count() == 0
    except Exception:
        return False


def hacer_login(page):
    """Llena usuario/clave y pausa para resolver el captcha manualmente."""
    try:
        page.fill('input[name="josso_username"]', USUARIO)
        page.wait_for_timeout(human_pause())
        page.fill('input[name="josso_password"]', CLAVE)
    except Exception:
        print("[!] No encontré los campos por name=josso_username/josso_password.")
        print("[!] Intentando por selectores genéricos de usuario/contraseña...")
        page.fill('input[type="text"]', USUARIO)
        page.wait_for_timeout(human_pause())
        page.fill('input[type="password"]', CLAVE)

    print("[+] Usuario y contraseña ingresados.")

    print("\n" + "=" * 60)
    print("PAUSA: resuelve el captcha manualmente en la ventana del navegador.")
    print("Cuando hayas hecho login y estés dentro del sistema,")
    print("vuelve aquí y presiona ENTER para continuar la navegación.")
    print("=" * 60 + "\n")
    input(">> Presiona ENTER cuando ya estés logueado... ")


def set_fecha_calendario(page, base_id: str, target: date, etiqueta: str):
    """
    Intenta setear la fecha en un calendario RichFaces llamando al método
    del componente JS directamente. Si falla, deja el popup abierto para
    selección manual.
    """
    popup_button_id = f"{base_id}PopupButton"
    input_id = f"{base_id}InputDate"

    print(f"[+] Abriendo calendario '{etiqueta}' ({target.strftime('%d/%m/%Y')})...")
    human_click(by_id(page, popup_button_id), page)
    page.wait_for_timeout(500)  # deja renderizar el popup

    # Intento 1: llamar al método del componente JS directamente.
    # month en JS Date es 0-indexado, por eso target.month - 1
    js = f"""
    (() => {{
        try {{
            const el = document.getElementById("{base_id}");
            if (!el || !el.component) return "NO_COMPONENT";
            const d = new Date({target.year}, {target.month - 1}, {target.day});
            if (typeof el.component.selectDate === "function") {{
                el.component.selectDate(d);
                return "OK_selectDate";
            }}
            if (typeof el.component.setSelectedDate === "function") {{
                el.component.setSelectedDate(d);
                return "OK_setSelectedDate";
            }}
            return "NO_METHOD";
        }} catch (e) {{
            return "ERROR: " + e.message;
        }}
    }})()
    """
    resultado = page.evaluate(js)
    print(f"    -> Resultado intento automático: {resultado}")

    if str(resultado).startswith("OK"):
        page.wait_for_timeout(human_pause(400, 900))
        page.wait_for_load_state("networkidle")
        valor_actual = by_id(page, input_id).input_value()
        print(f"    -> Valor actual del campo: {valor_actual}")
        if target.strftime("%d/%m/%Y") in valor_actual:
            print(f"    -> Fecha '{etiqueta}' seteada correctamente.")
            return
        print(f"    -> El valor no coincide con lo esperado, revisa manualmente.")

    # Fallback: dejar el popup abierto para selección manual
    print(f"\n[!] No pude setear la fecha '{etiqueta}' automáticamente.")
    print(f"[!] El calendario debería estar abierto en el navegador.")
    print(f"[!] Selecciona manualmente el día {target.strftime('%d/%m/%Y')}.")
    input(">> Presiona ENTER cuando hayas seleccionado la fecha... ")


def seleccionar_clases_contrato(page):
    """
    Abre el multi-select 'Clase de Contrato' y marca los checkboxes
    indicados en CLASES_CONTRATO_VALUES.
    """
    print(f"[+] Seleccionando {len(CLASES_CONTRATO_VALUES)} clases de contrato...")
    try:
        page.wait_for_timeout(human_pause())
        by_id(page, SELECT_CLASES_ID).select_option(CLASES_CONTRATO_VALUES)
        page.wait_for_timeout(human_pause(300, 800))
        page.wait_for_load_state("networkidle")
        print("[+] Clases de contrato seleccionadas.")
    except Exception as e:
        print(f"[!] No pude seleccionar las clases de contrato automáticamente: {e}")
        print("[!] Selecciónalas manualmente (Ctrl+clic) y presiona ENTER.")
        input(">> ENTER para continuar... ")


def consultar_y_descargar_excel(page):
    """
    Da clic en 'Consultar', espera que aparezca la tabla de resultados,
    y hace clic en el enlace 'Generar Excel' capturando la descarga.
    """
    print("[+] Haciendo clic en 'Consultar'...")
    human_click(by_id(page, BOTON_CONSULTAR_ID), page)
    page.wait_for_load_state("networkidle")
    print("[+] Consulta ejecutada.")

    print("[+] Buscando enlace 'Generar Excel' sobre la tabla de resultados...")
    generar_excel_link = page.get_by_text("Generar Excel", exact=False).first

    try:
        generar_excel_link.wait_for(state="visible", timeout=15000)
    except Exception as e:
        print(f"[!] No encontré el enlace 'Generar Excel' automáticamente: {e}")
        print("[!] Verifica manualmente que la tabla de resultados haya cargado.")
        input(">> ENTER cuando el enlace 'Generar Excel' sea visible... ")
        generar_excel_link = page.get_by_text("Generar Excel", exact=False).first

    print("[+] Haciendo clic en 'Generar Excel' y esperando la descarga...")
    DESCARGAS_DIR.mkdir(parents=True, exist_ok=True)

    page.wait_for_timeout(human_pause())
    with page.expect_download(timeout=60000) as download_info:
        generar_excel_link.click()
    download = download_info.value

    nombre_archivo = f"contratos_{date.today().strftime('%Y%m%d')}.xlsx"
    destino = DESCARGAS_DIR / nombre_archivo

    for archivo_anterior in DESCARGAS_DIR.glob(PATRON_CONTRATOS):
        archivo_anterior.unlink()

    download.save_as(str(destino))

    print(f"[+] Excel descargado en: {destino}")
    return destino


def main():
    ayer = date.today() - timedelta(days=1)
    print(f"[+] Fecha objetivo (ayer): {ayer.strftime('%d/%m/%Y')}")

    # Stealth().use_sync envuelve sync_playwright() para que cualquier
    # browser.new_context() posterior reciba automáticamente los
    # parches anti-detección (navigator.webdriver, plugins, etc).
    with Stealth().use_sync(sync_playwright()) as p:
        browser = p.chromium.launch(headless=False, slow_mo=100)
        context, sesion_reutilizada = crear_contexto(browser)
        page = context.new_page()

        print(f"[+] Navegando a {LOGIN_URL}")
        page.goto(LOGIN_URL, wait_until="networkidle")
        page.wait_for_timeout(human_pause(500, 1500))

        # --- Login (se salta si la sesión guardada sigue activa) ---
        if sesion_reutilizada and sesion_sigue_activa(page):
            print("[+] La sesión guardada sigue activa, saltando login y captcha.")
        else:
            if sesion_reutilizada:
                print("[!] La sesión guardada expiró, es necesario loguearse de nuevo.")
            hacer_login(page)

        # --- Navegación por el menú ---
        ruta = [
            "Financiero",
            "Analista Contratos",
            "Consultas Generales Contratación",
            "Consultar Información de Contratos",
        ]

        for paso in ruta:
            print(f"[+] Buscando y haciendo clic en: '{paso}'")
            try:
                elemento = page.get_by_text(paso, exact=False).first
                human_click(elemento, page, timeout=10000)
                page.wait_for_load_state("networkidle")
            except Exception as e:
                print(f"[!] No pude hacer clic automáticamente en '{paso}': {e}")
                print(
                    "[!] Haz clic manualmente en el navegador y presiona ENTER para seguir."
                )
                input(">> ENTER para continuar... ")

        print(
            "[+] Navegación completada. Deberías estar en 'Consulta información de contratos'."
        )

        # --- Selección de Clase de Contrato ---
        seleccionar_clases_contrato(page)

        # --- Fechas Desde / Hasta = ayer ---
        set_fecha_calendario(page, CALENDAR_DESDE_BASE, ayer, "Desde")
        set_fecha_calendario(page, CALENDAR_HASTA_BASE, ayer, "Hasta")

        # --- Clic en Consultar + descarga del Excel ---
        consultar_y_descargar_excel(page)

        # --- Guardar sesión para la próxima ejecución ---
        context.storage_state(path=str(STORAGE_STATE_PATH))
        print(f"[+] Sesión guardada en {STORAGE_STATE_PATH} para futuras ejecuciones.")

        print(
            "\nPresiona ENTER en la terminal para cerrar el navegador (o ciérralo tú manualmente)."
        )
        input()

        browser.close()


if __name__ == "__main__":
    main()
