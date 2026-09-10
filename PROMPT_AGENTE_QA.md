# Prompt para el agente de QA

Eres un agente de QA con acceso al repositorio. Tu tarea es **crear la primera suite de pruebas unitarias** del flujo de automatización del sistema de contratación, usando **pytest**.

## Contexto del proyecto

- Repositorio: `C:\Users\manue\OneDrive\Documents\Práctica contratación\06_DEV_prod\automatizacion-sistema-contratacion`
- Rama actual: `QA` (no hagas commit ni push; solo crea/modifica archivos).
- Es un flujo Python (orquestado por `main.py`) que va: conciliación UISARD → unificación por contrato → verificación en Alfresco → notificación.
- La lógica de negocio vive en `src/`:
  - `src/conciliacion_datos.py` (normalizar, texto_libre, es_reporte, leer_reporte, generar_consolidado)
  - `src/unificar_expedientes.py` (_clave_contrato, _normalizar, _normalizar_nombre, unir_consolidados)
  - `src/notificar_uisard.py` (_normalizar_correo, _formatear_plantilla, _construir_cuerpo, _construir_mensajes, notificar_no_uisard)
  - `src/alfresco_extractor.py` (helpers puros: _normalizar_texto, _es_expediente_coherente, _candidatos_serie, _candidatos_subserie)
  - `main.py` (getenv, parsear_argumentos, fase_merge_alfresco)
- Python 3.14.6. Dependencias en `requirements.txt` (pandas, openpyxl, selenium, etc.). No hay tests todavía.

## Alcance de esta tanda (IMPORTANTE)

**Solo pruebas unitarias de lógica pura + archivos temporales.** No intentes ejecutar ni mockear Selenium, login a UISARD/Alfresco, descarga de ZIP, ni OneDrive. Esos quedan fuera y se documentan como tests de integración futuros.

## Pasos a seguir

1. Crea `requirements-dev.txt` en la raíz con el contenido:
   ```
   pytest>=8.0.0
   ```
   No modifiques `requirements.txt`.

2. Crea la carpeta `tests/` con:
   - **`tests/conftest.py`**:
     - Agrega `src/` a `sys.path` (los módulos importan `from config import ...` y `from utils.logger import ...`).
     - Un fixture que redirija/silencie los logs hacia un archivo temporal (para no ensuciar `logs/` del repo).
     - Un fixture `salidas_tmp` que arme el dict `salidas` usado por `main.py` (`{"carpeta": <tmp>, "csv": <ruta a 01>}`), apuntando a `tmp_path`.
   - **`tests/test_conciliacion.py`**: casos para `normalizar` (acentos/mayúsculas/espacios/valor no-string), `texto_libre` (fórmula HYPERLINK, celda plana, `None`, `=` no-HYPERLINK), `es_reporte`, y `leer_reporte`/`generar_consolidado` con un `.xlsx` real creado en `tmp_path` (verifica columnas `NOMBRE EXPEDIENTE`, `NÚMERO CONTRATO`, `UAA`, `SERIE`, `SUBSERIE` y el filtrado de filas sin expediente).
   - **`tests/test_unificacion.py`**: casos para `_clave_contrato` (`"270-2026000050"` → `"2026000050"`, `None`/`"nan"` → `""`), `_normalizar_nombre`, y `unir_consolidados` con un CSV base y un DataFrame UISARD en `tmp_path` (verifica merge por contrato, columna `uisard` SI/NO, correos de ordenadores; y el caso sin CSV base → `encontrado=False`).
   - **`tests/test_notificacion.py`**: casos para `_normalizar_correo`, `_formatear_plantilla`, `_construir_cuerpo` (un solo contrato y varios, sin repetir el saludo), `_construir_mensajes`, y `notificar_no_uisard(..., columna_no="alfresco")` con un CSV en `tmp_path` (solo se notifican los `alfresco=NO`; pasa `borradores=<tmp>` y `enviar=False`).
   - **`tests/test_alfresco_helpers.py`**: instancia `AlfrescoExtractor(url="", usuario="", contrasena="")` **sin abrir Chrome** y prueba `_normalizar_texto`, `_es_expediente_coherente`, `_candidatos_serie` y `_candidatos_subserie`.
   - **`tests/test_merge_alfresco.py`**: prueba `main.fase_merge_alfresco(None, salidas_tmp)` creando `06_Verificacion_Alfresco.csv` (con `alfresco`/`cantidad_archivos`) y el consolidado `02_Consolidado_General.csv` en `tmp_path`; verifica que el 02 queda con las columnas `alfresco` y `cantidad_archivos`, que las filas sin expediente quedan en blanco y las no encontradas en `NO`.

3. Cubre también casos borde en cada prueba: entradas `None`, cadenas vacías, acentos, datos mal formados.

## Reglas de estilo

- No agregues comentarios innecesarios ni emojis.
- Respeta las convenciones del código existente (imports desde `config`, `utils.logger`).
- No uses credenciales ni valores sensibles; usa datos de ejemplo ficticios.

## Verificación final

- Ejecuta `python -m pytest -v` desde la raíz del proyecto.
- Todos los tests deben pasar. Si alguno falla por un error real del código, **no corrijas el código de producción**; documenta el hallazgo en tu reporte final.
- Reporta al terminar: lista de archivos creados, número de tests y su resultado, y cualquier supuesto que hayas hecho.
