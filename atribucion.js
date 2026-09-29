/**
 * De dónde vino el que está mirando la página.
 *
 * Guarda el `gclid` (el identificador del click de Google Ads) y los `utm_*` la
 * primera vez que alguien entra, y los devuelve después, cuando completa el
 * formulario. Hay que guardarlos porque casi nadie completa en la misma página
 * en la que cayó: entra por /polo, mira dos modelos y recién ahí deja el dato.
 * Si lo leyéramos de la URL en ese momento, el gclid ya no está.
 *
 * Con esto el lead queda pegado a su click, y eso sirve para dos cosas:
 *   1. Saber cuánto cuesta DE VERDAD un lead de Google (hoy se estima por
 *      origen, que mezcla el pago con el orgánico y el directo).
 *   2. Devolverle a Google las conversiones que valen (el lead que terminó en
 *      una charla comercial, no el que sólo mandó el formulario), para que la
 *      puja automática busque gente parecida a la que compra.
 *
 * Dura 90 días, igual que la ventana de atribución de Google.
 * Se usa así, en el body que va al CRM:  ...atribucion()
 */
(function () {
  'use strict';

  var CLAVE = 'tga_atrib';
  var DIAS = 90;

  // iOS y los bloqueadores rompen el gclid; Google manda gbraid/wbraid en su
  // lugar. Se guardan los tres: el que venga.
  var CAMPOS = ['gclid', 'gbraid', 'wbraid', 'utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content'];

  function leerGuardado() {
    try {
      var cruda = localStorage.getItem(CLAVE);
      if (!cruda) return null;
      var d = JSON.parse(cruda);
      if (!d || !d.ts) return null;
      if (Date.now() - d.ts > DIAS * 86400000) {
        localStorage.removeItem(CLAVE);
        return null;
      }
      return d;
    } catch (e) {
      // Modo incógnito o storage bloqueado: no es un error, simplemente no hay.
      return null;
    }
  }

  function deLaUrl() {
    var p;
    try {
      p = new URLSearchParams(location.search);
    } catch (e) {
      return null;
    }
    var d = null;
    for (var i = 0; i < CAMPOS.length; i++) {
      var v = p.get(CAMPOS[i]);
      if (v) {
        d = d || {};
        d[CAMPOS[i]] = v.slice(0, 500);
      }
    }
    if (d) {
      d.ts = Date.now();
      d.landing = (location.origin + location.pathname).slice(0, 500);
      // Sin gclid ni utm_source, el navegador es lo único que dice de dónde vino.
      if (document.referrer) d.referrer = document.referrer.slice(0, 500);
    }
    return d;
  }

  // La visita de ahora gana sobre la guardada: si vuelve por otro anuncio, el
  // lead es de ese anuncio nuevo. Si esta visita no trae nada, se conserva la
  // anterior — así el que entró por Google y volvió tipeando la dirección sigue
  // contando para Google, que es lo que hace Google también.
  var actual = deLaUrl();
  if (actual) {
    try {
      localStorage.setItem(CLAVE, JSON.stringify(actual));
    } catch (e) {
      /* sin storage: vale para esta página igual */
    }
  }
  var datos = actual || leerGuardado();

  /**
   * Lo que hay que mandarle al CRM. Devuelve {} si no se sabe nada, así se puede
   * esparcir en cualquier payload sin romperlo.
   */
  window.atribucion = function () {
    if (!datos) return {};
    return {
      gclid: datos.gclid || datos.gbraid || datos.wbraid || null,
      utm_source: datos.utm_source || null,
      utm_medium: datos.utm_medium || null,
      utm_campaign: datos.utm_campaign || null,
      utm_term: datos.utm_term || null,
      landing_page: datos.landing || null,
    };
  };
})();
