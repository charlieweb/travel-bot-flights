<template>
  <div class="mt-8 space-y-4">
    <div class="skeleton h-8 w-48"></div>
    <div v-for="i in 3" :key="i" class="card bg-base-100 shadow-lg">
      <div class="card-body">
        <div class="flex justify-between items-start">
          <div class="space-y-2">
            <div class="skeleton h-6 w-40"></div>
            <div class="skeleton h-4 w-28"></div>
          </div>
          <div class="skeleton h-8 w-24"></div>
        </div>
        <div class="skeleton h-4 w-full mt-4"></div>
        <div class="skeleton h-4 w-2/3"></div>
      </div>
    </div>
  </div>
</template>
