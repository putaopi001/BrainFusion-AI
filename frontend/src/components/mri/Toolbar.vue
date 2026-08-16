<template>
  <div class="toolbar">
    <div class="tool-group">
      <span class="group-label">工具</span>
      <el-button
        v-for="tool in tools"
        :key="tool.value"
        size="small"
        :type="activeTool === tool.value ? 'primary' : 'default'"
        @click="$emit('tool-change', tool.value)"
      >{{ tool.label }}</el-button>
    </div>

    <div class="tool-group">
      <span class="group-label">标注类别</span>
      <el-select
        :model-value="annotationType"
        size="small"
        style="width: 110px"
        @change="$emit('annotation-type-change', $event)"
      >
        <el-option
          v-for="item in annotationTypes"
          :key="item.value"
          :label="item.label"
          :value="item.value"
        >
          <span class="type-option">
            <span class="type-dot" :style="{ background: item.color }"></span>
            {{ item.label }}
          </span>
        </el-option>
      </el-select>
      <label class="color-label">
        颜色 <input type="color" :value="annotationColor" @input="$emit('color-change', $event.target.value)" />
      </label>
    </div>

    <div class="tool-group">
      <el-input
        :model-value="author"
        size="small"
        class="compact-input"
        placeholder="阅片医生"
        @update:model-value="$emit('author-change', $event)"
      />
      <el-input
        :model-value="note"
        size="small"
        class="note-input"
        placeholder="标注说明"
        @update:model-value="$emit('note-change', $event)"
      />
    </div>

    <div class="tool-group">
      <el-button
        size="small"
        :type="showSegmentation ? 'danger' : 'default'"
        :disabled="!segmentationAvailable"
        @click="$emit('toggle-segmentation')"
      >{{ showSegmentation ? "隐藏分割" : "AI分割叠加" }}</el-button>
    </div>

    <div class="tool-group">
      <el-button size="small" type="success" :disabled="!pendingCount" @click="$emit('save')">保存标注</el-button>
      <el-button size="small" :disabled="!pendingCount" @click="$emit('undo')">撤销</el-button>
      <el-button size="small" :disabled="!pendingCount" @click="$emit('clear')">清空草稿</el-button>
      <el-button size="small" @click="$emit('reset')">重置视图</el-button>
      <el-button size="small" @click="$emit('fullscreen')">全屏</el-button>
    </div>
  </div>
</template>

<script setup>
import { ANNOTATION_TYPES } from "./constants"

defineProps({
  activeTool: { type: String, default: "pan" },
  annotationType: { type: String, default: "other" },
  annotationColor: { type: String, default: "#f97316" },
  author: { type: String, default: "" },
  note: { type: String, default: "" },
  showSegmentation: { type: Boolean, default: false },
  segmentationAvailable: { type: Boolean, default: false },
  pendingCount: { type: Number, default: 0 },
})

defineEmits([
  "tool-change",
  "annotation-type-change",
  "color-change",
  "author-change",
  "note-change",
  "toggle-segmentation",
  "save",
  "undo",
  "clear",
  "reset",
  "fullscreen",
])

const tools = [
  { value: "pan", label: "平移" },
  { value: "zoom", label: "缩放" },
  { value: "windowlevel", label: "窗宽窗位" },
  { value: "line", label: "测距" },
  { value: "angle", label: "角度" },
  { value: "rectangle", label: "矩形ROI" },
  { value: "ellipse", label: "椭圆ROI" },
  { value: "circle", label: "圆形ROI" },
  { value: "freehand", label: "自由ROI" },
  { value: "point", label: "标记点" },
  { value: "probe", label: "探针" },
  { value: "bidirectional", label: "双向测量" },
  { value: "text", label: "文字" },
]

const annotationTypes = ANNOTATION_TYPES
</script>

<style scoped>
.toolbar { display: flex; flex-wrap: wrap; gap: 10px; align-items: center; margin-bottom: 14px; }
.tool-group { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
.group-label { font-size: 12px; color: #94a3b8; margin-right: 2px; }
.color-label { display: flex; align-items: center; gap: 6px; font-size: 13px; }
.color-label input[type="color"] { width: 28px; height: 28px; border: 0; background: transparent; }
.compact-input { width: 120px; }
.note-input { width: 180px; }
.type-option { display: inline-flex; align-items: center; gap: 6px; }
.type-dot { display: inline-block; width: 10px; height: 10px; border-radius: 50%; }
</style>
