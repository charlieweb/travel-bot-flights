<template>
  <div class="card bg-base-100 shadow-xl">
    <div class="card-body">
      <form @submit.prevent="handleSubmit" class="space-y-4">
        <!-- Airport Selection -->
        <div class="flex gap-4 items-end">
      <div class="flex-1">
        <label class="label">
          <span class="label-text font-semibold">From</span>
        </label>
        <AirportAutocomplete
          v-model="store.origin"
          placeholder="Search airport or city..."
        />
      </div>

      <SwapButton @click="swapLocations" />

      <div class="flex-1">
            <label class="label">
              <span class="label-text font-semibold">To</span>
            </label>
            <AirportAutocomplete
              v-model="store.destination"
              placeholder="Search airport or city..."
            />
          </div>
        </div>

        <!-- Date Selection -->
        <div class="flex gap-4 justify-between">
          <div class="flex-1">
            <label class="label">
              <span class="label-text font-semibold">Depart</span>
            </label>
            <DatePicker
              v-model="store.departDate"
              placeholder="Select departure date"
              :min="today"
            />
          </div>
          <div class="flex-1">
            <label class="label">
              <span class="label-text font-semibold">Return</span>
            </label>
            <DatePicker
              v-model="store.returnDate"
              placeholder="Select return date"
              :min="store.departDate || today"
            />
          </div>
        </div>

        <!-- Submit Button -->
        <button
          type="submit"
          class="btn btn-primary w-full"
          :disabled="store.loading || !store.origin || !store.destination"
        >
          <span v-if="store.loading" class="loading loading-spinner" />
          {{ store.loading ? 'Searching...' : 'Search Flights' }}
        </button>
      </form>
    </div>
  </div>
</template>

<script setup lang="ts">
import SwapButton from './SwapButton.vue'

const store = useTravelStore()

const today = new Date().toISOString().split('T')[0]

function swapLocations() {
  const temp = store.origin
  store.origin = store.destination
  store.destination = temp
}

async function handleSubmit() {
  if (!store.origin || !store.destination) return
  await store.search()
}
</script>