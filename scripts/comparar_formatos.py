#!/usr/bin/env python3
"""
Compara la estructura de dos XMLTV para encontrar por que uno funciona y otro no.

Compara:
  - declaracion XML y atributos de <tv>
  - estructura de <channel> (atributos y hijos)
  - estructura de <programme> (atributos y hijos)
  - orden de elementos
  - caracteres raros
"""

import io
import os
import re
import sys
import unicodedata
from collections import Counter
from xml.etree import ElementTree as ET

MIO = r"C:\Users\GIGABYTE-PC\Documents\mi-epg\output\mi-epg-compatible.xml"
REF = r"C:\Users\GIGABYTE-PC\Documents\mi-epg\.cache\guiatv.xml"


def primera_linea(ruta: str, n: int = 3) -> list[str]:
    with io.open(ruta, "r", encoding="utf-8", errors="replace") as fh:
        return [next(fh, "").rstrip("\n") for _ in range(n)]


def describir(ruta: str, etiqueta: str) -> None:
    print("=" * 74)
    print(f"  {etiqueta}: {os.path.basename(ruta)}")
    print("=" * 74)

    with io.open(ruta, "r", encoding="utf-8", errors="replace") as fh:
        cabecera = [next(fh, "").rstrip("\n") for _ in range(2)]
    print(f"  linea 1: {cabecera[0][:78]}")
    print(f"  linea 2: {cabecera[1][:78]}")

    raiz = ET.parse(ruta).getroot()
    print(f"  <tv> atributos: {raiz.attrib}")

    # Orden de los hijos de <tv>
    orden = []
    for hijo in raiz:
        if not orden or orden[-1][0] != hijo.tag:
            orden.append([hijo.tag, 0])
        orden[-1][1] += 1
    print(f"  orden de hijos: {[(t, n) for t, n in orden]}")

    canales = raiz.findall("channel")
    programas = raiz.findall("programme")

    # Estructura de canal
    if canales:
        c = canales[0]
        print(f"  canal[0] id={c.get('id')!r}")
        print(f"           atributos: {list(c.attrib.keys())}")
        print(f"           hijos: {[(h.tag) for h in c]}")

    # Estructura de programa
    if programas:
        p = programas[0]
        print(f"  programa[0] atributos: {list(p.attrib.keys())}")
        print(f"              channel={p.get('channel')!r}")
        print(f"              start={p.get('start')!r}")
        print(f"              stop={p.get('stop')!r}")
        print(f"              hijos: {[h.tag for h in p]}")

    # Hijos distintos que aparecen en programas
    etiquetas = Counter()
    for p in programas[:5000]:
        for h in p:
            etiquetas[h.tag] += 1
    print(f"  etiquetas dentro de <programme>: {dict(etiquetas)}")

    # Valores de start: cuantos tienen zona horaria
    sin_zona = 0
    formatos = Counter()
    for p in programas[:5000]:
        s = p.get("start", "")
        if re.fullmatch(r"\d{14}\s*[+-]\d{4}", s):
            formatos["14digitos +zona"] += 1
        elif re.fullmatch(r"\d{14}", s):
            formatos["14digitos sin zona"] += 1
            sin_zona += 1
        else:
            formatos["OTRO"] += 1
    print(f"  formato de start: {dict(formatos)}")

    # Caracteres no ASCII en ids de canal
    raros = [c.get("id", "") for c in canales if any(ord(ch) > 127 for ch in (c.get("id") or ""))]
    print(f"  ids con caracteres no ASCII: {len(raros)}  {raros[:5]}")
    print()


print()
print("COMPARACION DE FORMATO XMLTV")
print()
describir(MIO, "MIO")
describir(REF, "REFERENCIA (funciona)")
