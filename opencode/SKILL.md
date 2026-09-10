---
name : automatizacion-sistema-contratacion
description: Analiza la arquitectura de un repositorio, mapea el flujo de datos real y detecta cuellos de botella o fallos en el flujo de trabajo.
---

# Protocolo de Auditoría y Mapeo de Flujo

Usa esta habilidad cuando se requiera entender las limitaciones de un repositorio, rastrear datos o encontrar fallas estructurales.

## 1. Mapeo del Flujo de Datos (Data Lifecycle)
Para explicar cómo avanzan los datos, debes documentar:
- **Punto de Entrada (Ingress):** Dónde y cómo entran los datos al sistema (API, base de datos, inputs del usuario).
- **Transformaciones:** Lista cada función o servicio que modifica o propaga el estado del dato.
- **Punto de Salida (Egress):** Dónde terminan los datos (persistencia, respuestas HTTP, colas de mensajería).

*Formato de entrega:* Representa el camino con un diagrama de texto simplificado (ASCII/Mermaid) que muestre el orden de ejecución y los archivos involucrados.

## 2. Diagnóstico de Fallas en el Flujo de Trabajo
Para encontrar dónde se rompe el flujo, analiza:
- **Manejo de Errores (Try/Catch):** Identifica bloques donde los errores se silencian o no se propagan correctamente.
- **Validaciones Intermedias:** Verifica si los datos cambian de tipo o pierden propiedades críticas a mitad del camino.
- **Asincronía y Concurrencia:** Busca condiciones de carrera (race conditions) o promesas no resueltas.

## 3. Identificación de Limitaciones Estructurales
Determina las fronteras del sistema actual respondiendo:
- ¿Qué pasa si el volumen de datos escala? (Problemas de memoria, queries ineficientes).
- ¿Qué dependencias críticas o acoplamientos rígidos congelan el flujo si fallan?
- ¿Dónde falta observabilidad (logs, métricas)?
