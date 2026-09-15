"""Rutas compartidas y configuración del flujo de contratación."""

import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv


def _directorio_base() -> Path:
    """Carpeta donde viven los datos de entrada/salida.

    En modo compilado (PyInstaller) `__file__` queda en la carpeta temporal de
    extracción, así que se usa la carpeta del ejecutable para conservar el .env,
    los archivos/ y los logs junto al .exe.
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


BASE_DIR = _directorio_base()
ARCHIVOS_DIR = BASE_DIR / "archivos"
REPORTES_DIR = ARCHIVOS_DIR / "04_Contratos_Descargados_UISARD"
CONTRATOS_DIR = ARCHIVOS_DIR / "01_Contratos_Descargados"
MATRIZ_MANUAL_DIR = ARCHIVOS_DIR / "00_Datos_Raw"
MATRIZ_ACTUALIZADA_DIR = ARCHIVOS_DIR / "02_Matriz_actualizada"
EXTRACCION_DIR = ARCHIVOS_DIR / "03_Contratos_Conciliacion"
RESULTADOS_DIR = ARCHIVOS_DIR / "05_Datos_filtrados"
# Carpeta de trabajo interno: consolidados, verificaciones y borradores que NO
# son entregables para el cliente (solo se entregan 09 y 11).
INTERNO_DIR = ARCHIVOS_DIR / "_interno"
EXHIBITOS_DIR = ARCHIVOS_DIR / "06_Expedientes"
EXHIBITOS_VERIFICADOS_DIR = EXHIBITOS_DIR / "expedientes_verificados"
STORAGE_STATE_PATH = ARCHIVOS_DIR / "sesion" / "uis_storage_state.json"

# Archivos manuales que el usuario puede seleccionar desde la GUI (rutas por defecto).
NOMBRE_MATRIZ_MANUAL = "Matriz Seguimiento Contractual UIS.xlsx"
PATRON_ORDENADORES = "Ordenadores_*.xlsx"

# Nombre del archivo de salida de la matriz actualizada generado por seguimiento_p2.py.
NOMBRE_MATRIZ_ACTUALIZADA = "02_Matriz_Seguimiento_actualizada.xlsx"

# Carpeta relativa fija dentro de OneDrive donde se copia la matriz (se puede
# sobrescribir desde la GUI; la raíz de OneDrive se detecta por equipo).
ONEDRIVE_CARPETA_DESTINO_REL = "02_Matriz_actualizada"

# Persistencia de las rutas configuradas desde la GUI.
ARCHIVO_CONFIG_RUTAS = BASE_DIR / "config_rutas.json"
SERVICIO_CREDENCIALES = "automatizacion-sistema-contratacion/alfresco"

load_dotenv(BASE_DIR / ".env")


def _ruta_matriz_default() -> Path:
    """Ruta por defecto de la matriz manual (la carpeta histórica)."""
    return MATRIZ_MANUAL_DIR / NOMBRE_MATRIZ_MANUAL


def _ruta_ordenadores_default() -> Path:
    """Ruta por defecto del archivo de ordenadores: el más reciente de la carpeta."""
    archivos = sorted(
        MATRIZ_MANUAL_DIR.glob(PATRON_ORDENADORES),
        key=lambda a: a.stat().st_mtime,
    )
    return archivos[-1] if archivos else (MATRIZ_MANUAL_DIR / "Ordenadores_Agosto.xlsx")


def _cargar_config_rutas() -> dict:
    """Lee el JSON de rutas configuradas. Devuelve dict vacío si no existe o falla."""
    try:
        with open(ARCHIVO_CONFIG_RUTAS, "r", encoding="utf-8") as fh:
            data = json.load(fh)
            return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _detectar_raiz_onedrive() -> str:
    """Detecta la carpeta raíz de OneDrive del equipo desde el registro de Windows.

    Devuelve la primera ruta existente. Si OneDrive no está instalado, configurado
    o no es accesible, devuelve una cadena vacía.
    """
    try:
        import winreg
    except ImportError:
        return ""

    raices = []
    rutas_registro = (
        r"Software\Microsoft\OneDrive\Accounts",
        r"Software\SyncEngines\Providers\OneDrive",
    )
    for ruta in rutas_registro:
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, ruta) as clave_padre:
                for i in range(winreg.QueryInfoKey(clave_padre)[0]):
                    subclave = winreg.EnumKey(clave_padre, i)
                    try:
                        with winreg.OpenKey(clave_padre, subclave) as clave:
                            valor, _ = winreg.QueryValueEx(clave, "UserFolder")
                            if valor:
                                raices.append(str(valor))
                    except OSError:
                        pass
        except OSError:
            pass

    for raiz in raices:
        try:
            if Path(raiz).is_dir():
                return raiz
        except OSError:
            continue
    return ""


def _guardar_config_rutas(config: dict) -> None:
    """Guarda el JSON de rutas configuradas de forma atómica."""
    try:
        with open(ARCHIVO_CONFIG_RUTAS, "w", encoding="utf-8") as fh:
            json.dump(config, fh, ensure_ascii=False, indent=2)
    except OSError:
        pass


def ruta_matriz_manual() -> Path:
    """Ruta de la matriz manual: la configurada por la GUI o la por defecto."""
    ruta = _cargar_config_rutas().get("matriz_manual", "")
    if ruta and Path(ruta).is_file():
        return Path(ruta)
    return _ruta_matriz_default()


def ruta_ordenadores() -> Path:
    """Ruta del archivo de ordenadores: el configurado o el más reciente por defecto."""
    ruta = _cargar_config_rutas().get("ordenadores", "")
    if ruta and Path(ruta).is_file():
        return Path(ruta)
    return _ruta_ordenadores_default()


def ruta_onedrive_destino() -> Path:
    """Carpeta destino en OneDrive: la configurada por la GUI o la detectada.

    Si el usuario eligió una carpeta manualmente (config_rutas.json) y sigue
    existiendo, se usa esa. Si no, se toma la raíz de OneDrive detectada por
    registro y se le concatena la carpeta fija ``ONEDRIVE_CARPETA_DESTINO_REL``.
    Como último recurso se asume ``~/OneDrive/``.
    """
    ruta = _cargar_config_rutas().get("onedrive_destino", "")
    if ruta and Path(ruta).is_dir():
        return Path(ruta)

    raiz = _detectar_raiz_onedrive()
    if raiz:
        return Path(raiz) / ONEDRIVE_CARPETA_DESTINO_REL

    return Path.home() / "OneDrive" / ONEDRIVE_CARPETA_DESTINO_REL


def configurar_rutas(
    matriz_manual: str = "", ordenadores: str = "", onedrive_destino: str = ""
) -> None:
    """Guarda las rutas manuales elegidas en la GUI (vacías = usar el valor por defecto)."""
    config = _cargar_config_rutas()
    config["matriz_manual"] = str(matriz_manual) if matriz_manual else ""
    config["ordenadores"] = str(ordenadores) if ordenadores else ""
    config["onedrive_destino"] = str(onedrive_destino) if onedrive_destino else ""
    _guardar_config_rutas(config)


def credenciales_alfresco() -> dict:
    """Obtiene las credenciales desde ``.env`` o el almacén seguro de Windows."""
    config = _cargar_config_rutas()
    url = (
        os.getenv("ALFRESCO_SHARE_URL")
        or os.getenv("ALFRESCO_URL")
        or config.get("alfresco_url", "")
        or "https://gesdoc.uis.edu.co/share/page"
    ).strip()
    usuario = (
        os.getenv("ALFRESCO_SHARE_USER")
        or os.getenv("ALFRESCO_USER")
        or config.get("alfresco_user", "")
        or "consulta_contratos"
    ).strip()
    contrasena = (
        os.getenv("ALFRESCO_SHARE_PASS")
        or os.getenv("ALFRESCO_PASS")
        or ""
    ).strip()

    if not contrasena and usuario:
        try:
            import keyring

            contrasena = keyring.get_password(SERVICIO_CREDENCIALES, usuario) or ""
        except Exception:
            # La aplicación puede seguir funcionando con .env si keyring no está disponible.
            contrasena = ""

    return {
        "url": url,
        "usuario": usuario,
        "contrasena": contrasena,
        "auth_method": os.getenv("ALFRESCO_AUTH_METHOD", "basic").strip() or "basic",
    }


def guardar_credenciales_alfresco(url: str, usuario: str, contrasena: str) -> None:
    """Guarda URL/usuario localmente y la contraseña en el almacén del sistema."""
    url = str(url or "").strip()
    usuario = str(usuario or "").strip()
    contrasena = str(contrasena or "")
    if not url or not usuario:
        raise ValueError("La URL y el usuario de Alfresco son obligatorios.")

    actuales = credenciales_alfresco()
    if not contrasena:
        contrasena = actuales.get("contrasena", "")
    if not contrasena:
        raise ValueError("La contraseña de Alfresco es obligatoria la primera vez.")

    try:
        import keyring

        keyring.set_password(SERVICIO_CREDENCIALES, usuario, contrasena)
        if actuales.get("usuario") and actuales["usuario"] != usuario:
            try:
                keyring.delete_password(SERVICIO_CREDENCIALES, actuales["usuario"])
            except Exception:
                pass
    except ImportError as exc:
        raise RuntimeError("Falta la dependencia keyring para guardar credenciales de forma segura.") from exc
    except Exception as exc:
        raise RuntimeError(f"No se pudieron guardar las credenciales en Windows: {exc}") from exc

    config = _cargar_config_rutas()
    config["alfresco_url"] = url
    config["alfresco_user"] = usuario
    _guardar_config_rutas(config)


def restablecer_rutas() -> None:
    """Vuelve a dejar las rutas manuales en sus valores por defecto."""
    configurar_rutas("", "", "")


def preparar_directorios() -> None:
    """Crea las carpetas de trabajo sin tocar archivos existentes."""
    for carpeta in (
        REPORTES_DIR,
        CONTRATOS_DIR,
        MATRIZ_MANUAL_DIR,
        MATRIZ_ACTUALIZADA_DIR,
        EXTRACCION_DIR,
        RESULTADOS_DIR,
        INTERNO_DIR,
        EXHIBITOS_DIR,
        EXHIBITOS_VERIFICADOS_DIR,
        STORAGE_STATE_PATH.parent,
    ):
        carpeta.mkdir(parents=True, exist_ok=True)


def variable(nombre: str, predeterminado: str = "") -> str:
    return os.getenv(nombre, predeterminado).strip()
