# -*- coding: utf-8 -*-
"""Consulta GitHub Releases y prepara la actualización de la aplicación."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

from PyQt6.QtCore import QThread, pyqtSignal

from desktop import __version__
from desktop.paths import BASE_DIR

GITHUB_REPOSITORY = os.getenv(
    "CONTRATACIONES_GITHUB_REPOSITORY",
    "Magvride/automatizacion-sistema-contratacion",
)
API_URL = f"https://api.github.com/repos/{GITHUB_REPOSITORY}/releases/latest"
USER_AGENT = "SistemaContrataciones-Updater"


def _version_tuple(version: str) -> tuple[int, ...]:
    values = re.findall(r"\d+", version.lstrip("vV"))
    return tuple(int(value) for value in values[:4]) or (0,)


def _get_json(url: str) -> dict:
    request = urllib.request.Request(
        url,
        headers={"Accept": "application/vnd.github+json", "User-Agent": USER_AGENT},
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def _get_text(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=20) as response:
        return response.read().decode("utf-8")


def _checksum(checksums: str, filename: str) -> str | None:
    for line in checksums.splitlines():
        parts = line.strip().split()
        if len(parts) >= 2 and Path(parts[-1]).name == filename:
            return parts[0].lower()
    return None


def check_latest() -> dict:
    """Devuelve la información del último release instalable."""
    release = _get_json(API_URL)
    tag = str(release.get("tag_name", ""))
    latest_version = tag.lstrip("vV")
    if not latest_version:
        raise RuntimeError("El release no tiene una versión válida.")

    if _version_tuple(latest_version) <= _version_tuple(__version__):
        return {"available": False, "version": __version__}

    assets = release.get("assets", [])
    installer = next(
        (
            asset
            for asset in assets
            if str(asset.get("name", "")).lower().endswith(".exe")
            and "setup" in str(asset.get("name", "")).lower()
        ),
        None,
    )
    checksums_asset = next(
        (
            asset
            for asset in assets
            if str(asset.get("name", "")).lower() == "checksums.txt"
        ),
        None,
    )
    if not installer or not checksums_asset:
        raise RuntimeError(
            "El release no contiene un instalador y checksums.txt."
        )

    installer_name = str(installer["name"])
    checksums = _get_text(str(checksums_asset["browser_download_url"]))
    expected_sha256 = _checksum(checksums, installer_name)
    if not expected_sha256 or not re.fullmatch(r"[0-9a-f]{64}", expected_sha256):
        raise RuntimeError(f"No hay SHA-256 válido para {installer_name}.")

    return {
        "available": True,
        "version": latest_version,
        "installer_name": installer_name,
        "installer_url": str(installer["browser_download_url"]),
        "sha256": expected_sha256,
        "release_url": str(release.get("html_url", "")),
    }


class UpdateCheckWorker(QThread):
    """Ejecuta la consulta HTTP fuera del hilo de la interfaz."""

    resultado = pyqtSignal(object)

    def run(self) -> None:
        try:
            self.resultado.emit({"ok": True, "data": check_latest()})
        except (OSError, urllib.error.URLError, ValueError, RuntimeError) as exc:
            self.resultado.emit({"ok": False, "error": str(exc)})


def launch_update(update: dict) -> None:
    """Copia el updater a TEMP y lo inicia antes de cerrar la aplicación."""
    updater = Path(BASE_DIR) / "updater.exe"
    if not updater.is_file():
        raise FileNotFoundError("No se encontró updater.exe en la instalación.")

    temp_dir = Path(tempfile.mkdtemp(prefix="contrataciones-update-"))
    updater_copy = temp_dir / "updater.exe"
    shutil.copy2(updater, updater_copy)
    command = [
        str(updater_copy),
        "--pid",
        str(os.getpid()),
        "--app",
        str(Path(sys.executable).resolve()),
        "--url",
        update["installer_url"],
        "--sha256",
        update["sha256"],
    ]
    subprocess.Popen(command, cwd=temp_dir, close_fds=True)

