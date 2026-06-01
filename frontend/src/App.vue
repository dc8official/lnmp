<template>
  <div id="app">
    <RouterView />
  </div>
</template>

<script setup>
import { onMounted } from 'vue'
import { RouterView } from 'vue-router'

onMounted(() => {
  const currentTheme = localStorage.getItem('theme') || 'dark'
  if (currentTheme === 'light') {
    document.body.classList.add('light-mode')
    document.body.classList.remove('dark-mode')
  } else {
    document.body.classList.add('dark-mode')
    document.body.classList.remove('light-mode')
  }
})
</script>

<style>
:root {
  --canvas-bg: #0a0a0a; /* bg-neutral-950 solid dark charcoal */
  --card-bg: #000000;   /* pitch black */
  --card-border: #262626;
  --text-primary: #ffffff;
  --text-secondary: #a3a3a3;
  --text-muted: #737373;
}

body.light-mode {
  --canvas-bg: #ffffff; /* bg-white clean, crisp flat white */
  --card-bg: #fafafa;   /* bg-neutral-50 light minimalist gray */
  --card-border: #cbd5e1;
  --text-primary: #000000;
  --text-secondary: #334155;
  --text-muted: #64748b;
}

* {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}

body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI',
    Roboto, Oxygen, Ubuntu, sans-serif;
  background-color: var(--canvas-bg);
  color: var(--text-secondary);
  transition: background-color 0.2s ease, color 0.2s ease;
}

#app {
  min-height: 100vh;
}
</style>
