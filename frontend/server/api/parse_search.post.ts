import { defineEventHandler, readBody } from 'h3'

export default defineEventHandler(async (event) => {
  const body = await readBody(event)

  // Read from environment at runtime (not build time)
  const apiBase = process.env.NUXT_INTERNAL_API_BASE || 'http://localhost:8000'

  try {
    const response = await $fetch(`${apiBase}/api/parse_search`, {
      method: 'POST',
      body,
      timeout: 30_000,
    })
    return response
  } catch (error: any) {
    throw createError({
      statusCode: error?.response?.status || 500,
      statusMessage: error?.message || 'Failed to parse search query',
    })
  }
})
