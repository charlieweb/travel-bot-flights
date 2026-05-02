import { defineStore } from 'pinia'
import type { TravelOption, SearchState } from '~/lib'

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
    async search() {
      this.loading = true
      this.error = ''
      this.results = []

      try {
        const response = await $fetch<TravelOption[]>('/api/search_travel', {
          method: 'POST',
          body: {
            origin: this.origin,
            destination: this.destination,
            depart_date: this.departDate,
            return_date: this.returnDate || null,
          },
        })
        this.results = response
      } catch (e: unknown) {
        this.error = e instanceof Error ? e.message : 'Failed to fetch travel options'
      } finally {
        this.loading = false
      }
    },
  },
})