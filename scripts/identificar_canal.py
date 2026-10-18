#!/usr/bin/env python3
"""
Identifica que canal estas viendo, a partir de lo que emite ahora mismo.

El truco: si en TiviMate ves una pelicula o programa, busca ese titulo aqui y
te dice en que canal(es) de la EPG se esta emitiendo. Asi descubres el nombre
real de un canal que tu proveedor tiene mal etiquetado.

Uso:
    python identificar_canal.py                  # que emiten ahora todos
    python identificar_canal.py harry potter     # quien emite eso ahora
    python identificar_canal.py "los simpson"
"""

import argparse
import os
import sys
from datetime import datetime, timedelta, timezone

from lxml import etree

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(ROOT, ".cache")


def parsear_fecha(texto: str) -> datetime | None:
    """Convierte '20261018153500 +0200' en datetime con zona."""
    texto = (texto or "").strip()
    if len(texto) < 14:
        return None
    try:
        base = datetime.strptime(texto[:14], "%Y%m%d%H%M%S")
    except ValueError:
        return None
    zona = texto[15:20] if len(texto) > 15 else "+0000"
    try:
        signo = 1 if zona[0] == "+" else -1
        desfase = timedelta(hours=int(zona[1:3]), minutes=int(zona[3:5]))
        return base.replace(tzinfo=timezone(signo * desfase))
    except (ValueError, IndexError):
        return base.replace(tzinfo=timezone.utc)


def cargar_programas() -> list[dict]:
    """Devuelve todos los programas con canal, titulo y horario."""
    programas = []
    vistos = set()

    for archivo in ("epg_ripper_ES1.xml", "guiatv.xml"):
        ruta = os.path.join(CACHE, archivo)
        if not os.path.exists(ruta):
            continue
        raiz = etree.parse(ruta).getroot()

        nombres = {}
        for canal in raiz.findall("channel"):
            dns = [(d.text or "").strip() for d in canal.findall("display-name")]
            dns = [d for d in dns if d]
            nombres[canal.get("id")] = dns[0] if dns else canal.get("id", "")

        for prog in raiz.findall("programme"):
            titulo_el = prog.find("title")
            if titulo_el is None or not titulo_el.text:
                continue
            cid = prog.get("channel", "")
            titulo = titulo_el.text.strip()
            inicio = parsear_fecha(prog.get("start", ""))
            fin = parsear_fecha(prog.get("stop", ""))
            if not inicio or not fin:
                continue

            clave = (cid, titulo, inicio)
            if clave in vistos:
                continue
            vistos.add(clave)

            desc_el = prog.find("desc")
            programas.append(
                {
                    "canal_id": cid,
                    "canal": nombres.get(cid, cid),
                    "titulo": titulo,
                    "desc": (desc_el.text or "").strip() if desc_el is not None else "",
                    "inicio": inicio,
                    "fin": fin,
                }
            )
    return programas


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass

    parser = argparse.ArgumentParser(description="Identifica un canal por lo que emite")
    parser.add_argument("busqueda", nargs="*", help="texto a buscar en el titulo")
    args = parser.parse_args()

    programas = cargar_programas()
    ahora = datetime.now(timezone.utc)
    consulta = " ".join(args.busqueda).lower().strip()

    print(f"Programas cargados: {len(programas)}")
    print(f"Ahora: {datetime.now().strftime('%Y-%m-%d %H:%M')} (local)")
    print()

    en_emision = [p for p in programas if p["inicio"] <= ahora <= p["fin"]]

    if consulta:
        # --- Modo busqueda: quien emite esto ahora ---
        coincidencias = [p for p in en_emision if consulta in p["titulo"].lower()]
        if not coincidencias:
            # Ampliamos a todo el dia
            coincidencias = [
                p
                for p in programas
                if consulta in p["titulo"].lower() and p["inicio"].date() == ahora.date()
            ]
            if coincidencias:
                print(f'"{consulta}" no se emite AHORA, pero si hoy:\n')
            else:
                print(f'No encontrado: "{consulta}"')
                return 0

        vistos = set()
        for p in sorted(coincidencias, key=lambda x: x["inicio"]):
            marca = (p["canal_id"], p["titulo"])
            if marca in vistos:
                continue
            vistos.add(marca)
            estado = "AHORA" if p["inicio"] <= ahora <= p["fin"] else "     "
            print(f"  [{estado}] {p['canal']:<28} {p['inicio'].strftime('%H:%M')}-{p['fin'].strftime('%H:%M')}")
            print(f"            id: {p['canal_id']}")
            print(f"            {p['titulo'][:70]}")
        return 0

    # --- Modo lista: que emiten ahora todos los canales ---
    print("=== QUE SE ESTA EMITIENDO AHORA ===")
    print()
    por_canal = {}
    for p in en_emision:
        por_canal.setdefault(p["canal_id"], p)

    for cid in sorted(por_canal, key=lambda c: por_canal[c]["canal"].lower()):
        p = por_canal[cid]
        print(f"  {p['canal']:<28} {p['inicio'].strftime('%H:%M')}-{p['fin'].strftime('%H:%M')}  {p['titulo'][:52]}")

    print()
    print(f"Canales emitiendo ahora: {len(por_canal)}")
    print()
    print("Para identificar uno:  python identificar_canal.py <texto del titulo>")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
