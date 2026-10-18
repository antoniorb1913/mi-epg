#!/usr/bin/env python3
"""
Analiza un archivo M3U/M3U8 y muestra como identifica los canales.

Ayuda a decidir como emparejar la EPG con la lista del proveedor.

Uso:
    python analizar_m3u.py              # busca .m3u en Downloads y Documents
    python analizar_m3u.py lista.m3u    # archivo concreto
    python analizar_m3u.py lista.m3u --csv   # exporta tabla a CSV

NO imprime URLs de streaming ni credenciales: solo metadatos de canal.
"""

import argparse
import csv
import glob
import os
import re
import sys
from collections import Counter

# Atributos que nos interesan de la linea #EXTINF
ATRIBUTOS = ("tvg-id", "tvg-name", "tvg-logo", "group-title", "tvg-chno")


def buscar_m3u() -> list[str]:
    """Busca archivos .m3u/.m3u8 en las carpetas habituales."""
    patrones = []
    for carpeta in (
        os.path.join(os.path.expanduser("~"), "Downloads"),
        os.path.join(os.path.expanduser("~"), "Documents"),
        os.path.join(os.path.expanduser("~"), "Desktop"),
    ):
        patrones += glob.glob(os.path.join(carpeta, "**", "*.m3u"), recursive=True)
        patrones += glob.glob(os.path.join(carpeta, "**", "*.m3u8"), recursive=True)
    return sorted(set(patrones))


def parsear(linea: str) -> dict:
    """Extrae los atributos y el nombre visible de una linea #EXTINF."""
    datos = {a: "" for a in ATRIBUTOS}
    for atributo in ATRIBUTOS:
        m = re.search(rf'{atributo}="([^"]*)"', linea)
        if m:
            datos[atributo] = m.group(1).strip()
    # El nombre visible va despues de la ultima coma
    m = re.match(r"^#EXTINF:[^,]*,(.*)$", linea.strip())
    datos["nombre"] = m.group(1).strip() if m else ""
    return datos


def analizar(ruta: str) -> tuple[list[dict], dict]:
    """Devuelve (canales, metricas)."""
    canales = []
    with open(ruta, encoding="utf-8", errors="replace") as fh:
        for linea in fh:
            if linea.startswith("#EXTINF"):
                canales.append(parsear(linea))

    total = len(canales)
    con_id = sum(1 for c in canales if c["tvg-id"])
    con_nombre = sum(1 for c in canales if c["tvg-name"])
    con_logo = sum(1 for c in canales if c["tvg-logo"])
    grupos = Counter(c["group-title"] for c in canales if c["group-title"])

    metricas = {
        "total": total,
        "con_tvg_id": con_id,
        "con_tvg_name": con_nombre,
        "con_logo": con_logo,
        "grupos": grupos,
    }
    return canales, metricas


def main() -> int:
    parser = argparse.ArgumentParser(description="Analiza un M3U")
    parser.add_argument("archivo", nargs="?", help="ruta del .m3u")
    parser.add_argument("--csv", action="store_true", help="exporta tabla a CSV")
    args = parser.parse_args()

    ruta = args.archivo
    if not ruta:
        encontrados = buscar_m3u()
        if not encontrados:
            print("No se encontro ningun .m3u en Downloads, Documents ni Desktop.")
            print("Descarga la lista o pasa la ruta como argumento.")
            return 1
        ruta = encontrados[0]
        print(f"Usando: {ruta}\n")

    if not os.path.exists(ruta):
        print(f"No existe: {ruta}")
        return 1

    canales, m = analizar(ruta)

    print("=" * 64)
    print(f"  ARCHIVO : {os.path.basename(ruta)}")
    print(f"  CANALES : {m['total']}")
    print("=" * 64)
    print(f"  con tvg-id    : {m['con_tvg_id']:>4}  ({m['con_tvg_id']/max(m['total'],1)*100:.0f} %)")
    print(f"  con tvg-name  : {m['con_tvg_name']:>4}  ({m['con_tvg_name']/max(m['total'],1)*100:.0f} %)")
    print(f"  con tvg-logo  : {m['con_logo']:>4}  ({m['con_logo']/max(m['total'],1)*100:.0f} %)")
    print(f"  grupos        : {len(m['grupos'])}")

    # Veredicto sobre los ids
    print()
    if m["con_tvg_id"] == 0:
        print("  >>> NO HAY tvg-id. El reproductor no puede emparejar la EPG")
        print("      por id: habra que generar una M3U con los ids correctos.")
    else:
        ejemplos = [c["tvg-id"] for c in canales if c["tvg-id"]][:12]
        print("  >>> Ejemplos de tvg-id del proveedor:")
        for e in ejemplos:
            print(f"        {e}")

    # Muestra de canales
    print()
    print("  Primeros 15 canales:")
    print(f"    {'NOMBRE':<28} {'tvg-id':<24} {'grupo':<18}")
    print(f"    {'-'*28} {'-'*24} {'-'*18}")
    for c in canales[:15]:
        nombre = (c["nombre"] or c["tvg-name"])[:27]
        tid = (c["tvg-id"] or "(vacio)")[:23]
        grupo = (c["group-title"] or "-")[:17]
        print(f"    {nombre:<28} {tid:<24} {grupo:<18}")

    if args.csv:
        salida = os.path.splitext(ruta)[0] + "_canales.csv"
        with open(salida, "w", encoding="utf-8", newline="") as fh:
            w = csv.writer(fh, delimiter=";")
            w.writerow(["nombre", "tvg_id", "tvg_name", "group_title"])
            for c in canales:
                w.writerow([c["nombre"], c["tvg-id"], c["tvg-name"], c["group-title"]])
        print(f"\n  Tabla exportada: {salida}")

    # Grupos mas usados
    if m["grupos"]:
        print()
        print("  Grupos con mas canales:")
        for grupo, n in m["grupos"].most_common(12):
            print(f"    {n:>4}  {grupo}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
