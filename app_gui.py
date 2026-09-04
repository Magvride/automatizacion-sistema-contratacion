# -*- coding: utf-8 -*-
"""Interfaz gráfica de escritorio (Tkinter) para ejecutar el flujo de contratación.

El cliente final solo elige el rango de fechas y pulsa "Empezar"; el resto del
flujo (Financiero UIS → matriz → CSV → UISARD → Alfresco) se ejecuta de forma
automática. Ocupa la biblioteca estándar `tkinter` (sin dependencias extra).
"""

# comprobación
import builtins
import logging
import os
import queue
import shutil
import subprocess
import sys
import threading
from datetime import date, datetime, timedelta

import tkinter as tk
from tkinter import filedialog, font as tkfont, messagebox, ttk

from config import (
    ruta_matriz_manual,
    ruta_ordenadores,
    configurar_rutas,
    restablecer_rutas,
)

FROZEN = getattr(sys, "frozen", False)

if FROZEN:
    BASE_DIR = os.path.dirname(os.path.abspath(sys.executable))
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MAIN_PY = os.path.join(BASE_DIR, "main.py")

FORMATO_FECHA = "%Y-%m-%d"

COLOR_VERDE_UIS = "#016937"
COLOR_VERDE_OSCURO = "#004d29"
COLOR_DORADO = "#d6a62e"
COLOR_TEXTO = "#17352a"
COLOR_SECUNDARIO = "#60756a"
COLOR_BORDE = "#d9e4dd"
COLOR_FONDO = "#ffffff"


class _BotonRedondeado(tk.Canvas):
    """Botón ligero con esquinas redondeadas y estados ttk compatibles."""

    def __init__(
        self,
        parent,
        text,
        command,
        width=130,
        height=38,
        color=COLOR_VERDE_UIS,
        color_hover=COLOR_VERDE_OSCURO,
        **kwargs,
    ):
        super().__init__(
            parent,
            width=width,
            height=height,
            highlightthickness=0,
            bd=0,
            relief=tk.FLAT,
            bg=COLOR_FONDO,
            **kwargs,
        )
        self._text = text
        self._command = command
        self._color = color
        self._color_hover = color_hover
        self._habilitado = True
        self._dibujar()
        self.bind("<Enter>", self._al_entrar)
        self.bind("<Leave>", self._al_salir)
        self.bind("<Button-1>", self._al_click)

    def _dibujar(self, color=None):
        self.delete("all")
        color = color or self._color
        ancho = int(self["width"])
        alto = int(self["height"])
        radio = min(11, alto // 2)
        self.create_arc(
            0, 0, radio * 2, radio * 2, start=90, extent=90, fill=color, outline=color
        )
        self.create_arc(
            ancho - radio * 2,
            0,
            ancho,
            radio * 2,
            start=0,
            extent=90,
            fill=color,
            outline=color,
        )
        self.create_arc(
            0,
            alto - radio * 2,
            radio * 2,
            alto,
            start=180,
            extent=90,
            fill=color,
            outline=color,
        )
        self.create_arc(
            ancho - radio * 2,
            alto - radio * 2,
            ancho,
            alto,
            start=270,
            extent=90,
            fill=color,
            outline=color,
        )
        self.create_rectangle(radio, 0, ancho - radio, alto, fill=color, outline=color)
        self.create_rectangle(0, radio, ancho, alto - radio, fill=color, outline=color)
        self.create_text(
            ancho // 2,
            alto // 2,
            text=self._text,
            fill=COLOR_FONDO if self._habilitado else COLOR_SECUNDARIO,
            font=("Segoe UI Semibold", 10),
        )

    def configure(self, **kwargs):
        estado = kwargs.pop("state", None)
        if estado is not None:
            self._habilitado = estado != tk.DISABLED
            self._dibujar(self._color if self._habilitado else COLOR_BORDE)
        return super().configure(**kwargs)

    config = configure

    def _al_entrar(self, _event):
        if self._habilitado:
            self._dibujar(self._color_hover)

    def _al_salir(self, _event):
        if self._habilitado:
            self._dibujar()

    def _al_click(self, _event):
        if self._habilitado:
            self._command()


class _TituloRedondeado(tk.Canvas):
    """Encabezado tipo pastilla: fondo verde redondeado que envuelve solo el texto."""

    def __init__(
        self,
        parent,
        text,
        color=COLOR_VERDE_UIS,
        texto_color=COLOR_FONDO,
        alto=46,
        radio=23,
        **kwargs,
    ):
        self._texto = text
        self._color_relleno = color
        self._color_texto = texto_color
        self._radio = radio
        self._fuente = ("Segoe UI Semibold", 15)
        self._ancho_texto = self._medir_texto(text)

        super().__init__(
            parent,
            width=self._ancho_texto + self._radio * 2 + 44,
            height=alto,
            highlightthickness=0,
            bd=0,
            relief=tk.FLAT,
            bg=COLOR_FONDO,
            **kwargs,
        )
        self._dibujar()

    def _medir_texto(self, texto):
        """Calcula el ancho real del texto usando la fuente real del widget."""
        fuente = tkfont.Font(family="Segoe UI", size=15, weight="bold")
        return max(fuente.measure(texto), 1)

    def _dibujar(self):
        self.delete("all")
        ancho = int(self["width"])
        alto = int(self["height"])
        radio = min(self._radio, alto // 2)
        c = self._color_relleno
        self.create_arc(
            0, 0, radio * 2, radio * 2, start=90, extent=90, fill=c, outline=c
        )
        self.create_arc(
            ancho - radio * 2,
            0,
            ancho,
            radio * 2,
            start=0,
            extent=90,
            fill=c,
            outline=c,
        )
        self.create_arc(
            0,
            alto - radio * 2,
            radio * 2,
            alto,
            start=180,
            extent=90,
            fill=c,
            outline=c,
        )
        self.create_arc(
            ancho - radio * 2,
            alto - radio * 2,
            ancho,
            alto,
            start=270,
            extent=90,
            fill=c,
            outline=c,
        )
        self.create_rectangle(radio, 0, ancho - radio, alto, fill=c, outline=c)
        self.create_rectangle(0, radio, ancho, alto - radio, fill=c, outline=c)
        self.create_text(
            ancho // 2,
            alto // 2,
            text=self._texto,
            fill=self._color_texto,
            font=self._fuente,
        )


def fecha_por_defecto() -> str:
    return (date.today() - timedelta(days=1)).strftime(FORMATO_FECHA)


class _ColaWriter:
    """Pseudo-stream: convierte lo escrito (print) en líneas para la cola de la GUI."""

    def __init__(self, cola) -> None:
        self.cola = cola
        self._buf = ""

    def write(self, texto: str) -> None:
        if not texto:
            return
        self._buf += texto
        while "\n" in self._buf:
            linea, self._buf = self._buf.split("\n", 1)
            self.cola.put(("linea", linea + "\n"))

    def flush(self) -> None:
        if self._buf:
            self.cola.put(("linea", self._buf))
            self._buf = ""


class _ColaLogHandler(logging.Handler):
    """Handler de logging que envía cada registro a la ventana y a un archivo."""

    def __init__(self, cola, nombre_log_dir: str) -> None:
        super().__init__(level=logging.DEBUG)
        self.cola = cola
        self.setFormatter(
            logging.Formatter(
                "%(asctime)s | %(levelname)-8s | %(module)s:%(lineno)d | %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
        os.makedirs(nombre_log_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self._archivo = os.path.join(nombre_log_dir, f"ejecucion_{timestamp}.log")
        self._fh = open(self._archivo, "a", encoding="utf-8")

    def emit(self, record) -> None:
        try:
            self._fh.write(self.format(record) + "\n")
            self._fh.flush()
        except OSError:
            pass
        self.cola.put(("linea", self.format(record) + "\n"))


class AppContratacion(tk.Tk):
    """Aplicación de escritorio: rango de fechas + empezar."""

    def __init__(self) -> None:
        super().__init__()
        self.title("Sistema Automatizado de contrataciones")
        self.geometry("900x660")
        self.minsize(780, 580)

        self.proc: subprocess.Popen | None = None
        self.cola = queue.Queue()
        self._entradas = queue.Queue()
        self._en_git = False

        self._estilo_ttk()
        self._construir_interfaz()

        self.protocol("WM_DELETE_WINDOW", self._al_cerrar)

        self.var_fecha_inicio.set(fecha_por_defecto())
        self.var_fecha_fin.set(fecha_por_defecto())
        self._procesar_cola()

    # ------------------------------------------------------------------
    # Estilos
    # ------------------------------------------------------------------
    def _estilo_ttk(self) -> None:
        estilo = ttk.Style(self)
        estilo.theme_use("clam")

        self.configure(bg=COLOR_FONDO)

        estilo.configure(".", font=("Segoe UI", 10))
        estilo.configure("TFrame", background=COLOR_FONDO)
        estilo.configure("TLabel", background=COLOR_FONDO, foreground=COLOR_TEXTO)
        estilo.configure(
            "Header.TLabel",
            background=COLOR_VERDE_UIS,
            foreground=COLOR_FONDO,
            font=("Segoe UI Semibold", 17),
            padding=16,
        )
        estilo.configure(
            "Title.TLabel",
            background=COLOR_FONDO,
            foreground=COLOR_VERDE_OSCURO,
            font=("Segoe UI Semibold", 10),
        )
        estilo.configure(
            "TLabelframe",
            background=COLOR_FONDO,
            bordercolor=COLOR_BORDE,
            relief=tk.GROOVE,
        )
        estilo.configure(
            "TLabelframe.Label",
            background=COLOR_FONDO,
            foreground=COLOR_VERDE_OSCURO,
            font=("Segoe UI Semibold", 10),
        )
        estilo.configure(
            "TEntry",
            fieldbackground=COLOR_FONDO,
            foreground=COLOR_TEXTO,
            bordercolor=COLOR_BORDE,
            lightcolor=COLOR_VERDE_UIS,
            darkcolor=COLOR_BORDE,
            padding=6,
        )

    # ------------------------------------------------------------------
    # Interfaz
    # ------------------------------------------------------------------
    def _construir_interfaz(self) -> None:
        header = ttk.Frame(self, style="TFrame")
        header.pack(fill=tk.X)

        # --- Barra superior: configuración (izquierda) + título centrado + actualizar (derecha) ---
        barra_superior = ttk.Frame(header, style="TFrame", padding=(10, 6, 10, 6))
        barra_superior.pack(fill=tk.X)

        # Empaquetamos primero los dos botones a los extremos y el título al
        # centro, con expand para que ocupe el espacio restante sin deformarse.
        self.btn_git = _BotonRedondeado(
            barra_superior,
            text="↻",
            command=self._actualizar_codigo,
            width=44,
            height=36,
            color=COLOR_VERDE_OSCURO,
            color_hover=COLOR_VERDE_UIS,
        )
        self.btn_git.pack(side=tk.RIGHT)

        self.btn_configuracion = _BotonRedondeado(
            barra_superior,
            text="⚙",
            command=self._abrir_configuracion,
            width=44,
            height=36,
            color=COLOR_VERDE_OSCURO,
            color_hover=COLOR_VERDE_UIS,
        )
        self.btn_configuracion.pack(side=tk.LEFT)

        self.titulo = _TituloRedondeado(
            barra_superior,
            text="Sistema Automatizado de contrataciones",
            alto=46,
        )
        self.titulo.pack(side=tk.LEFT, expand=True, anchor="center")

        contenedor = ttk.Frame(self, style="TFrame", padding=16)
        contenedor.pack(fill=tk.BOTH, expand=True)

        # --- Rango de fechas ---
        marco_fechas = ttk.LabelFrame(
            contenedor,
            text="  Rango de fechas  ",
            padding=16,
        )
        marco_fechas.pack(fill=tk.X)

        grid = ttk.Frame(marco_fechas, style="TFrame")
        grid.pack(anchor=tk.W)

        ttk.Label(grid, text="Desde:").grid(row=0, column=0, sticky=tk.W, padx=(0, 6))
        self.var_fecha_inicio = tk.StringVar()
        ttk.Entry(grid, textvariable=self.var_fecha_inicio, width=12).grid(
            row=0, column=1, sticky=tk.W
        )

        ttk.Label(grid, text="Hasta:").grid(row=0, column=2, sticky=tk.W, padx=(20, 6))
        self.var_fecha_fin = tk.StringVar()
        ttk.Entry(grid, textvariable=self.var_fecha_fin, width=12).grid(
            row=0, column=3, sticky=tk.W
        )

        ttk.Label(
            grid,
            text="Formato: AAAA-MM-DD",
        ).grid(row=0, column=4, sticky=tk.W, padx=(10, 0))

        ttk.Label(
            marco_fechas,
            text="Si se dejan en blanco, se utilizará el día anterior a la ejecución.",
            foreground=COLOR_SECUNDARIO,
        ).pack(anchor=tk.W, pady=(10, 0))

        # --- Botonera ---
        barra = ttk.Frame(contenedor, style="TFrame", padding=(0, 16, 0, 8))
        barra.pack(fill=tk.X)

        self.btn_ejecutar = _BotonRedondeado(
            barra,
            text="Empezar",
            command=self._ejecutar,
            width=126,
            height=38,
        )
        self.btn_ejecutar.pack(side=tk.LEFT)

        self.btn_detener = _BotonRedondeado(
            barra,
            text="Detener",
            command=self._detener,
            width=108,
            height=38,
            color="#a33a32",
            color_hover="#862d27",
        )
        self.btn_detener.configure(state=tk.DISABLED)
        self.btn_detener.pack(side=tk.LEFT, padx=(8, 0))

        self.btn_continuar = _BotonRedondeado(
            barra,
            text="Continuar",
            command=self._continuar,
            width=112,
            height=38,
            color=COLOR_DORADO,
            color_hover="#b88920",
        )
        self.btn_continuar.configure(state=tk.DISABLED)
        self.btn_continuar.pack(side=tk.LEFT, padx=(8, 0))

        self.var_estado = tk.StringVar(value="")
        ttk.Label(
            barra,
            textvariable=self.var_estado,
            style="Title.TLabel",
        ).pack(side=tk.RIGHT)

        # --- Log en vivo ---
        marco_log = ttk.LabelFrame(
            contenedor,
            text="  Registro de ejecución  ",
            padding=8,
        )
        marco_log.pack(fill=tk.BOTH, expand=True, pady=(6, 0))

        self.txt_log = tk.Text(
            marco_log,
            wrap=tk.WORD,
            font=("Consolas", 9),
            background=COLOR_FONDO,
            foreground=COLOR_TEXTO,
            insertbackground=COLOR_TEXTO,
            relief=tk.FLAT,
            highlightthickness=1,
            highlightbackground=COLOR_BORDE,
            highlightcolor=COLOR_VERDE_UIS,
            padx=12,
            pady=10,
            state=tk.DISABLED,
        )
        scroll = ttk.Scrollbar(
            marco_log, orient=tk.VERTICAL, command=self.txt_log.yview
        )
        self.txt_log.configure(yscrollcommand=scroll.set)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.txt_log.pack(fill=tk.BOTH, expand=True)

        self.txt_log.tag_configure("error", foreground="#a33a32")
        self.txt_log.tag_configure("aviso", foreground="#9a7413")
        self.txt_log.tag_configure("exito", foreground=COLOR_VERDE_UIS)

        # Permite confirmar el captcha o cualquier pausa manual sin necesitar
        # una consola externa.
        self.bind_all("<Return>", lambda _event: self._continuar())

    # ------------------------------------------------------------------
    # Comandos
    # ------------------------------------------------------------------
    def _validar_fechas(self) -> bool:
        for var in (self.var_fecha_inicio, self.var_fecha_fin):
            valor = var.get().strip()
            if not valor:
                continue
            try:
                datetime.strptime(valor, FORMATO_FECHA)
            except ValueError:
                messagebox.showerror(
                    "Fecha inválida",
                    f"La fecha '{valor}' no es válida. Usa el formato AAAA-MM-DD,\n"
                    f"por ejemplo {fecha_por_defecto()}.",
                )
                return False
        if (
            self.var_fecha_inicio.get().strip()
            and self.var_fecha_fin.get().strip()
            and self.var_fecha_inicio.get().strip() > self.var_fecha_fin.get().strip()
        ):
            messagebox.showerror(
                "Rango inválido",
                "La fecha inicial no puede ser posterior a la fecha final.",
            )
            return False
        return True

    def _construir_argumentos(self) -> list:
        """Devuelve solo los flags de CLI (sin el script), p. ej. ['--fecha-inicio','2026-...']."""
        args = []
        inicio = self.var_fecha_inicio.get().strip()
        fin = self.var_fecha_fin.get().strip()
        if inicio:
            args += ["--fecha-inicio", inicio]
        if fin:
            args += ["--fecha-fin", fin]
        return args

    # ------------------------------------------------------------------
    # Configuración de rutas manuales
    # ------------------------------------------------------------------
    def _abrir_configuracion(self) -> None:
        """Despliega un menú desde el botón ⚙ para cambiar las rutas manuales."""
        menu = tk.Menu(self, tearoff=False)

        matriz_actual = ruta_matriz_manual()
        menu.add_command(
            label=f"Matriz manual: {matriz_actual.name}",
            command=self._seleccionar_matriz,
        )
        menu.add_command(
            label=f"Ordenadores: {ruta_ordenadores().name}",
            command=self._seleccionar_ordenadores,
        )
        menu.add_separator()
        menu.add_command(
            label="Restablecer rutas por defecto",
            command=self._restablecer_configuracion,
        )

        x = self.btn_configuracion.winfo_rootx()
        y = self.btn_configuracion.winfo_rooty() + self.btn_configuracion.winfo_height()
        try:
            menu.tk_popup(x, y)
        finally:
            menu.grab_release()

    def _seleccionar_matriz(self) -> None:
        ruta = filedialog.askopenfilename(
            title="Selecciona la matriz manual (Matriz Seguimiento Contractual UIS.xlsx)",
            initialdir=str(ruta_matriz_manual().parent),
            filetypes=[("Excel", "*.xlsx"), ("Todos los archivos", "*.*")],
        )
        if not ruta:
            return
        configurar_rutas(matriz_manual=ruta, ordenadores=str(ruta_ordenadores()))
        self._append_log(f"[CONFIG] Matriz manual cambiada a:\n  {ruta}\n")
        self.var_estado.set("Ruta de la matriz manual actualizada")

    def _seleccionar_ordenadores(self) -> None:
        ruta = filedialog.askopenfilename(
            title="Selecciona el archivo de ordenadores (Ordenadores_*.xlsx)",
            initialdir=str(ruta_ordenadores().parent),
            filetypes=[("Excel", "*.xlsx"), ("Todos los archivos", "*.*")],
        )
        if not ruta:
            return
        configurar_rutas(matriz_manual=str(ruta_matriz_manual()), ordenadores=ruta)
        self._append_log(f"[CONFIG] Ordenadores cambiado a:\n  {ruta}\n")
        self.var_estado.set("Ruta de ordenadores actualizada")

    def _restablecer_configuracion(self) -> None:
        restablecer_rutas()
        self._append_log(
            "[CONFIG] Rutas manuales restablecidas a los valores por defecto.\n"
        )
        self.var_estado.set("Rutas manuales por defecto")

    def _ejecutar(self) -> None:
        if self.proc is not None or getattr(self, "_en_proceso", False):
            return
        if not self._validar_fechas():
            return

        self.btn_ejecutar.configure(state=tk.DISABLED)
        self.var_estado.set("Ejecutando…")
        self._append_log("Ejecutando flujo de contratación…\n")
        self.btn_continuar.configure(state=tk.NORMAL)

        if FROZEN:
            # Ejecución embebida (sin pythonw ni main.py en disco): correr en un hilo.
            self._en_proceso = True
            self.btn_detener.configure(state=tk.DISABLED)
            threading.Thread(target=self._ejecutar_en_proceso, daemon=True).start()
        else:
            self._en_proceso = False
            self.btn_detener.configure(state=tk.NORMAL)
            self._ejecutar_subproceso()

    def _ejecutar_subproceso(self) -> None:
        cmd = [sys.executable, MAIN_PY] + self._construir_argumentos()
        env = os.environ.copy()
        env.setdefault("PYTHONIOENCODING", "utf-8")
        try:
            self.proc = subprocess.Popen(
                cmd,
                cwd=BASE_DIR,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                stdin=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                shell=False,
            )
        except OSError as exc:
            messagebox.showerror(
                "No se pudo iniciar", f"No se pudo lanzar el proceso:\n{exc}"
            )
            self.var_estado.set("Error al iniciar")
            self.btn_ejecutar.configure(state=tk.NORMAL)
            self.btn_detener.configure(state=tk.DISABLED)
            self.btn_continuar.configure(state=tk.DISABLED)
            return
        threading.Thread(
            target=self._leer_salida, args=(self.proc,), daemon=True
        ).start()

    def _configurar_loggers(self) -> None:
        """Redirige el logging de todos los módulos del flujo hacia la ventana y a un archivo."""
        import logging

        handler = _ColaLogHandler(self.cola, os.path.join(BASE_DIR, "logs"))
        nombres = [
            "main",
            "uisard",
            "conciliacion",
            "alfresco",
            "notificacion",
            "unificacion",
            "limpieza",
            "uisard_alfresco",
        ]
        for nombre in nombres:
            lg = logging.getLogger(nombre)
            lg.handlers = [handler]  # se reemplazan los handlers de StreamHandler
            lg.setLevel(logging.DEBUG)
            lg.propagate = False

    def _ejecutar_en_proceso(self) -> None:
        """Ejecuta main.main() dentro del mismo proceso (modo compilado)."""
        self._configurar_loggers()

        escritor = _ColaWriter(self.cola)
        viejo_out, viejo_err = sys.stdout, sys.stderr
        viejo_input = builtins.input
        sys.stdout = escritor
        sys.stderr = escritor
        sys.argv = ["main.py"] + self._construir_argumentos()

        def input_desde_gui(prompt=""):
            if prompt:
                self.cola.put(("linea", prompt))
            self._entradas.get()
            return ""

        builtins.input = input_desde_gui

        codigo = 0
        try:
            import main

            main.main()
        except SystemExit as exc:
            codigo = exc.code if isinstance(exc.code, int) else 1
        except KeyboardInterrupt:
            self.cola.put(("linea", "\n[APP] Proceso interrumpido por el usuario.\n"))
            codigo = 0
        except Exception as exc:
            import traceback

            self.cola.put(("linea", f"ERROR FATAL: {exc}\n"))
            self.cola.put(("linea", traceback.format_exc() + "\n"))
            codigo = 1
        finally:
            sys.stdout = viejo_out
            sys.stderr = viejo_err
            builtins.input = viejo_input

        self.cola.put(("fin", codigo))

    def _leer_salida(self, proc: subprocess.Popen) -> None:
        try:
            if proc.stdout:
                for linea in proc.stdout:
                    self.cola.put(("linea", linea))
        finally:
            self.cola.put(("fin", proc.wait()))

    def _procesar_cola(self) -> None:
        try:
            while True:
                tipo, valor = self.cola.get_nowait()
                if tipo == "linea":
                    self._append_log(valor)
                elif tipo == "fin":
                    self._finalizar(valor)
                elif tipo == "git_fin":
                    self._finalizar_git(valor)
        except queue.Empty:
            pass
        self.after(100, self._procesar_cola)

    def _append_log(self, texto: str) -> None:
        self.txt_log.configure(state=tk.NORMAL)
        if any(p in texto for p in ("ERROR", "error", "Error", "CRITICAL", "crítico")):
            etiqueta = "error"
        elif any(p in texto for p in ("WARN", "warn", "aviso", "Aviso")):
            etiqueta = "aviso"
        elif any(
            p in texto
            for p in (
                "finalizado",
                "Proceso completo",
                "Verificación finalizada",
                "éxito",
            )
        ):
            etiqueta = "exito"
        else:
            etiqueta = None
        self.txt_log.insert(tk.END, texto, etiqueta)
        self.txt_log.see(tk.END)
        self.txt_log.configure(state=tk.DISABLED)

    def _finalizar(self, codigo: int) -> None:
        self.proc = None
        self._en_proceso = False
        self.btn_ejecutar.configure(state=tk.NORMAL)
        self.btn_detener.configure(state=tk.DISABLED)
        self.btn_continuar.configure(state=tk.DISABLED)
        if codigo == 0:
            self.var_estado.set("Proceso finalizado correctamente")
            self._append_log("Proceso finalizado con éxito.\n")
        else:
            self.var_estado.set(f"Proceso terminado con código {codigo}")
            self._append_log(f"El proceso terminó con el código {codigo}.\n")

    def _detener(self) -> None:
        if self.proc is not None and self.proc.poll() is None:
            self.proc.terminate()
            self._append_log("Detenido por el usuario.\n")
            self.var_estado.set("Proceso detenido")

    def _continuar(self) -> None:
        """Envía Enter al flujo cuando espera captcha o una pausa manual."""
        if FROZEN:
            if self._en_proceso:
                self._entradas.put("")
                self._append_log("[GUI] Enter enviado al proceso.\n")
            return

        if self.proc is None or self.proc.poll() is not None or self.proc.stdin is None:
            return
        try:
            self.proc.stdin.write("\n")
            self.proc.stdin.flush()
            self._append_log("[GUI] Enter enviado al proceso.\n")
        except (OSError, ValueError):
            pass

    def _actualizar_codigo(self) -> None:
        if self.proc is not None or getattr(self, "_en_proceso", False) or self._en_git:
            return
        git = shutil.which("git")
        if not git:
            messagebox.showerror(
                "Git no encontrado",
                "No se encontró Git en el sistema. Instálalo (https://git-scm.com)\n"
                "o ejecuta 'git pull' desde la terminal.",
            )
            return
        self._en_git = True
        self.btn_ejecutar.configure(state=tk.DISABLED)
        self.btn_detener.configure(state=tk.DISABLED)
        self.btn_git.configure(state=tk.DISABLED)
        self.var_estado.set("Descargando cambios…")
        self._append_log("\n[GIT] Actualizando código desde el repositorio…\n")
        threading.Thread(target=self._ejecutar_git, args=(git,), daemon=True).start()

    def _ejecutar_git(self, git: str) -> None:
        def correr(args):
            proc = subprocess.Popen(
                [git] + args,
                cwd=BASE_DIR,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            for linea in proc.stdout:
                linea = linea.rstrip()
                if linea:
                    self.cola.put(("linea", linea + "\n"))
            return proc.wait()

        resultado = "error"
        if correr(["rev-parse", "--is-inside-work-tree"]) != 0:
            self.cola.put(("linea", "\n[GIT] La carpeta no es un repositorio Git.\n"))
            resultado = "no_repo"
        elif correr(["remote", "-v"]) != 0:
            self.cola.put(
                ("linea", "\n[GIT] El repositorio no tiene un remoto configurado.\n")
            )
            resultado = "no_remote"
        else:
            self.cola.put(("linea", "[GIT] Descargando referencias (git fetch)…\n"))
            correr(["fetch", "--all", "--prune"])
            self.cola.put(("linea", "[GIT] Integrando cambios (git pull --ff-only)…\n"))
            codigo = correr(["pull", "--ff-only"])
            if codigo == 0:
                self.cola.put(("linea", "[GIT] Código actualizado correctamente.\n"))
                resultado = "ok"
            else:
                self.cola.put(
                    (
                        "linea",
                        "\n[GIT] Hubo conflictos o cambios locales que no se pudieron integrar solos.\n",
                    )
                )
                resultado = "conflicto"
        self.cola.put(("git_fin", resultado))

    def _finalizar_git(self, resultado: str) -> None:
        self._en_git = False
        self.btn_ejecutar.configure(state=tk.NORMAL)
        self.btn_git.configure(state=tk.NORMAL)
        if resultado == "ok":
            self.var_estado.set("Código actualizado")
        elif resultado == "no_repo":
            self.var_estado.set("No es un repositorio Git")
        elif resultado == "no_remote":
            self.var_estado.set("No hay remoto configurado")
        elif resultado == "conflicto":
            self.var_estado.set("Conflicto: revisar cambios locales")
        else:
            self.var_estado.set("Error al actualizar")
        self._append_log("[GIT] Fin de la actualización.\n")

    def _al_cerrar(self) -> None:
        if self.proc is not None and self.proc.poll() is None:
            self.proc.terminate()
        self.destroy()


if __name__ == "__main__":
    app = AppContratacion()
    app.mainloop()
