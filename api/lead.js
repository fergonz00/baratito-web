// Función serverless (Vercel) para la landing de Plan de Ahorro.
// La landing postea acá (mismo dominio, sin token en el navegador); esta función
// agrega el token + area=plan_ahorro y reenvía al CRM. Así el token nunca queda
// expuesto en el cliente (Camino B).

const CRM_ENDPOINT = 'https://crm.titogonzalez.online/api/lead-externo'
const ORIGEN = 'Envios Masivos'

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
        modelo: modelo || 'Amarok',
        comentario: comentario || null,
        origen: ORIGEN,
        area: 'plan_ahorro',
        via_em: true,
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
