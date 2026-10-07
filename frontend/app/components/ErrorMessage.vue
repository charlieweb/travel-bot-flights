<template>
  <dialog
    ref="dialogEl"
    class="modal"
    aria-labelledby="city-prompt-title"
    @close="store.dismissCityPrompt()"
  >
    <div class="modal-box">
      <h3 id="city-prompt-title" class="text-xl font-bold">Add both cities</h3>
      <p class="py-4 text-base-content/80">{{ message }}</p>
      <div class="modal-action">
        <button type="button" class="btn btn-primary" autofocus @click="close">
          Got it
        </button>
      </div>
    </div>
    <form method="dialog" class="modal-backdrop">
      <button type="submit">Close</button>
    </form>
  </dialog>

  <div v-if="store.error" class="alert alert-error mt-6 shadow-lg">
    <svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z" />
    </svg>
    <span>{{ store.error }}</span>
    <button class="btn btn-sm btn-ghost" @click="store.error = ''">Dismiss</button>
  </div>
</template>

<script setup lang="ts">
import { useTravelStore } from '~/stores/travel'

const store = useTravelStore()
const dialogEl = useTemplateRef<HTMLDialogElement>('dialogEl')

const message = computed(() => {
  const prompt = store.cityPrompt
  if (!prompt) return ''
  if (prompt.missing === 'destination' && prompt.known) {
    return `We found ${prompt.known} as the departure, but not where you want to go. Add an arrival city, for example “${prompt.known} to Tokyo, leaving Dec 10”.`
  }
  if (prompt.missing === 'origin' && prompt.known) {
    return `We found ${prompt.known} as the arrival, but not where you are leaving from. Add a departure city, for example “London to ${prompt.known}, leaving Dec 10”.`
  }
  return 'A flight search needs a departure city and an arrival city. Try “London to Tokyo, leaving Dec 10”.'
})

watch(
  () => store.cityPrompt,
  async (prompt) => {
    await nextTick()
    const dialog = dialogEl.value
    if (!dialog) return
    if (prompt && !dialog.open) dialog.showModal()
    else if (!prompt && dialog.open) dialog.close()
  },
)

function close() {
  dialogEl.value?.close()
}
</script>
