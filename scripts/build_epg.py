#!/usr/bin/env python3
"""
mi-epg — Generador propio de EPG en formato XMLTV.

Lee tu lista de canales, la empareja contra fuentes EPG publicas y emite un
unico XMLTV limpio con TUS nombres, TUS logos y solo TUS canales.

Uso:
    python build_epg.py                 # genera output/mi-epg.xml
    python build_epg.py --report        # solo informe de cobertura
    python build_epg.py --dias 7        # ventana de dias (por defecto 7)
"""

import argparse
import csv
import difflib
import gzip
import io
import os
import re
import sys
import unicodedata
import urllib.request
from datetime import datetime, timedelta, timezone
from xml.etree import ElementTree as ET

BASE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(BASE)
CONFIG = os.path.join(ROOT, "config")
OUTPUT = os.path.join(ROOT, "output")

# ----------------------------------------------------------------------------
# Normalizacion
# ----------------------------------------------------------------------------

# Sufijos de calidad que NO identifican al canal
_RUIDO = re.compile(
    r"(?:\b(?:full\s*hd|fhd|uhd|4k|8k|hd|sd|h265|hevc)\b)",
    re.IGNORECASE,
)

# Palabras que tampoco diferencian canales (pais, idioma, proveedor)
_EXTRA = re.compile(
    r"\b(?:es|spain|espana|castellano|latino|internacional|internat|int)\b",
    re.IGNORECASE,
)


def sin_acentos(texto: str) -> str:
    """Quita diacriticos: 'Aragón' -> 'Aragon'."""
    descompuesto = unicodedata.normalize("NFD", texto)
    return "".join(c for c in descompuesto if unicodedata.category(c) != "Mn")


def clave(texto: str) -> str:
    """
    Clave canonica para emparejar canales.

    'ANTENA 3 HD'          -> 'antena3'
    'Antena.3.es'          -> 'antena3'
    'M+ LaLigaTV HD'       -> 'mlaligatv'
    'M+.LALIGA.TV.es'      -> 'mlaligatv'
    'Cine+ TERROR'         -> 'cineterror'
    'LA SEXTA HD'          -> 'lasexta'
    """
    if not texto:
        return ""
    t = sin_acentos(texto).lower()
    # El simbolo '+' y la palabra 'plus' son ruido: M+ / M Plus / Mplus
    t = t.replace("+", " ").replace("plus", " ")
    t = re.sub(r"\.(es|com|tv|net|org|pt|fr|de|uk|it)$", "", t)  # sufijo pais
    t = _RUIDO.sub(" ", t)
    t = _EXTRA.sub(" ", t)
    t = re.sub(r"[^a-z0-9]+", "", t)  # fuera todo lo que no sea alfanumerico
    return t


def etiqueta_calidad(nombre: str) -> str:
    """Detecta la calidad para elegir el nombre canonico del grupo."""
    n = nombre.upper()
    if "4K" in n or "UHD" in n:
        return "4K"
    if "FULL HD" in n or "FHD" in n:
        return "FULL HD"
    if re.search(r"\bHD\b", n):
        return "HD"
    if re.search(r"\bSD\b", n):
        return "SD"
    return ""


def nombre_limpio(nombre: str) -> str:
    """Nombre sin el sufijo de calidad: 'ANTENA 3 HD' -> 'ANTENA 3'."""
    n = _RUIDO.sub(" ", nombre)
    n = re.sub(r"\s+", " ", n).strip(" -_|")
    return n or nombre


# ----------------------------------------------------------------------------
# Lectura de configuracion
# ----------------------------------------------------------------------------


def leer_canales_propios() -> list[dict]:
    """
    Lee config/canales.txt -> [{grupo, nombre}].

    Deduplica por clave normalizada: un mismo canal puede aparecer en varios
    grupos (COSMO en SERIES y en OTROS, FDF, ENERGY...). Se queda el primero.
    """
    ruta = os.path.join(CONFIG, "canales.txt")
    canales = []
    vistos = {}
    with open(ruta, encoding="utf-8") as fh:
        for linea in fh:
            linea = linea.strip()
            if not linea or linea.startswith("#"):
                continue
            if "|" in linea:
                grupo, nombre = linea.split("|", 1)
            else:
                grupo, nombre = "OTROS", linea
            grupo, nombre = grupo.strip(), nombre.strip()
            if not nombre:
                continue
            k = clave(nombre)
            if k in vistos:
                # Ya existe: solo anotamos el grupo alternativo
                if grupo != vistos[k]["grupo"]:
                    vistos[k]["otros_grupos"].append(grupo)
                continue
            registro = {"grupo": grupo, "nombre": nombre, "otros_grupos": []}
            vistos[k] = registro
            canales.append(registro)
    return canales


def leer_fuentes() -> list[str]:
    ruta = os.path.join(CONFIG, "fuentes.txt")
    with open(ruta, encoding="utf-8") as fh:
        return [l.strip() for l in fh if l.strip() and not l.startswith("#")]


def leer_aliases() -> dict[str, str]:
    """
    Lee config/aliases.csv -> {clave: id_epg}.

    Admite separador ';' o ',' y ambas formas: clave;id  o  nombre;id
    """
    ruta = os.path.join(CONFIG, "aliases.csv")
    aliases = {}
    if not os.path.exists(ruta):
        return aliases
    with open(ruta, encoding="utf-8-sig") as fh:
        for linea in fh:
            linea = linea.strip().lstrip("\ufeff")
            if not linea or linea.startswith("#"):
                continue
            partes = re.split(r"[;,]", linea, maxsplit=1)
            if len(partes) != 2:
                continue
            izq, der = partes[0].strip(), partes[1].strip()
            if not izq or not der:
                continue
            aliases[clave(izq)] = der
    return aliases


def leer_correcciones() -> dict[str, str]:
    """
    Lee config/correcciones.csv -> {clave: id_epg}.

    Correcciones manuales del usuario, para cuando el proveedor tiene el
    nombre del canal cambiado. Tienen PRIORIDAD sobre aliases.csv.

    Formato:  nombre_en_tu_lista ; id_epg_real
    Ejemplo:  DARK ; STAR Channel HD
    """
    ruta = os.path.join(CONFIG, "correcciones.csv")
    correcciones = {}
    if not os.path.exists(ruta):
        return correcciones
    with open(ruta, encoding="utf-8-sig") as fh:
        for linea in fh:
            linea = linea.strip().lstrip("\ufeff")
            if not linea or linea.startswith("#"):
                continue
            partes = re.split(r"[;,]", linea, maxsplit=1)
            if len(partes) != 2:
                continue
            izq, der = partes[0].strip(), partes[1].strip()
            if not izq:
                continue
            # Un destino vacio significa "quitar la guia a este canal"
            correcciones[clave(izq)] = der
    return correcciones


# ----------------------------------------------------------------------------
# Descarga y lectura de fuentes EPG
# ----------------------------------------------------------------------------


def descargar(url: str, cache_dir: str) -> str:
    """Descarga una fuente (xml o xml.gz) y devuelve la ruta local descomprimida."""
    os.makedirs(cache_dir, exist_ok=True)
    nombre = re.sub(r"[^A-Za-z0-9._-]", "_", url.split("/")[-1])
    destino = os.path.join(cache_dir, nombre)
    crudo = destino if nombre.endswith(".xml") else destino + ".gz"

    if os.path.exists(destino) and os.path.getsize(destino) > 1024:
        print(f"   [cache] {os.path.basename(destino)}")
        return destino

    print(f"   Descargando {url}")
    peticion = urllib.request.Request(url, headers={"User-Agent": "mi-epg/1.0"})
    with urllib.request.urlopen(peticion, timeout=180) as respuesta:
        datos = respuesta.read()

    if datos[:2] == b"\x1f\x8b":
        datos = gzip.decompress(datos)

    with open(destino, "wb") as fh:
        fh.write(datos)
    print(f"   -> {len(datos):,} bytes")
    return destino


def iterar_elementos(ruta_xml: str, etiqueta: str):
    """
    Itera <channel> o <programme> sin cargar el arbol completo en memoria.

    Usa iterparse + limpieza, imprescindible con XML de decenas de MB.
    """
    contexto = ET.iterparse(ruta_xml, events=("end",))
    for _, elemento in contexto:
        if elemento.tag == etiqueta:
            yield elemento
            elemento.clear()


def indice_fuente(ruta_xml: str) -> tuple[dict, dict]:
    """
    Construye dos indices de los canales de una fuente EPG.

    Devuelve (por_id, por_nombre_clave) mapeando a {id, nombre, icono}.
    """
    por_id, por_clave = {}, {}
    for canal in iterar_elementos(ruta_xml, "channel"):
        cid = canal.get("id", "")
        if not cid:
            continue
        nombre = ""
        icono = ""
        for hijo in canal:
            if hijo.tag == "display-name" and not nombre:
                nombre = (hijo.text or "").strip()
            elif hijo.tag == "icon" and not icono:
                icono = hijo.get("src", "")
        registro = {"id": cid, "nombre": nombre, "icono": icono}
        por_id[cid] = registro
        for k in (clave(cid), clave(nombre)):
            if k and k not in por_clave:
                por_clave[k] = registro
    return por_id, por_clave


# ----------------------------------------------------------------------------
# Emparejamiento
# ----------------------------------------------------------------------------


def emparejar(canales: list[dict], por_id: dict, por_clave: dict, aliases: dict,
              correcciones: dict | None = None):
    """
    Empareja canales propios con el EPG en cascada.

    Orden de prioridad:
      0. correcciones.csv  (el usuario manda)
      1. aliases.csv
      2. clave normalizada
      3. similitud

    Devuelve (grupos, informe) donde grupos es
        {clave_canal: {epg_id, epg_nombre, icono, variantes:[...]}}
    """
    grupos = {}
    informe = []
    correcciones = correcciones or {}

    for canal in canales:
        nombre = canal["nombre"]
        k_canal = clave(nombre)
        match, via = None, None

        # 0. Correccion manual del usuario (maxima prioridad)
        if k_canal in correcciones:
            objetivo = correcciones[k_canal]
            if objetivo:
                match = por_id.get(objetivo)
                via = "correccion" if match else "correccion-fallida"
            else:
                # Destino vacio = sin guia a proposito
                via = "descartado"
                informe.append(
                    {
                        "nombre": nombre,
                        "grupo": canal["grupo"],
                        "clave": k_canal,
                        "epg_id": "",
                        "epg_nombre": "",
                        "via": "descartado",
                    }
                )
                continue

        # 1. Alias manual explicito
        if not match and k_canal in aliases:
            objetivo = aliases[k_canal]
            match = por_id.get(objetivo)
            via = "alias" if match else "alias-fallido"

        # 2. Coincidencia por clave normalizada (ID o display-name)
        if not match:
            match = por_clave.get(k_canal)
            via = "normalizado" if match else None

        # 3. Base sin sufijo de calidad (ya cubierto por clave) -> extra
        if not match:
            k_limpio = clave(nombre_limpio(nombre))
            if k_limpio and k_limpio != k_canal:
                match = por_clave.get(k_limpio)
                via = "nombre-limpio" if match else None

        # 4. Similitud como ultimo recurso (solo claves parecidas)
        if not match and k_canal:
            mejor, mejor_p = None, 0.0
            for k_epg, registro in por_clave.items():
                if abs(len(k_epg) - len(k_canal)) > 6:
                    continue
                p = difflib.SequenceMatcher(None, k_canal, k_epg).ratio()
                if p > mejor_p:
                    mejor, mejor_p = registro, p
            if mejor is not None and mejor_p >= 0.90:
                match, via = mejor, f"similitud-{mejor_p:.2f}"

        informe.append(
            {
                "nombre": nombre,
                "grupo": canal["grupo"],
                "clave": k_canal,
                "epg_id": match["id"] if match else "",
                "epg_nombre": match["nombre"] if match else "",
                "via": via or "sin-guia",
            }
        )

        if not match:
            continue

        # Agrupamos todas las calidades del mismo canal bajo un solo EPG id
        grupo = grupos.setdefault(
            match["id"],
            {
                "epg_id": match["id"],
                "epg_nombre": match["nombre"],
                "icono": match["icono"],
                "grupo": canal["grupo"],
                "variantes": [],
                "calidad": "",
            },
        )
        grupo["variantes"].append(nombre)
        calidad = etiqueta_calidad(nombre)
        orden = {"": 0, "SD": 1, "HD": 2, "FULL HD": 3, "4K": 4}
        if orden.get(calidad, 0) > orden.get(grupo["calidad"], 0):
            grupo["calidad"] = calidad

    return grupos, informe


# ----------------------------------------------------------------------------
# Generacion XMLTV
# ----------------------------------------------------------------------------


def _fmt(dt: datetime) -> str:
    """Formato XMLTV: 20261018200000 +0200."""
    return dt.strftime("%Y%m%d%H%M%S %z")


def _parsear_fecha(texto: str) -> datetime | None:
    """Parsea '20261018200000 +0200' tolerando variantes."""
    if not texto:
        return None
    limpio = texto.strip()
    m = re.match(r"^(\d{14})(?:\s*([+-]\d{4}))?$", limpio)
    if not m:
        return None
    base = datetime.strptime(m.group(1), "%Y%m%d%H%M%S")
    zona = m.group(2)
    if zona:
        signo = 1 if zona[0] == "+" else -1
        desfase = timedelta(hours=int(zona[1:3]), minutes=int(zona[3:5]))
        return base.replace(tzinfo=timezone(signo * desfase))
    return base.replace(tzinfo=timezone.utc)


def generar(grupos: dict, fuentes: list[str], salida: str, dias: int):
    """Escribe el XMLTV con los canales y programas que hemos emparejado."""
    ids_buscados = set(grupos.keys())

    # Nombre visible: el mas representativo del grupo
    def nombre_final(grupo: dict) -> str:
        base = nombre_limpio(grupo["variantes"][0])
        if grupo["calidad"]:
            return f"{base} {grupo['calidad']}"
        return base

    escapar = lambda s: re.sub(r"[<>&]", lambda m: {"<": "&lt;", ">": "&gt;", "&": "&amp;"}[m.group(0)], s or "")

    ahora = datetime.now(timezone.utc)
    desde = ahora - timedelta(days=1)
    hasta = ahora + timedelta(days=dias)
    escritos = 0
    canales_escritos = set()

    with open(salida, "w", encoding="utf-8") as fh:
        fh.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        fh.write('<tv generator-info-name="mi-epg" generator-info-url="">\n')

        for epg_id, grupo in grupos.items():
            fh.write(f'  <channel id="{escapar(epg_id)}">\n')
            # Primero el nombre canonico, luego el resto de variantes sin repetir
            nombres = [nombre_final(grupo)]
            for variante in grupo["variantes"]:
                if variante not in nombres:
                    nombres.append(variante)
            for nombre in nombres:
                fh.write(f'    <display-name>{escapar(nombre)}</display-name>\n')
            if grupo["icono"]:
                fh.write(f'    <icon src="{escapar(grupo["icono"])}"/>\n')
            fh.write("  </channel>\n")
            canales_escritos.add(epg_id)

        # Programas: streaming por fuente, solo los canales que nos interesan
        for ruta in fuentes:
            for prog in iterar_elementos(ruta, "programme"):
                cid = prog.get("channel", "")
                if cid not in ids_buscados:
                    continue
                inicio = _parsear_fecha(prog.get("start", ""))
                fin = _parsear_fecha(prog.get("stop", ""))
                if not inicio or not fin:
                    continue
                if fin < desde or inicio > hasta:
                    continue

                titulo = desc = categoria = ""
                for hijo in prog:
                    if hijo.tag == "title" and not titulo:
                        titulo = (hijo.text or "").strip()
                    elif hijo.tag == "desc" and not desc:
                        desc = (hijo.text or "").strip()
                    elif hijo.tag == "category" and not categoria:
                        categoria = (hijo.text or "").strip()

                fh.write(
                    f'  <programme start="{_fmt(inicio)}" stop="{_fmt(fin)}" '
                    f'channel="{escapar(cid)}">\n'
                )
                fh.write(f"    <title>{escapar(titulo)}</title>\n")
                if desc:
                    fh.write(f"    <desc>{escapar(desc)}</desc>\n")
                if categoria:
                    fh.write(f"    <category>{escapar(categoria)}</category>\n")
                fh.write("  </programme>\n")
                escritos += 1

        fh.write("</tv>\n")

    return len(canales_escritos), escritos


def limpiar(salida: str) -> tuple[int, int]:
    """
    Post-proceso del XMLTV generado.

    - Elimina <channel> con id duplicado (se queda el primero).
    - Elimina <channel> que no tengan ni un solo <programme>.
    Devuelve (canales_antes, canales_despues).
    """
    doc = ET.parse(salida)
    raiz = doc.getroot()

    canales = [c for c in raiz if c.tag == "channel"]
    programas = [p for p in raiz if p.tag == "programme"]
    antes = len(canales)

    con_programas = {p.get("channel") for p in programas}
    vistos = set()
    finales = []
    for canal in canales:
        cid = canal.get("id", "")
        if not cid or cid in vistos or cid not in con_programas:
            continue
        vistos.add(cid)
        finales.append(canal)

    # Reconstruimos el arbol en orden canonico: canales y luego programas
    for hijo in list(raiz):
        raiz.remove(hijo)
    for canal in finales:
        raiz.append(canal)
    for prog in programas:
        if prog.get("channel") in vistos:
            raiz.append(prog)

    doc.write(salida, encoding="UTF-8", xml_declaration=True)
    return antes, len(finales)


# ----------------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description="Genera un XMLTV propio")
    parser.add_argument("--report", action="store_true", help="solo informe, no genera")
    parser.add_argument("--dias", type=int, default=7, help="dias de programacion")
    args = parser.parse_args()

    canales = leer_canales_propios()
    fuentes_url = leer_fuentes()
    aliases = leer_aliases()
    correcciones = leer_correcciones()

    print(f"Canales propios : {len(canales)}")
    print(f"Fuentes EPG     : {len(fuentes_url)}")
    print(f"Alias manuales  : {len(aliases)}")
    print(f"Correcciones    : {len(correcciones)}")
    print()

    cache = os.path.join(ROOT, ".cache")
    rutas = []
    por_id, por_clave = {}, {}
    for url in fuentes_url:
        try:
            ruta = descargar(url, cache)
        except Exception as exc:  # noqa: BLE001
            print(f"   ERROR descargando: {exc}")
            continue
        rutas.append(ruta)
        ids, claves = indice_fuente(ruta)
        por_id.update(ids)
        for k, v in claves.items():
            por_clave.setdefault(k, v)
        print(f"   Indice: {len(ids)} canales")

    if not por_id:
        print("No hay fuentes EPG validas.")
        return 1

    grupos, informe = emparejar(canales, por_id, por_clave, aliases, correcciones)

    ok = [i for i in informe if i["epg_id"]]
    ko = [i for i in informe if not i["epg_id"]]
    total = len(informe)
    pct = (len(ok) / total * 100) if total else 0

    print()
    print("=" * 62)
    print(f"  EMPAREJADOS : {len(ok)}/{total}  ({pct:.1f}%)")
    print(f"  SIN GUIA    : {len(ko)}")
    print(f"  Canales XML : {len(grupos)} (agrupados HD/SD/4K)")
    print("=" * 62)

    por_via = {}
    for i in informe:
        por_via[i["via"]] = por_via.get(i["via"], 0) + 1
    print("  Por via:", ", ".join(f"{k}={v}" for k, v in sorted(por_via.items())))

    if ko:
        print()
        print("  Sin guia (candidatos a alias manual):")
        for i in ko:
            print(f"    - {i['nombre']:<32} [{i['clave']}]")

    os.makedirs(OUTPUT, exist_ok=True)

    # Guardamos el mapeo para que sea auditable y editable
    mapa_csv = os.path.join(OUTPUT, "mapeo.csv")
    with open(mapa_csv, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, delimiter=";")
        w.writerow(["nombre_proveedor", "grupo", "clave", "epg_id", "epg_nombre", "via"])
        for i in informe:
            w.writerow([i["nombre"], i["grupo"], i["clave"], i["epg_id"], i["epg_nombre"], i["via"]])
    print(f"\n  Mapeo guardado en {mapa_csv}")

    if args.report:
        return 0

    salida = os.path.join(OUTPUT, "mi-epg.xml")
    n_canales, n_progs = generar(grupos, rutas, salida, args.dias)

    antes, despues = limpiar(salida)
    if antes != despues:
        print(f"\n  Limpieza: {antes} canales -> {despues} "
              f"(quitados {antes - despues} duplicados o sin programas)")

    # Version comprimida: los reproductores la descargan mucho mas rapido
    salida_gz = salida + ".gz"
    with open(salida, "rb") as origen, gzip.open(salida_gz, "wb", compresslevel=9) as destino:
        destino.write(origen.read())

    tam = os.path.getsize(salida) / (1024 * 1024)
    tam_gz = os.path.getsize(salida_gz) / 1024
    print(f"\n  Generado: {salida}")
    print(f"  Canales en el XML : {despues}")
    print(f"  Programas         : {n_progs}")
    print(f"  Tamano            : {tam:.2f} MB  ({tam_gz:.0f} KB comprimido)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
