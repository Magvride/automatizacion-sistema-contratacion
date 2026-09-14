# -*- coding: utf-8 -*-
"""
Valida el archivo del diccionario de documentos.

Comprueba que exista, que tenga la hoja de catálogo con las columnas necesarias
y muestra cuántos documentos obligatorios hay por clase.

Uso:
    python scripts/validar_diccionario.py
    python scripts/validar_diccionario.py "C:\\ruta\\Diccionario_Documentos.xlsx"
"""

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "src"))

from auditoria_documental.diccionario import (  # noqa: E402
    buscar_diccionario,
    cargar_diccionario,
    obligatorios_por_clase,
)

# Sin estas columnas el flujo no puede evaluar obligatorios.
REQUERIDAS = ("CODIGO_CLASE", "DOCUMENTO", "OBLIGATORIEDAD")
# Mejoran el resultado (código FCO, etapa, alias, identificadores).
RECOMENDADAS = ("ID_DOC", "CLASE", "CODIGO_FORMATO", "ETAPA", "ALIAS")
CLASES = ("20", "19", "298", "450", "270", "18 PN", "18 PJ")


def main() -> int:
    ruta = buscar_diccionario(sys.argv[1] if len(sys.argv) > 1 else "")
    if not ruta:
        print("[ERROR] No se encontró el archivo del diccionario en "
              "archivos/00_Datos_Raw (Diccionario_Documentos.xlsx o "
              "Matriz_Documentos_por_Clase*.xlsx).")
        return 1

    data = cargar_diccionario(ruta)
    registros = data["diccionario"]

    print(f"Archivo: {ruta}")
    print(f"Documentos en el catálogo: {len(registros)}")
    print(f"Filas de etapas (hoja MATRIZ/Matriz_Etapas): {len(data['etapas'])}")

    presentes = set()
    for registro in registros:
        presentes.update(registro.keys())

    faltan = [col for col in REQUERIDAS if col not in presentes]
    ausentes = [col for col in RECOMENDADAS if col not in presentes]

    print("Columnas requeridas: " + ("OK" if not faltan else f"FALTAN {faltan}"))
    print("Columnas recomendadas ausentes: " + (", ".join(ausentes) if ausentes else "ninguna"))

    print("Obligatorios por clase:")
    for clase in CLASES:
        print(f"  {clase:<6}: {len(obligatorios_por_clase(registros, clase))}")

    return 0 if not faltan else 2


if __name__ == "__main__":
    raise SystemExit(main())
