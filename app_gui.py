# -*- coding: utf-8 -*-
"""Interfaz gráfica de escritorio (Tkinter) para ejecutar el flujo de contratación.

El cliente final solo elige el rango de fechas y pulsa "Empezar"; el resto del
flujo (Financiero UIS → matriz → CSV → UISARD → Alfresco) se ejecuta de forma
automática. Ocupa la biblioteca estándar `tkinter` (sin dependencias extra).
"""

import os
import queue
import subprocess
import sys
import threading
from datetime import date, datetime, timedelta

import tkinter as tk
from tkinter import messagebox, ttk

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MAIN_PY = os.path.join(BASE_DIR, "main.py")
RESULTADOS_DIR = os.path.join(BASE_DIR, "archivos", "resultados")

FORMATO_FECHA = "%Y-%m-%d"


def fecha_por_defecto() -> str:
    return (date.today() - timedelta(days=1)).strftime(FORMATO_FECHA)


class AppContratacion(tk.Tk):
    """Aplicación de escritorio: rango de fechas + empezar."""

    def __init__(self) -> None:
        super().__init__()
        self.title("Sistema de Contratación — Automatización")
        self.geometry("880x640")
        self.minsize(760, 560)

        self.proc: subprocess.Popen | None = None
        self.cola = queue.Queue()

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
        try:
            estilo.theme_use("clam")
        except tk.TclError:
            pass

        self.configure(bg="#f5f6fa")

        estilo.configure(".", font=("Segoe UI", 10))
        estilo.configure("TFrame", background="#f5f6fa")
        estilo.configure("TLabel", background="#f5f6fa", foreground="#1f2937")
        estilo.configure(
            "Header.TLabel", background="#1d4ed8", foreground="#ffffff",
            font=("Segoe UI Semibold", 15), padding=12,
        )
        estilo.configure(
            "Title.TLabel", background="#f5f6fa", foreground="#1f2937",
            font=("Segoe UI Semibold", 11),
        )
        estilo.configure("TButton", padding=(12, 6))
        estilo.configure(
            "Accent.TButton", background="#1d4ed8", foreground="#ffffff",
            font=("Segoe UI Semibold", 12),
        )
        estilo.map("Accent.TButton", background=[("active", "#2563eb")])
        estilo.configure(
            "Danger.TButton", background="#dc2626", foreground="#ffffff",
            font=("Segoe UI Semibold", 10),
        )
        estilo.map("Danger.TButton", background=[("active", "#ef4444")])
        estilo.configure("TEntry", fieldbackground="#ffffff")

    # ------------------------------------------------------------------
    # Interfaz
    # ------------------------------------------------------------------
    def _construir_interfaz(self) -> None:
        header = ttk.Frame(self, style="TFrame")
        header.pack(fill=tk.X)
        ttk.Label(
            header, text="Sistema de Contratación — Automatización",
            style="Header.TLabel", anchor="center",
        ).pack(fill=tk.X)

        contenedor = ttk.Frame(self, style="TFrame", padding=16)
        contenedor.pack(fill=tk.BOTH, expand=True)

        # --- Rango de fechas ---
        marco_fechas = ttk.LabelFrame(
            contenedor, text="  Rango de fechas  ", padding=14,
        )
        marco_fechas.pack(fill=tk.X)

        grid = ttk.Frame(marco_fechas, style="TFrame")
        grid.pack(anchor=tk.W)

        ttk.Label(grid, text="Desde:").grid(row=0, column=0, sticky=tk.W, padx=(0, 6))
        self.var_fecha_inicio = tk.StringVar()
        ttk.Entry(grid, textvariable=self.var_fecha_inicio, width=12).grid(
            row=0, column=1, sticky=tk.W)

        ttk.Label(grid, text="Hasta:").grid(row=0, column=2, sticky=tk.W, padx=(20, 6))
        self.var_fecha_fin = tk.StringVar()
        ttk.Entry(grid, textvariable=self.var_fecha_fin, width=12).grid(
            row=0, column=3, sticky=tk.W)

        ttk.Label(
            grid, text="Formato: AAAA-MM-DD",
        ).grid(row=0, column=4, sticky=tk.W, padx=(10, 0))

        ttk.Label(
            marco_fechas, text="Nota: si se dejan en blanco, se usa el día anterior a la ejecución.",
            foreground="#6b7280",
        ).pack(anchor=tk.W, pady=(10, 0))

        # --- Botonera ---
        barra = ttk.Frame(contenedor, style="TFrame", padding=(0, 12, 0, 6))
        barra.pack(fill=tk.X)

        self.btn_ejecutar = ttk.Button(
            barra, text="▶  Empezar", style="Accent.TButton",
            command=self._ejecutar, width=18,
        )
        self.btn_ejecutar.pack(side=tk.LEFT)

        self.btn_detener = ttk.Button(
            barra, text="⏹  Detener", style="Danger.TButton",
            command=self._detener, state=tk.DISABLED,
        )
        self.btn_detener.pack(side=tk.LEFT, padx=(8, 0))

        self.btn_abrir = ttk.Button(
            barra, text="Abrir resultados", command=self._abrir_resultados,
        )
        self.btn_abrir.pack(side=tk.LEFT, padx=(8, 0))

        self.var_estado = tk.StringVar(value="")
        ttk.Label(
            barra, textvariable=self.var_estado, style="Title.TLabel",
        ).pack(side=tk.RIGHT)

        # --- Log en vivo ---
        marco_log = ttk.LabelFrame(
            contenedor, text="  Registro de ejecución  ", padding=8,
        )
        marco_log.pack(fill=tk.BOTH, expand=True, pady=(6, 0))

        self.txt_log = tk.Text(
            marco_log, wrap=tk.WORD, font=("Consolas", 9),
            background="#111827", foreground="#e5e7eb",
            insertbackground="#e5e7eb", relief=tk.FLAT,
            state=tk.DISABLED,
        )
        scroll = ttk.Scrollbar(marco_log, orient=tk.VERTICAL, command=self.txt_log.yview)
        self.txt_log.configure(yscrollcommand=scroll.set)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.txt_log.pack(fill=tk.BOTH, expand=True)

        self.txt_log.tag_configure("error", foreground="#f87171")
        self.txt_log.tag_configure("aviso", foreground="#fbbf24")
        self.txt_log.tag_configure("exito", foreground="#4ade80")

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
        if (self.var_fecha_inicio.get().strip()
                and self.var_fecha_fin.get().strip()
                and self.var_fecha_inicio.get().strip() > self.var_fecha_fin.get().strip()):
            messagebox.showerror(
                "Rango inválido",
                "La fecha inicial no puede ser posterior a la fecha final.",
            )
            return False
        return True

    def _construir_comando(self) -> list:
        cmd = [sys.executable, MAIN_PY]
        inicio = self.var_fecha_inicio.get().strip()
        fin = self.var_fecha_fin.get().strip()
        if inicio:
            cmd += ["--fecha-inicio", inicio]
        if fin:
            cmd += ["--fecha-fin", fin]
        return cmd

    def _ejecutar(self) -> None:
        if self.proc is not None:
            return
        if not self._validar_fechas():
            return

        cmd = self._construir_comando()
        env = os.environ.copy()
        env.setdefault("PYTHONIOENCODING", "utf-8")

        try:
            self.proc = subprocess.Popen(
                cmd,
                cwd=BASE_DIR,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                shell=False,
            )
        except OSError as exc:
            messagebox.showerror("No se pudo iniciar", f"No se pudo lanzar el proceso:\n{exc}")
            self.var_estado.set("Error al iniciar")
            return

        self.btn_ejecutar.configure(state=tk.DISABLED)
        self.btn_detener.configure(state=tk.NORMAL)
        self.var_estado.set("Ejecutando…")
        self._append_log("Ejecutando flujo de contratación…\n")

        threading.Thread(target=self._leer_salida, args=(self.proc,), daemon=True).start()

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
        except queue.Empty:
            pass
        self.after(100, self._procesar_cola)

    def _append_log(self, texto: str) -> None:
        self.txt_log.configure(state=tk.NORMAL)
        if any(p in texto for p in ("ERROR", "error", "Error", "CRITICAL", "crítico")):
            etiqueta = "error"
        elif any(p in texto for p in ("WARN", "warn", "aviso", "Aviso")):
            etiqueta = "aviso"
        elif any(p in texto for p in ("finalizado", "Proceso completo", "Verificación finalizada", "éxito")):
            etiqueta = "exito"
        else:
            etiqueta = None
        self.txt_log.insert(tk.END, texto, etiqueta)
        self.txt_log.see(tk.END)
        self.txt_log.configure(state=tk.DISABLED)

    def _finalizar(self, codigo: int) -> None:
        self.proc = None
        self.btn_ejecutar.configure(state=tk.NORMAL)
        self.btn_detener.configure(state=tk.DISABLED)
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

    def _abrir_resultados(self) -> None:
        os.makedirs(RESULTADOS_DIR, exist_ok=True)
        try:
            os.startfile(RESULTADOS_DIR)
        except OSError as exc:
            messagebox.showerror("No se pudo abrir", f"No se pudo abrir la carpeta:\n{exc}")

    def _al_cerrar(self) -> None:
        if self.proc is not None and self.proc.poll() is None:
            self.proc.terminate()
        self.destroy()


if __name__ == "__main__":
    app = AppContratacion()
    app.mainloop()
