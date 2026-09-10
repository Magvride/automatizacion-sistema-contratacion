# -*- coding: utf-8 -*-
"""Genera ``icon.ico`` (256x256) sin dependencias externas.

Dibuja el logotipo de la aplicación (cuadrado redondeado verde con una flecha
de descarga) y lo serializa en formato ICO con un DIB de 32 bits.
"""

import os
import struct

N = 256
SS = 3  # supermuestreo
MARGEN = 0
RADIO = 58

BG = (14, 65, 61)       # #0E413D
BLANCO = (255, 255, 255)
MENTA = (95, 217, 199)  # #5FD9C7


def _rect_redondeado(x, y, x0, y0, x1, y1, r):
    if x < x0 or x > x1 or y < y0 or y > y1:
        return False
    cx = min(max(x, x0 + r), x1 - r)
    cy = min(max(y, y0 + r), y1 - r)
    return (x - cx) ** 2 + (y - cy) ** 2 <= r * r


def _rect(x, y, x0, y0, x1, y1):
    return x0 <= x <= x1 and y0 <= y <= y1


def _triangulo(x, y, p1, p2, p3):
    def signo(a, b, c):
        return (a[0] - c[0]) * (b[1] - c[1]) - (b[0] - c[0]) * (a[1] - c[1])

    d1 = signo((x, y), p1, p2)
    d2 = signo((x, y), p2, p3)
    d3 = signo((x, y), p3, p1)
    hay_neg = (d1 < 0) or (d2 < 0) or (d3 < 0)
    hay_pos = (d1 > 0) or (d2 > 0) or (d3 > 0)
    return not (hay_neg and hay_pos)


def _color_pixel(x, y):
    """Devuelve (r, g, b, a) en el rango [0, 255] para un punto."""
    # Fondo redondeado
    if _rect_redondeado(x, y, MARGEN, MARGEN, N - 1 - MARGEN, N - 1 - MARGEN, RADIO):
        # Flecha de descarga (blanca)
        if _rect(x, y, 112, 62, 144, 150):
            return (*BLANCO, 255)
        if _triangulo(x, y, (74, 146), (182, 146), (128, 202)):
            return (*BLANCO, 255)
        # Línea base menta
        if _rect_redondeado(x, y, 70, 214, 186, 226, 6):
            return (*MENTA, 255)
        return (*BG, 255)
    return (0, 0, 0, 0)


def _promediar(x0, y0):
    sr = sg = sb = sa = 0.0
    for dy in range(SS):
        for dx in range(SS):
            x = x0 + (dx + 0.5) / SS
            y = y0 + (dy + 0.5) / SS
            r, g, b, a = _color_pixel(x, y)
            alfa = a / 255.0
            sr += r * alfa
            sg += g * alfa
            sb += b * alfa
            sa += alfa
    n = SS * SS
    if sa == 0:
        return (0, 0, 0, 0)
    return (
        int(round(sr / sa)),
        int(round(sg / sa)),
        int(round(sb / sa)),
        int(round(sa / n * 255)),
    )


def _bytes_dib():
    filas = []
    for y in range(N - 1, -1, -1):  # BMP es bottom-up
        fila = bytearray()
        for x in range(N):
            r, g, b, a = _promediar(x, y)
            fila += bytes((b, g, r, a))  # BGRA
        filas.append(bytes(fila))
    pixeles = b"".join(filas)
    mascara = b"\x00" * (N * N // 8)
    return pixeles + mascara


def generar(ruta):
    dib = _bytes_dib()
    cabecera_dib = struct.pack(
        "<IiiHHIIiiII",
        40,          # biSize
        N,           # biWidth
        N * 2,       # biHeight (doble por la máscara AND)
        1,           # biPlanes
        32,          # biBitCount
        0,           # biCompression
        len(dib),    # biSizeImage
        0, 0, 0, 0,
    )
    imagen = cabecera_dib + dib
    cabecera_ico = struct.pack("<HHH", 0, 1, 1)
    entrada = struct.pack(
        "<BBBBHHII",
        0, 0, 0, 0, 1, 32, len(imagen), 6 + 16,
    )
    with open(ruta, "wb") as fh:
        fh.write(cabecera_ico + entrada + imagen)


if __name__ == "__main__":
    destino = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icon.ico")
    generar(destino)
    print("Icono generado:", destino, os.path.getsize(destino), "bytes")
