import { createError, defineEventHandler, getQuery } from 'h3'

export default defineEventHandler(async (event) => {
  const { query } = getQuery(event)
  const apiBase = process.env.NUXT_INTERNAL_API_BASE || 'http://localhost:8000'

  try {
    return await $fetch(`${apiBase}/api/airports`, {
      query: { query },
      timeout: 10_000,
    })
  } catch (error: unknown) {
    const err = error as { response?: { status?: number }; message?: string }
    throw createError({
      statusCode: err?.response?.status || 500,
      statusMessage: err?.message || 'Failed to fetch airports',
    })
  }
})
