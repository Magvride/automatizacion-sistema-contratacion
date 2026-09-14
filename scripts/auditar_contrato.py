# -*- coding: utf-8 -*-
"""
Ejecuta el servicio «Auditoría Documental Automatizada» contra Alfresco real.

Uso:
    python scripts/auditar_contrato.py 0450-2026000003
    python scripts/auditar_contrato.py 0450-2026000003 20-2026000004

Genera en ``output/auditoria_real/``: 06, 07, 09, 10 y el informe 11.
No modifica nada en Alfresco: solo lee carpetas y archivos.
"""

import os
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "src"))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(RAIZ / ".env")

from alfresco_mcp.rest_gateway import RestAlfrescoGateway  # noqa: E402
from auditoria_documental.servicio import (  # noqa: E402
    DESCRIPCION,
    NOMBRE,
    SALIDAS,
    ejecutar_servicio,
)

SALIDA = RAIZ / "output" / "auditoria_real"


def _crear_gateway() -> RestAlfrescoGateway:
    base = os.getenv("ALFRESCO_URL") or os.getenv("ALFRESCO_SHARE_URL") or ""
    usuario = os.getenv("ALFRESCO_USER") or os.getenv("ALFRESCO_SHARE_USER") or ""
    contrasena = os.getenv("ALFRESCO_PASS") or os.getenv("ALFRESCO_SHARE_PASS") or ""
    if not base or not usuario or not contrasena:
        raise SystemExit("Faltan credenciales de Alfresco en el archivo .env.")
    return RestAlfrescoGateway(
        base_url=base,
        usuario=usuario,
        contrasena=contrasena,
        verify_ssl=os.getenv("ALFRESCO_VERIFY_SSL", "true").lower() == "true",
        timeout=int(os.getenv("ALFRESCO_TIMEOUT", "30")),
        auth_method=os.getenv("ALFRESCO_AUTH_METHOD", "basic"),
    )


def main() -> int:
    if len(sys.argv) < 2:
        print(f"{NOMBRE}\n{DESCRIPCION}\n")
        print("Uso: python scripts/auditar_contrato.py <contrato> [<contrato> ...]")
        print("Ej.:  python scripts/auditar_contrato.py 0450-2026000003")
        return 2

    contratos = [{"contrato": codigo} for codigo in sys.argv[1:]]
    gateway = _crear_gateway()
    try:
        resumen = ejecutar_servicio(contratos, gateway, str(SALIDA), periodo="REAL")
    finally:
        gateway.cerrar()

    print("=" * 70)
    print(NOMBRE.upper())
    print("=" * 70)
    for resultado in resumen["resultados"]:
        ver = resultado.get("verificacion", {})
        print(
            f"  {resultado['contrato']:<18} clase={resultado.get('cod',''):<6} "
            f"carpeta={'SÍ' if ver.get('alfresco') == 'SI' else 'NO':<3} "
            f"hallados={resultado.get('encontrados',0):>2}/{resultado.get('esperados',0):<2} "
            f"({resultado.get('pct_cumpl',0)}%)  {resultado.get('carpeta','')}"
        )
    print("-" * 70)
    print(f"  Contratos: {resumen['total']} | encontradas: {resumen['encontradas']} | "
          f"no encontradas: {resumen['no_encontradas']}")
    print(f"  Salidas en: {SALIDA}")
    for clave in ("verificacion", "faltantes", "auditoria", "correos", "informe"):
        print(f"    - {SALIDAS[clave]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
