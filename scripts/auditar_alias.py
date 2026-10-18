#!/usr/bin/env python3
"""
Auditoria de calidad de los alias.

Detecta alias donde el nombre del canal propio y el nombre real del canal EPG
apuntado NO se parecen. Un ratio bajo significa que el mapeo es dudoso y
posiblemente estas mostrando la programacion de otro canal.

Uso: python auditar_alias.py
"""

import difflib
import os
import re
import sys
import unicodedata

from lxml import etree

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(ROOT, ".cache")
CONFIG = os.path.join(ROOT, "config")

RUIDO = re.compile(r"(?:\b(?:full\s*hd|fhd|uhd|4k|8k|hd|sd|h265|hevc)\b)", re.IGNORECASE)


def sin_acentos(texto: str) -> str:
    d = unicodedata.normalize("NFD", texto)
    return "".join(c for c in d if unicodedata.category(c) != "Mn")


def clave(texto: str) -> str:
    if not texto:
        return ""
    t = sin_acentos(texto).lower().replace("+", " ").replace("plus", " ")
    t = re.sub(r"\.(es|com|tv|net|org|pt|fr|de|uk|it)$", "", t)
    t = RUIDO.sub(" ", t)
    return re.sub(r"[^a-z0-9]+", "", t)


def cargar_nombres() -> dict[str, str]:
    """id_canal -> mejor display-name de las fuentes."""
    nombres: dict[str, str] = {}
    for archivo in ("epg_ripper_ES1.xml", "guiatv.xml"):
        ruta = os.path.join(CACHE, archivo)
        if not os.path.exists(ruta):
            continue
        raiz = etree.parse(ruta).getroot()
        for canal in raiz.findall("channel"):
            cid = canal.get("id", "")
            if not cid or cid in nombres:
                continue
            dns = [(d.text or "").strip() for d in canal.findall("display-name")]
            dns = [d for d in dns if d]
            nombres[cid] = dns[0] if dns else cid
    return nombres


def main() -> int:
    # La consola de Windows usa cp1252: forzamos UTF-8 en la salida
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass

    nombres = cargar_nombres()
    print(f"Canales EPG indexados: {len(nombres)}\n")

    filas = []
    with open(os.path.join(CONFIG, "aliases.csv"), encoding="utf-8-sig") as fh:
        for linea in fh:
            linea = linea.strip().lstrip("\ufeff")
            if not linea or linea.startswith("#"):
                continue
            partes = re.split(r"[;,]", linea, maxsplit=1)
            if len(partes) != 2:
                continue
            izq, der = partes[0].strip(), partes[1].strip()
            if izq and der:
                filas.append((izq, der))

    dudosos = []
    for k_canal, destino in filas:
        if destino not in nombres:
            dudosos.append((k_canal, destino, nombres.get(destino, "(no existe)"), 0.0))
            continue
        real = nombres[destino]
        p = difflib.SequenceMatcher(None, k_canal, clave(real)).ratio()
        if p < 0.70:
            dudosos.append((k_canal, destino, real, p))

    print(f"Alias revisados: {len(filas)}")
    print(f"Marcados como dudosos: {len(dudosos)}\n")
    print(f"{'CLAVE CANAL':<24} {'DESTINO ALIAS':<34} {'NOMBRE REAL EPG':<28} RATIO")
    print("-" * 100)
    for k, d, real, p in sorted(dudosos, key=lambda x: x[3]):
        print(f"{k:<24} {d:<34} {real:<28} {p:.2f}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
