# -*- coding: utf-8 -*-
"""Actualizador externo: descarga, valida y ejecuta el nuevo instalador."""

from __future__ import annotations

import argparse
import hashlib
import os
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path


def _log(message: str) -> None:
    path = Path(tempfile.gettempdir()) / "SistemaContrataciones-updater.log"
    with path.open("a", encoding="utf-8") as stream:
        stream.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {message}\n")


def _wait_for_process(pid: int) -> None:
    for _ in range(120):
        if sys.platform == "win32":
            import ctypes

            handle = ctypes.windll.kernel32.OpenProcess(0x00100000, False, pid)
            if not handle:
                return
            ctypes.windll.kernel32.CloseHandle(handle)
        else:
            try:
                os.kill(pid, 0)
            except (OSError, ProcessLookupError):
                return
        time.sleep(0.5)
    raise TimeoutError("La aplicación no se cerró dentro del tiempo esperado.")


def _download(url: str, target: Path) -> None:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "SistemaContrataciones-Updater"},
    )
    with urllib.request.urlopen(request, timeout=120) as response, target.open("wb") as stream:
        while True:
            block = response.read(1024 * 1024)
            if not block:
                break
            stream.write(block)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pid", type=int, required=True)
    parser.add_argument("--app", required=True)
    parser.add_argument("--url", required=True)
    parser.add_argument("--sha256", required=True)
    args = parser.parse_args()

    installer = Path(tempfile.gettempdir()) / "SistemaContrataciones-update.exe"
    try:
        _wait_for_process(args.pid)
        _log("Descargando instalador")
        _download(args.url, installer)
        actual = _sha256(installer)
        if actual.lower() != args.sha256.lower():
            raise RuntimeError("La verificación SHA-256 del instalador falló.")

        _log("Ejecutando instalador")
        subprocess.run(
            [
                str(installer),
                "/VERYSILENT",
                "/SUPPRESSMSGBOXES",
                "/NORESTART",
                "/CLOSEAPPLICATIONS",
            ],
            check=True,
        )
        subprocess.Popen([args.app], close_fds=True)
        return 0
    except Exception as exc:  # noqa: BLE001
        _log(f"Error: {exc}")
        return 1
    finally:
        try:
            installer.unlink(missing_ok=True)
        except OSError:
            pass


if __name__ == "__main__":
    sys.exit(main())
