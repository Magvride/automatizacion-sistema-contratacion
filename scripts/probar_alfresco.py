# -*- coding: utf-8 -*-
"""
Prueba la conexión a Alfresco con las credenciales del ``.env``.

Uso:
    python scripts/probar_alfresco.py                # prueba de conexión
    python scripts/probar_alfresco.py 2026000003     # además busca ese número

No modifica nada en Alfresco: solo lee la raíz y, opcionalmente, busca una
carpeta por número.
"""

import os
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "src"))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(RAIZ / ".env")

from alfresco_mcp.rest_gateway import RestAlfrescoGateway  # noqa: E402


def _crear_gateway() -> RestAlfrescoGateway:
    base = os.getenv("ALFRESCO_URL") or os.getenv("ALFRESCO_SHARE_URL") or ""
    usuario = os.getenv("ALFRESCO_USER") or os.getenv("ALFRESCO_SHARE_USER") or ""
    contrasena = os.getenv("ALFRESCO_PASS") or os.getenv("ALFRESCO_SHARE_PASS") or ""
    if not base or not usuario or not contrasena:
        raise SystemExit(
            "Faltan credenciales. Define ALFRESCO_URL, ALFRESCO_USER y "
            "ALFRESCO_PASS en el archivo .env (copia de .env.example)."
        )
    return RestAlfrescoGateway(
        base_url=base,
        usuario=usuario,
        contrasena=contrasena,
        verify_ssl=os.getenv("ALFRESCO_VERIFY_SSL", "true").lower() == "true",
        timeout=int(os.getenv("ALFRESCO_TIMEOUT", "30")),
        auth_method=os.getenv("ALFRESCO_AUTH_METHOD", "basic"),
    )


def main() -> int:
    gateway = _crear_gateway()
    print(f"Servidor: {gateway.base}")
    try:
        listado = gateway.listar_archivos("-root-", max_items=5)
        print(f"[OK] Conexión establecida. Nodos en la raíz: {listado['total']}")
        for archivo in listado["archivos"][:5]:
            print(f"     - {archivo['NOMBRE']}")

        if len(sys.argv) > 1:
            numero = sys.argv[1]
            candidatas = gateway.buscar_carpetas(numero, max_items=10)
            print(f"[OK] Búsqueda '{numero}': {len(candidatas)} candidata(s)")
            for candidata in candidatas:
                print(f"     - {candidata['nombre']} ({candidata['id']})")
    except Exception as exc:  # noqa: BLE001
        print(f"[ERROR] No se pudo conectar o consultar: {exc}")
        return 1
    finally:
        gateway.cerrar()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
