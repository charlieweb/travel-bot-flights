<template>
  <div class="form-control w-full">
    <button
      type="button"
      :popovertarget="popoverId"
      class="input input-bordered w-full flex items-center justify-between"
      :style="`anchor-name:--${popoverId}`"
    >
      <span :class="{ 'opacity-50': !modelValue }">
        {{ displayValue || placeholder }}
      </span>
      <svg
        class="w-5 h-5 opacity-50"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
      >
        <path
          stroke-linecap="round"
          stroke-linejoin="round"
          stroke-width="2"
          d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"
        />
      </svg>
    </button>

    <div
      :id="popoverId"
      popover
      class="dropdown bg-base-100 rounded-box shadow-lg z-50 p-4"
      :style="`position-anchor:--${popoverId}`"
    >
      <calendar-date
        :value="callyDate"
        class="cally"
        @change="handleDateChange"
      >
        <svg
          slot="previous"
          aria-label="Previous"
          class="w-4 h-4"
          viewBox="0 0 24 24"
        >
          <path fill="currentColor" d="M15.75 19.5 8.25 12l7.5-7.5" />
        </svg>
        <svg
          slot="next"
          aria-label="Next"
          class="w-4 h-4"
          viewBox="0 0 24 24"
        >
          <path fill="currentColor" d="m8.25 4.5 7.5 7.5-7.5 7.5" />
        </svg>
        <calendar-month />
      </calendar-date>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import 'cally'

interface Props {
  modelValue: string
  placeholder?: string
}

const props = withDefaults(defineProps<Props>(), {
  placeholder: 'Select a date',
})

const emit = defineEmits<{
  'update:modelValue': [value: string]
}>()

const popoverId = `date-picker-${Math.random().toString(36).slice(2, 9)}`

const callyDate = computed(() => {
  if (!props.modelValue) return undefined
  const date = new Date(props.modelValue + 'T12:00:00')
  return date
})

const displayValue = computed(() => {
  if (!props.modelValue) return ''
  const date = new Date(props.modelValue + 'T00:00:00')
  return date.toLocaleDateString('en-US', {
    weekday: 'short',
    month: 'short',
    day: 'numeric',
  })
})

function handleDateChange(event: Event) {
  const customEvent = event as CustomEvent
  let value = ''

  if (customEvent.detail) {
    if (customEvent.detail instanceof Date) {
      const d = customEvent.detail
      const year = d.getUTCFullYear()
      const month = String(d.getUTCMonth() + 1).padStart(2, '0')
      const day = String(d.getUTCDate()).padStart(2, '0')
      value = `${year}-${month}-${day}`
    } else if (typeof customEvent.detail === 'string') {
      value = customEvent.detail
    } else if (customEvent.detail.target?.value) {
      value = customEvent.detail.target.value
    }
  }

  if (!value) {
    const target = event.target as any
    if (target?.value) {
      value = target.value
    } else if (target?.detail) {
      value = typeof target.detail === 'string' ? target.detail : target.detail?.value || ''
    }
  }

  if (value && typeof value === 'string') {
    if (value.includes('T')) {
      value = value.split('T')[0]
    }
    emit('update:modelValue', value)
  }

  const popover = document.getElementById(popoverId) as HTMLElement & { hidePopover?: () => void }
  popover?.hidePopover?.()
}
</script>

<style>
.cally {
  font-family: inherit;
}
</style>