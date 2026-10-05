<template>
  <div class="card bg-base-100 shadow-xl">
    <div class="card-body">
      <form @submit.prevent="handleSubmit" class="space-y-4">
        <div>
          <label class="label">
            <span class="label-text font-semibold">Where would you like to go?</span>
          </label>
          <input
            v-model="query"
            type="text"
            class="input input-bordered w-full"
            placeholder="e.g. London to Tokyo, leaving Dec 10, back Dec 20"
            :disabled="store.parsing || store.loading"
            required
          />
        </div>

        <button
          type="submit"
          class="btn btn-primary w-full"
          :disabled="busy || !query.trim()"
        >
          <span v-if="busy" class="loading loading-spinner" />
          {{ store.parsing ? 'Understanding…' : store.loading ? 'Searching…' : 'Search Flights' }}
        </button>
      </form>

      <p
        v-if="store.origin && store.destination"
        class="text-sm text-base-content/70 text-center"
      >
        ✈️ {{ store.origin }} → {{ store.destination }}
        <template v-if="store.departDate">
          · {{ formatDate(store.departDate) }}
          <template v-if="store.returnDate">
            → {{ formatDate(store.returnDate) }} (round trip)
          </template>
          <template v-else> (one way)</template>
        </template>
      </p>

      <div
        v-if="store.origin && store.destination"
        class="flex justify-between text-center text-sm text-base-content/60"
      >
        <div>
          <p class="font-semibold text-base-content">Departure</p>
          <p>{{ store.originAirport?.name || store.origin }}</p>
          <p v-if="store.originAirport?.country">{{ formatCountry(store.originAirport.country) }}</p>
        </div>
        <div>
          <p class="font-semibold text-base-content">Arrival</p>
          <p>{{ store.destinationAirport?.name || store.destination }}</p>
          <p v-if="store.destinationAirport?.country">{{ formatCountry(store.destinationAirport.country) }}</p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { formatDate, formatCountry } from '~/lib'

const store = useTravelStore()
const query = ref(store.query)

const busy = computed(() => store.parsing || store.loading)

async function handleSubmit() {
  await store.parseAndSearch(query.value)
}
</script>
