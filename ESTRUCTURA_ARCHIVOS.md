# Estructura de archivos

Todas las entradas y salidas del flujo se guardan dentro de `archivos/`:

| Carpeta | Uso |
| --- | --- |
| `reportes_demo/` | Reportes demo o reportes descargados por `uisard_extractor.py`. |
| `contratos_uis/` | Excel descargado por `uis_login_p1.py`. |
| `matriz_manual/` | Entrada manual. Aquí debe colocarse `Matriz Seguimiento Contractual UIS.xlsx`. |
| `matriz_actualizada/` | Salida de `seguimiento_p2.py` (matriz + `nuevos_contratos.csv`). |
| `extraccion_csv/` | CSV generado por `extraccion_p21.py`. |
| `resultados/` | Consolidado y resultados de la parte UISARD/Alfresco. |

## Flujo propio

1. `uis_login_p1.py` descarga `contratos_*.xlsx` en `archivos/contratos_uis/`.
2. `seguimiento_p2.py` toma el Excel más reciente y la matriz manual, y guarda la matriz actualizada en `archivos/matriz_actualizada/`.
3. `extraccion_p21.py` toma la matriz actualizada más reciente y guarda `contratos_normalizados.csv` en `archivos/extraccion_csv/`.

Para ejecutar el flujo completo con el rango predeterminado (ayer hasta ayer), coloca primero la matriz manual en su carpeta y ejecuta:

```text
python main.py
```

El rango de fechas se puede cambiar para ambos sistemas con:

```text
python main.py --fecha-inicio 2026-08-01 --fecha-fin 2026-08-31
```

Si no se indican fechas, tanto Financiero UIS como UISARD consultan únicamente el día anterior a la ejecución.

También se puede iniciar el flujo desde la interfaz gráfica mediante `app_gui.py` o el ejecutable generado por `compilar_exe.bat`.

El orquestador `main.py` encadena de forma secuencial:

1. **Bloque propio (Financiero UIS):**
   `uis_login_p1` → `seguimiento_p2` (guarda en `matriz_actualizada/nuevos_contratos.csv` solo los contratos nuevos del día) → `extraccion_p21` (`archivos/extraccion_csv/contratos_normalizados.csv`).
2. **FASE 1 — UISARD:** descarga reportes por serie a `archivos/reportes_demo/`.
3. **FASE 2 — Conciliación:** `conciliacion_datos.py` genera `archivos/resultados/conciliacion_datos.csv`.
4. **FASE 2.5 — Unificación:** `unificar_expedientes.py` une los contratos del bloque propio con los datos UISARD por número de contrato y genera `archivos/resultados/contratos_unificados.csv` (rellena las columnas `uisard` y adjunta `NOMBRE EXPEDIENTE`/`UAA`/`SERIE`/`SUB-SERIE`).
5. **FASE 3 — Alfresco:** `alfresco_extractor.py` verifica el CSV unido y guarda `verificacion_alfresco.csv` y `verificacion_alfresco_pasos.csv`.

Las credenciales de `uis_login_p1.py` se leen desde `UIS_LOGIN_USER`/`UIS_LOGIN_PASS` del `.env`. Si no existen, usa `UISARD_USER`/`UISARD_PASS`.
