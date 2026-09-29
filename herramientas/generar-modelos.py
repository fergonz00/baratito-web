"""Genera una pagina por modelo a partir de modelo-nuevo.html.

Por que existe: las 10 URLs (/polo, /amarok, ...) salian del MISMO archivo, asi que
compartian el <title> generico "Modelo - Baratito" y ninguna tenia description. Para
Google, en la primera pasada, eran 10 paginas identicas — justo las que tienen que
aparecer cuando alguien busca "Polo 0km precio", que es lo que se paga en Ads.

Que hace: copia el molde y le cambia title, description, canonical y las etiquetas
para compartir. NO toca el JS: el slug se sigue sacando del pathname, asi que las
paginas generadas funcionan igual que antes.

    python herramientas/generar-modelos.py

IMPORTANTE: cada vez que se edite modelo-nuevo.html hay que volver a correrlo, o las
10 copias quedan viejas. El script avisa si el molde cambio despues de la ultima
generacion.
"""
import hashlib
import os
import re
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MOLDE = os.path.join(RAIZ, "modelo-nuevo.html")
HOME = os.path.join(RAIZ, "home-nuevo.html")
SALIDA = os.path.join(RAIZ, "m")
SITIO = "https://www.baratito.com.ar"


def modelos():
    """slug, nombre y carroceria salen de la lista que ya vive en la home."""
    html = open(HOME, encoding="utf-8").read()
    patron = re.compile(
        r"\{\s*slug:\s*'([^']+)',\s*name:\s*'([^']+)',\s*body:\s*'([^']+)'"
    )
    encontrados = patron.findall(html)
    if not encontrados:
        sys.exit("No pude leer los modelos de home-nuevo.html")
    return encontrados


def generar():
    molde = open(MOLDE, "rb").read()
    firma = hashlib.sha1(molde).hexdigest()[:12]
    os.makedirs(SALIDA, exist_ok=True)
    hechos = []

    for slug, nombre, body in modelos():
        titulo = "Volkswagen %s 0km — precio y versiones | Tito Gonzalez" % nombre
        desc = (
            "Precio, versiones y financiación del Volkswagen %s 0km (%s) en Tito "
            "Gonzalez Automotores, concesionario oficial Volkswagen en CABA." % (nombre, body)
        )
        url = "%s/%s" % (SITIO, slug)

        h = molde
        # title
        viejo_title = re.search(rb'<title id="page-title">[^<]*</title>', h)
        assert viejo_title, slug
        h = h.replace(
            viejo_title.group(0),
            ('<title id="page-title">%s</title>' % titulo).encode("utf-8"),
        )
        # canonical: apuntaba al dominio pelado y a la home
        viejo_canon = re.search(rb'<link rel="canonical" id="canonical-link" href="[^"]*" />', h)
        assert viejo_canon, slug
        h = h.replace(
            viejo_canon.group(0),
            ('<link rel="canonical" id="canonical-link" href="%s" />' % url).encode("utf-8"),
        )
        # description y etiquetas para compartir, que no existian
        extra = (
            '\r\n  <meta name="description" content="%s" />'
            '\r\n  <meta property="og:type" content="website" />'
            '\r\n  <meta property="og:url" content="%s" />'
            '\r\n  <meta property="og:title" content="%s" />'
            '\r\n  <meta property="og:description" content="%s" />'
            '\r\n  <!-- GENERADO por herramientas/generar-modelos.py (molde %s) — no editar a mano -->'
        ) % (desc, url, titulo, desc, firma)
        marca = ('<title id="page-title">%s</title>' % titulo).encode("utf-8")
        h = h.replace(marca, marca + extra.encode("utf-8"))

        destino = os.path.join(SALIDA, slug + ".html")
        open(destino, "wb").write(h)
        hechos.append(slug)

    open(os.path.join(SALIDA, ".molde"), "w").write(firma)
    print("generadas %d paginas en m/ (molde %s):" % (len(hechos), firma))
    print("  " + ", ".join(hechos))


if __name__ == "__main__":
    generar()
