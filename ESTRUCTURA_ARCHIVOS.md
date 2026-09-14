# Estructura de archivos

Todas las entradas y salidas del flujo se guardan dentro de `archivos/`:

| Carpeta | Uso |
| --- | --- |
| `00_Datos_Raw/` | Entrada manual: `Matriz Seguimiento Contractual UIS.xlsx`, `Ordenadores_*.xlsx` y `Diccionario_Documentos.xlsx`. |
| `01_Contratos_Descargados/` | Excel de nuevas versiones (carga manual en la GUI o `uis_login_p1.py` en el flujo legado). |
| `02_Matriz_actualizada/` | Salida de `seguimiento_p2.py` (matriz actualizada). |
| `03_Contratos_Conciliacion/` | CSV normalizado generado por `seguimiento_p2.py` (`contratos_normalizados.csv`). |
| `05_Datos_filtrados/` | **Entregables al cliente:** `Auditoria_Contratos.xlsx` y `Informe_Auditoria_Contrato.html`. |
| `_interno/` | Archivos de trabajo que **no** se entregan (02, 03, 06, 07, 10). |
| `06_Expedientes/` | Expedientes corroborados en Alfresco (backend Selenium legado). |

## Flujo por defecto (MCP/REST, sin UISARD)

El orquestador `main.py` encadena de forma secuencial:

1. **Bloque propio (nuevas versiones):**
   `seguimiento_p2.py` actualiza la matriz y exporta
   `03_Contratos_Conciliacion/contratos_normalizados.csv` con los contratos
   nuevos del día.
2. **FASE 2 (MCP) — Consolidación:** `src/consolidar.py` arma el consolidado
   solo con las nuevas versiones y lo **enriquece** con datos del reporte
   financiero (fechas, valor, contratista, unidad, estado, supervisor).
3. **FASE 3 (MCP) — Alfresco + auditoría:** `src/alfresco_mcp/` resuelve cada
   carpeta por API REST, lista sus archivos y evalúa los documentos
   obligatorios del diccionario. Genera:
   - **Entregables** en `05_Datos_filtrados/`:
     - `Auditoria_Contratos.xlsx` (Resumen, etapas, `DIAGNOSTICO` enriquecido,
       una hoja por contrato y `Notas_Diccionario`).
     - `Informe_Auditoria_Contrato.html` (módulos con/sin carpeta, faltantes en
       desplegable, tabla general descargable en Excel y botón de PDF).
   - **Internos** en `_interno/`: `06_Verificacion_Alfresco.csv`,
     `07_Expedientes_Faltantes.csv`, `02_Consolidado_General.csv`,
     `03_Resultado_Final.xlsx` y `10_Correos_Auditoria.txt`.

Para ejecutar con el rango predeterminado (ayer hasta ayer):

```text
python main.py
```

El rango de fechas se puede cambiar con:

```text
python main.py --fecha-inicio 2026-08-01 --fecha-fin 2026-08-31
```

El diccionario se toma de `archivos/00_Datos_Raw/Diccionario_Documentos.xlsx`
(o se indica con `--ruta-diccionario`). También se puede iniciar el flujo desde
la interfaz gráfica (`python -m desktop`), que pide el Excel de nuevas
versiones y el diccionario.

## Flujo legado (Selenium, con UISARD)

Disponible solo en desarrollo con Selenium/Playwright instalados:

```text
python main.py --backend-alfresco selenium
```

Encadena `uisard_extractor` → `conciliacion_datos` → `unificar_expedientes` →
`alfresco_extractor` (Selenium/Share), manteniendo el esquema histórico con la
columna `uisard`. Los módulos `src/uisard_extractor.py`,
`src/alfresco_extractor.py`, `src/conciliacion_datos.py`,
`src/unificar_expedientes.py` y `src/uis_login_p1.py` pertenecen a este flujo.
