# -*- coding: utf-8 -*-
"""
Demo del servicio «Auditoría Documental Automatizada» (sin Alfresco).

Usa el diccionario real y un Alfresco simulado para generar en
``output/demo_auditoria/``: 06, 07, 09, 10 y el informe 11.

    python scripts/demo_auditoria.py
"""

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "src"))

from alfresco_mcp.demo import CONTRATOS_DEMO, GatewayDemo, carpetas_demo  # noqa: E402
from auditoria_documental.diccionario import cargar_diccionario  # noqa: E402
from auditoria_documental.servicio import (  # noqa: E402
    NOMBRE,
    SALIDAS,
    ejecutar_servicio,
)

SALIDA = RAIZ / "output" / "demo_auditoria"
FECHA_REVISION = "2026-08-31"
FECHA_LIMITE = "2026-09-03"


def main() -> int:
    diccionario = cargar_diccionario()["diccionario"]
    resumen = ejecutar_servicio(
        CONTRATOS_DEMO,
        GatewayDemo(carpetas_demo(diccionario)),
        str(SALIDA),
        periodo="DEMO",
        fecha_revision=FECHA_REVISION,
        fecha_limite=FECHA_LIMITE,
    )

    print("=" * 70)
    print(NOMBRE.upper() + " — DEMO (Alfresco simulado)")
    print("=" * 70)
    for resultado in resumen["resultados"]:
        ver = resultado.get("verificacion", {})
        print(
            f"  {resultado['contrato']:<16} clase={resultado.get('cod',''):<6} "
            f"carpeta={'SÍ' if ver.get('alfresco') == 'SI' else 'NO':<3} "
            f"hallados={resultado.get('encontrados',0):>2}/{resultado.get('esperados',0):<2} "
            f"({resultado.get('pct_cumpl',0)}%)"
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
