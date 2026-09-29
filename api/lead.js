// Función serverless (Vercel) para la landing de Plan de Ahorro.
// La landing postea acá (mismo dominio, sin token en el navegador); esta función
// agrega el token + area=plan_ahorro y reenvía al CRM. Así el token nunca queda
// expuesto en el cliente (Camino B).

const CRM_ENDPOINT = 'https://crm.titogonzalez.online/api/lead-externo'
// Guion largo (U+2013), igual que el resto de los origenes web del CRM.
const ORIGEN = 'Web – Plan de Ahorro'

module.exports = async (req, res) => {
  if (req.method === 'OPTIONS') {
    res.setHeader('Allow', 'POST, OPTIONS')
    return res.status(204).end()
  }
  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'Método no permitido' })
  }

  try {
    // Vercel parsea JSON automáticamente; por las dudas contemplamos string.
    const body = typeof req.body === 'string' ? JSON.parse(req.body || '{}') : (req.body || {})
    const { nombre, telefono, email, comentario, modelo, hp } = body
    // De donde vino el cliente (lo pone atribucion.js en el navegador). Se
    // reenvia tal cual: el CRM lo guarda en leads para poder atribuir el lead a
    // su click de Google y devolverle la conversion despues.
    const { gclid, utm_source, utm_medium, utm_campaign, utm_term, landing_page } = body

    // Honeypot: si viene relleno, es un bot. Respondemos OK pero no hacemos nada.
    if (hp) return res.status(200).json({ ok: true })

    if (!nombre || !telefono) {
      return res.status(400).json({ error: 'Nombre y teléfono son obligatorios' })
    }

    const token = process.env.LEAD_EXTERNO_TOKEN
    if (!token) {
      return res.status(503).json({ error: 'Endpoint no configurado (falta token)' })
    }

    const crmRes = await fetch(CRM_ENDPOINT, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Lead-Token': token,
      },
      body: JSON.stringify({
        nombre,
        telefono,
        email: email || null,
        modelo: modelo || null,
        comentario: comentario || null,
        origen: ORIGEN,
        area: 'plan_ahorro',
        gclid: gclid || null,
        utm_source: utm_source || null,
        utm_medium: utm_medium || null,
        utm_campaign: utm_campaign || null,
        utm_term: utm_term || null,
        landing_page: landing_page || null,
      }),
    })

    const data = await crmRes.json().catch(() => ({}))
    if (!crmRes.ok) {
      return res.status(crmRes.status).json({ error: data.error || 'Error al registrar el lead' })
    }
    return res.status(200).json({ ok: true, vendedor: data.vendedor || null })
  } catch (err) {
    return res.status(500).json({ error: 'Error interno' })
  }
}
