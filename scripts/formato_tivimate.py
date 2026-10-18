#!/usr/bin/env python3
"""
Convierte el XMLTV al formato que usa TiviMate y SFVIP-Player.

Diferencias con el formato estandar XMLTV:

  Estandar : <channel id="La.1.es">  +  <display-name>La 1</display-name>
  Este     : <channel id="LA 1 HD">  +  <display-name>LA 1 HD</display-name>
                                         <display-name>LA 1 SD</display-name>
                                         <display-name>LA 1 FHD</display-name>
                                         <display-name>La 1</display-name>
                                         <display-name>La.1.es</display-name>

El id del canal pasa a ser el nombre visible, y se anaden como display-name
todas las variantes (con y sin calidad, con el id XMLTV original...), para
maximizar las posibilidades de que el reproductor encuentre la coincidencia.

Uso:
    python formato_tivimate.py
    python formato_tivimate.py --entrada output/mi-epg.xml --salida output/mi-epg-tivimate.xml
"""

import argparse
import gzip
import os
import re
import unicodedata
from xml.etree import ElementTree as ET

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT = os.path.join(ROOT, "output")


def sin_acentos(texto: str) -> str:
    d = unicodedata.normalize("NFD", texto)
    return "".join(c for c in d if unicodedata.category(c) != "Mn")


CALIDADES = ["", " SD", " HD", " FHD", " FULL HD", " UHD", " 4K", " 720", " 1080"]


def variantes_de_nombre(nombre: str, id_xmltv: str) -> list[str]:
    """
    Genera todas las formas plausibles del nombre de un canal.

    'LA 1 HD' -> LA 1 HD, LA 1, LA 1 SD, LA 1 FHD, LA 1 FULL HD,
                LA 1 UHD, LA 1 4K, La 1, La 1 HD, La.1.es ...
    """
    base = re.sub(r"\s+(SD|HD|FHD|UHD|4K|FULL HD|720|1080)$", "", nombre, flags=re.I).strip()
    if not base:
        base = nombre

    salida = []
    vistos = set()

    def anadir(texto: str) -> None:
        t = texto.strip()
        if t and t.lower() not in vistos:
            vistos.add(t.lower())
            salida.append(t)

    # Nombre tal cual, luego con cada sufijo de calidad
    anadir(nombre)
    for cal in CALIDADES:
        anadir(base + cal)

    # Formas con otra capitalizacion: 'STAR Channel' -> 'Star Channel', 'Star Channel HD'...
    anadir(base.title())
    for cal in CALIDADES:
        anadir(base.title() + cal)

    # El id XMLTV original, util si el reproductor empareja por el
    anadir(id_xmltv)
    anadir(sin_acentos(id_xmltv))

    return salida


def convertir(entrada: str, salida: str) -> tuple[int, int]:
    """Reescribe el XMLTV con ids de canal basados en el nombre visible."""
    arbol = ET.parse(entrada)
    raiz = arbol.getroot()

    canales = [c for c in raiz if c.tag == "channel"]
    programas = [p for p in raiz if p.tag == "programme"]

    # Mapa id original -> lista de nombres del canal
    info = {}
    for canal in canales:
        cid = canal.get("id", "")
        nombres = [d.text.strip() for d in canal.findall("display-name") if d.text and d.text.strip()]
        info[cid] = {
            "nombres": nombres,
            "icono": (canal.find("icon").get("src") if canal.find("icon") is not None else ""),
        }

    # El id nuevo es el primer display-name (el nombre canonico del canal)
    mapa = {}
    for cid, datos in info.items():
        nuevo = datos["nombres"][0] if datos["nombres"] else cid
        mapa[cid] = nuevo

    # Reconstruimos el arbol
    for hijo in list(raiz):
        raiz.remove(hijo)

    for cid, datos in info.items():
        nuevo_id = mapa[cid]
        canal = ET.SubElement(raiz, "channel", {"id": nuevo_id})
        for nombre in variantes_de_nombre(nuevo_id, cid):
            dn = ET.SubElement(canal, "display-name")
            dn.text = nombre
        if datos["icono"]:
            ET.SubElement(canal, "icon", {"src": datos["icono"]})

    escritos = 0
    for prog in programas:
        cid = prog.get("channel", "")
        if cid not in mapa:
            continue
        prog.set("channel", mapa[cid])
        raiz.append(prog)
        escritos += 1

    # Cabecera SIN DOCTYPE y con comillas dobles.
    #
    # 1) <!DOCTYPE tv SYSTEM "xmltv.dtd"> hace que algunos parsers intenten
    #    descargar "xmltv.dtd" desde la misma URL, que no existe, y descarten
    #    el archivo entero. Los XMLTV que funcionan en TiviMate (por ejemplo
    #    los de EPG_dobleM) no llevan DOCTYPE, asi que tampoco lo ponemos.
    # 2) ElementTree escribe la declaracion con comillas simples:
    #       <?xml version='1.0' encoding='UTF-8'?>
    #    y el XMLTV de referencia usa comillas dobles. Es XML valido en ambos
    #    casos, pero igualamos el formato del que sabemos que funciona.
    ET.indent(arbol, space="  ")
    arbol.write(salida, encoding="UTF-8", xml_declaration=True)

    with open(salida, "rb") as fh:
        contenido = fh.read().decode("utf-8")
    contenido = contenido.replace(
        "<?xml version='1.0' encoding='UTF-8'?>",
        '<?xml version="1.0" encoding="UTF-8"?>',
        1,
    )
    with open(salida, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(contenido)

    # Version comprimida
    with open(salida, "rb") as fh, gzip.open(salida + ".gz", "wb", compresslevel=9) as gz:
        gz.write(fh.read())

    return len(info), escritos


def main() -> int:
    parser = argparse.ArgumentParser(description="Formato compatible TiviMate")
    parser.add_argument("--entrada", default=os.path.join(OUTPUT, "mi-epg.xml"))
    parser.add_argument("--salida", default=os.path.join(OUTPUT, "mi-epg-tivimate.xml"))
    args = parser.parse_args()

    if not os.path.exists(args.entrada):
        print(f"No existe: {args.entrada}")
        return 1

    canales, programas = convertir(args.entrada, args.salida)

    tam = os.path.getsize(args.salida) / (1024 * 1024)
    tam_gz = os.path.getsize(args.salida + ".gz") / 1024
    print(f"  Canales  : {canales}")
    print(f"  Programas: {programas}")
    print(f"  Salida   : {args.salida}")
    print(f"  Tamano   : {tam:.2f} MB  ({tam_gz:.0f} KB comprimido)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
