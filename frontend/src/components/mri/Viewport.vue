<template>
  <article class="viewport-panel" :data-view="view">
    <header class="panel-header">
      <strong>{{ title }}</strong>
      <span class="sequence-identity">{{ sequenceLabel }}</span>
      <span class="panel-meta">{{ sliceIndex + 1 }} / {{ maxIndex + 1 }}</span>
    </header>
    <div
      class="viewport"
      :style="{ cursor: cursorStyle }"
      @wheel.prevent="onWheel"
      @contextmenu.prevent
      @dragstart.prevent
      @pointerdown="onPointerDown"
      @pointermove="onPointerMove"
      @pointerup="onPointerUp"
      @pointercancel="$emit('pointercancel')"
      @pointerleave="onPointerLeave"
    >
      <div class="stage" :style="stageStyle">
        <div ref="boxRef" class="image-box" :style="boxStyle">
          <img
            v-if="imageUrl"
            :src="imageUrl"
            :alt="title + ' MRI 切片'"
            class="slice-img"
            :draggable="false"
            @load="onLoad"
            @error="onError"
          />
          <img
            v-if="showMask && maskUrl"
            :src="maskUrl"
            alt="分割掩膜"
            class="mask-img"
            :draggable="false"
            @error="$emit('maskerror')"
          />
          <AnnotationLayer
            :view="view"
            :width="width"
            :height="height"
            :annotations="annotations"
            :draft="draft"
            :crosshair="crosshair"
            :shape="shape"
            :spacing="spacing"
          />
        </div>
      </div>

      <!-- 方位标记（PACS 风格，固定在视口边缘） -->
      <span class="orient orient-top">{{ orient.top }}</span>
      <span class="orient orient-bottom">{{ orient.bottom }}</span>
      <span class="orient orient-left">{{ orient.left }}</span>
      <span class="orient orient-right">{{ orient.right }}</span>

      <!-- 四角信息叠加 -->
      <div class="corner corner-tl">{{ patientName || "BrainFusion AI" }}</div>
      <div class="corner corner-tr">{{ Math.round(zoom * 100) }}%</div>
      <div class="corner corner-bl">WW {{ Math.round(windowWidth) }} · WL {{ Math.round(windowLevel) }}</div>

      <div v-if="!loaded" class="loading-overlay">加载中…</div>
      <div v-if="error" class="error-overlay">{{ error }}</div>
    </div>
  </article>
</template>

<script setup>
import { computed, ref, watch } from "vue"
import AnnotationLayer from "./AnnotationLayer.vue"
import { clamp, sliceDims } from "./utils"

const props = defineProps({
  view: { type: String, default: "axial" },
  title: { type: String, default: "" },
  sequenceLabel: { type: String, default: "序列未标识" },
  imageUrl: { type: String, default: "" },
  maskUrl: { type: String, default: "" },
  showMask: { type: Boolean, default: false },
  width: { type: Number, default: 100 },
  height: { type: Number, default: 100 },
  shape: { type: Array, default: null },
  spacing: { type: Array, default: null },
  sliceIndex: { type: Number, default: 0 },
  maxIndex: { type: Number, default: 0 },
  annotations: { type: Array, default: () => [] },
  draft: { type: Object, default: null },
  crosshair: { type: Object, default: null },
  zoom: { type: Number, default: 1 },
  pan: { type: Object, default: () => ({ x: 0, y: 0 }) },
  activeTool: { type: String, default: "pan" },
  patientName: { type: String, default: "" },
  windowWidth: { type: Number, default: 100 },
  windowLevel: { type: Number, default: 50 },
})

const emit = defineEmits(["pointerdown", "pointermove", "pointerup", "pointercancel", "pointerleave", "wheel", "loaded", "maskerror"])

const boxRef = ref(null)
const loaded = ref(false)
const error = ref("")
const BASE_WIDTH = 320

// 放射学方位标记（示意，基于常见 RAS 方向约定）
const ORIENTATION = {
  axial: { top: "A", bottom: "P", left: "R", right: "L" },
  coronal: { top: "S", bottom: "I", left: "R", right: "L" },
  sagittal: { top: "S", bottom: "I", left: "A", right: "P" },
}
const orient = computed(() => ORIENTATION[props.view] || {})

const boxStyle = computed(() => ({
  width: BASE_WIDTH + "px",
  aspectRatio: props.shape && props.spacing ? (() => { const d = sliceDims(props.shape, props.view); return (props.width * props.spacing[d.colAxis]) + " / " + (props.height * props.spacing[d.rowAxis]) })() : (props.width || 1) + " / " + (props.height || 1),
}))

const stageStyle = computed(() => ({
  transform: "translate(" + props.pan.x + "px, " + props.pan.y + "px) scale(" + props.zoom + ")",
}))

const cursorStyle = computed(() => {
  if (props.activeTool === "pan") return "grab"
  if (props.activeTool === "text") return "text"
  return "crosshair"
})

watch(
  () => props.imageUrl,
  () => {
    loaded.value = false
    error.value = ""
  },
)

function onLoad() {
  loaded.value = true
  error.value = ""
  emit("loaded")
}
function onError() {
  loaded.value = true
  error.value = "切片加载失败"
}

function normalizePoint(event) {
  const rect = boxRef.value ? boxRef.value.getBoundingClientRect() : null
  if (!rect || !rect.width || !rect.height) return { x: 0, y: 0, clientX: event.clientX, clientY: event.clientY, button: event.button }
  return {
    x: clamp((event.clientX - rect.left) / rect.width),
    y: clamp((event.clientY - rect.top) / rect.height),
    clientX: event.clientX,
    clientY: event.clientY,
    button: event.button,
  }
}

function onPointerDown(event) {
  try {
    event.currentTarget.setPointerCapture(event.pointerId)
  } catch (e) {
    /* ignore */
  }
  emit("pointerdown", normalizePoint(event))
}
function onPointerMove(event) {
  emit("pointermove", normalizePoint(event))
}
function onPointerUp(event) {
  emit("pointerup", normalizePoint(event))
}
function onPointerLeave(event) {
  emit("pointerleave", normalizePoint(event))
}
function onWheel(event) {
  emit("wheel", { deltaY: event.deltaY, ctrlKey: event.ctrlKey })
}
</script>

<style scoped>
.viewport-panel { min-width: 0; border: 1px solid #334155; background: #020617; border-radius: 6px; overflow: hidden; }
.panel-header { display: flex; justify-content: space-between; align-items: center; padding: 8px 10px; font-size: 12px; background: #172033; color: #e2e8f0; }
.panel-meta { color: #94a3b8; font-variant-numeric: tabular-nums; }
.viewport { position: relative; display: flex; min-height: 300px; overflow: hidden; align-items: center; justify-content: center; background: #020617; user-select: none; touch-action: none; }
.stage { transition: transform 0.06s ease-out; }
.image-box { position: relative; line-height: 0; transform-origin: center center; }
.slice-img { display: block; width: 100%; height: 100%; image-rendering: auto; }
.mask-img { position: absolute; inset: 0; width: 100%; height: 100%; pointer-events: none; }

.orient { position: absolute; color: #38bdf8; font-size: 12px; font-weight: 700; pointer-events: none; text-shadow: 0 0 3px #000; }
.orient-top { top: 4px; left: 50%; transform: translateX(-50%); }
.orient-bottom { bottom: 4px; left: 50%; transform: translateX(-50%); }
.orient-left { left: 6px; top: 50%; transform: translateY(-50%); }
.orient-right { right: 6px; top: 50%; transform: translateY(-50%); }

.corner { position: absolute; color: #7dd3fc; font-size: 11px; pointer-events: none; text-shadow: 0 0 3px #000; opacity: 0.9; }
.corner-tl { top: 4px; left: 6px; }
.corner-tr { top: 4px; right: 6px; }
.corner-bl { bottom: 4px; left: 6px; }

.loading-overlay,
.error-overlay { position: absolute; inset: 0; display: flex; align-items: center; justify-content: center; color: #94a3b8; font-size: 13px; pointer-events: none; }
.error-overlay { color: #fca5a5; }
</style>
