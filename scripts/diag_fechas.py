#!/usr/bin/env python3
"""Diagnostico: revisa fechas y horas de la EPG publicada."""

import gzip
import io
import sys
import urllib.request
from collections import Counter
from datetime import datetime, timedelta, timezone
from xml.etree import ElementTree as ET

URL_XML = "https://raw.githubusercontent.com/antoniorb1913/mi-epg/main/publico/epg.xml"
URL_GZ = "https://raw.githubusercontent.com/antoniorb1913/mi-epg/main/publico/epg.xml.gz"


def descargar(url: str) -> bytes:
    pet = urllib.request.Request(url, headers={"User-Agent": "diag/1.0", "Cache-Control": "no-cache"})
    with urllib.request.urlopen(pet, timeout=180) as r:
        datos = r.read()
    if datos[:2] == b"\x1f\x8b":
        datos = gzip.decompress(datos)
    return datos


def parsear(texto: str) -> datetime | None:
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
        off = timedelta(hours=int(zona[1:3]), minutes=int(zona[3:5]))
        return base.replace(tzinfo=timezone(signo * off))
    except (ValueError, IndexError):
        return base.replace(tzinfo=timezone.utc)


for nombre, url in (("XML", URL_XML), ("GZ", URL_GZ)):
    print("=" * 66)
    print(f"  {nombre}: {url.split('/')[-1]}")
    print("=" * 66)
    try:
        datos = descargar(url)
    except Exception as exc:  # noqa: BLE001
        print(f"  ERROR descargando: {exc}\n")
        continue

    print(f"  bytes: {len(datos):,}")
    texto = datos.decode("utf-8", errors="replace")
    print(f"  tiene DOCTYPE: {'DOCTYPE' in texto}")
    print(f"  primera linea: {texto.splitlines()[0][:70]}")

    raiz = ET.fromstring(datos)
    canales = raiz.findall("channel")
    programas = raiz.findall("programme")
    print(f"  canales: {len(canales)}   programas: {len(programas)}")

    ahora = datetime.now(timezone.utc)
    print(f"  AHORA (UTC): {ahora.strftime('%Y-%m-%d %H:%M')}")

    inicios = [parsear(p.get("start")) for p in programas]
    inicios = [i for i in inicios if i]
    if inicios:
        print(f"  primer programa: {min(inicios).strftime('%Y-%m-%d %H:%M')}")
        print(f"  ultimo programa: {max(inicios).strftime('%Y-%m-%d %H:%M')}")

        # Cuantos programas estan en curso AHORA
        en_curso = 0
        for p in programas:
            ini = parsear(p.get("start"))
            fin = parsear(p.get("stop"))
            if ini and fin and ini <= ahora <= fin:
                en_curso += 1
        print(f"  programas EN CURSO ahora mismo: {en_curso}")

        # Dias cubiertos
        dias = Counter(i.date().isoformat() for i in inicios)
        print("  programas por dia:")
        for d in sorted(dias):
            marca = "  <-- HOY" if d == ahora.date().isoformat() else ""
            print(f"      {d}: {dias[d]}{marca}")

    # Muestra de un canal concreto
    print()
    print("  Muestra: programas de 'LA 1 HD' los proximos 2 dias")
    n = 0
    for p in programas:
        if p.get("channel") != "LA 1 HD":
            continue
        ini = parsear(p.get("start"))
        if not ini or ini < ahora - timedelta(hours=2):
            continue
        t = p.find("title")
        print(f"      {p.get('start')}  ->  {(t.text or '')[:52] if t is not None else ''}")
        n += 1
        if n >= 6:
            break
    if n == 0:
        print("      NO HAY PROGRAMAS para 'LA 1 HD' desde ahora")
    print()
