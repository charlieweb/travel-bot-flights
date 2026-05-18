import { defineStore } from 'pinia'
import type { TravelOption, SearchState } from '~/lib'

function sortOptions(options: TravelOption[]): TravelOption[] {
  return [...options].sort((a, b) => {
    const pa = a.price > 0 ? a.price : 99999
    const pb = b.price > 0 ? b.price : 99999
    return pa - pb
  })
}

export const useTravelStore = defineStore('travel', {
  state: (): SearchState => ({
    origin: '',
    destination: '',
    departDate: '',
    returnDate: '',
    results: [],
    loading: false,
    error: '',
  }),
  actions: {
    setSearch(data: { origin: string; destination: string; departDate: string; returnDate: string }) {
      this.origin = data.origin
      this.destination = data.destination
      this.departDate = data.departDate
      this.returnDate = data.returnDate
    },
    mergeResults(incoming: TravelOption[], source?: string) {
      const hasRealFares = incoming.some(
        (o) => o.source_type !== 'search' && o.price > 0,
      )

      if (source === 'fallback') {
        this.results = sortOptions(incoming)
        return
      }

      const existing = hasRealFares
        ? this.results.filter((o) => o.source_type !== 'search')
        : this.results

      const mergeKey = (o: TravelOption) => `${o.source_type ?? 'unknown'}-${o.id}`
      const byId = new Map(existing.map((r) => [mergeKey(r), r]))
      for (const option of incoming) {
        if (hasRealFares && option.source_type === 'search') continue
        byId.set(mergeKey(option), option)
      }
      this.results = sortOptions(Array.from(byId.values()))
    },
    async search() {
      this.loading = true
      this.error = ''
      this.results = []

      const body = {
        origin: this.origin,
        destination: this.destination,
        depart_date: this.departDate,
        return_date: this.returnDate || null,
      }

      try {
        await this.searchStream(body)
      } catch {
        try {
          await this.searchSync(body)
        } catch (syncErr) {
          this.error =
            syncErr instanceof Error ? syncErr.message : 'Search failed'
        }
      } finally {
        this.loading = false
      }
    },
    handleStreamEvent(event: {
      event?: string
      options?: TravelOption[]
      message?: string
      source?: string
    }): boolean {
      if (event.event === 'chunk' && event.options?.length) {
        this.mergeResults(event.options, event.source)
        if (this.results.length > 0) {
          this.loading = false
        }
        return false
      }
      if (event.event === 'error') {
        this.error = event.message || 'Search failed'
        return true
      }
      if (event.event === 'done') {
        return true
      }
      return false
    },
    async searchStream(body: Record<string, unknown>) {
      const controller = new AbortController()
      const timeoutId = setTimeout(() => controller.abort(), 300_000)

      try {
        const response = await fetch('/api/search_travel/stream', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body),
          signal: controller.signal,
        })

        if (!response.ok || !response.body) {
          throw new Error(`Stream search failed (${response.status})`)
        }

        const reader = response.body.getReader()
        const decoder = new TextDecoder()
        let buffer = ''
        let streamDone = false

        const processSseBuffer = () => {
          const parts = buffer.split('\n\n')
          buffer = parts.pop() || ''
          for (const part of parts) {
            for (const line of part.split('\n')) {
              if (!line.startsWith('data: ')) continue
              try {
                const event = JSON.parse(line.slice(6)) as {
                  event?: string
                  options?: TravelOption[]
                  message?: string
                  source?: string
                }
                if (this.handleStreamEvent(event)) {
                  streamDone = true
                }
              } catch {
                // ignore malformed SSE lines
              }
            }
          }
        }

        while (!streamDone) {
          const { done, value } = await reader.read()
          if (done) break
          buffer += decoder.decode(value, { stream: true })
          processSseBuffer()
        }

        processSseBuffer()

        if (!this.results.length) {
          throw new Error('No results from stream')
        }
      } finally {
        clearTimeout(timeoutId)
      }
    },
    async searchSync(body: Record<string, unknown>) {
      const response = await $fetch<TravelOption[]>('/api/search_travel', {
        method: 'POST',
        body,
        timeout: 90_000,
      })
      this.results = sortOptions(response)
    },
  },
})
