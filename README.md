# mi-epg

Generador **propio** de guía de programación (EPG) en formato **XMLTV**.

Lee tu lista de canales, la empareja contra fuentes públicas de programación y
emite un único XML con **tus nombres**, **tus logos** y **solo tus canales**.

Código original. No copia ningún script de terceros: solo usa fuentes de datos
públicas y el formato estándar XMLTV.

---

## URL de la guía (lista para usar)

```
https://raw.githubusercontent.com/antoniorb1913/mi-epg/main/output/mi-epg-compatible.xml.gz
```

Se regenera **sola cada 12 horas** con GitHub Actions (03:00 y 15:00, hora
española). No hace falta tener ningún PC encendido.

Pégala en el reproductor: TiviMate → Ajustes → Guía de EPG → Añadir fuente → URL.

- Formato compatible TiviMate: `output/mi-epg-compatible.xml.gz`
- Formato XMLTV estándar: `output/mi-epg.xml.gz`

---

## Resultado actual

| Concepto | Valor |
|---|---|
| Canales en la lista | 286 |
| Emparejados con guía | **164** |
| Canales en el XML | **149** (HD/SD/4K agrupados) |
| Programas | **21.710** |
| Días de guía | 9 |
| Canales con logo | 148 de 149 |
| Canales vacíos | 0 |

Los 122 canales sin guía están clasificados en
[`output/faltantes-clasificados.txt`](output/faltantes-clasificados.txt):

- **89 inventados** por el proveedor (Cine+ por actor, SERIES+, DAZN Eventos…)
- **17 servicios VOD** convertidos en canal (HBO Max, Netflix, Prime Video…)
- **16 reales sin EPG público** (locales, o cerrados como Disney Junior)

Ninguno es recuperable: no existen como canal lineal con programación.

---

## Corregir canales mal etiquetados

El proveedor tiene canales con el nombre cambiado. Para arreglarlos, añade una
línea a [`config/correcciones.csv`](config/correcciones.csv):

```
nombre_en_tu_lista ; id_del_canal_real
```

Ejemplos ya aplicados:

```
DARK      ; STAR Channel HD
M+ Series ; TCM HD
```

Para saber el id real de un canal, usa `scripts/identificar_canal.py`: buscas
lo que estás viendo y te dice qué canal de la EPG lo emite.

```bash
python scripts/identificar_canal.py harry potter
```

---

## Estructura

```
mi-epg/
├── .github/workflows/epg.yml   Automatización (GitHub Actions)
├── config/
│   ├── canales.txt             Tu lista de canales
│   ├── fuentes.txt             URLs de fuentes EPG
│   └── aliases.csv             Tabla de equivalencias canal -> id EPG
├── scripts/
│   └── build_epg.py            Generador (Python 3.9+, sin dependencias)
├── output/
│   ├── mi-epg.xml              XMLTV generado
│   ├── mi-epg.xml.gz           Igual, comprimido
│   └── mapeo.csv               Informe: qué canal se emparejó con qué
└── .cache/                     Descargas (ignorado por git)
```

---

## Uso

### Generar la guía

```bash
python scripts/build_epg.py
```

### Solo ver el informe de cobertura (no genera XML)

```bash
python scripts/build_epg.py --report
```

### Cambiar los días de programación

```bash
python scripts/build_epg.py --dias 3
```

Opciones disponibles:

| Opción | Descripción |
|---|---|
| `--report` | Solo informe, no genera el XML |
| `--dias N` | Ventana de días (por defecto 7) |

---

## Cómo funciona

```
config/canales.txt
        │
        │  1. Normalizar nombres
        │     "ANTENA 3 HD" -> antena3
        │     "Antena.3.es" -> antena3
        ▼
   ┌──────────────────┐     2. Cascada de emparejamiento
   │  EMPAREJADOR     │        a) alias manual (aliases.csv)
   └──────────────────┘        b) clave normalizada
        │                      c) similitud (>= 0,90)
        │
        │  3. Agrupar HD / SD / 4K bajo un mismo id
        ▼
fuentes EPG  ──►  4. Filtrar solo tus canales + ventana de días
   (XMLTV)        5. Escribir canal + icono + programas
        │
        ▼
output/mi-epg.xml
```

### La normalización es la clave

El problema real del EPG es que **cada fuente nombra los canales a su manera**:

| Tu proveedor | Fuente EPG | Clave normalizada |
|---|---|---|
| `ANTENA 3 HD` | `Antena.3.es` | `antena3` |
| `LA 1 HD` | `La.1.es` | `la1` |
| `M+ LaLigaTV HD` | `M+.LALIGA.TV.es` | `mlaligatv` |
| `Cine+ TERROR` | `M+ Drama` | `cineterror` → alias |

Se quitan acentos, sufijos de calidad (`HD`, `SD`, `4K`, `FULL HD`), el sufijo
de país (`.es`), el símbolo `+` y todo lo que no sea alfanumérico.

Sin normalización, la cobertura por ID exacto era del **37 %**.
Con normalización y alias: **86,6 %**.

---

## Añadir un canal nuevo

### 1. Si la guía ya lo cubre

Añade el canal a `config/canales.txt`:

```
GENERAL | MI CANAL HD
```

Y ejecuta. El emparejador automático hará el resto.

### 2. Si no lo encuentra

Mira el informe: te lista los canales **sin guía**. Busca cómo se llama en la
fuente y añádelo a `config/aliases.csv`:

```csv
micalan;Nombre.En.La.Fuente.es
```

La clave es tu nombre de canal normalizado (minúsculas, sin acentos, sin
`HD`/`SD`/`4K`, sin símbolos).

### 3. Si el canal no existe en ninguna fuente

Es normal en canales propios del proveedor (DAZN Eventos, 24/7 temáticos…).
Déjalo sin alias: no aparecerá en el XML, que es lo correcto.

---

## Añadir una fuente EPG

Edita `config/fuentes.txt`, una URL por línea (admite `.xml` y `.xml.gz`):

```
https://epgshare01.online/epgshare01/epg_ripper_ES1.xml.gz
```

Si añades varias, los índices se fusionan y tiene prioridad la primera.

---

## Logos

El script usa el `<icon>` que ya venga en la fuente EPG (111 de 115 canales
lo tienen). Para poner los tuyos:

1. Mete los PNG en `logos/`.
2. Añade una columna de logo a `aliases.csv` o modifica el bloque de
   `generar()` en `scripts/build_epg.py`:

```python
if grupo["icono"]:
    fh.write(f'    <icon src="{escapar(grupo["icono"])}"/>\n')
```

Cámbialo por tu URL base, por ejemplo:

```python
LOGO_BASE = "https://tu-usuario.github.io/mi-epg/logos"
fh.write(f'    <icon src="{LOGO_BASE}/{epg_id}.png"/>\n')
```

---

## Automatización con GitHub Actions

El workflow `.github/workflows/epg.yml` se ejecuta **cada 12 horas** y también
a mano desde la pestaña *Actions*.

Una vez subido el repo, tu URL pública será:

```
https://raw.githubusercontent.com/TU-USUARIO/mi-epg/main/output/mi-epg.xml
```

> **Nota**: `raw.githubusercontent.com` tiene caché de unos minutos y límites
> de peticiones. Para un uso intensivo, activa **GitHub Pages** y sirve el XML
> desde ahí.

---

## Conectar con el reproductor

En **IPTVnator**: `Ajustes → EPG / Fuentes XMLTV` y pega la URL de tu XML.

Los reproductores emparejan por **id de canal**: tu lista M3U debe tener en
`tvg-id` el mismo valor que el `id` del XML. Consulta `output/mapeo.csv` para
ver qué id le tocó a cada canal.

Si tu proveedor usa otros ids (o ninguno), hay dos salidas:

1. **Generar una M3U propia** que reescriba los `tvg-id` con los del XML.
2. Añadir una capa de mapeo `stream_id → epg_id` leyendo la API Xtream
   (`player_api.php?action=get_live_streams`).

---

## Fuentes de datos

Actualmente hay **dos**, y se fusionan automaticamente:

- epgshare01 ES1 — 373 canales, la base principal
- EPG_dobleM guiatv — cubre canales que la anterior no tiene (Star Channel, etc.)

Ventaja del diseno: si una fuente cae, la otra sigue dando guia. Para anadir
una tercera basta con una linea mas en config/fuentes.txt.

Aviso legal: la programación (título y hora) es dato fáctico. Las descripciones
y las imágenes son contenido de cada cadena. Para uso personal es correcto; si
publicas el repo abierto, tenlo en cuenta.

---

## Requisitos

- Python 3.9 o superior
- Sin dependencias externas (solo biblioteca estándar)

---

## Licencia

Código propio, libre para usar y modificar.

