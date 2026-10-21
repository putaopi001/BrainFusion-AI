<template>
  <div class="wl-panel">
    <div class="wl-row">
      <span class="wl-label">窗宽 WW</span>
      <el-slider
        :model-value="localWw"
        :min="1"
        :max="wwMax"
        :step="1"
        @input="onWwInput"
        @change="emitNow"
      />
      <span class="wl-value">{{ Math.round(localWw) }}</span>
    </div>
    <div class="wl-row">
      <span class="wl-label">窗位 WL</span>
      <el-slider
        :model-value="localWl"
        :min="min"
        :max="max"
        :step="1"
        @input="onWlInput"
        @change="emitNow"
      />
      <span class="wl-value">{{ Math.round(localWl) }}</span>
    </div>
    <div class="wl-presets">
      <el-button size="small" @click="preset('brain')">脑窗</el-button>
      <el-button size="small" @click="preset('full')">全窗</el-button>
      <el-button size="small" @click="preset('auto')">自动</el-button>
    </div>
    <p class="wl-hint">窗宽窗位作用于原始体素强度（真实 MRI 强度值映射）。</p>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, ref, watch } from "vue"

const props = defineProps({
  windowWidth: { type: Number, default: 238 },
  windowLevel: { type: Number, default: 119 },
  min: { type: Number, default: 0 },
  max: { type: Number, default: 625 },
  displayMin: { type: Number, default: 0 },
  displayMax: { type: Number, default: 238 },
})

const emit = defineEmits(["change"])

const localWw = ref(props.windowWidth)
const localWl = ref(props.windowLevel)
let timer = null

const wwMax = computed(() => Math.max(1, Math.round(props.max - props.min)))

watch(
  () => props.windowWidth,
  (value) => {
    if (Math.abs(value - localWw.value) > 1) localWw.value = value
  },
)
watch(
  () => props.windowLevel,
  (value) => {
    if (Math.abs(value - localWl.value) > 1) localWl.value = value
  },
)

function onWwInput(value) {
  localWw.value = value
  schedule()
}
function onWlInput(value) {
  localWl.value = value
  schedule()
}
function schedule() {
  clearTimeout(timer)
  timer = setTimeout(emitNow, 140)
}
function emitNow() {
  clearTimeout(timer)
  emit("change", { ww: localWw.value, wl: localWl.value })
}
function preset(name) {
  const span = Math.max(1, props.displayMax - props.displayMin)
  const center = (props.displayMax + props.displayMin) / 2
  if (name === "brain") {
    localWw.value = span
    localWl.value = center
  } else if (name === "full") {
    localWw.value = props.max - props.min
    localWl.value = (props.max + props.min) / 2
  } else {
    localWw.value = span
    localWl.value = center
  }
  emitNow()
}
onBeforeUnmount(() => clearTimeout(timer))
</script>

<style scoped>
.wl-panel { padding: 10px 12px; background: #172033; border-radius: 6px; font-size: 12px; color: #cbd5e1; }
.wl-row { display: flex; align-items: center; gap: 10px; margin-bottom: 4px; }
.wl-label { width: 64px; flex: none; }
.wl-value { width: 48px; text-align: right; color: #e2e8f0; font-variant-numeric: tabular-nums; }
.wl-row :deep(.el-slider) { flex: 1; }
.wl-presets { display: flex; gap: 6px; margin: 8px 0 4px; }
.wl-hint { margin: 4px 0 0; color: #64748b; }
</style>
