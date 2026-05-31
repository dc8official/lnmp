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
* {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}

body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI',
    Roboto, Oxygen, Ubuntu, sans-serif;
  background-color: #0A0A0A;
  color: #A3A3A3;
  transition: background-color 0.2s ease, color 0.2s ease;
}

body.light-mode {
  background-color: #f1f5f9;
  color: #334155;
}

#app {
  min-height: 100vh;
}
</style>
