# Estructura de archivos

Todas las entradas y salidas del flujo se guardan dentro de `archivos/`:

| Carpeta | Uso |
| --- | --- |
| `04_Contratos_Descargados_UISARD/` | Reportes demo o reportes descargados por `uisard_extractor.py`. |
| `01_Contratos_Descargados/` | Excel descargado por `uis_login_p1.py`. |
| `00_Datos_Raw/` | Entrada manual. Aquí debe colocarse `Matriz Seguimiento Contractual UIS.xlsx`. |
| `02_Matriz_actualizada/` | Salida de `seguimiento_p2.py` (matriz actualizada). |
| `03_Contratos_Conciliacion/` | CSV normalizado generado por `seguimiento_p2.py` (`contratos_normalizados.csv`). |
| `05_Datos_filtrados/` | Consolidado y resultados de la parte UISARD/Alfresco. |
| `06_Expedientes/` | Expedientes verificados/descargados en Alfresco. |

## Flujo propio

1. `uis_login_p1.py` descarga `contratos_*.xlsx` en `archivos/01_Contratos_Descargados/`.
2. `seguimiento_p2.py` toma el Excel más reciente y la matriz manual, y guarda la matriz actualizada en `archivos/02_Matriz_actualizada/` como `02_Matriz_Seguimiento_actualizada.xlsx`.
3. `seguimiento_p2.py` exporta los contratos nuevos normalizados a `archivos/03_Contratos_Conciliacion/contratos_normalizados.csv` (con `correo_ordenador` y `uisard` vacías).

Para ejecutar el flujo completo con el rango predeterminado (ayer hasta ayer), coloca primero la matriz manual en su carpeta y ejecuta:

```text
python main.py
```

El rango de fechas se puede cambiar para ambos sistemas con:

```text
python main.py --fecha-inicio 2026-08-01 --fecha-fin 2026-08-31
```

Si no se indican fechas, tanto Financiero UIS como UISARD consultan únicamente el día anterior a la ejecución.

También se puede iniciar el flujo desde la interfaz gráfica mediante `app_gui.py`.

El orquestador `main.py` encadena de forma secuencial:

1. **Bloque propio (Financiero UIS):**
   `uis_login_p1` → `seguimiento_p2` (guarda en `03_Contratos_Conciliacion/contratos_normalizados.csv` los contratos nuevos del día).
2. **FASE 1 — UISARD:** descarga reportes por serie a `archivos/04_Contratos_Descargados_UISARD/`.
3. **FASE 2 — Conciliación:** `conciliacion_datos.py` genera `archivos/05_Datos_filtrados/01_Contratos_en_UISARD.csv`.
4. **FASE 2.5 — Unificación:** `unificar_expedientes.py` une los contratos del bloque propio con los datos UISARD por número de contrato (unión completa: propios en UISARD, propios sin UISARD y los que solo están en UISARD) y genera `archivos/05_Datos_filtrados/02_Consolidado_General.csv` (rellena las columnas `uisard` y adjunta `NOMBRE EXPEDIENTE`/`UAA`/`SERIE`/`SUB-SERIE`).
5. **FASE 3 — Alfresco:** `alfresco_extractor.py` verifica el CSV unido y guarda únicamente `06_Verificacion_Alfresco.csv` (todos los registros con `alfresco` = SI/NO y `cantidad_archivos`) y `07_Expedientes_Faltantes.csv` (los no encontrados) en `archivos/05_Datos_filtrados/`, y los expedientes corroborados en `archivos/06_Expedientes/expedientes_verificados/`. Durante esta fase también se refresca en vivo `03_Resultado_Final.xlsx`.
6. **FASE 3.5 — Merge Alfresco:** agrega al consolidado `02_Consolidado_General.csv` las columnas `alfresco` y `cantidad_archivos` (unión por `NOMBRE EXPEDIENTE`).
7. **FASE 3.6 — Reporte maestro:** `resultados.py` genera `archivos/05_Datos_filtrados/03_Resultado_Final.xlsx`, que resume por contrato si está en UISARD (`uisard`) y si el expediente se encontró en Alfresco con archivos (`alfresco`/`cantidad_archivos`), más una columna `estado` legible. Es el insumo del envío final.
8. **FASE 3.7 — Dashboards:** `dashboard.py` genera `archivos/05_Datos_filtrados/04_Tablero_Resumen.html` (informe visual: UISARD, nuevas versiones, intersección, encontrados/faltantes, resumen por estado y vista previa) y `archivos/05_Datos_filtrados/05_Tablero_en_Vivo.html` (panel en tiempo real con el expediente en curso; se auto-refresca cada 5 s).

Las credenciales de `uis_login_p1.py` se leen desde `UIS_LOGIN_USER`/`UIS_LOGIN_PASS` del `.env`. Si no existen, usa `UISARD_USER`/`UISARD_PASS`.
