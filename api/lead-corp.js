// Función serverless (Vercel) para la página de Ventas Corporativas.
// Igual que /api/lead pero con su propio origen: la landing postea acá (mismo
// dominio, sin token en el navegador) y esta función agrega el token y reenvía
// al CRM. Así el token nunca queda expuesto en el cliente.
//
// El origen tiene guion largo (U+2013) como el resto de los origenes web, y
// existe una regla de asignacion propia que rota entre Ines y Marta: sin eso el
// lead caeria en la rueda general de 0km, con un vendedor de mostrador.

const CRM_ENDPOINT = 'https://crm.titogonzalez.online/api/lead-externo'
const ORIGEN = 'Web – Ventas Corporativas'

module.exports = async (req, res) => {
  if (req.method === 'OPTIONS') {
    res.setHeader('Allow', 'POST, OPTIONS')
    return res.status(204).end()
  }
  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'Método no permitido' })
  }

  try {
    const body = typeof req.body === 'string' ? JSON.parse(req.body || '{}') : (req.body || {})
    const { nombre, telefono, email, empresa, cuit, unidades, modelo, comentario, hp } = body

    // Honeypot: si viene relleno, es un bot. Respondemos OK pero no hacemos nada.
    if (hp) return res.status(200).json({ ok: true })

    if (!nombre || !telefono) {
      return res.status(400).json({ error: 'Nombre y teléfono son obligatorios' })
    }

    const token = process.env.LEAD_EXTERNO_TOKEN
    if (!token) {
      return res.status(503).json({ error: 'Endpoint no configurado (falta token)' })
    }

    // El CRM no tiene campos de empresa, asi que lo que define al lead corporativo
    // (razon social, CUIT y cuantas unidades) va en el comentario, que es lo primero
    // que ve el vendedor al abrir la ficha.
    const partes = []
    if (empresa) partes.push('Empresa: ' + empresa)
    if (cuit) partes.push('CUIT: ' + cuit)
    if (unidades) partes.push('Unidades: ' + unidades)
    if (modelo) partes.push('Modelo: ' + modelo)
    if (comentario) partes.push(comentario)

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
        comentario: partes.join(' · ') || null,
        origen: ORIGEN,
        area: 'convencional',
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
