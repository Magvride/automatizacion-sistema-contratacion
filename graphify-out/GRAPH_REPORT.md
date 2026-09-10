# Graph Report - automatizacion-sistema-contratacion  (2026-09-09)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 365 nodes · 665 edges · 20 communities (17 shown, 1 thin omitted)
- Extraction: 96% EXTRACTED · 4% INFERRED · 0% AMBIGUOUS · INFERRED: 24 edges (avg confidence: 0.85)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `5b1362ca`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- AppContratacion
- main.py
- UISARDExtractor
- conciliacion_datos.py
- notificar_uisard.py
- uis_login_p1.py
- seguimiento_p2.py
- logger.py
- AlfrescoExtractor
- unificar_expedientes.py
- _BotonRedondeado
- ._bajar_por_ruta
- ._normalizar_texto
- ._navegar_arbol
- .verificar_expedientes_desde_csv
- ._buscar_expediente_por_busqueda
- ._descargar_zip_en_carpeta
- _ColaWriter

## God Nodes (most connected - your core abstractions)
1. `AlfrescoExtractor` - 57 edges
2. `AppContratacion` - 29 edges
3. `UISARDExtractor` - 26 edges
4. `notificar_no_uisard()` - 12 edges
5. `main()` - 11 edges
6. `ruta_ordenadores()` - 10 edges
7. `main()` - 10 edges
8. `unir_consolidados()` - 10 edges
9. `_BotonRedondeado` - 9 edges
10. `ruta_matriz_manual()` - 9 edges

## Surprising Connections (you probably didn't know these)
- `main()` --calls--> `preparar_directorios()`  [INFERRED]
  prueba_conciliacion.py → src/config.py
- `leer_y_normalizar()` --calls--> `_celda()`  [INFERRED]
  prueba_conciliacion.py → src/notificar_uisard.py
- `main()` --calls--> `unir_consolidados()`  [INFERRED]
  prueba_conciliacion.py → src/unificar_expedientes.py
- `fase_uisard()` --calls--> `UISARDExtractor`  [EXTRACTED]
  main.py → src/uisard_extractor.py
- `fase_alfresco()` --calls--> `AlfrescoExtractor`  [EXTRACTED]
  main.py → src/alfresco_extractor.py

## Import Cycles
- None detected.

## Communities (20 total, 1 thin omitted)

### Community 0 - "AppContratacion"
Cohesion: 0.06
Nodes (36): Popen, AppContratacion, _ColaLogHandler, fecha_por_defecto(), Interfaz gráfica de escritorio (Tkinter) para ejecutar el flujo de…, Handler de logging que envía cada registro a la ventana y a un archivo., Aplicación de escritorio: rango de fechas + empezar., Devuelve solo los flags de CLI (sin el script), p. ej. ['--fecha-… (+28 more)

### Community 1 - "main.py"
Cohesion: 0.09
Nodes (31): construir_salidas(), ejecutar_bloque_propio(), fase_alfresco(), fase_conciliacion(), fase_merge_alfresco(), fase_notificacion(), fase_uisard(), fase_unificacion() (+23 more)

### Community 2 - "UISARDExtractor"
Cohesion: 0.14
Nodes (9): construir_salidas(), fase_uisard(), main(), parsear_argumentos(), Chrome, DataFrame, Namespace, Extrae reportes de la plataforma UISARD en formato Excel. (+1 more)

### Community 3 - "conciliacion_datos.py"
Cohesion: 0.12
Nodes (20): buscar_excel_nuevas_versiones(), leer_y_normalizar(), main(), normalizar(), Prueba: genera la conciliación (CSV) a partir del reporte de nuevas versiones.…, Normaliza mayúsculas y tildes para comparar encabezados., Devuelve el InformacionContratos*.xls más reciente de 01_Contratos_Descargados., Lee el Excel descargado y devuelve un DataFrame con las columnas del bloque… (+12 more)

### Community 4 - "notificar_uisard.py"
Cohesion: 0.15
Nodes (21): _celda(), _construir_cuerpo(), _construir_mensajes(), _enviar(), _formatear_plantilla(), _guardar_borradores(), _normalizar_correo(), notificar_no_uisard() (+13 more)

### Community 5 - "uis_login_p1.py"
Cohesion: 0.18
Nodes (20): by_id(), consultar_y_descargar_excel(), crear_contexto(), hacer_login(), human_click(), human_pause(), main(), date (+12 more)

### Community 6 - "seguimiento_p2.py"
Cohesion: 0.15
Nodes (19): buscar_archivo_contratos(), buscar_primera_fila_vacia(), buscar_ultima_fila_con_datos(), buscar_ultima_formula(), copiar_estilo(), main(), normalizar_encabezado(), Busca la última fila con información en una columna. (+11 more)

### Community 7 - "logger.py"
Cohesion: 0.14
Nodes (14): Logger, main(), parsear_argumentos(), Namespace, Path, Sube la matriz de seguimiento actualizada a la carpeta de OneDrive del equipo.…, Ruta de la matriz actualizada generada por ``seguimiento_p2.py``., Copia la matriz a la carpeta de OneDrive del equipo. Crea la carpeta destino si… (+6 more)

### Community 8 - "AlfrescoExtractor"
Cohesion: 0.22
Nodes (5): AlfrescoExtractor, Chrome, Añade ``filas`` a un CSV creando la cabecera la primera vez. Permite que los…, Extrae el atributo title del menú de repositorio en Alfresco Share., Clica el enlace del resultado para abrir la carpeta/expediente.

### Community 9 - "unificar_expedientes.py"
Cohesion: 0.18
Nodes (14): _buscar_archivo_ordenadores(), _cargar_correos_ordenadores(), _clave_contrato(), _normalizar(), _normalizar_nombre(), DataFrame, Une los contratos del sistema Financiero con los datos UISARD (indicador +…, FASE 2.5 — Unificación. Une el bloque propio (contratos del sistema Financiero… (+6 more)

### Community 10 - "_BotonRedondeado"
Cohesion: 0.20
Nodes (5): _BotonRedondeado, Encabezado tipo pastilla: fondo verde redondeado que envuelve solo el texto., Calcula el ancho real del texto usando la fuente real del widget., Botón ligero con esquinas redondeadas y estados ttk compatibles., _TituloRedondeado

### Community 11 - "._bajar_por_ruta"
Cohesion: 0.21
Nodes (6): Devuelve el div.ygtvitem que contiene la etiqueta texto (consulta fresca)., Baja por la ruta de etiquetas re-anclando desde self.driver (consulta fresca).…, True si el nodo ruta[-1] ya tiene hijos renderizados (chequeo fresco)., Espera y devuelve el div.ygtvitem cuya etiqueta coincide con texto., Expande el nodo ruta[-1] y devuelve su contenedor de hijos (div.ygtvchildren).…, Entra/selecciona el nodo ruta[-1] haciendo clic en su etiqueta.

### Community 12 - "._normalizar_texto"
Cohesion: 0.21
Nodes (6): Devuelve el span.ygtvlabel cuyo texto coincide exactamente con texto., True si en la biblioteca de documentos hay un ítem cuyo nombre coincide.…, Número de página mostrado por el paginador YUI (.yui-pg-current-page)., Número de páginas totales a partir del texto 'N - M de TOTAL' del paginador., Clica el botón '>>' del paginador y espera a que cargue la página ``esperada``., Busca el expediente dentro de la biblioteca de la subserie actual (AJAX). La…

### Community 13 - "._navegar_arbol"
Cohesion: 0.18
Nodes (6): Limpia las cachés de navegación del árbol (ruta y nodos expandidos)., Etiquetas probables de la SERIE en el árbol. La serie se guarda con el código…, Etiquetas probables de la SUB-SERIE en el árbol. La subserie se guarda con el…, Navega Repositorio -> UAA -> SERIE -> SUB-SERIE y entra/selecciona la subserie.…, Ruta manual: Repositorio -> UAA -> SERIE -> SUB-SERIE y busca el expediente.…, Verifica un registro: fast path (buscadores) y, como último recurso, la ruta…

### Community 14 - ".verificar_expedientes_desde_csv"
Cohesion: 0.15
Nodes (6): Deriva una ruta CSV auxiliar en la misma carpeta que el resumen., True si el nombre parece un expediente real (Numero_Sufijo)., Describe qué puede estar pasando cuando el nombre no es un expediente coherente., Calcula el motivo y apila en ``resumen``/``pasos``. Devuelve (fila_resumen,…, Verifica en dos fases: primero búsqueda (header + searchTerm), luego ruta…, Llega al repositorio y espera a que cargue el árbol de carpetas. Primero…

### Community 15 - "._buscar_expediente_por_busqueda"
Cohesion: 0.17
Nodes (6): Devuelve la fila de resultado de búsqueda que mejor coincide con ``objetivo``.…, True si la carpeta abierta muestra ficheros O subcarpetas., Escribe el término en la caja de búsqueda de forma robusta (JS como respaldo)., Dispara la búsqueda: clic en el icono de búsqueda o Enter., Devuelve los buscadores disponibles en orden de preferencia. Orden: (1) caja…, Fast path: busca el expediente probando los buscadores en orden. 1) Primero la…

### Community 16 - "._descargar_zip_en_carpeta"
Cohesion: 0.17
Nodes (6): Vuelca el HTML actual a logs/diagnostico/ (máx. 10 por corrida)., Cierra el menú desplegable si quedó abierto (restaura el estado)., Espera y devuelve el primer elemento visible que cumple ``xpath`` (o None)., Espera a que termine y aparezca el ZIP de la descarga (prefiere el del…, Mueve el ZIP a <destino>/<expediente>/ y lo descomprime., Dentro de la carpeta abierta, selecciona todo y descarga el ZIP.

## Knowledge Gaps
- **1 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `AlfrescoExtractor` connect `AlfrescoExtractor` to `main.py`, `logger.py`, `._bajar_por_ruta`, `._normalizar_texto`, `._navegar_arbol`, `.verificar_expedientes_desde_csv`, `._buscar_expediente_por_busqueda`, `._descargar_zip_en_carpeta`?**
  _High betweenness centrality (0.429) - this node is a cross-community bridge._
- **Why does `UISARDExtractor` connect `UISARDExtractor` to `main.py`?**
  _High betweenness centrality (0.124) - this node is a cross-community bridge._
- **Why does `AppContratacion` connect `AppContratacion` to `logger.py`?**
  _High betweenness centrality (0.120) - this node is a cross-community bridge._
- **Should `AppContratacion` be split into smaller, more focused modules?**
  _Cohesion score 0.05563093622795115 - nodes in this community are weakly interconnected._
- **Should `main.py` be split into smaller, more focused modules?**
  _Cohesion score 0.0928030303030303 - nodes in this community are weakly interconnected._
- **Should `UISARDExtractor` be split into smaller, more focused modules?**
  _Cohesion score 0.13763440860215054 - nodes in this community are weakly interconnected._
- **Should `conciliacion_datos.py` be split into smaller, more focused modules?**
  _Cohesion score 0.11857707509881422 - nodes in this community are weakly interconnected._