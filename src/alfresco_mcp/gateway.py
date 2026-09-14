# -*- coding: utf-8 -*-
"""
Interfaz abstracta del repositorio Alfresco.

Define el contrato mínimo que necesita el verificador. Cualquier transporte
(REST v1, CMIS, un cliente MCP en proceso o un doble de prueba) puede
implementarlo, lo que permite testear la verificación sin un Alfresco real.

Formas de retorno:
    buscar_carpetas(numero, max_items) -> [
        {"id": str, "nombre": str, "es_carpeta": bool, "tipo": str}, ...
    ]
    listar_archivos(node_id, max_items) -> {
        "archivos": [{"NOMBRE": str, "ID": str,
                      "FECHA_CREACION": str, "FECHA_MODIFICACION": str}, ...],
        "total": int,  # pagination.count (puede superar max_items)
    }
    obtener_nodo(node_id) -> dict | None  # {"id","nombre","es_carpeta","tipo"}
    descargar(node_id, destino) -> str    # ruta del archivo descargado
"""


class AlfrescoGateway:
    """Contrato del repositorio. Las implementaciones concretas lo heredan."""

    def buscar_carpetas(self, numero: str, max_items: int = 10) -> list:
        raise NotImplementedError

    def listar_archivos(self, node_id: str, max_items: int = 100) -> dict:
        raise NotImplementedError

    def obtener_nodo(self, node_id: str):
        raise NotImplementedError

    def descargar(self, node_id: str, destino: str) -> str:
        raise NotImplementedError

    def cerrar(self) -> None:
        """Libera recursos (sesión HTTP). Por defecto no hace nada."""

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.cerrar()
        return False
