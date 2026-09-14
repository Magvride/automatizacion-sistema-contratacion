# -*- coding: utf-8 -*-
"""
Datos y gateway simulados para demostrar la auditoría sin Alfresco.

Se usan tanto por ``scripts/demo_auditoria.py`` como por el modo demo de la GUI
(``desktop``). No requieren credenciales ni conexión.

Casos de ejemplo:
* ``20-2026000003``  — carpeta con 3 obligatorios  → Incompleto.
* ``18-2026001515``  — todos los obligatorios + FCO.74 → Completo (regla cierre).
* ``270-2026000050`` — sin carpeta → No encontrada.
"""

from .gateway import AlfrescoGateway
from auditoria_documental.diccionario import obligatorios_por_clase

CONTRATOS_DEMO = [
    {"contrato": "20-2026000003", "ordenador": "JUAN PEREZ", "centro_costo": "RECTORIA"},
    {
        "contrato": "18-2026001515",
        "contratista": "ACME S.A.S",
        "ordenador": "MARIA GOMEZ",
        "centro_costo": "VICERRECTORIA",
    },
    {
        "contrato": "270-2026000050",
        "ordenador": "CARLOS RUIZ",
        "centro_costo": "SECRETARIA GENERAL",
    },
]


def nombre_archivo(documento: dict) -> str:
    """Nombre de archivo plausible a partir de un documento del diccionario."""
    formato = str(documento.get("CODIGO_FORMATO", "")).strip()
    texto = str(documento.get("DOCUMENTO", "")).strip()
    base = f"{formato} {texto}".strip() or "documento"
    return f"{base}.pdf"


def carpetas_demo(diccionario: list) -> dict:
    """Mapa número de contrato -> carpeta/archivos simulados."""
    parciales = [
        nombre_archivo(d) for d in obligatorios_por_clase(diccionario, "20")[:3]
    ]
    completos = [
        nombre_archivo(d) for d in obligatorios_por_clase(diccionario, "18 PJ")
    ]
    completos.append("FCO.74 Acta de pago final.pdf")

    return {
        "2026000003": {
            "carpeta": {"id": "nA", "nombre": "0020_2026000003_9707", "es_carpeta": True},
            "archivos": parciales,
        },
        "2026001515": {
            "carpeta": {"id": "nB", "nombre": "0018_2026001515_7810", "es_carpeta": True},
            "archivos": completos,
        },
        # 270-2026000050 no aparece: carpeta no encontrada.
    }


class GatewayDemo(AlfrescoGateway):
    """Alfresco simulado: un mapa número de contrato -> carpeta/archivos."""

    def __init__(self, carpetas: dict):
        self.carpetas = carpetas

    def buscar_carpetas(self, numero, max_items=10):
        datos = self.carpetas.get(numero)
        return [datos["carpeta"]] if datos and datos.get("carpeta") else []

    def listar_archivos(self, node_id, max_items=100):
        for datos in self.carpetas.values():
            if datos.get("carpeta", {}).get("id") == node_id:
                nombres = datos.get("archivos", [])
                archivos = [
                    {
                        "NOMBRE": nombre,
                        "ID": f"doc{i}",
                        "FECHA_CREACION": "2026-01-15",
                        "FECHA_MODIFICACION": "2026-01-15",
                    }
                    for i, nombre in enumerate(nombres, start=1)
                ]
                return {"archivos": archivos, "total": len(archivos)}
        return {"archivos": [], "total": 0}

    def obtener_nodo(self, node_id):
        return None

    def descargar(self, node_id, destino):
        return destino
