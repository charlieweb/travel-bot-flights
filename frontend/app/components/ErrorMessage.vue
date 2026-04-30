<template>
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
</script>
