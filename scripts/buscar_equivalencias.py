#!/usr/bin/env python3
"""
Busca equivalentes en las fuentes EPG para los canales que se quedaron sin guia.

Para cada canal sin guia muestra:
  - coincidencia exacta (misma clave normalizada)
  - o hasta 3 candidatos por similitud, con su puntuacion

Uso: python buscar_equivalencias.py
"""

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


def indice_fuentes() -> tuple[dict[str, str], dict[str, str]]:
    """Devuelve (por_clave_id, por_clave_nombre) -> id de canal."""
    por_clave_id: dict[str, str] = {}
    por_clave_nombre: dict[str, str] = {}

    for archivo in ("epg_ripper_ES1.xml", "guiatv.xml"):
        ruta = os.path.join(CACHE, archivo)
        if not os.path.exists(ruta):
            continue
        raiz = etree.parse(ruta).getroot()
        for canal in raiz.findall("channel"):
            cid = canal.get("id", "")
            if not cid:
                continue
            k = clave(cid)
            if k and k not in por_clave_id:
                por_clave_id[k] = cid
            for dn in canal.findall("display-name"):
                nombre = (dn.text or "").strip()
                kn = clave(nombre)
                if kn and kn not in por_clave_nombre:
                    por_clave_nombre[kn] = cid
    return por_clave_id, por_clave_nombre


def main() -> int:
    por_clave_id, por_clave_nombre = indice_fuentes()
    universo = dict(por_clave_nombre)
    universo.update({k: v for k, v in por_clave_id.items() if k not in universo})
    print(f"Canales indexados en las fuentes: {len(set(universo.values()))}")
    print(f"Claves unicas: {len(universo)}\n")

    ruta_csv = os.path.join(OUTPUT, "mapeo.csv")
    with open(ruta_csv, encoding="utf-8") as fh:
        filas = list(csv.DictReader(fh, delimiter=";"))

    sin_guia = [f["nombre_proveedor"] for f in filas if not f["epg_id"]]
    print(f"Canales sin guia a revisar: {len(sin_guia)}")
    print("=" * 78)

    exactos, parecidos, nada = [], [], []

    for nombre in sin_guia:
        k = clave(nombre)
        objetivo = por_clave_id.get(k) or por_clave_nombre.get(k)
        if objetivo:
            exactos.append((nombre, objetivo))
            print(f"  [EXACTO]   {nombre:<34} -> {objetivo}")
            continue

        candidatos = difflib.get_close_matches(k, list(universo), n=3, cutoff=0.72)
        if candidatos:
            marcas = [
                (universo[c], difflib.SequenceMatcher(None, k, c).ratio()) for c in candidatos
            ]
            marcas.sort(key=lambda x: -x[1])
            parecidos.append((nombre, marcas))
            texto = ", ".join(f"{cid} ({p:.2f})" for cid, p in marcas)
            print(f"  [PARECIDO] {nombre:<34} ~ {texto}")
        else:
            nada.append(nombre)
            print(f"  [NADA]     {nombre:<34} -- sin candidato")

    print()
    print("=" * 78)
    print(f"  Exactos    : {len(exactos)}")
    print(f"  Parecidos  : {len(parecidos)}")
    print(f"  Sin nada   : {len(nada)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
