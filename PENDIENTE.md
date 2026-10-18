# PENDIENTE — dónde lo dejamos

Última sesión: 18/10/2026, noche.

## Lo que YA funciona

- Proyecto completo en `C:\Users\GIGABYTE-PC\Documents\mi-epg`
- Subido a https://github.com/antoniorb1913/mi-epg (público)
- GitHub Actions lo regenera **solo cada 12 h** (03:00 y 15:00, hora española)
- Guía: **149 canales, 21.704 programas, 9 días**
- Probado el workflow 2 veces: **success**

## Lo que NO funciona

TiviMate NO carga la programación desde GitHub, pero **SÍ la cargaba**
desde el servidor local (`http://192.168.1.138:8765/...`).

## Lo que se ha descubierto

El problema es el **Content-Type** (tipo MIME). TiviMate decide si
descomprimir el `.gz` según esa cabecera:

| Origen                                | Content-Type             | ¿Funciona? |
|---------------------------------------|--------------------------|------------|
| Servidor local Python                 | `application/gzip`       | ✅ SÍ      |
| GitHub raw `.xml.gz`                  | `application/octet-stream` | ❌ NO    |
| GitHub raw `.xml`                     | `text/plain`             | ❌ NO      |
| jsDelivr `.xml.gz`                    | `application/gzip`       | ? sin probar |
| TinyURL → jsDelivr                    | `application/gzip`       | ❌ NO (probado) |

**Ojo**: cuando el usuario probó jsDelivr/TinyURL, dijo "no funciona",
pero no está claro si borró la fuente anterior en TiviMate ni si
asignó la nueva a la lista.

## Corregido por el camino

- DOCTYPE eliminado (el de davidmuma no lo lleva)
- `<category>` eliminado de los programas (el de davidmuma tampoco lo lleva)
- `generator-info-url` relleno (estaba vacío)
- Declaración XML con comillas dobles

Tras estos cambios el archivo es **estructuralmente idéntico** al de
davidmuma, que sí funciona en el mismo TiviMate.

## URLs publicadas

```
https://cdn.jsdelivr.net/gh/antoniorb1913/mi-epg@main/publico/epg.xml.gz
https://cdn.jsdelivr.net/gh/antoniorb1913/mi-epg@main/publico/epg.xml
https://tinyurl.com/27r67gwc                    (-> la primera)
https://raw.githubusercontent.com/antoniorb1913/mi-epg/main/publico/epg.xml
```

## Plan para la próxima sesión

1. **Truco que aún no se ha probado**: levantar el servidor local otra vez
   y comprobar que sigue funcionando. Si funciona, el archivo está bien y
   el problema es 100% de MIME/host.
2. Si jsDelivr tampoco va, probar **GitHub Pages** (sirve `.xml` como
   `application/xml`, y permite URL corta `usuario.github.io/mi-epg/epg.xml`).
3. **Comprobar en TiviMate**: Ajustes → Guía de EPG → tocar la fuente.
   Ahí sale el contador "Canales: X / Programas: Y". Ese número lo dice todo:
   - 149 / 21704 -> descarga bien, falla la asignación
   - 149 / 0     -> descarga el archivo pero rechaza los programas
   - 0 / 0       -> no descarga nada
4. Alternativa que **YA funciona** en su TiviMate (usar si se acaba la paciencia):
   ```
   https://raw.githubusercontent.com/davidmuma/EPG_dobleM/master/guiatv.xml
   ```

## Recordatorios

- 2 APK pirata en Descargas (TiviMate Premium y TiviMate-8K), no instalar
- El servidor local se para al apagar el PC; se levanta con `servir-epg.bat`
- Comandos git desde WSL: `wsl -- bash -lc 'cd /mnt/c/... && git push'`
