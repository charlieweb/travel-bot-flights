<template>
  <div class="dropdown w-full" :class="{ 'dropdown-open': showDropdown && filteredAirports.length > 0 }">
    <div class="form-control w-full">
      <div class="relative">
        <input
          ref="inputRef"
          v-model="searchQuery"
          type="text"
          :placeholder="placeholder"
          class="input input-bordered w-full"
          @input="handleInput"
          @focus="showDropdown = true"
          @blur="handleBlur"
          @keydown.down.prevent="highlightNext"
          @keydown.up.prevent="highlightPrev"
          @keydown.enter.prevent="selectHighlighted"
          @keydown.esc="showDropdown = false"
        />
        <div v-if="loading" class="absolute right-3 top-1/2 -translate-y-1/2">
          <span class="loading loading-spinner loading-sm text-primary" />
        </div>
        <div v-else-if="selectedAirport" class="absolute right-3 top-1/2 -translate-y-1/2 text-sm text-success font-medium">
          {{ selectedAirport.code }}
        </div>
      </div>
    </div>

    <ul
      v-if="showDropdown && filteredAirports.length > 0"
      class="dropdown-content z-1 menu p-2 shadow bg-base-100 rounded-box w-full max-h-60 overflow-auto border border-base-300"
    >
      <li
        v-for="(airport, index) in filteredAirports"
        :key="airport.code"
        :class="['cursor-pointer', index === highlightedIndex ? 'bg-primary/10' : 'hover:bg-base-200']"
      >
        <div @click.prevent="selectAirport(airport)" class="block py-2 px-3">
          <div class="flex items-center gap-2">
            <span class="font-bold text-primary">{{ airport.code }}</span>
            <span class="text-sm">{{ airport.name }}</span>
          </div>
          <div class="text-xs text-base-content/60 truncate">
            {{ airport.city }}, {{ airport.country }}
          </div>
        </div>
      </li>
    </ul>

    <div
      v-if="showDropdown && searchQuery.length >= 2 && filteredAirports.length === 0 && !loading"
      class="dropdown-content p-4 shadow bg-base-100 rounded-box w-full border border-base-300"
    >
      <p class="text-sm text-base-content/60">No airports found</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { Airport } from '~/lib'

interface Props {
  modelValue: string
  placeholder?: string
}

const props = defineProps<Props>()

const emit = defineEmits<{
  'update:modelValue': [value: string]
}>()

const inputRef = useTemplateRef<HTMLInputElement>('inputRef')

// State
const searchQuery = shallowRef('')
const airports = shallowRef<Airport[]>([])
const showDropdown = shallowRef(false)
const loading = shallowRef(false)
const highlightedIndex = shallowRef(-1)
const selectedAirport = shallowRef<Airport | null>(null)

// Debounce timer + in-flight abort
let fetchTimeout: ReturnType<typeof setTimeout> | null = null
let fetchAbort: AbortController | null = null

onBeforeUnmount(() => {
  if (fetchTimeout) clearTimeout(fetchTimeout)
  fetchAbort?.abort()
})

// Computed: sorted airports
const filteredAirports = computed(() => {
  if (!searchQuery.value || searchQuery.value.length < 2) return []

  const query = searchQuery.value.toLowerCase()

  return [...airports.value].sort((a, b) => {
    const aCode = a.code.toLowerCase()
    const bCode = b.code.toLowerCase()
    const aCity = a.city.toLowerCase()
    const bCity = b.city.toLowerCase()

    // Exact match
    if (aCode === query) return -1
    if (bCode === query) return 1

    // Code starts with
    if (aCode.startsWith(query) && !bCode.startsWith(query)) return -1
    if (bCode.startsWith(query) && !aCode.startsWith(query)) return 1

    // City starts with
    if (aCity.startsWith(query) && !bCity.startsWith(query)) return -1
    if (bCity.startsWith(query) && !aCity.startsWith(query)) return 1

    return 0
  })
})

// Methods
const fetchAirports = async () => {
  const query = searchQuery.value
  if (query.length < 2) {
    loading.value = false
    airports.value = []
    return
  }

  fetchAbort?.abort()
  fetchAbort = new AbortController()
  const signal = fetchAbort.signal

  loading.value = true
  showDropdown.value = true

  try {
    const response = await $fetch<Airport[]>('/api/airports', {
      query: { query },
      signal,
    })
    if (!signal.aborted) {
      airports.value = response
    }
  } catch (error) {
    if (signal.aborted) return
    console.error('Failed to fetch airports:', error)
    airports.value = []
  } finally {
    if (!signal.aborted) {
      loading.value = false
    }
  }
}

const handleInput = () => {
  highlightedIndex.value = -1
  selectedAirport.value = null

  if (fetchTimeout) clearTimeout(fetchTimeout)

  if (searchQuery.value.length >= 2) {
    fetchTimeout = setTimeout(fetchAirports, 300)
  } else {
    loading.value = false
    airports.value = []
  }
}

const selectAirport = (airport: Airport) => {
  selectedAirport.value = airport
  searchQuery.value = `${airport.city} (${airport.code})`
  emit('update:modelValue', airport.code)
  showDropdown.value = false
  highlightedIndex.value = -1
  airports.value = []
  if (fetchTimeout) clearTimeout(fetchTimeout)
}

const handleBlur = () => {
  setTimeout(() => {
    showDropdown.value = false
  }, 200)
}

const highlightNext = () => {
  if (highlightedIndex.value < filteredAirports.value.length - 1) {
    highlightedIndex.value++
  }
}

const highlightPrev = () => {
  if (highlightedIndex.value > 0) {
    highlightedIndex.value--
  }
}

const selectHighlighted = () => {
  const airport = filteredAirports.value[highlightedIndex.value]
  if (airport) selectAirport(airport)
}

// Watch for external modelValue changes
watch(
  () => props.modelValue,
  async (newValue, oldValue) => {
    if (newValue === oldValue) return

    if (!newValue) {
      searchQuery.value = ''
      selectedAirport.value = null
      return
    }

    if (newValue === selectedAirport.value?.code) return

    selectedAirport.value = null
    loading.value = false

    if (/^[A-Za-z]{3}$/.test(newValue)) {
      searchQuery.value = newValue.toUpperCase()
      return
    }

    try {
      const response = await $fetch<Airport[]>('/api/airports', {
        query: { query: newValue },
      })

      const matchingAirport = response.find((a) => a.code === newValue)
      if (matchingAirport) {
        selectedAirport.value = matchingAirport
        searchQuery.value = `${matchingAirport.city} (${matchingAirport.code})`
      } else {
        searchQuery.value = newValue
      }
    } catch {
      searchQuery.value = newValue
      selectedAirport.value = null
    }
  },
  { immediate: true }
)
</script>