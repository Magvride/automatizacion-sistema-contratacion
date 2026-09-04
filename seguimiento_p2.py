import os
import re
import unicodedata
from copy import copy

import openpyxl
from openpyxl.formula.translate import Translator
from openpyxl.styles import PatternFill

from config import CONTRATOS_DIR, MATRIZ_ACTUALIZADA_DIR, preparar_directorios
from config import ruta_matriz_manual

try:
    import win32com.client as win32com
    EXCEL_COM_DISPONIBLE = True
except ImportError:
    win32com = None
    EXCEL_COM_DISPONIBLE = False

# =========================
# CONFIGURACIÓN
# =========================
CARPETA_CONTRATOS = CONTRATOS_DIR
PATRON_CONTRATOS = "contratos_*.xlsx"

ARCHIVO_MATRIZ = ruta_matriz_manual()
ARCHIVO_SALIDA = MATRIZ_ACTUALIZADA_DIR / "Matriz Seguimiento Contractual UIS_actualizada.xlsx"
ARCHIVO_NUEVOS = MATRIZ_ACTUALIZADA_DIR / "nuevos_contratos.csv"

# Tiempo máximo de espera (segundos) para que Excel abra y recalcule.
# Si tarda más, se cancela para no colgar el flujo.
EXCEL_ESPERA_SEGUNDOS = 300

HOJA_MAESTRO = "MAESTRO"
HOJA_SEGUIMIENTO = "SEGUIMIENTO"

# En el archivo descargado de la UIS los encabezados están en la fila 4
FILA_ENCABEZADOS_ORIGEN = 4
PRIMERA_FILA_DATOS_ORIGEN = 5

# Columnas que exporta la matriz para alimentar el bloque UISARD/Alfresco.
# (nombre de encabezado normalizado en MAESTRO -> nombre final en el CSV)
COLUMNAS_EXPORTE = {
    "CONTRATO": "contrato",
    "CENTRO DE COSTO": "centro_costo",
    "ORDENADOR DE GASTO CENTRO DE COSTO": "ordenador",
}


def buscar_archivo_contratos():
    """Encuentra el archivo de contratos más reciente en la carpeta de trabajo."""
    archivos = list(CARPETA_CONTRATOS.glob(PATRON_CONTRATOS))

    if not archivos:
        raise FileNotFoundError(
            f"No se encontró ningún archivo {PATRON_CONTRATOS} en: "
            f"{CARPETA_CONTRATOS}"
        )

    return max(archivos, key=lambda archivo: archivo.stat().st_mtime)


def normalizar_encabezado(valor):
    """Normaliza espacios, mayúsculas y tildes para comparar encabezados."""
    if valor is None:
        return ""

    texto = str(valor).strip().upper()
    texto = "".join(
        c
        for c in unicodedata.normalize("NFD", texto)
        if unicodedata.category(c) != "Mn"
    )
    return re.sub(r"\s+", " ", texto)


def copiar_estilo(origen, destino, copiar_color=True):
    """Copia solamente el formato de una celda.

    Si copiar_color es False, la celda destino conserva el color por
    defecto (sin relleno heredado de la celda superior).
    """
    if origen.has_style:
        destino._style = copy(origen._style)

    destino.font = copy(origen.font)

    if copiar_color:
        destino.fill = copy(origen.fill)
    else:
        destino.fill = copy(PatternFill())

    destino.border = copy(origen.border)
    destino.alignment = copy(origen.alignment)
    destino.protection = copy(origen.protection)
    destino.number_format = origen.number_format


def buscar_ultima_fila_con_datos(ws, columna, inicio=2):
    """Busca la última fila con información en una columna."""
    for fila in range(ws.max_row, inicio - 1, -1):
        if ws.cell(fila, columna).value not in (None, ""):
            return fila
    return inicio - 1


def buscar_primera_fila_vacia(ws, columna=1, inicio=2):
    """Busca la primera fila vacía consecutiva para insertar nuevos contratos."""
    fila = inicio
    while ws.cell(fila, columna).value not in (None, ""):
        fila += 1
    return fila


def buscar_ultima_formula(ws, columna, fila_inicio):
    """
    Busca hacia arriba la fórmula más cercana de una columna.
    Esto permite replicar también fórmulas que no estén presentes
    exactamente en la última fila anterior.
    """
    for fila in range(fila_inicio, 1, -1):
        valor = ws.cell(fila, columna).value
        if isinstance(valor, str) and valor.startswith("="):
            return ws.cell(fila, columna)

    return None


def siguiente_numero_maestro(ws_maestro):
    """Obtiene el siguiente valor para la columna N°."""
    ultimo = 0

    for fila in range(2, ws_maestro.max_row + 1):
        valor = ws_maestro.cell(fila, 1).value

        try:
            if valor not in (None, ""):
                ultimo = max(ultimo, int(float(valor)))
        except (ValueError, TypeError):
            pass

    return ultimo + 1


def valores_exporte(ws_maestro, fila, encabezados_maestro):
    """Extrae de una fila de MAESTRO las columnas que alimentan el bloque UISARD/Alfresco."""
    exporte = {}
    for encabezado, destino in COLUMNAS_EXPORTE.items():
        columna = encabezados_maestro.get(encabezado)
        exporte[destino] = ws_maestro.cell(fila, columna).value if columna else None
    return exporte


def recalcular_con_excel(ruta_archivo, timeout=EXCEL_ESPERA_SEGUNDOS):
    """Abre el libro con Excel y lo recalcula para guardar los valores de las fórmulas.

    openpyxl solo escribe el *texto* de cada fórmula, sin su resultado. Por eso, sin
    este paso, las hojas calculadas (p. ej. SEGUIMIENTO) aparecen vacías al abrirlas
    en Excel si este no recalculan automáticamente. Excel suele recalcular al abrir,
    pero este método deja siempre guardado el valor, de modo que se vea incluso en
    otros visores que leen únicamente el valor en caché.

    Devuelve True si Excel recalculó y guardó; False si no fue posible (sin Excel,
    sin pywin32, o se superó el tiempo de espera) sin lanzar excepción.
    """
    if not EXCEL_COM_DISPONIBLE:
        print("[!] No está disponible pywin32; se omite la recalculación por Excel.")
        return False

    ruta = str(ruta_archivo)
    app = None
    try:
        app = win32com.Dispatch("Excel.Application")
        app.DisplayAlerts = False
        app.Visible = False
        app.ScreenUpdating = False
        # En algunos equipos puede tardar en aparecer la ventana.
        app.EnableEvents = False

        # Workbook con protección de estructura no se puede guardar con guiones: desactivarla.
        libro = app.Workbooks.Open(
            ruta, ReadOnly=False, UpdateLinks=3, Password="", WriteResPassword="",
        )

        # Recálculo completo de todas las fórmulas.
        app.CalculateFull()

        # CalcularFull() es síncrono; esperamos un margen por si el libro es muy
        # pesado y Excel aún está terminando de recalcular.
        try:
            tiempo_restante = timeout
            while tiempo_restante > 0:
                if app.CalculationState == 0:  # xlDone
                    break
                import time
                time.sleep(2)
                tiempo_restante -= 2
        except Exception:
            pass

        libro.Save()
        libro.Close(SaveChanges=False)
        print("[OK] Excel recalculó y guardó los valores de las fórmulas.")
        return True

    except Exception as exc:
        print(f"[!] No se pudo recalcular con Excel: {exc}")
        return False

    finally:
        try:
            if app is not None:
                app.Quit()
        except Exception:
            pass


def main():
    preparar_directorios()
    if not os.path.exists(ARCHIVO_MATRIZ):
        raise FileNotFoundError(
            "No se encontró la matriz manual. Colócala en: "
            f"{ARCHIVO_MATRIZ}"
        )

    archivo_contratos = buscar_archivo_contratos()

    # Se cargan las fórmulas, no los valores calculados.
    wb_matriz = openpyxl.load_workbook(ARCHIVO_MATRIZ, data_only=False)

    wb_origen = openpyxl.load_workbook(archivo_contratos, data_only=False)

    ws_maestro = wb_matriz[HOJA_MAESTRO]
    ws_seguimiento = wb_matriz[HOJA_SEGUIMIENTO]
    ws_origen = wb_origen.active

    # ---------------------------------------------------------
    # 1. MAPEAR ENCABEZADOS DEL ARCHIVO FUENTE Y DE MAESTRO
    # ---------------------------------------------------------
    encabezados_origen = {}

    for columna in range(1, ws_origen.max_column + 1):
        encabezado = normalizar_encabezado(
            ws_origen.cell(FILA_ENCABEZADOS_ORIGEN, columna).value
        )

        if encabezado:
            encabezados_origen[encabezado] = columna

    encabezados_maestro = {}

    for columna in range(1, ws_maestro.max_column + 1):
        encabezado = normalizar_encabezado(ws_maestro.cell(1, columna).value)

        if encabezado:
            encabezados_maestro[encabezado] = columna

    # ---------------------------------------------------------
    # 2. CONTRATOS QUE YA EXISTEN EN MAESTRO
    # ---------------------------------------------------------
    contratos_existentes = set()

    for fila in range(2, ws_maestro.max_row + 1):
        contrato = ws_maestro.cell(fila, 3).value

        if contrato not in (None, ""):
            contratos_existentes.add(str(contrato).strip())

    # ---------------------------------------------------------
    # 3. AGREGAR NUEVOS CONTRATOS A MAESTRO
    # ---------------------------------------------------------
    ultima_fila_maestro = buscar_ultima_fila_con_datos(ws_maestro, columna=3)

    siguiente_fila_maestro = ultima_fila_maestro + 1
    numero_maestro = siguiente_numero_maestro(ws_maestro)

    contratos_agregados = []

    for fila_origen in range(PRIMERA_FILA_DATOS_ORIGEN, ws_origen.max_row + 1):
        columna_contrato_origen = encabezados_origen.get("CONTRATO")

        if not columna_contrato_origen:
            raise ValueError("No se encontró la columna CONTRATO en el archivo fuente.")

        contrato = ws_origen.cell(fila_origen, columna_contrato_origen).value

        if contrato in (None, ""):
            continue

        contrato_texto = str(contrato).strip()

        # Evita duplicar contratos si el archivo descargado ya fue procesado.
        if contrato_texto in contratos_existentes:
            continue

        fila_destino = siguiente_fila_maestro

        # Copiar primero el formato de la fila anterior.
        for columna in range(1, ws_maestro.max_column + 1):
            copiar_estilo(
                ws_maestro.cell(fila_destino - 1, columna),
                ws_maestro.cell(fila_destino, columna),
            )

        # Columna N° autoincremental.
        ws_maestro.cell(fila_destino, 1).value = numero_maestro

        # Copiar datos según el nombre del encabezado.
        # Si una columna de MAESTRO no existe en el archivo fuente,
        # queda vacía.
        for encabezado, columna_maestro in encabezados_maestro.items():
            if encabezado == "N°":
                continue

            columna_origen = encabezados_origen.get(encabezado)

            if columna_origen is None:
                ws_maestro.cell(fila_destino, columna_maestro).value = None
            else:
                ws_maestro.cell(fila_destino, columna_maestro).value = ws_origen.cell(
                    fila_origen, columna_origen
                ).value

        contratos_agregados.append({
            "fila_maestro": fila_destino,
            "contrato": contrato,
            "exporte": valores_exporte(ws_maestro, fila_destino, encabezados_maestro),
        })

        contratos_existentes.add(contrato_texto)
        siguiente_fila_maestro += 1
        numero_maestro += 1

    # ---------------------------------------------------------
    # 4. AGREGAR CONTRATOS EN SEGUIMIENTO
    # ---------------------------------------------------------
    if contratos_agregados:
        primera_fila_seguimiento = buscar_primera_fila_vacia(
            ws_seguimiento, columna=1, inicio=2
        )

        # Para cada columna buscamos la última fórmula disponible.
        # Esa fórmula se traduce a la nueva fila usando Translator.
        fuentes_formula = {}

        for columna in range(1, ws_seguimiento.max_column + 1):
            celda_formula = buscar_ultima_formula(
                ws_seguimiento, columna, primera_fila_seguimiento - 1
            )

            if celda_formula is not None:
                fuentes_formula[columna] = celda_formula

        for indice, nuevo in enumerate(contratos_agregados):
            fila_destino = primera_fila_seguimiento + indice

            # Copiar solamente formato de la fila anterior,
            # pero SIN heredar los colores de la celda superior.
            for columna in range(1, ws_seguimiento.max_column + 1):
                copiar_estilo(
                    ws_seguimiento.cell(fila_destino - 1, columna),
                    ws_seguimiento.cell(fila_destino, columna),
                    copiar_color=False,
                )

            # La columna A contiene el contrato.
            # Las demás columnas con fórmula se calculan automáticamente.
            ws_seguimiento.cell(fila_destino, 1).value = nuevo["contrato"]

            # Replicar TODAS las fórmulas existentes en la plantilla.
            #
            # Ejemplos:
            # - MATCH / INDEX contra MAESTRO.
            # - PERSONA.
            # - MES DE RENDICIÓN.
            # - FECHA LÍMITE.
            # - Porcentajes y demás cálculos internos.
            #
            # Las columnas sin fórmula se dejan vacías para conservar
            # el comportamiento manual de la matriz.
            for columna, celda_origen_formula in fuentes_formula.items():
                if columna == 1:
                    continue

                try:
                    formula_nueva = Translator(
                        celda_origen_formula.value,
                        origin=celda_origen_formula.coordinate,
                    ).translate_formula(
                        ws_seguimiento.cell(fila_destino, columna).coordinate
                    )

                    ws_seguimiento.cell(fila_destino, columna).value = formula_nueva

                except Exception:
                    # Si por alguna razón una fórmula no puede traducirse,
                    # se conserva la fórmula original como último recurso.
                    ws_seguimiento.cell(fila_destino, columna).value = (
                        celda_origen_formula.value
                    )

            # Mantener la altura de la fila anterior.
            ws_seguimiento.row_dimensions[fila_destino].height = (
                ws_seguimiento.row_dimensions[fila_destino - 1].height
            )

    # ---------------------------------------------------------
    # 5. GUARDAR RESULTADO
    # ---------------------------------------------------------
    # Pedir también a openpyxl que marque el libro para recalcular al abrirse.
    # Es una red de seguridad por si la recalculación por Excel COM no está disponible.
    try:
        wb_matriz.calculation.fullCalcOnLoad = True
    except Exception:
        pass

    wb_matriz.save(ARCHIVO_SALIDA)

    # Recalcular con Excel para que las fórmulas de SEGUIMIENTO (y demás hojas
    # calculadas) queden con su valor guardado y no aparezcan vacías al abrir.
    recalcular_con_excel(ARCHIVO_SALIDA)

    # Exporta solo los contratos nuevos del día (los que no estaban en el MAESTRO),
    # para que el bloque UISARD/Alfresco verifique únicamente las incorporaciones de hoy.
    if contratos_agregados:
        import pandas as pd

        df_nuevos = pd.DataFrame([nuevo["exporte"] for nuevo in contratos_agregados])
        df_nuevos.to_csv(ARCHIVO_NUEVOS, index=False, encoding="utf-8-sig")
        print(f"Contratos nuevos exportados a UISARD: {len(df_nuevos)} -> {ARCHIVO_NUEVOS}")
    elif ARCHIVO_NUEVOS.exists():
        ARCHIVO_NUEVOS.unlink()
        print("[+] Sin contratos nuevos hoy; se limpia el exporte de nuevos contratos.")

    print("=" * 60)
    print("PROCESO TERMINADO")
    print("=" * 60)
    print(f"Contratos nuevos agregados: {len(contratos_agregados)}")

    if contratos_agregados:
        print(
            "Filas nuevas en MAESTRO: "
            f"{contratos_agregados[0]['fila_maestro']} "
            f"a {contratos_agregados[-1]['fila_maestro']}"
        )

        print("Primera fila nueva en SEGUIMIENTO: " f"{primera_fila_seguimiento}")

    print(f"Archivo generado: {ARCHIVO_SALIDA}")


if __name__ == "__main__":
    main()
