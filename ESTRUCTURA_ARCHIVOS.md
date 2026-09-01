# Estructura de archivos

Todas las entradas y salidas del flujo se guardan dentro de `archivos/`:

| Carpeta | Uso |
| --- | --- |
| `reportes_demo/` | Reportes demo o reportes descargados por `uisard_extractor.py`. |
| `contratos_uis/` | Excel descargado por `uis_login_p1.py`. |
| `matriz_manual/` | Entrada manual. Aquí debe colocarse `Matriz Seguimiento Contractual UIS.xlsx`. |
| `matriz_actualizada/` | Salida de `seguimiento_p2.py`. |
| `extraccion_csv/` | CSV generado por `extraccion_p21.py`. |
| `resultados/` | Consolidado y resultados de la parte UISARD/Alfresco. |

## Flujo propio

1. `uis_login_p1.py` descarga `contratos_*.xlsx` en `archivos/contratos_uis/`.
2. `seguimiento_p2.py` toma el Excel más reciente y la matriz manual, y guarda la matriz actualizada en `archivos/matriz_actualizada/`.
3. `extraccion_p21.py` toma la matriz actualizada más reciente y guarda `contratos_normalizados.csv` en `archivos/extraccion_csv/`.

Para ejecutar el flujo completo, coloca primero la matriz manual en su carpeta y ejecuta:

```text
python main.py
```

Las credenciales de `uis_login_p1.py` se leen desde `UIS_LOGIN_USER`/`UIS_LOGIN_PASS` del `.env`. Si no existen, usa `UISARD_USER`/`UISARD_PASS`.
