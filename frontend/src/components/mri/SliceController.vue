<template>
  <div class="slice-row">
    <span class="slice-label">{{ label }}</span>
    <el-slider
      :model-value="sliceIndex"
      :min="0"
      :max="maxIndex"
      :show-tooltip="false"
      @input="onInput"
      @change="onChange"
    />
    <span class="slice-value">{{ sliceIndex + 1 }} / {{ maxIndex + 1 }}</span>
  </div>
</template>

<script setup>
import { computed } from "vue"

const props = defineProps({
  label: { type: String, default: "" },
  sliceIndex: { type: Number, default: 0 },
  maxIndex: { type: Number, default: 0 },
})

const emit = defineEmits(["change"])

const safeMax = computed(() => Math.max(0, props.maxIndex))

function onInput(value) {
  emit("change", value)
}
function onChange(value) {
  emit("change", value)
}
</script>

<style scoped>
.slice-row { display: flex; align-items: center; gap: 10px; margin-bottom: 4px; }
.slice-label { width: 56px; flex: none; color: #cbd5e1; font-size: 12px; }
.slice-value { width: 72px; text-align: right; color: #94a3b8; font-size: 12px; font-variant-numeric: tabular-nums; }
.slice-row :deep(.el-slider) { flex: 1; }
</style>
