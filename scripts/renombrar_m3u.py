#!/usr/bin/env python3
"""
Renombra y repone los logos de una lista M3U usando la EPG como referencia.

El problema: tu proveedor tiene canales con el nombre y el logo equivocados
(por ejemplo "M+ Series" que en realidad emite TCM).

La solucion: este script lee tu M3U, mira que canal es cada uno segun
config/correcciones.csv y config/aliases.csv, y escribe una M3U NUEVA con:
  - el nombre correcto
  - el logo correcto (sacado de la fuente EPG)
  - el tvg-id correcto

Las URLs de streaming NO se tocan: se copian tal cual.

Uso:
    python renombrar_m3u.py lista.m3u
    python renombrar_m3u.py lista.m3u --salida nueva.m3u
    python renombrar_m3u.py lista.m3u --csv informe.csv   # informe de cambios
"""

import argparse
import csv
import os
import re
import sys
import unicodedata

from lxml import etree

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(ROOT, ".cache")
CONFIG = os.path.join(ROOT, "config")
OUTPUT = os.path.join(ROOT, "output")

RUIDO = re.compile(r"(?:\b(?:full\s*hd|fhd|uhd|4k|8k|hd|sd|h265|hevc)\b)", re.IGNORECASE)
RUIDO_PEGADO = re.compile(
    r"(?<=[a-z0-9])(?:full[-\s]?hd|fhd|uhd|4k|8k|hd|sd)(?=$|[^a-z0-9])", re.IGNORECASE
)
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
    t = RUIDO_PEGADO.sub(" ", t)
    t = EXTRA.sub(" ", t)
    return re.sub(r"[^a-z0-9]+", "", t)


def leer_pares(nombre_archivo: str) -> dict[str, str]:
    """Lee un CSV 'clave;valor' de config/."""
    ruta = os.path.join(CONFIG, nombre_archivo)
    datos: dict[str, str] = {}
    if not os.path.exists(ruta):
        return datos
    with open(ruta, encoding="utf-8-sig") as fh:
        for linea in fh:
            linea = linea.strip().lstrip("\ufeff")
            if not linea or linea.startswith("#"):
                continue
            partes = re.split(r"[;,]", linea, maxsplit=1)
            if len(partes) != 2:
                continue
            izq, der = partes[0].strip(), partes[1].strip()
            if izq:
                datos[clave(izq)] = der
    return datos


def cargar_epg() -> dict[str, dict]:
    """id_canal -> {nombre, icono} de las fuentes EPG."""
    info: dict[str, dict] = {}
    for archivo in ("epg_ripper_ES1.xml", "guiatv.xml"):
        ruta = os.path.join(CACHE, archivo)
        if not os.path.exists(ruta):
            continue
        raiz = etree.parse(ruta).getroot()
        for canal in raiz.findall("channel"):
            cid = canal.get("id", "")
            if not cid or cid in info:
                continue
            dns = [(d.text or "").strip() for d in canal.findall("display-name")]
            dns = [d for d in dns if d]
            icono = canal.find("icon")
            info[cid] = {
                "nombre": dns[0] if dns else cid,
                "icono": icono.get("src", "") if icono is not None else "",
            }
    return info


def parsear_extinf(linea: str) -> dict:
    """Extrae atributos y nombre visible de una linea #EXTINF."""
    datos = {}
    for atributo in ("tvg-id", "tvg-name", "tvg-logo", "group-title"):
        m = re.search(rf'{atributo}="([^"]*)"', linea)
        datos[atributo] = m.group(1) if m else ""
    m = re.match(r"^#EXTINF:[^,]*,(.*)$", linea.strip())
    datos["nombre"] = m.group(1).strip() if m else ""
    return datos


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass

    parser = argparse.ArgumentParser(description="Renombra una M3U con datos de la EPG")
    parser.add_argument("archivo", help="ruta del .m3u original")
    parser.add_argument("--salida", default=None, help="ruta del .m3u de salida")
    parser.add_argument("--csv", default=None, help="informe de cambios en CSV")
    parser.add_argument(
        "--canales",
        default=None,
        help="escribe tambien la lista de canales para config/canales.txt",
    )
    args = parser.parse_args()

    if not os.path.exists(args.archivo):
        print(f"No existe: {args.archivo}")
        return 1

    salida = args.salida or os.path.splitext(args.archivo)[0] + "_corregida.m3u"

    correcciones = leer_pares("correcciones.csv")
    aliases = leer_pares("aliases.csv")
    epg = cargar_epg()

    print(f"EPG cargada      : {len(epg)} canales")
    print(f"Alias            : {len(aliases)}")
    print(f"Correcciones     : {len(correcciones)}")
    print()

    cambios = []
    total = 0
    renombrados = 0
    con_logo_nuevo = 0
    nuevos_canales: list[tuple[str, str]] = []

    with open(args.archivo, encoding="utf-8", errors="replace") as entrada, open(
        salida, "w", encoding="utf-8", newline="\n"
    ) as salible:
        for linea in entrada:
            if not linea.startswith("#EXTINF"):
                salible.write(linea)
                continue

            total += 1
            datos = parsear_extinf(linea)
            nombre_original = datos["nombre"]
            grupo = datos["group-title"] or "OTROS"

            # Que clave usamos: el nombre visible
            k = clave(nombre_original)

            # Buscar canal real: correcciones primero, luego alias
            real_id = correcciones.get(k) or aliases.get(k)
            if not real_id and k in correcciones:
                real_id = None  # descartado a proposito

            info = epg.get(real_id) if real_id else None

            if not info:
                salible.write(linea)
                nuevos_canales.append((grupo, nombre_original))
                continue

            nombre_nuevo = info["nombre"]
            logo_nuevo = info["icono"] or datos["tvg-logo"]

            # Reconstruimos la linea con los valores corregidos.
            # El tvg-id se pone igual que el nombre, para que empareje con
            # output/mi-epg-compatible.xml (donde el id es el nombre visible).
            nueva = linea
            if 'tvg-id="' in nueva:
                nueva = re.sub(r'tvg-id="[^"]*"', f'tvg-id="{nombre_nuevo}"', nueva, count=1)
            nueva = re.sub(r'tvg-name="[^"]*"', f'tvg-name="{nombre_nuevo}"', nueva, count=1)
            if logo_nuevo:
                if 'tvg-logo="' in nueva:
                    nueva = re.sub(r'tvg-logo="[^"]*"', f'tvg-logo="{logo_nuevo}"', nueva, count=1)
                else:
                    nueva = nueva.replace("#EXTINF:-1", f'#EXTINF:-1 tvg-logo="{logo_nuevo}"', 1)
            # El nombre visible va tras la ultima coma
            nueva = re.sub(r"^(#EXTINF:[^,]*),.*$", rf"\g<1>,{nombre_nuevo}", nueva.strip()) + "\n"

            if nueva != linea:
                if nombre_nuevo != nombre_original:
                    renombrados += 1
                if logo_nuevo and logo_nuevo != datos["tvg-logo"]:
                    con_logo_nuevo += 1
                cambios.append(
                    {
                        "nombre_original": nombre_original,
                        "nombre_nuevo": nombre_nuevo,
                        "epg_id": real_id,
                        "logo": logo_nuevo,
                    }
                )

            salible.write(nueva)
            nuevos_canales.append((grupo, nombre_nuevo))

    print("=" * 60)
    print(f"  Canales procesados : {total}")
    print(f"  Renombrados        : {renombrados}")
    print(f"  Logo actualizado   : {con_logo_nuevo}")
    print("=" * 60)
    print()
    print(f"  Guardada: {salida}")

    if args.csv and cambios:
        with open(args.csv, "w", encoding="utf-8", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=["nombre_original", "nombre_nuevo", "epg_id", "logo"], delimiter=";")
            w.writeheader()
            w.writerows(cambios)
        print(f"  Informe:  {args.csv}")

    # Lista de canales con los nombres NUEVOS, para regenerar la EPG
    if args.canales:
        vistos = set()
        with open(args.canales, "w", encoding="utf-8", newline="\n") as fh:
            fh.write("# Lista generada por renombrar_m3u.py\n")
            fh.write("# Formato: grupo | nombre\n\n")
            for grupo, nombre in nuevos_canales:
                if nombre in vistos:
                    continue
                vistos.add(nombre)
                fh.write(f"{grupo} | {nombre}\n")
        print(f"  Canales:  {args.canales}  ({len(vistos)} unicos)")
        print()
        print("  Siguiente paso: copia ese archivo sobre config/canales.txt y")
        print("  ejecuta build_epg.py para que la guia use los nombres nuevos.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
