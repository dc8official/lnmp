<template>
  <div 
    ref="containerRef" 
    class="virtual-scroller" 
    :style="{ height: formattedContainerHeight }"
    @scroll.passive="onScroll"
  >
    <!-- Spacer matching the full calculated height of all items -->
    <div class="virtual-spacer" :style="{ height: `${totalHeight}px` }"></div>

    <!-- Active recycled items slice positioned at current offset -->
    <div class="virtual-content" :style="{ transform: `translateY(${offsetY}px)` }">
      <div 
        v-for="(item, idx) in visibleItems" 
        :key="itemKey(item, startIndex + idx)"
        class="virtual-item-wrapper"
        :style="{ height: `${itemHeight}px` }"
      >
        <slot :item="item" :index="startIndex + idx" />
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'

const props = defineProps({
  items: {
    type: Array,
    required: true,
    default: () => []
  },
  itemHeight: {
    type: Number,
    default: 48
  },
  buffer: {
    type: Number,
    default: 6
  },
  containerHeight: {
    type: [String, Number],
    default: '540px'
  },
  keyField: {
    type: String,
    default: 'id'
  }
})

const containerRef = ref(null)
const scrollTop = ref(0)
const viewportHeight = ref(540)

const formattedContainerHeight = computed(() => {
  return typeof props.containerHeight === 'number'
    ? `${props.containerHeight}px`
    : props.containerHeight
})

const totalHeight = computed(() => {
  return props.items.length * props.itemHeight
})

const startIndex = computed(() => {
  const index = Math.floor(scrollTop.value / props.itemHeight) - props.buffer
  return Math.max(0, index)
})

const endIndex = computed(() => {
  const visibleCount = Math.ceil(viewportHeight.value / props.itemHeight)
  const index = Math.floor(scrollTop.value / props.itemHeight) + visibleCount + props.buffer
  return Math.min(props.items.length, index)
})

const visibleItems = computed(() => {
  return props.items.slice(startIndex.value, endIndex.value)
})

const offsetY = computed(() => {
  return startIndex.value * props.itemHeight
})

function onScroll(e) {
  scrollTop.value = e.target.scrollTop
}

function itemKey(item, fallbackIndex) {
  if (item && props.keyField && item[props.keyField] !== undefined) {
    return item[props.keyField]
  }
  return fallbackIndex
}

let resizeObserver = null

onMounted(() => {
  if (containerRef.value) {
    viewportHeight.value = containerRef.value.clientHeight || 540
    if (typeof ResizeObserver !== 'undefined') {
      resizeObserver = new ResizeObserver((entries) => {
        for (const entry of entries) {
          if (entry.contentRect) {
            viewportHeight.value = entry.contentRect.height
          }
        }
      })
      resizeObserver.observe(containerRef.value)
    }
  }
})

onUnmounted(() => {
  if (resizeObserver) {
    resizeObserver.disconnect()
  }
})
</script>

<style scoped>
.virtual-scroller {
  position: relative;
  overflow-y: auto;
  overflow-x: hidden;
  will-change: transform;
  contain: strict;
}

.virtual-spacer {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  pointer-events: none;
  visibility: hidden;
}

.virtual-content {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  will-change: transform;
}

.virtual-item-wrapper {
  box-sizing: border-box;
}
</style>
