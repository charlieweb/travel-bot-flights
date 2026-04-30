<template>
  <div class="min-h-screen bg-base-200">
    <div class="container mx-auto px-4 py-8 max-w-4xl">
      <header class="text-center mb-8">
        <h1 class="text-5xl font-bold text-primary mb-2">✈️ Travel Bot</h1>
        <p class="text-lg text-base-content/70">Find the best flights for your journey</p>
      </header>

      <main>
        <TravelSearchForm />
        <TravelResults />
        <ErrorMessage />
      </main>
    </div>
  </div>
</template>

<script setup lang="ts">
</script>
