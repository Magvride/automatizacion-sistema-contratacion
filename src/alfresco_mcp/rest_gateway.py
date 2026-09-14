# -*- coding: utf-8 -*-
"""
Implementación REST v1 del gateway de Alfresco (``requests``).

Sustituye al webscraping Selenium: habla con
``/alfresco/api/-default-/public/alfresco/versions/1`` y
``.../search/versions/1``.

La sesión HTTP es inyectable (``session=``) para poder testear sin red.
"""

import base64
import os
import time

import requests

from utils.logger import configurar_logger
from .gateway import AlfrescoGateway

logger = configurar_logger("alfresco_rest")

# Sufijos de la URL de Share que deben recortarse para llegar a la raíz del API.
_SUFIJOS_SHARE = ("/share/page", "/share")

# Reintentos ante errores transitorios (BadStatusLine / cortes de conexión).
REINTENTOS_POR_DEFECTO = 3

# Códigos HTTP transitorios del proxy/Alfresco que conviene reintentar.
_ESTADOS_REINTENTABLES = frozenset({429, 500, 502, 503, 504})


class RestAlfrescoGateway(AlfrescoGateway):
    """Cliente REST de Alfresco.

    Args:
        base_url: URL del servidor (se recorta ``/share/page`` si viene de la GUI).
        usuario, contrasena: credenciales de Alfresco.
        auth_method: ``basic`` (por defecto) o ``ticket``.
        session: sesión ``requests`` (o doble) inyectable para pruebas.
    """

    def __init__(
        self,
        base_url: str,
        usuario: str,
        contrasena: str,
        verify_ssl: bool = False,
        timeout: int = 15,
        session=None,
        auth_method: str = "basic",
        reintentos: int = REINTENTOS_POR_DEFECTO,
    ):
        self.base = str(base_url or "").rstrip("/")
        for sufijo in _SUFIJOS_SHARE:
            if self.base.endswith(sufijo):
                self.base = self.base[: -len(sufijo)]
        self.api = f"{self.base}/alfresco/api/-default-/public/alfresco/versions/1"
        self.search_api = f"{self.base}/alfresco/api/-default-/public/search/versions/1"
        self.auth_api = f"{self.base}/alfresco/api/-default-/public/authentication/versions/1"

        self.usuario = usuario
        self.contrasena = contrasena
        self.auth_method = (auth_method or "basic").lower()
        self.verify_ssl = verify_ssl
        self.timeout = timeout
        self.session = session if session is not None else requests.Session()
        self.reintentos = max(1, int(reintentos))
        self._ticket = None

    # ------------------------------------------------------------------ auth
    def _cabeceras_ticket(self) -> dict:
        if self._ticket is None:
            respuesta = self._ejecutar(
                self.session.post,
                f"{self.auth_api}/tickets",
                json={"userId": self.usuario, "password": self.contrasena},
                verify=self.verify_ssl,
                timeout=self.timeout,
            )
            self._ticket = self._json(respuesta, "ticket").get("entry", {}).get("id", "")
            logger.info("Ticket de Alfresco obtenido.")
        token = base64.b64encode(self._ticket.encode("utf-8")).decode("ascii")
        return {"Authorization": f"Basic {token}"}

    def _kwargs_comunes(self) -> dict:
        kwargs = {"verify": self.verify_ssl, "timeout": self.timeout}
        if self.auth_method == "ticket":
            kwargs["headers"] = self._cabeceras_ticket()
        else:
            kwargs["auth"] = (self.usuario, self.contrasena)
        return kwargs

    def _ejecutar(self, funcion, *args, **kwargs):
        """Ejecuta una petición con reintentos ante errores transitorios.

        Alfresco 7.x devuelve de forma esporádica ``BadStatusLine HTTP/1.1 0``
        y, bajo carga, su proxy responde ``502/503/504``; el proyecto de
        referencia lo resolvía con reintentos y backoff. Se reintentan tanto
        los cortes de conexión como los estados HTTP transitorios.
        """
        ultimo = None
        for intento in range(1, self.reintentos + 1):
            try:
                respuesta = funcion(*args, **kwargs)
            except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as exc:
                ultimo = exc
            else:
                if getattr(respuesta, "status_code", 200) not in _ESTADOS_REINTENTABLES:
                    return respuesta
                ultimo = requests.exceptions.HTTPError(
                    f"{respuesta.status_code} de Alfresco", response=respuesta
                )
            logger.warning(
                "Error transitorio de Alfresco (intento %d/%d): %s",
                intento, self.reintentos, ultimo,
            )
            if intento < self.reintentos:
                time.sleep(0.7 * intento)
        raise ultimo

    def _get(self, url: str, params: dict = None):
        return self._ejecutar(self.session.get, url, params=params, **self._kwargs_comunes())

    def _post(self, url: str, json: dict = None):
        return self._ejecutar(self.session.post, url, json=json, **self._kwargs_comunes())

    @staticmethod
    def _json(respuesta, contexto: str = ""):
        """Devuelve el JSON de la respuesta con un error claro si no lo es."""
        respuesta.raise_for_status()
        try:
            return respuesta.json()
        except ValueError as exc:
            cabeceras = getattr(respuesta, "headers", None) or {}
            tipo = cabeceras.get("Content-Type", "") if hasattr(cabeceras, "get") else ""
            texto = str(getattr(respuesta, "text", ""))[:200]
            detalle = f" ({contexto})" if contexto else ""
            raise RuntimeError(
                f"Respuesta no JSON de Alfresco{detalle}. Revisa ALFRESCO_URL: debe "
                "apuntar al servidor Alfresco (p. ej. https://gesdoc.uis.edu.co), no "
                "a otro sistema. "
                f"Content-Type={tipo!r}. Inicio de la respuesta: {texto!r}"
            ) from exc

    # ------------------------------------------------------------- búsqueda
    def buscar_carpetas(self, numero: str, max_items: int = 10) -> list:
        """Busca carpetas por número (AFTS) y devuelve candidatas normalizadas."""
        cuerpo = {
            "query": {
                "query": f'{numero} AND TYPE:"td:carpeta"',
                "language": "afts",
            },
            "paging": {"maxItems": max_items},
        }
        respuesta = self._post(f"{self.search_api}/search", json=cuerpo)
        entradas = self._json(respuesta, "búsqueda").get("list", {}).get("entries", [])
        candidatas = []
        for envoltura in entradas:
            entry = envoltura.get("entry", envoltura) if isinstance(envoltura, dict) else {}
            candidatas.append(
                {
                    "id": entry.get("id", ""),
                    "nombre": entry.get("name", ""),
                    "es_carpeta": entry.get("isFolder", False),
                    "tipo": entry.get("nodeType", ""),
                }
            )
        logger.debug("Búsqueda '%s': %d candidatas.", numero, len(candidatas))
        return candidatas

    # -------------------------------------------------------------- listado
    @staticmethod
    def _archivo_desde_entry(entry: dict) -> dict:
        return {
            "NOMBRE": entry.get("name", ""),
            "ID": entry.get("id", ""),
            "FECHA_CREACION": entry.get("createdAt", "") or "",
            "FECHA_MODIFICACION": entry.get("modifiedAt", "") or "",
        }

    def listar_archivos(self, node_id: str, max_items: int = 100) -> dict:
        """Lista los hijos de una carpeta, paginando hasta ``max_items``."""
        archivos = []
        total = 0
        skip = 0
        while True:
            faltan = max_items - len(archivos)
            if faltan <= 0:
                break
            respuesta = self._get(
                f"{self.api}/nodes/{node_id}/children",
                params={"maxItems": min(1000, faltan), "skipCount": skip},
            )
            lista = self._json(respuesta, "listar hijos").get("list", {})
            entradas = lista.get("entries", [])
            total = lista.get("pagination", {}).get("count", total)
            for envoltura in entradas:
                entry = envoltura.get("entry", envoltura) if isinstance(envoltura, dict) else {}
                archivos.append(self._archivo_desde_entry(entry))
            skip += len(entradas)
            if not entradas or skip >= total:
                break
        logger.debug("Nodo %s: %d archivos (total %d).", node_id, len(archivos), total)
        return {"archivos": archivos, "total": total}

    def obtener_nodo(self, node_id: str):
        respuesta = self._get(f"{self.api}/nodes/{node_id}", params={"include": "path"})
        if respuesta.status_code == 404:
            return None
        entry = self._json(respuesta, "nodo").get("entry", {})
        return {
            "id": entry.get("id", ""),
            "nombre": entry.get("name", ""),
            "es_carpeta": entry.get("isFolder", False),
            "tipo": entry.get("nodeType", ""),
        }

    # ------------------------------------------------------------- descarga
    def descargar(self, node_id: str, destino: str) -> str:
        respuesta = self._get(f"{self.api}/nodes/{node_id}/content", params={"attachment": "true"})
        respuesta.raise_for_status()
        os.makedirs(os.path.dirname(destino) or ".", exist_ok=True)
        with open(destino, "wb") as archivo:
            archivo.write(respuesta.content)
        logger.info("Descargado nodo %s -> %s", node_id, destino)
        return destino

    def clonar(self):
        """Nuevo gateway con sesión propia (para uso concurrente por hilos)."""
        return RestAlfrescoGateway(
            base_url=self.base,
            usuario=self.usuario,
            contrasena=self.contrasena,
            verify_ssl=self.verify_ssl,
            timeout=self.timeout,
            auth_method=self.auth_method,
            reintentos=self.reintentos,
        )

    def cerrar(self) -> None:
        cerrar = getattr(self.session, "close", None)
        if callable(cerrar):
            cerrar()
