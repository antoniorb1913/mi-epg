#!/usr/bin/env python3
"""
Clasifica los canales que se quedaron sin guia segun el motivo.

Tres categorias:
  A. INVENTADOS   -> no existen como canal en ninguna plataforma
  B. VOD          -> existen como plataforma, pero no como canal lineal
  C. SIN EPG      -> canales reales, pero sin guia publica (o cerrados)

Uso: python clasificar_faltantes.py
"""

import csv
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT = os.path.join(ROOT, "output")

# --- Canales que el proveedor se ha inventado (no existen fuera) ---
INVENTADOS = {
    # Comodines de eventos: solo emiten cuando hay algo
    "DAZN EVENTOS 1", "DAZN EVENTOS 2", "DAZN EVENTOS 3", "DAZN EVENTOS 4",
    "DAZN EVENTOS 5", "DAZN EVENTOS 6", "DAZN EVENTOS 7", "DAZN EVENTOS 8",
    "DAZN EVENTOS 9", "DAZN EVENTOS 10",
    # Cine+ tematicos por actor: marca del proveedor
    "Cine+ Al Pacino", "Cine+ Antonio Banderas", "Cine+ Arnold Schwarzenegger",
    "Cine+ Brad Pitt", "Cine+ Bruce Willis", "Cine+ Christian Bale",
    "Cine+ Denzel Washington", "Cine+ Dolph Lundgren", "Cine+ GUERRA",
    "Cine+ Jackie Chan", "Cine+ Jason Statham", "Cine+ John Travolta",
    "Cine+ Johnny Depp", "Cine+ Keanu Reeves", "Cine+ Kurt Russell",
    "Cine+ Leonardo DiCaprio", "Cine+ Matt Damon", "Cine+ Mel Gibson",
    "Cine+ Nicolas Cage", "Cine+ Richard Gere", "Cine+ Robert De Niro",
    "Cine+ Robert Downey Jr.", "Cine+ Russell Crowe", "Cine+ SAGA",
    "Cine+ Steven Seagal", "Cine+ Sylvester Stallone", "Cine+ Tom Cruise",
    "Cine+ Tom Hanks", "Cine+ Tom Hardy", "Cine+ Vin Diesel",
    "Cine+ Wesley Snipes", "Cine+ Will Smith",
    # SERIES+ : marca del proveedor
    "SERIES+ ACCION", "SERIES+ ANIMACION", "SERIES+ CIENCIA-FICCION",
    "SERIES+ COMEDIA", "SERIES+ CRIMEN", "SERIES+ DOCUMENTAL",
    "SERIES+ DRAMA", "SERIES+ ÉXITOS 1", "SERIES+ ÉXITOS 2",
    "SERIES+ FAMILIA", "SERIES+ GUERRA", "SERIES+ INFANTIL",
    "SERIES+ LEYENDAS 1", "SERIES+ LEYENDAS 2", "SERIES+ WESTERN ES",
    # M+ tematicos inventados
    "M+ Mission impossible", "M+ Ficcion Premium", "M+ Cinesur 1",
    "M+ Ficcion 1 HD", "M+ Ficcion 2 HD", "M+ Cine HD",
    "M+ Iberian Screen", "M+ Navidad",
    "Marvel Studios 1", "Marvel Studios 2",
    # Otros inventados
    "Procaja Tv1", "Procaja Tv2", "Procaja Tv3",
    "La Casa de las Series", "El Rincón del Profesor",
    "TV NACIONAL 1", "TV NACIONAL 3", "TV NACIONAL 4",
    "TV NACIONAL 5", "TV NACIONAL 6",
    "24/7 Masha y el Oso", "24/7 El Bombero Sam",
    "Disney + 1", "Disney Junior Movies 1", "Disney Junior Movies 2",
    "101 PLAY", "### SUP MOVIES ###",
    "CINE+ 1 HD", "CINE+ 2 HD", "Canal Alquiler HD 1", "Trailer 2020",
    "STAR",
}

# --- Plataformas VOD convertidas en canal (no tienen parrilla) ---
VOD = {
    "HBO Max 1", "HBO Max 2", "HBO Max 3", "HBO Max 4", "HBO Max 5",
    "M+ Netflix 1", "M+ Netflix 2",
    "Prime Video 1", "Prime Video 2",
    "Apple TV+ 1", "Apple TV+ 2",
    "Rakuten TV Top 1 HD", "Rakuten TV Top 2 HD", "Rakuten TV Family HD",
    "MOVISTAR CINE 1 HD", "MOVISTAR CINE 2 HD", "MOVISTAR CINE 3 HD",
}


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass

    with open(os.path.join(OUTPUT, "mapeo.csv"), encoding="utf-8") as fh:
        filas = list(csv.DictReader(fh, delimiter=";"))

    sin = [f["nombre_proveedor"] for f in filas if not f["epg_id"]]

    a = sorted([n for n in sin if n in INVENTADOS])
    b = sorted([n for n in sin if n in VOD])
    c = sorted([n for n in sin if n not in INVENTADOS and n not in VOD])

    lineas = []
    lineas.append("CANALES SIN GUIA — CLASIFICADOS POR MOTIVO")
    lineas.append("=" * 70)
    lineas.append("")
    lineas.append(f"Total sin guia: {len(sin)}")
    lineas.append("")

    lineas.append("-" * 70)
    lineas.append(f"A. INVENTADOS POR TU PROVEEDOR — {len(a)} canales")
    lineas.append("   No existen como canal en ninguna plataforma del mundo.")
    lineas.append("-" * 70)
    for n in a:
        lineas.append(f"   {n}")

    lineas.append("")
    lineas.append("-" * 70)
    lineas.append(f"B. PLATAFORMAS VOD CONVERTIDAS EN CANAL — {len(b)} canales")
    lineas.append("   Existen como app de streaming, no como canal lineal.")
    lineas.append("   No tienen parrilla, asi que no puede haber guia.")
    lineas.append("-" * 70)
    for n in b:
        lineas.append(f"   {n}")

    lineas.append("")
    lineas.append("-" * 70)
    lineas.append(f"C. CANALES REALES SIN EPG PUBLICO — {len(c)} canales")
    lineas.append("   Existen de verdad, pero no publican guia (o ya cerraron).")
    lineas.append("-" * 70)
    for n in c:
        lineas.append(f"   {n}")

    lineas.append("")
    lineas.append("=" * 70)
    lineas.append(f"  Suma: {len(a)} + {len(b)} + {len(c)} = {len(a)+len(b)+len(c)}")

    texto = "\n".join(lineas)
    ruta = os.path.join(OUTPUT, "faltantes-clasificados.txt")
    with open(ruta, "w", encoding="utf-8") as fh:
        fh.write(texto + "\n")

    print(texto)
    print()
    print(f"Guardado: {ruta}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
