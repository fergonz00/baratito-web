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
import json
import os
import re
import subprocess
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



SPECS_JS = os.path.join(RAIZ, "specs.js")

# Siglas que no se capitalizan como una palabra cualquiera.
SIGLAS = {"msi", "tsi", "gli", "gts", "tdi", "at", "mt", "cs", "cd", "v6", "4x2", "4x4"}


def specs():
    """Lee specs.js. Es JavaScript (comillas simples, y strings con comillas dobles
    adentro como '10" con App-Connect'), asi que lo convierte node, no un regex."""
    codigo = (
        "const fs=require('fs');"
        "const src=fs.readFileSync(process.argv[1],'utf8');"
        r"const S=eval('('+src.replace(/^[\s\S]*?const SPECS\s*=\s*/,'').replace(/;\s*$/,'')+')');"
        "process.stdout.write(JSON.stringify(S));"
    )
    try:
        salida = subprocess.run(
            ["node", "-e", codigo, SPECS_JS], capture_output=True, text=True, encoding="utf-8", timeout=60
        )
    except FileNotFoundError:
        print("  aviso: sin node, las paginas salen sin ficha tecnica")
        return {}
    if salida.returncode != 0:
        print("  aviso: no pude leer specs.js, las paginas salen sin ficha tecnica")
        return {}
    return json.loads(salida.stdout)


def bloque_js(texto, marca):
    """Recorta un objeto JS ({...}) contando llaves, sin contar las que van dentro
    de un string. Sirve para sacar MODELS del molde sin evaluar todo el script."""
    i = texto.index(marca)
    j = texto.index("{", i)
    nivel, k, comilla, escape = 0, j, None, False
    while k < len(texto):
        c = texto[k]
        if escape:
            escape = False
        elif c == "\\":
            escape = True
        elif comilla:
            if c == comilla:
                comilla = None
        elif c in "'\"`":
            comilla = c
        elif c == "{":
            nivel += 1
        elif c == "}":
            nivel -= 1
            if nivel == 0:
                return texto[j:k + 1]
        k += 1
    raise ValueError("no pude recortar " + marca)


def a_json(codigo_js):
    # MODELS referencia CAMPAIGNS (las campañas del mes), que no viene en el recorte.
    # Un proxy que devuelve null para cualquier propiedad alcanza: de MODELS solo
    # queremos las specs.
    programa = (
        "const CAMPAIGNS = new Proxy({}, { get: () => null });"
        "const src = require('fs').readFileSync(0, 'utf8');"
        "process.stdout.write(JSON.stringify(eval('(' + src + ')')));"
    )
    salida = subprocess.run(
        ["node", "-e", programa],
        input=codigo_js, capture_output=True, text=True, encoding="utf-8", timeout=60,
    )
    if salida.returncode != 0:
        raise ValueError(salida.stderr[:200])
    return json.loads(salida.stdout)


def specs_del_molde(molde_txt):
    """El Polo NO esta en specs.js: sus specs viven inline en MODELS, dentro del
    molde. Sin esto quedaba como la unica pagina sin ficha tecnica."""
    try:
        modelos_js = a_json(bloque_js(molde_txt, "const MODELS"))
    except Exception as e:
        print("  aviso: no pude leer las specs inline del molde (%s)" % str(e)[:60])
        return {}
    fuera = {}
    for slug, m in modelos_js.items():
        versiones = {}
        for v in m.get("versions", []):
            if v.get("specs") and v.get("id"):
                versiones[v["id"]] = v["specs"]
        if versiones:
            fuera[slug] = versiones
    return fuera


FICHAS_API = "https://precios.titogonzalez.online/api/public/fichas"


def fichas_pdf():
    """Fichas tecnicas oficiales por modelo. Los PDF viven en el portal y son
    publicos; aca solo se enlazan."""
    try:
        import urllib.request
        with urllib.request.urlopen(FICHAS_API, timeout=20) as r:
            d = json.loads(r.read().decode("utf-8"))
        return d.get("modelos", {}) if d.get("ok") else {}
    except Exception as e:
        print("  aviso: no pude traer las fichas tecnicas (%s)" % str(e)[:60])
        return {}


def bloque_fichas(nombre, lista):
    if not lista:
        return ""
    items = []
    for f in lista:
        titulo = f.get("titulo") or nombre
        tipo = "Comparativo de versiones" if f.get("tipo") == "comparativo" else "Ficha de versión"
        paginas = f.get("paginas")
        detalle = "PDF" + (", %s páginas" % paginas if paginas else "")
        items.append(
            '<li><a href="%s" target="_blank" rel="noopener">%s — %s</a> <span>(%s)</span></li>'
            % (escapar(f.get("url")), escapar(titulo), tipo, detalle)
        )
    return (
        '\n<section class="fichas-pdf">'
        "<h2>Fichas técnicas oficiales del Volkswagen %s</h2>"
        "<p>Material de Volkswagen Argentina, con el detalle completo de cada versión.</p>"
        "<ul>%s</ul></section>\n"
    ) % (escapar(nombre), "".join(items))


ESTILO_FICHAS_PDF = """
    .fichas-pdf { padding: 28px 16px; }
    .fichas-pdf h2 { font-size: 19px; font-weight: 800; color: var(--vw-blue, #001E50); letter-spacing: -0.4px; }
    .fichas-pdf > p { font-size: 13px; color: var(--grey-700, #4A4A4A); margin-top: 6px; }
    .fichas-pdf ul { list-style: none; margin-top: 12px; padding: 0; }
    .fichas-pdf li { padding: 10px 0; border-bottom: 1px solid var(--grey-200, #EBEBEB); font-size: 13.5px; }
    .fichas-pdf a { color: var(--vw-blue, #001E50); font-weight: 600; text-decoration: none; }
    .fichas-pdf span { color: var(--grey-500, #8A8A8A); font-size: 12px; }
    @media (min-width: 900px) { .fichas-pdf { padding: 40px; } }
"""


def linda(clave):
    partes = re.split(r"[-_ ]", clave)
    return " ".join(p.upper() if p.lower() in SIGLAS else p.capitalize() for p in partes)


def ficha_tecnica(nombre, versiones):
    """El texto que Google no veia: lo pintaba el JS y quedaban 222 palabras por pagina."""
    if not versiones:
        return ""
    bloques = []
    for clave, v in versiones.items():
        m = v.get("motor") or {}
        partes = []
        motor = " ".join(x for x in [m.get("nombre"), m.get("subtitulo")] if x)
        if motor:
            partes.append("<p>Motor %s.</p>" % escapar(motor))
        potencia = ", ".join(
            x for x in [m.get("potencia"), " ".join(y for y in [m.get("torque"), m.get("torqueRpm")] if y)] if x
        )
        mecanica = ". ".join(x for x in [potencia, m.get("caja"), m.get("traccion")] if x)
        if mecanica:
            partes.append("<p>%s.</p>" % escapar(mecanica))
        for etiqueta, campo in (
            ("Equipamiento destacado", "destacados"),
            ("Seguridad", "seguridad"),
            ("Confort", "confort"),
            ("Exterior", "exterior"),
            ("Tecnologia", "tecnologia"),
        ):
            items = v.get(campo) or []
            if items:
                partes.append(
                    "<p><b>%s:</b> %s.</p>" % (etiqueta, escapar(" · ".join(items)))
                )
        if partes:
            bloques.append(
                "<article><h3>%s %s</h3>%s</article>" % (escapar(nombre), escapar(linda(clave)), "".join(partes))
            )
    if not bloques:
        return ""
    return (
        '\n<section class="ficha-seo">'
        "<h2>Ficha técnica del Volkswagen %s</h2>%s"
        '<p class="ficha-nota">Datos de los flyers oficiales de Volkswagen Argentina. '
        "El equipamiento puede variar según la versión y la disponibilidad.</p>"
        "</section>\n"
    ) % (escapar(nombre), "".join(bloques))


def escapar(t):
    return str(t).replace("&", "&amp;").replace("<", "&lt;")


ESTILO_FICHA = """
    .ficha-seo { padding: 28px 16px; background: var(--grey-100, #F5F5F5); }
    .ficha-seo h2 { font-size: 19px; font-weight: 800; color: var(--vw-blue, #001E50); letter-spacing: -0.4px; }
    .ficha-seo article { background: #fff; border-radius: 12px; padding: 14px; margin-top: 12px; }
    .ficha-seo h3 { font-size: 15px; font-weight: 700; color: var(--vw-blue, #001E50); }
    .ficha-seo p { font-size: 13px; color: var(--grey-700, #4A4A4A); line-height: 1.55; margin-top: 6px; }
    .ficha-seo .ficha-nota { font-size: 11.5px; color: var(--grey-500, #8A8A8A); margin-top: 14px; }
    @media (min-width: 900px) { .ficha-seo { padding: 40px; } .ficha-seo article { padding: 20px; } }
"""


def generar():
    molde = open(MOLDE, "rb").read()
    firma = hashlib.sha1(molde).hexdigest()[:12]
    os.makedirs(SALIDA, exist_ok=True)
    hechos = []
    todas = specs()
    # La pagina hace lo mismo: si una version tiene specs inline, se respetan.
    for slug, versiones in specs_del_molde(molde.decode("utf-8")).items():
        todas.setdefault(slug, {}).update(versiones)
    sin_ficha = []
    pdfs = fichas_pdf()

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

        # La ficha tecnica, como TEXTO. Antes solo la pintaba el JS y cada pagina
        # tenia 222 palabras para Google.
        ficha = ficha_tecnica(nombre, todas.get(slug))
        if ficha:
            h = h.replace(b"</style>", ESTILO_FICHA.encode("utf-8") + b"  </style>", 1)
            marca = b'<nav class="nav-pie"'
            if marca in h:
                h = h.replace(marca, ficha.encode("utf-8") + marca, 1)
            else:
                i = h.rindex(b"</body>")
                h = h[:i] + ficha.encode("utf-8") + h[i:]
        else:
            sin_ficha.append(slug)

        # Las fichas oficiales en PDF, que ya estaban en el portal y no se ofrecian
        # en ningun lado de la web.
        bloque = bloque_fichas(nombre, pdfs.get(nombre))
        if bloque:
            h = h.replace(b"</style>", ESTILO_FICHAS_PDF.encode("utf-8") + b"  </style>", 1)
            marca = b'<nav class="nav-pie"'
            if marca in h:
                h = h.replace(marca, bloque.encode("utf-8") + marca, 1)
            else:
                i = h.rindex(b"</body>")
                h = h[:i] + bloque.encode("utf-8") + h[i:]

        destino = os.path.join(SALIDA, slug + ".html")
        open(destino, "wb").write(h)
        hechos.append(slug)

    open(os.path.join(SALIDA, ".molde"), "w").write(firma)
    print("generadas %d paginas en m/ (molde %s):" % (len(hechos), firma))
    print("  " + ", ".join(hechos))
    if sin_ficha:
        print("  sin ficha tecnica (no estan en specs.js): " + ", ".join(sin_ficha))


if __name__ == "__main__":
    generar()
