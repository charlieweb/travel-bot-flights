import { defineEventHandler, readBody, setResponseHeaders } from 'h3'

export default defineEventHandler(async (event) => {
  const body = await readBody(event)
  const apiBase = process.env.NUXT_INTERNAL_API_BASE || 'http://localhost:8000'

  const response = await fetch(`${apiBase}/api/search_travel/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    signal: AbortSignal.timeout(300_000),
  })

  if (!response.ok || !response.body) {
    throw createError({
      statusCode: response.status || 500,
      statusMessage: `Stream search failed (${response.status})`,
    })
  }

  setResponseHeaders(event, {
    'Content-Type': 'text/event-stream',
    'Cache-Control': 'no-cache',
    Connection: 'keep-alive',
    'X-Accel-Buffering': 'no',
  })

  return response.body
})
