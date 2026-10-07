<template>
  <div
    v-if="store.results.length"
    class="mt-8 space-y-4"
  >
    <div class="flex flex-wrap items-center justify-between gap-3">
      <h2 class="text-2xl font-bold">Available Flights</h2>
      <div class="flex items-center gap-2">
        <span class="badge badge-lg">{{ visibleResults.length }} of {{ store.results.length }}</span>
        <button
          v-if="remaining > 0"
          type="button"
          class="btn btn-primary btn-sm"
          @click="loadMore"
        >
          Load more ({{ nextBatchSize }})
        </button>
      </div>
    </div>

    <div ref="listEl" class="space-y-4">
      <div
        v-for="option in visibleResults"
        :key="`${option.source_type}-${option.id}`"
        data-flight-card
        class="card bg-base-100 shadow-lg hover:shadow-xl transition-shadow"
      >
        <div class="card-body">
          <div class="flex justify-between items-start">
            <div>
              <div class="flex items-center gap-2">
                <h3 class="text-xl font-bold">{{ option.airline }}</h3>
                <span
                  v-if="option.source_type"
                  class="badge badge-sm"
                  :class="{
                    'badge-primary': option.source_type === 'airline',
                    'badge-secondary': option.source_type === 'aggregator',
                    'badge-neutral': option.source_type === 'search',
                  }"
                >
                  {{
                    option.source_type === 'airline'
                      ? 'Airline'
                      : option.source_type === 'aggregator'
                        ? 'Aggregator'
                        : 'Search'
                  }}
                </span>
              </div>
              <p class="text-sm text-base-content/60 mt-1">
                <span>{{ stopsLabel(option.stops) }}</span>
                <span v-if="option.duration"> · {{ option.duration }}</span>
              </p>
              <p
                v-if="option.depart_date || option.return_date"
                class="text-sm text-base-content/70 mt-1"
              >
                <span v-if="option.depart_date">Depart {{ formatDate(option.depart_date) }}</span>
                <span v-if="option.depart_date && option.return_date"> · </span>
                <span v-if="option.return_date">Return {{ formatDate(option.return_date) }}</span>
                <span
                  v-if="option.return_date"
                  class="badge badge-outline badge-xs ml-2 align-middle"
                >Round trip</span>
              </p>
            </div>
            <div class="text-right">
              <p v-if="option.price > 0.01" class="text-3xl font-bold text-primary">
                {{ formatUsdPrice(option.price) }}
              </p>
              <p v-else class="text-sm text-base-content/60">Price unavailable</p>
            </div>
          </div>

          <div class="flex items-center justify-between mt-6 pt-4 border-t border-base-200">
            <div class="text-center">
              <p class="text-2xl font-bold">{{ option.depart_time }}</p>
              <p class="text-sm text-base-content/60">Departure</p>
            </div>

            <div class="flex-1 mx-8 flex items-center">
              <div class="h-0.5 flex-1 bg-base-300"></div>
              <svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6 mx-2 text-primary" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
              </svg>
              <div class="h-0.5 flex-1 bg-base-300"></div>
            </div>

            <div class="text-center">
              <p class="text-2xl font-bold">{{ option.arrival_time }}</p>
              <p class="text-sm text-base-content/60">Arrival</p>
            </div>
          </div>

          <div class="card-actions justify-end mt-4 pt-4 border-t border-base-200">
            <a
              v-if="option.source_url"
              :href="getBookingUrl(option.source_url)"
              target="_blank"
              rel="noopener noreferrer"
              class="btn btn-primary btn-sm"
            >
              <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4 mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
              </svg>
              Select Flight
            </a>
            <button v-else class="btn btn-primary btn-sm" disabled>
              Select Flight
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useTravelStore } from '~/stores/travel'
import { formatUsdPrice, formatDate } from '~/lib'

const PAGE_SIZE = 10

const store = useTravelStore()
const listEl = useTemplateRef<HTMLElement>('listEl')
const visibleCount = shallowRef(PAGE_SIZE)

const visibleResults = computed(() => store.results.slice(0, visibleCount.value))
const remaining = computed(() => Math.max(store.results.length - visibleCount.value, 0))
const nextBatchSize = computed(() => Math.min(PAGE_SIZE, remaining.value))

watch(
  () => store.results.length,
  (count) => {
    if (count === 0) visibleCount.value = PAGE_SIZE
  },
)

async function loadMore() {
  const firstNewIndex = visibleCount.value
  visibleCount.value = Math.min(store.results.length, visibleCount.value + PAGE_SIZE)
  await nextTick()
  const card = listEl.value?.querySelectorAll<HTMLElement>('[data-flight-card]')[firstNewIndex]
  card?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

const getBookingUrl = (sourceUrl: string): string => sourceUrl || ''

function stopsLabel(stops: number): string {
  if (stops === 0) return 'Nonstop'
  return `${stops} stop${stops > 1 ? 's' : ''}`
}
</script>

