<template>
  <svg
    class="annotation-svg"
    :viewBox="viewBox"
    preserveAspectRatio="none"
  >
    <!-- crosshair -->
    <g v-if="crosshair" class="crosshair">
      <line
        :x1="crosshair.x * width"
        y1="0"
        :x2="crosshair.x * width"
        :y2="height"
        class="crosshair-line"
      />
      <line
        x1="0"
        :y1="crosshair.y * height"
        :x2="width"
        :y2="crosshair.y * height"
        class="crosshair-line"
      />
    </g>

    <!-- saved + pending annotations -->
    <g v-for="annotation in annotations" :key="annotationKey(annotation)">
      <rect
        v-if="annotation.tool === 'rectangle'"
        :x="annotation.x * width"
        :y="annotation.y * height"
        :width="annotation.width * width"
        :height="annotation.height * height"
        :stroke="annotation.color"
        fill="rgba(255,255,255,0.06)"
        class="shape"
      />
      <circle
        v-else-if="annotation.tool === 'point'"
        :cx="annotation.x * width"
        :cy="annotation.y * height"
        r="4"
        :fill="annotation.color"
        class="shape"
      />
      <g v-else-if="annotation.tool === 'ellipse'">
        <ellipse
          :cx="(annotation.x + annotation.width / 2) * width"
          :cy="(annotation.y + annotation.height / 2) * height"
          :rx="annotation.width * width / 2"
          :ry="annotation.height * height / 2"
          :stroke="annotation.color"
          fill="rgba(255,255,255,0.06)"
          class="shape"
        />
        <text
          :x="(annotation.x + annotation.width / 2) * width"
          :y="annotation.y * height - 8"
          :fill="annotation.color"
          font-size="14"
          text-anchor="middle"
          class="label-text"
        >{{ roiAreaLabel(annotation) }}</text>
      </g>
      <g v-else-if="annotation.tool === 'circle'">
        <circle
          :cx="(annotation.x + annotation.width / 2) * width"
          :cy="(annotation.y + annotation.height / 2) * height"
          :r="Math.max(annotation.width * width, annotation.height * height) / 2"
          :stroke="annotation.color"
          fill="rgba(255,255,255,0.06)"
          class="shape"
        />
        <text
          :x="(annotation.x + annotation.width / 2) * width"
          :y="annotation.y * height - 8"
          :fill="annotation.color"
          font-size="14"
          text-anchor="middle"
          class="label-text"
        >{{ roiAreaLabel(annotation) }}</text>
      </g>
      <circle
        v-else-if="annotation.tool === 'probe'"
        :cx="annotation.x * width"
        :cy="annotation.y * height"
        r="3"
        :fill="annotation.color"
        class="shape"
      />
      <g v-else-if="annotation.tool === 'bidirectional'">
        <template v-if="bidirectionalLines(annotation).length >= 1">
          <line
            v-for="(line, idx) in bidirectionalLines(annotation)"
            :key="idx"
            :x1="line[0] * width"
            :y1="line[1] * height"
            :x2="line[2] * width"
            :y2="line[3] * height"
            :stroke="annotation.color"
            class="shape"
          />
          <text
            v-if="bidirectionalLines(annotation).length >= 2"
            :x="bidirectionalLines(annotation)[0][0] * width"
            :y="bidirectionalLines(annotation)[0][1] * height - 8"
            :fill="annotation.color"
            font-size="14"
            class="label-text"
          >{{ bidirectionalLabel(annotation) }}</text>
        </template>
      </g>
      <g v-else-if="annotation.tool === 'line'">
        <line
          :x1="annotation.x * width"
          :y1="annotation.y * height"
          :x2="(annotation.x + annotation.width) * width"
          :y2="(annotation.y + annotation.height) * height"
          :stroke="annotation.color"
          class="shape"
        />
        <text
          :x="(annotation.x + annotation.width / 2) * width"
          :y="(annotation.y + annotation.height / 2) * height - 6"
          :fill="annotation.color"
          font-size="14"
          text-anchor="middle"
          class="label-text"
        >{{ lineLengthLabel(annotation) }}</text>
      </g>
      <polygon
        v-else-if="annotation.tool === 'freehand'"
        :points="polygonPoints(annotation)"
        :stroke="annotation.color"
        fill="rgba(255,255,255,0.08)"
        class="shape"
      />
      <g v-else-if="annotation.tool === 'angle'">
        <template v-if="anglePoints(annotation).length >= 3">
          <line
            :x1="anglePoints(annotation)[0][0] * width"
            :y1="anglePoints(annotation)[0][1] * height"
            :x2="anglePoints(annotation)[1][0] * width"
            :y2="anglePoints(annotation)[1][1] * height"
            :stroke="annotation.color"
            class="shape"
          />
          <line
            :x1="anglePoints(annotation)[0][0] * width"
            :y1="anglePoints(annotation)[0][1] * height"
            :x2="anglePoints(annotation)[2][0] * width"
            :y2="anglePoints(annotation)[2][1] * height"
            :stroke="annotation.color"
            class="shape"
          />
          <text
            :x="anglePoints(annotation)[0][0] * width + 10"
            :y="anglePoints(annotation)[0][1] * height + 4"
            :fill="annotation.color"
            font-size="14"
            class="label-text"
          >{{ angleDegrees(anglePoints(annotation)) }}°</text>
        </template>
      </g>
      <text
        v-else-if="annotation.tool === 'text'"
        :x="annotation.x * width"
        :y="annotation.y * height"
        :fill="annotation.color"
        font-size="16"
        class="label-text"
      >{{ annotation.note || "" }}</text>

      <!-- optional note label -->
      <text
        v-if="annotation.note && annotation.tool !== 'text' && annotation.tool !== 'line' && annotation.tool !== 'ellipse' && annotation.tool !== 'circle'"
        :x="annotation.x * width + 8"
        :y="annotation.y * height - 8"
        :fill="annotation.color"
        font-size="13"
        class="label-text"
      >{{ annotation.note }}</text>
    </g>

    <!-- draft preview -->
    <g v-if="draft">
      <rect
        v-if="draft.tool === 'rectangle'"
        :x="Math.min(draft.originX, draft.x) * width"
        :y="Math.min(draft.originY, draft.y) * height"
        :width="Math.abs(draft.x - draft.originX) * width"
        :height="Math.abs(draft.y - draft.originY) * height"
        :stroke="draft.color"
        fill="transparent"
        stroke-dasharray="6 4"
        class="shape"
      />
      <ellipse
        v-else-if="draft.tool === 'ellipse'"
        :cx="((draft.originX + draft.x) / 2) * width"
        :cy="((draft.originY + draft.y) / 2) * height"
        :rx="Math.abs(draft.x - draft.originX) * width / 2"
        :ry="Math.abs(draft.y - draft.originY) * height / 2"
        :stroke="draft.color"
        fill="transparent"
        stroke-dasharray="6 4"
        class="shape"
      />
      <circle
        v-else-if="draft.tool === 'circle'"
        :cx="((draft.originX + draft.x) / 2) * width"
        :cy="((draft.originY + draft.y) / 2) * height"
        :r="Math.max(Math.abs(draft.x - draft.originX) * width, Math.abs(draft.y - draft.originY) * height) / 2"
        :stroke="draft.color"
        fill="transparent"
        stroke-dasharray="6 4"
        class="shape"
      />
      <line
        v-else-if="draft.tool === 'line'"
        :x1="draft.originX * width"
        :y1="draft.originY * height"
        :x2="draft.x * width"
        :y2="draft.y * height"
        :stroke="draft.color"
        stroke-dasharray="6 4"
        class="shape"
      />
      <polyline
        v-else-if="draft.tool === 'freehand'"
        :points="draftPolylinePoints(draft)"
        :stroke="draft.color"
        fill="none"
        class="shape"
      />
      <g v-else-if="draft.tool === 'angle'">
        <line
          v-if="draft.points && draft.points.length >= 2"
          :x1="draft.points[0][0] * width"
          :y1="draft.points[0][1] * height"
          :x2="draft.points[1][0] * width"
          :y2="draft.points[1][1] * height"
          :stroke="draft.color"
          stroke-dasharray="6 4"
          class="shape"
        />
        <line
          v-if="draft.points && draft.points.length >= 3"
          :x1="draft.points[0][0] * width"
          :y1="draft.points[0][1] * height"
          :x2="draft.points[2][0] * width"
          :y2="draft.points[2][1] * height"
          :stroke="draft.color"
          stroke-dasharray="6 4"
          class="shape"
        />
      </g>
      <g v-else-if="draft.tool === 'bidirectional'">
        <line
          v-for="(line, idx) in (draft.lines || [])"
          :key="idx"
          :x1="line[0] * width"
          :y1="line[1] * height"
          :x2="line[2] * width"
          :y2="line[3] * height"
          :stroke="draft.color"
          class="shape"
        />
        <line
          v-if="draft.drawing"
          :x1="draft.drawing.sx * width"
          :y1="draft.drawing.sy * height"
          :x2="draft.drawing.cx * width"
          :y2="draft.drawing.cy * height"
          :stroke="draft.color"
          stroke-dasharray="6 4"
          class="shape"
        />
      </g>
    </g>
  </svg>
</template>

<script setup>
import { computed } from "vue"
import { angleDegrees, parsePoints, roiAreaLabel as roiAreaUtil, sliceDims } from "./utils"

const props = defineProps({
  view: { type: String, default: "axial" },
  width: { type: Number, default: 100 },
  height: { type: Number, default: 100 },
  annotations: { type: Array, default: () => [] },
  draft: { type: Object, default: null },
  crosshair: { type: Object, default: null },
  shape: { type: Array, default: null },
})

const viewBox = computed(() => "0 0 " + props.width + " " + props.height)

function annotationKey(annotation) {
  return annotation.id || ("pending-" + annotation.view + "-" + annotation.slice_index + "-" + annotation.x + "-" + annotation.y + "-" + (annotation.tool || ""))
}

function anglePoints(annotation) {
  return parsePoints(annotation.points)
}

function polygonPoints(annotation) {
  const pts = parsePoints(annotation.points)
  return pts
    .map((p) => p[0] * props.width + "," + p[1] * props.height)
    .join(" ")
}

function draftPolylinePoints(draft) {
  const pts = draft.points || []
  return pts.map((p) => p[0] * props.width + "," + p[1] * props.height).join(" ")
}

function lineLengthLabel(annotation) {
  if (!props.shape) return ""
  const { width, height } = sliceDims(props.shape, props.view)
  const px = Math.hypot(annotation.width * width, annotation.height * height)
  return px.toFixed(1) + " px"
}

function roiAreaLabel(annotation) {
  if (!props.shape) return ""
  return roiAreaUtil(annotation, props.shape, props.view)
}

function bidirectionalLines(annotation) {
  return parsePoints(annotation.points)
}

function bidirectionalLabel(annotation) {
  const lines = bidirectionalLines(annotation)
  if (!props.shape || lines.length < 2) return ""
  const { width, height } = sliceDims(props.shape, props.view)
  const l1 = Math.hypot((lines[0][2] - lines[0][0]) * width, (lines[0][3] - lines[0][1]) * height)
  const l2 = Math.hypot((lines[1][2] - lines[1][0]) * width, (lines[1][3] - lines[1][1]) * height)
  return l1.toFixed(1) + " / " + l2.toFixed(1) + " px"
}
</script>

<style scoped>
.annotation-svg { position: absolute; inset: 0; width: 100%; height: 100%; pointer-events: none; }
.shape { vector-effect: non-scaling-stroke; stroke-width: 2; }
.crosshair-line { vector-effect: non-scaling-stroke; stroke-width: 1; stroke: #38bdf8; stroke-dasharray: 5 4; }
.label-text { paint-order: stroke; stroke: #000; stroke-width: 3px; }
</style>
