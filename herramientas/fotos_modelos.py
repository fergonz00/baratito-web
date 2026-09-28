"""Regenera el set de fotos de `imagenes/` desde el configurador oficial de VW.

Por que existe: las fotos viejas eran de 420x210 y el sitio las muestra hasta a
480px de alto, asi que se veian escaladas y sucias. Ademas cada una venia con
su propio encuadre, entonces entre un modelo y otro el auto cambiaba de tamano
y de altura.

De donde salen ahora: volkswagen.com.ar/es/configurador.html trae embebido un
JSON (`modelOverview`) con todas las versiones y, por cada una, la URL de su
render de estudio en `media.vw.mediaservice.avp.tech`. Son 1920x960 con fondo
transparente, todos con la misma camara, la misma luz y la misma escala
relativa (la Amarok ocupa mas cuadro que el Polo porque es mas grande de
verdad).

Como se mantiene la homogeneidad: a los 56 renders se les aplica EXACTAMENTE el
mismo recorte, calculado sobre la union de sus bounding boxes. Nada se ajusta
foto por foto, asi que la linea del piso siempre cae en el mismo lugar.

Uso:
    python herramientas/fotos_modelos.py            # escribe en imagenes-nuevas/
    python herramientas/fotos_modelos.py imagenes   # pisa el set en produccion

Gotchas que costaron tiempo, para no volver a descubrirlos:

  - `assets.volkswagen.com` (Scene7) devuelve 403 si le mandas los parametros
    en claro: la query va firmada en base64 y la firma depende SOLO de los
    parametros, no del asset. Ese CDN igual no sirve aca porque no tiene los
    renders por version.
  - El JSON del configurador viene URL-encodeado y escapado dentro del HTML:
    hay que hacer unquote varias veces y recien despues parsear.
  - VW define un unico color por version. No hay variantes de color en este
    payload.
"""
import json
import os
import re
import sys
import urllib.request
from urllib.parse import unquote

from PIL import Image

CONFIGURADOR = 'https://www.volkswagen.com.ar/es/configurador.html'
UA = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Recorte unico sobre los 1920x960 de origen -> 16:9.
# La union de los bounding boxes de los 56 renders es x 183..1678, y 95..917,
# asi que esto deja como minimo 40px de aire por lado.
CROP = (108, 32, 1753, 957)

# En desktop la galeria mide unos 630x416 px CSS (grid 1.35fr dentro de
# max-w 1320, menos 32px de padding). En pantalla retina eso pide ~1260px
# reales; 1400 alcanza con margen y deja cada foto en unos 73 KB.
OUT_W, OUT_H = 1400, 788
QUALITY = 80

# Las tarjetas del home muestran la foto a 420x240 px (la destacada a ~465),
# o sea ~840px en retina. Mandarles la de 1400 es tirar la mitad del peso:
# con 900px alcanza y el home baja de ~700 KB a ~350 KB.
CARD_W, CARD_H = 900, 506
CARD_QUALITY = 80

# La tira de miniaturas de modelo-nuevo.html las muestra a 100x74 px y las
# carga TODAS juntas al abrir la pagina, asi que ahi va una version chica:
# con 260px alcanza para retina y quedan en ~9 KB en vez de ~73 KB.
THUMB_W, THUMB_H = 260, 146
THUMB_QUALITY = 78

# nombre del archivo en imagenes/  ->  version en el configurador de VW
MAP = {
    'amarok blackstyle v6':      'Amarok > V6 Black Style',
    'amarok comfortline at 4x2': 'Amarok > Comfortline',
    'amarok comfortline mt 4x2': 'Amarok > Comfortline#2',
    'amarok comfortline v6':     'Amarok > V6 Comfortline',
    'amarok extreme v6':         'Amarok > V6 Extreme',
    'amarok hero v6':            'Amarok > V6 Hero',
    'amarok highline v6':        'Amarok > V6 Highline',
    'amarok trendline 4x2':      'Amarok > Trendline',

    'nivus comfortline':         'Nivus > Comfortline 200 TSI',
    'nivus highline':            'Nivus > Highline 200 TSI',
    'nivus outfit':              'Nivus > Highline Outfit 200 TSI',
    'nivus trendline':           'Nivus > Trendline 200 TSI',

    'polo comfortline':          'Polo > Comfortline',
    'polo highline':             'Polo > Highline',
    'polo track':                'Polo > Track',

    'saveiro comfortline':       'Saveiro > CD Comfortline',

    't-cross comfortline':       'T-Cross > Comfortline 200TSI',
    't-cross extreme':           'T-Cross > Extreme 200TSI',
    't-cross highline':          'T-Cross > Highline 200TSI',
    't-cross trendline at':      'T-Cross > Trendline 200TSI',
    't-cross trendline mt':      'T-Cross > Trendline 170TSI',
    'tcross-trendline-at':       'T-Cross > Trendline 200TSI',
    'tcross-trendline-mt':       'T-Cross > Trendline 170TSI',

    'taos comfortline':          'Taos > Comfortline 250TSI',
    'taos highline':             'Taos > Highline 250TSI',
    'taos highline bitono':      'Taos > Highline Bitono 250TSI',

    'tera comfort':              'Tera > Comfort',
    'tera high':                 'Tera > High',
    'tera outfit':               'Tera > Outfit',
    'tera trendline':            'Tera > Trend',

    'tiguan rline':              'Tiguan > R-Line',

    'vento gli':                 'Vento > GLI',

    # el sitio la llama MSI; en el configurador es la Sense
    'virtus MSI':                'Virtus > Sense',
    'virtus exclusive':          'Virtus > Exclusive',
    'virtus highline':           'Virtus > Highline',
    'virtus trendline':          'Virtus > Trendline',
}


def bajar_catalogo():
    """Devuelve {'Modelo > Version': url_del_render_3/4}."""
    req = urllib.request.Request(CONFIGURADOR, headers=UA)
    html = urllib.request.urlopen(req, timeout=90).read().decode('utf-8', 'replace')

    t = html
    for _ in range(3):
        t2 = unquote(t)
        if t2 == t:
            break
        t = t2
    t = t.replace(chr(92) + '"', '"').replace(chr(92) * 2, chr(92))

    i = t.find('"modelOverview"')
    if i < 0:
        raise SystemExit('no encontre modelOverview en el configurador; '
                         'VW debe haber cambiado la pagina')
    j = t.index('{', i)
    depth = 0
    for k in range(j, len(t)):
        if t[k] == '{':
            depth += 1
        elif t[k] == '}':
            depth -= 1
            if depth == 0:
                break
    data = json.loads(t[j:k + 1])

    catalogo = {}

    def walk(node, path):
        d = node.get('data') or {}
        p = path + [str(d.get('name') or node.get('nodeId'))]
        clave = ' > '.join(p)
        # dos versiones pueden llamarse igual (ej. Amarok Comfortline 4x4
        # manual y automatica); a la segunda le agregamos #2
        if clave in catalogo:
            n = 2
            while f'{clave}#{n}' in catalogo:
                n += 1
            clave = f'{clave}#{n}'
        url = ((d.get('media') or {}).get('firstLevelThreeQuarterView') or {}).get('url')
        if url:
            catalogo[clave] = url
        for c in (node.get('children') or []):
            walk(c, p)

    for m in data['models']:
        walk(m, [])
    return catalogo


def main():
    destino = os.path.join(RAIZ, sys.argv[1] if len(sys.argv) > 1 else 'imagenes-nuevas')
    os.makedirs(destino, exist_ok=True)

    print('leyendo el configurador de VW...')
    catalogo = bajar_catalogo()
    print(f'  {len(catalogo)} versiones con render 3/4')

    faltan = [v for v in MAP.values() if v not in catalogo]
    if faltan:
        raise SystemExit('estas versiones ya no estan en el configurador: '
                         + ', '.join(sorted(set(faltan))))

    cards = os.path.join(destino, 'cards')
    thumbs = os.path.join(destino, 'thumbs')
    os.makedirs(cards, exist_ok=True)
    os.makedirs(thumbs, exist_ok=True)

    total = 0
    total_card = 0
    total_thumb = 0
    for nombre, version in sorted(MAP.items()):
        req = urllib.request.Request(catalogo[version], headers=UA)
        crudo = urllib.request.urlopen(req, timeout=90).read()
        im = Image.open(__import__('io').BytesIO(crudo)).convert('RGBA')
        if im.size != (1920, 960):
            raise SystemExit(f'{version}: esperaba 1920x960 y vino {im.size}; '
                             'revisar CROP antes de seguir')
        recortada = im.crop(CROP)

        salida = os.path.join(destino, nombre + '.webp')
        recortada.resize((OUT_W, OUT_H), Image.LANCZOS).save(
            salida, 'WEBP', quality=QUALITY, method=6)
        n = os.path.getsize(salida)
        total += n

        tarjeta = os.path.join(cards, nombre + '.webp')
        recortada.resize((CARD_W, CARD_H), Image.LANCZOS).save(
            tarjeta, 'WEBP', quality=CARD_QUALITY, method=6)
        c = os.path.getsize(tarjeta)
        total_card += c

        mini = os.path.join(thumbs, nombre + '.webp')
        recortada.resize((THUMB_W, THUMB_H), Image.LANCZOS).save(
            mini, 'WEBP', quality=THUMB_QUALITY, method=6)
        m = os.path.getsize(mini)
        total_thumb += m

        print(f'  {nombre:<28} <- {version:<34} '
              f'{n//1024:>3} + {c//1024:>2} + {m//1024} KB')

    print(f'\ngaleria  {len(MAP)} fotos de {OUT_W}px en {destino}'
          f'  ·  {total//1024} KB')
    print(f'tarjetas {len(MAP)} fotos de {CARD_W}px en {cards}'
          f'  ·  {total_card//1024} KB')
    print(f'miniatur {len(MAP)} fotos de {THUMB_W}px en {thumbs}'
          f'  ·  {total_thumb//1024} KB')


if __name__ == '__main__':
    main()
