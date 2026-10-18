#!/usr/bin/env python3
"""
Genera una VARIANTE del EPG para diagnosticar problemas de emparejamiento.

Produce tres versiones del mismo XMLTV cambiando solo el <channel id>:

  nombre  -> id = nombre del canal tal cual (ej: "LA 1 HD")
             Util si el reproductor empareja por tvg-name o por nombre visible.

  slug    -> id = nombre en minusculas sin espacios (ej: "la1hd")
             Util si el proveedor usa ids tipo slug.

  numeros -> id = numero secuencial (1, 2, 3...)
             Sirve para comprobar que el XMLTV se parsea correctamente, aunque
             no emparejara con nada.

Uso:
    python variantes.py                 # genera las tres
    python variantes.py --solo nombre
"""

import argparse
import gzip
import os
import re
import unicodedata
from xml.etree import ElementTree as ET

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT = os.path.join(ROOT, "output")
ORIGEN = os.path.join(OUTPUT, "mi-epg.xml")
DIAG = os.path.join(OUTPUT, "diagnostico")


def sin_acentos(texto: str) -> str:
    d = unicodedata.normalize("NFD", texto)
    return "".join(c for c in d if unicodedata.category(c) != "Mn")


def slug(texto: str) -> str:
    """'LA 1 HD' -> 'la1hd'."""
    t = sin_acentos(texto).lower()
    return re.sub(r"[^a-z0-9]+", "", t)


def main() -> int:
    parser = argparse.ArgumentParser(description="Variantes de diagnostico")
    parser.add_argument("--solo", choices=["nombre", "slug", "numeros"], default=None)
    args = parser.parse_args()

    os.makedirs(DIAG, exist_ok=True)

    arbol = ET.parse(ORIGEN)
    raiz = arbol.getroot()

    # Mapa id original -> nombres canonicos
    canales = [c for c in raiz if c.tag == "channel"]
    originales = {}
    for canal in canales:
        cid = canal.get("id", "")
        nombres = [d.text.strip() for d in canal.findall("display-name") if d.text]
        originales[cid] = (canal, nombres)

    def escribir(modo: str, nuevo_id_fn) -> str:
        """Reescribe ids de canal y programas segun la funcion dada."""
        copia = ET.ElementTree(ET.fromstring(ET.tostring(raiz)))
        r = copia.getroot()

        mapa = {}
        for canal in list(r):
            if canal.tag != "channel":
                continue
            viejo = canal.get("id", "")
            nuevo = nuevo_id_fn(viejo, originales.get(viejo, (canal, []))[1])
            mapa[viejo] = nuevo
            canal.set("id", nuevo)

        for prog in r:
            if prog.tag == "programme":
                viejo = prog.get("channel", "")
                if viejo in mapa:
                    prog.set("channel", mapa[viejo])

        destino = os.path.join(DIAG, f"mi-epg-{modo}.xml")
        copia.write(destino, encoding="UTF-8", xml_declaration=True)
        with open(destino, "rb") as origen, gzip.open(destino + ".gz", "wb", compresslevel=9) as salida:
            salida.write(origen.read())
        return destino

    # --- modo nombre: id = primer display-name ---
    def por_nombre(viejo, nombres):
        return nombres[0] if nombres else viejo

    # --- modo slug: id = nombre sin espacios ---
    def por_slug(viejo, nombres):
        return slug(nombres[0]) if nombres else slug(viejo)

    # --- modo numeros ---
    contador = {"n": 0}

    def por_numeros(viejo, nombres):
        contador["n"] += 1
        return str(contador["n"])

    modos = {"nombre": por_nombre, "slug": por_slug, "numeros": por_numeros}
    if args.solo:
        modos = {args.solo: modos[args.solo]}

    for modo, funcion in modos.items():
        ruta = escribir(modo, funcion)
        tam = os.path.getsize(ruta) / (1024 * 1024)
        print(f"  {modo:<8} -> {os.path.basename(ruta)}  ({tam:.2f} MB)")
        if modo == "nombre":
            muestra = [v[1][0] for v in list(originales.values())[:5] if v[1]]
            print(f"           ids de ejemplo: {', '.join(muestra)}")
        elif modo == "slug":
            muestra = [slug(v[1][0]) for v in list(originales.values())[:5] if v[1]]
            print(f"           ids de ejemplo: {', '.join(muestra)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
