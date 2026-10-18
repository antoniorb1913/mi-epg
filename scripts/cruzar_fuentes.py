#!/usr/bin/env python3
"""
Cruza la lista de canales propios con los canales de cada fuente EPG y sugiere
el mejor candidato para los que se quedaron sin guia.

Muestra el id EXACTO de la fuente, listo para pegar en config/aliases.csv.

Uso:
    python cruzar_fuentes.py              # solo los que no tienen guia
    python cruzar_fuentes.py --todos      # revisa todos
    python cruzar_fuentes.py --min 0.80   # umbral de similitud
"""

import argparse
import csv
import difflib
import os
import re
import unicodedata

from lxml import etree

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(ROOT, ".cache")
OUTPUT = os.path.join(ROOT, "output")

RUIDO = re.compile(r"(?:\b(?:full\s*hd|fhd|uhd|4k|8k|hd|sd|h265|hevc)\b)", re.IGNORECASE)
EXTRA = re.compile(
    r"\b(?:es|spain|espana|castellano|latino|internacional|internat|int)\b", re.IGNORECASE
)


def sin_acentos(texto: str) -> str:
    d = unicodedata.normalize("NFD", texto)
    return "".join(c for c in d if unicodedata.category(c) != "Mn")


def clave(texto: str) -> str:
    if not texto:
        return ""
    t = sin_acentos(texto).lower().replace("+", " ").replace("plus", " ")
    t = re.sub(r"\.(es|com|tv|net|org|pt|fr|de|uk|it)$", "", t)
    t = RUIDO.sub(" ", t)
    t = EXTRA.sub(" ", t)
    return re.sub(r"[^a-z0-9]+", "", t)


def cargar_fuente(nombre_archivo: str) -> dict[str, str]:
    """Devuelve {clave: id_canal} de una fuente, indexando id y display-name."""
    ruta = os.path.join(CACHE, nombre_archivo)
    indice: dict[str, str] = {}
    if not os.path.exists(ruta):
        return indice
    raiz = etree.parse(ruta).getroot()
    for canal in raiz.findall("channel"):
        cid = canal.get("id", "")
        if not cid:
            continue
        for valor in [cid] + [(d.text or "").strip() for d in canal.findall("display-name")]:
            k = clave(valor)
            if k and k not in indice:
                indice[k] = cid
    return indice


def main() -> int:
    parser = argparse.ArgumentParser(description="Cruza canales con las fuentes")
    parser.add_argument("--todos", action="store_true", help="revisa todos, no solo los sin guia")
    parser.add_argument("--min", type=float, default=0.80, help="umbral de similitud")
    args = parser.parse_args()

    fuentes = {n: cargar_fuente(n) for n in ("epg_ripper_ES1.xml", "guiatv.xml")}
    for nombre, idx in fuentes.items():
        print(f"  {nombre:<24} {len(idx)} claves")
    print()

    # Universo combinado
    universo: dict[str, str] = {}
    origen: dict[str, str] = {}
    for nombre, idx in fuentes.items():
        for k, cid in idx.items():
            if k not in universo:
                universo[k] = cid
                origen[k] = nombre

    with open(os.path.join(OUTPUT, "mapeo.csv"), encoding="utf-8") as fh:
        filas = list(csv.DictReader(fh, delimiter=";"))

    objetivo = filas if args.todos else [f for f in filas if not f["epg_id"]]
    print(f"Canales a revisar: {len(objetivo)}")
    print("=" * 88)

    sugerencias = []
    for fila in objetivo:
        nombre = fila["nombre_proveedor"]
        k = clave(nombre)

        # 1. coincidencia exacta
        if k in universo:
            sugerencias.append((nombre, universo[k], 1.0, "exacto"))
            continue

        # 2. similitud
        cands = difflib.get_close_matches(k, list(universo), n=3, cutoff=args.min)
        if cands:
            mejor = max(cands, key=lambda c: difflib.SequenceMatcher(None, k, c).ratio())
            p = difflib.SequenceMatcher(None, k, mejor).ratio()
            sugerencias.append((nombre, universo[mejor], p, "similitud"))

    for nombre, cid, p, via in sorted(sugerencias, key=lambda x: -x[2]):
        print(f"  {nombre:<34} -> {cid:<38} [{via} {p:.2f}]")

    # Lineas listas para alias
    print()
    print("=" * 88)
    print("LINEAS PARA config/aliases.csv")
    print("=" * 88)
    for nombre, cid, p, via in sorted(sugerencias, key=lambda x: -x[2]):
        if p >= 0.90:
            print(f"{clave(nombre)};{cid}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
