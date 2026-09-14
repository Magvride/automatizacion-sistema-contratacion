# -*- coding: utf-8 -*-
"""Integración con Alfresco vía API REST/CMIS (sin Selenium).

Submódulos:
    gateway      — interfaz abstracta del repositorio (inyectable en tests).
    rest_gateway — implementación REST v1 (``requests``).
    verifier     — lógica de verificación de un contrato (pura).
    writer       — salidas ``06_Verificacion_Alfresco.csv`` y ``07``.
"""

from .gateway import AlfrescoGateway  # noqa: F401
from .motor import ejecutar_auditoria  # noqa: F401
from .verifier import numero_y_pad, verificar_contrato  # noqa: F401
from .writer import escribir_verificacion  # noqa: F401
