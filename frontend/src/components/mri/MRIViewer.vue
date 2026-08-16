<template>
  <section ref="workstationRef" class="workstation">
    <header class="workstation-header">
      <div>
        <h3>MRI 阅片工作站</h3>
        <p>教学与原型工具，不能替代医生诊断或临床认证阅片系统。</p>
      </div>
      <div class="header-actions">
        <el-tag v-if="mode === 'volume'" type="success" size="small">真实窗宽窗位</el-tag>
        <el-tag v-else type="info" size="small">预览模式</el-tag>
        <span v-if="hoverInfo" class="hover-info">{{ hoverInfo }}</span>
        <el-button size="small" @click="toggleLayout">{{ layoutMode === "1view" ? "三视图" : "单视图" }}</el-button>
        <el-button size="small" @click="toggleFullscreen">全屏</el-button>
      </div>
    </header>

    <Toolbar
      :active-tool="activeTool"
      :annotation-type="annotationType"
      :annotation-color="annotationColor"
      :author="author"
      :note="note"
      :show-segmentation="showSegmentation"
      :segmentation-available="segmentationAvailable"
      :pending-count="pendingAnnotations.length"
      @tool-change="activeTool = $event"
      @annotation-type-change="onTypeChange"
      @color-change="annotationColor = $event"
      @author-change="author = $event"
      @note-change="note = $event"
      @toggle-segmentation="toggleSegmentation"
      @save="saveAnnotations"
      @undo="undoPending"
      @clear="pendingAnnotations = []"
      @reset="resetView"
      @fullscreen="toggleFullscreen"
    />

    <p v-if="toolHint" class="tool-hint">提示：{{ toolHint }}</p>

    <div v-if="isLoading" class="state">正在加载 MRI 数据…</div>
    <div v-else-if="loadError" class="state error">{{ loadError }}</div>
    <div v-else-if="!hasAnySlices" class="state">暂无可用 MRI 预览，请先生成预览切片。</div>

    <template v-else>
      <div class="viewport-grid">
        <Viewport
          v-for="view in visibleViews"
          :key="view"
          :view="view"
          :title="viewLabels[view]"
          :image-url="imageUrl(view)"
          :mask-url="mode === 'volume' && showSegmentation ? maskUrl(view) : ''"
          :show-mask="mode === 'volume' && showSegmentation"
          :width="viewWidth(view)"
          :height="viewHeight(view)"
          :shape="shape"
          :slice-index="sliceIndices[view]"
          :max-index="viewMaxIndex(view)"
          :annotations="visibleAnnotations(view)"
          :draft="draftFor(view)"
          :crosshair="mode === 'volume' ? crosshairFor(view) : null"
          :zoom="zoomPerView[view]"
          :pan="panPerView[view]"
          :active-tool="activeTool"
          :patient-name="patientName"
          :window-width="windowWidth"
          :window-level="windowLevel"
          @pointerdown="(p) => onPointerDown(view, p)"
          @pointermove="(p) => onPointerMove(view, p)"
          @pointerup="(p) => onPointerUp(view, p)"
          @pointerleave="onPointerLeave"
          @wheel="(payload) => onWheel(view, payload)"
        />
      </div>

      <div class="control-panel">
        <div class="slice-controls">
          <SliceController
            v-for="view in visibleViews"
            :key="view"
            :label="viewLabels[view]"
            :slice-index="sliceIndices[view]"
            :max-index="viewMaxIndex(view)"
            @change="(index) => (sliceIndices[view] = index)"
          />
        </div>
        <div class="zoom-buttons">
          <el-button size="small" @click="zoomAll(0.15)">放大</el-button>
          <el-button size="small" @click="zoomAll(-0.15)">缩小</el-button>
          <el-button size="small" @click="resetView">重置</el-button>
        </div>
        <WindowLevel
          v-if="mode === 'volume'"
          :window-width="windowWidth"
          :window-level="windowLevel"
          :min="volumeMeta ? volumeMeta.min : 0"
          :max="volumeMeta ? volumeMeta.max : 625"
          :display-min="volumeMeta ? volumeMeta.display_min : 0"
          :display-max="volumeMeta ? volumeMeta.display_max : 238"
          @change="onWindowLevelChange"
        />
      </div>

      <p v-if="showSegmentation && mode === 'volume'" class="seg-disclaimer">
        AI 分割叠加为演示用模拟掩膜（红色区域），非真实模型输出。
      </p>
    </template>

    <section v-if="allAnnotations.length" class="annotation-list">
      <div class="annotation-list-header">
        <h4>医生标注</h4>
        <el-button size="small" type="danger" plain :loading="deletingAll" @click="deleteAllAnnotations">删除全部</el-button>
      </div>
      <div
        v-for="item in [...pendingAnnotations, ...savedAnnotations]"
        :key="annotationKey(item)"
        class="annotation-item"
      >
        <span class="ann-type" :style="{ color: item.color }">
          {{ viewLabels[item.view] }} · 第 {{ item.slice_index + 1 }} 层 · {{ toolLabel(item.tool) }} · {{ typeLabel(item.annotation_type) }}
        </span>
        <span class="ann-note">{{ item.note || "无说明" }}</span>
        <el-button v-if="item.id" link type="danger" @click="deleteAnnotation(item.id)">删除</el-button>
      </div>
    </section>

    <a v-if="sourceUrl" :href="sourceUrl" target="_blank" rel="noopener" class="source-link">打开原始 MRI 文件</a>
  </section>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue"
import { ElMessage, ElMessageBox } from "element-plus"
import request from "../../api/axios"
import Toolbar from "./Toolbar.vue"
import Viewport from "./Viewport.vue"
import SliceController from "./SliceController.vue"
import WindowLevel from "./WindowLevel.vue"
import {
  VIEW_AXIS,
  VIEW_LABELS,
  TOOL_LABELS,
  ANNOTATION_TYPE_COLORS,
  ANNOTATION_TYPE_LABELS,
} from "./constants"
import { clamp, crosshair as computeCrosshair, sliceDims, voxelCoordinate } from "./utils"

const props = defineProps({
  caseId: { type: Number, default: 0 },
  fileUrl: { type: String, default: "" },
  sliceUrl: { type: String, default: "" },
  previewUrls: { type: Array, default: () => [] },
  previewViews: { type: Object, default: () => ({}) },
  filename: { type: String, default: "" },
  patientName: { type: String, default: "" },
})

const viewLabels = VIEW_LABELS
const toolLabels = TOOL_LABELS
const views = ["axial", "coronal", "sagittal"]
const layoutMode = ref("3view") // 3view | 1view
const visibleViews = computed(() => (layoutMode.value === "1view" ? ["axial"] : views))

const workstationRef = ref(null)
const isLoading = ref(true)
const loadError = ref("")
const mode = ref("preview") // volume | preview
const volumeMeta = ref(null)
const segmentationAvailable = ref(false)
const showSegmentation = ref(false)

const sliceIndices = ref({ axial: 0, coronal: 0, sagittal: 0 })
const windowWidth = ref(238)
const windowLevel = ref(119)

const zoomPerView = ref({ axial: 1, coronal: 1, sagittal: 1 })
const panPerView = ref({
  axial: { x: 0, y: 0 },
  coronal: { x: 0, y: 0 },
  sagittal: { x: 0, y: 0 },
})

const activeTool = ref("pan")
const annotationType = ref("other")
const annotationColor = ref("#f97316")
const author = ref("")
const note = ref("")

const savedAnnotations = ref([])
const pendingAnnotations = ref([])
const deletingAll = ref(false)
const draft = ref(null)
const panStart = ref(null)
const zoomDrag = ref(null)
const wlDrag = ref(null)
let wlTimer = null
let hoverTimer = null
const hoverInfo = ref("")

// ---- derived ----
const shape = computed(() => (volumeMeta.value ? volumeMeta.value.shape : null))
const sourceUrl = computed(() => resolveApiUrl(props.fileUrl))
const hasAnySlices = computed(() => views.some((view) => viewSlices(view).length > 0))
const allAnnotations = computed(() => [...savedAnnotations.value, ...pendingAnnotations.value])

const toolHint = computed(() => {
  const hints = {
    pan: "平移：按住拖拽移动视图",
    zoom: "缩放：上下拖拽缩放",
    windowlevel: "窗宽窗位：左右拖拽调窗宽，上下拖拽调窗位",
    line: "测距：按住拖拽画一条线测长度",
    angle: "角度：按住拖拽画第一条边 → 松开 → 移动鼠标预览第二条边 → 单击确定",
    rectangle: "矩形ROI：按住拖拽框选区域",
    ellipse: "椭圆ROI：按住拖拽框选椭圆区域",
    circle: "圆形ROI：按住拖拽框选圆形区域",
    freehand: "自由ROI：按住沿轮廓描绘",
    point: "标记点：单击放置标记点",
    probe: "探针：单击读取该点体素值",
    bidirectional: "双向测量：依次拖拽两条测量线",
    text: "文字：单击放置文字标注",
  }
  return hints[activeTool.value] || ""
})

function viewSlices(view) {
  return props.previewViews[view]?.length
    ? props.previewViews[view]
    : view === "axial"
      ? props.previewUrls
      : []
}

function viewSliceCount(view) {
  if (mode.value === "volume" && shape.value) return shape.value[VIEW_AXIS[view]]
  return viewSlices(view).length
}

function viewMaxIndex(view) {
  return Math.max(0, viewSliceCount(view) - 1)
}

function viewWidth(view) {
  if (mode.value === "volume" && shape.value) return sliceDims(shape.value, view).width
  return 1000
}

function viewHeight(view) {
  if (mode.value === "volume" && shape.value) return sliceDims(shape.value, view).height
  return 1000
}

function crosshairFor(view) {
  if (!shape.value) return null
  return computeCrosshair(view, sliceIndices.value, shape.value)
}

function imageUrl(view) {
  if (mode.value === "volume" && props.caseId) {
    const index = sliceIndices.value[view]
    const path =
      "/mri/" + props.caseId + "/slice/" + view + "/" + index +
      "?ww=" + Math.round(windowWidth.value) + "&wl=" + Math.round(windowLevel.value)
    return resolveApiUrl(path)
  }
  const slices = viewSlices(view)
  const index = Math.min(sliceIndices.value[view], Math.max(0, slices.length - 1))
  return resolveApiUrl(slices[index] || props.sliceUrl)
}

function maskUrl(view) {
  if (!props.caseId) return ""
  return resolveApiUrl("/mri/" + props.caseId + "/mask/" + view + "/" + sliceIndices.value[view])
}

function resolveApiUrl(path) {
  if (!path) return ""
  if (new RegExp("^https?://", "i").test(path)) return path
  return new URL(path, request.defaults.baseURL).toString()
}

function draftFor(view) {
  return draft.value && draft.value.view === view ? draft.value : null
}

function visibleAnnotations(view) {
  const index = sliceIndices.value[view]
  return allAnnotations.value.filter((item) => item.view === view && item.slice_index === index)
}

function annotationKey(annotation) {
  return (
    annotation.id ||
    "pending-" + annotation.view + "-" + annotation.slice_index + "-" + annotation.x + "-" + annotation.y + "-" + (annotation.tool || "")
  )
}

function toolLabel(tool) {
  return toolLabels[tool] || tool
}
function typeLabel(type) {
  return ANNOTATION_TYPE_LABELS[type] || "其他"
}

// ---- lifecycle ----
async function init() {
  isLoading.value = true
  loadError.value = ""
  try {
    await loadAnnotations()
    if (props.caseId) {
      try {
        const res = await request.get("/mri/" + props.caseId + "/volume")
        const meta = res.data.data
        volumeMeta.value = meta
        const s = meta.shape
        sliceIndices.value = {
          axial: Math.floor(s[0] / 2),
          coronal: Math.floor(s[1] / 2),
          sagittal: Math.floor(s[2] / 2),
        }
        windowWidth.value = meta.display_max - meta.display_min
        windowLevel.value = (meta.display_max + meta.display_min) / 2
        mode.value = "volume"
        try {
          const seg = await request.get("/mri/" + props.caseId + "/segmentation")
          segmentationAvailable.value = !!seg.data.data.available
        } catch (e) {
          segmentationAvailable.value = false
        }
      } catch (e) {
        mode.value = "preview"
        initPreviewIndices()
      }
    } else {
      mode.value = "preview"
      initPreviewIndices()
    }
  } catch (e) {
    loadError.value = "MRI 数据加载失败，请检查后端服务。"
  } finally {
    isLoading.value = false
  }
}

function initPreviewIndices() {
  sliceIndices.value = {
    axial: Math.max(0, Math.floor((viewSlices("axial").length - 1) / 2)),
    coronal: Math.max(0, Math.floor((viewSlices("coronal").length - 1) / 2)),
    sagittal: Math.max(0, Math.floor((viewSlices("sagittal").length - 1) / 2)),
  }
}

async function loadAnnotations() {
  if (!props.caseId) return
  try {
    const response = await request.get("/mri/" + props.caseId + "/annotations")
    savedAnnotations.value = response.data.data || []
  } catch (error) {
    if (error.response?.status !== 404) ElMessage.warning("医生标注加载失败")
  }
}

// ---- tool interactions ----
function onTypeChange(type) {
  annotationType.value = type
  if (ANNOTATION_TYPE_COLORS[type]) annotationColor.value = ANNOTATION_TYPE_COLORS[type]
}

function baseAnnotation(view, tool, extra) {
  return {
    view,
    slice_index: sliceIndices.value[view],
    tool,
    annotation_type: annotationType.value,
    color: annotationColor.value,
    note: note.value,
    created_by: author.value,
    ...extra,
  }
}

function withVoxel(annotation) {
  if (mode.value === "volume" && shape.value) {
    const vc = voxelCoordinate(annotation.view, annotation.slice_index, annotation.x, annotation.y, shape.value)
    annotation.voxel_coordinate = JSON.stringify(vc)
  }
  return annotation
}

async function placeProbe(view, point) {
  const vc = mode.value === "volume" && shape.value
    ? voxelCoordinate(view, sliceIndices.value[view], point.x, point.y, shape.value)
    : null
  if (!props.caseId || mode.value !== "volume") {
    pendingAnnotations.value.push(baseAnnotation(view, "probe", {
      x: point.x, y: point.y, width: 0, height: 0,
      note: vc ? "(" + vc.x + "," + vc.y + "," + vc.z + ")" : "",
      voxel_coordinate: vc ? JSON.stringify(vc) : null,
    }))
    return
  }
  try {
    const res = await request.get("/mri/" + props.caseId + "/voxel", {
      params: { view, index: sliceIndices.value[view], nx: point.x, ny: point.y },
    })
    const data = res.data.data
    pendingAnnotations.value.push(baseAnnotation(view, "probe", {
      x: point.x, y: point.y, width: 0, height: 0,
      note: "值 " + Math.round(data.value),
      voxel_coordinate: JSON.stringify(data.voxel),
    }))
  } catch (e) {
    ElMessage.warning("探针读取失败")
  }
}

function onPointerDown(view, point) {
  if (activeTool.value === "pan") {
    panStart.value = { view, clientX: point.clientX, clientY: point.clientY, panX: panPerView.value[view].x, panY: panPerView.value[view].y }
    return
  }
  if (activeTool.value === "zoom") {
    zoomDrag.value = { view, clientY: point.clientY, zoom: zoomPerView.value[view] }
    return
  }
  if (activeTool.value === "windowlevel") {
    wlDrag.value = { clientX: point.clientX, clientY: point.clientY, ww: windowWidth.value, wl: windowLevel.value }
    return
  }
  if (activeTool.value === "point") {
    pendingAnnotations.value.push(withVoxel(baseAnnotation(view, "point", { x: point.x, y: point.y, width: 0, height: 0 })))
    return
  }
  if (activeTool.value === "text") {
    pendingAnnotations.value.push(withVoxel(baseAnnotation(view, "text", { x: point.x, y: point.y, width: 0, height: 0 })))
    return
  }
  if (activeTool.value === "probe") {
    placeProbe(view, point)
    return
  }
  if (activeTool.value === "angle") {
    const current = draft.value && draft.value.view === view && draft.value.tool === "angle" ? draft.value : null
    if (!current) {
      // 第一次按下：确定顶点，开始拖拽第一条边
      draft.value = {
        ...baseAnnotation(view, "angle", {}),
        points: [[point.x, point.y], [point.x, point.y], [point.x, point.y]],
        phase: "arm1",
        x: point.x, y: point.y, width: 0, height: 0,
      }
    } else if (current.phase === "arm2") {
      // 第二条边已预览，单击确定
      const annotation = withVoxel(baseAnnotation(view, "angle", {
        x: current.points[0][0], y: current.points[0][1], width: 0, height: 0,
        points: JSON.stringify(current.points),
      }))
      pendingAnnotations.value.push(annotation)
      draft.value = null
    }
    return
  }
  if (activeTool.value === "freehand") {
    draft.value = { ...baseAnnotation(view, "freehand", {}), points: [[point.x, point.y]], x: point.x, y: point.y, width: 0, height: 0 }
    return
  }
  // rectangle | ellipse | circle | line：拖拽绘制
  if (["rectangle", "ellipse", "circle", "line"].includes(activeTool.value)) {
    draft.value = {
      ...baseAnnotation(view, activeTool.value, {}),
      originX: point.x,
      originY: point.y,
      x: point.x,
      y: point.y,
      width: 0,
      height: 0,
    }
    return
  }

  // bidirectional：两次拖拽（两条测量线）
  if (activeTool.value === "bidirectional") {
    const current = draft.value && draft.value.view === view && draft.value.tool === "bidirectional" ? draft.value : null
    if (!current) {
      draft.value = {
        ...baseAnnotation(view, "bidirectional", {}),
        lines: [],
        drawing: { sx: point.x, sy: point.y, cx: point.x, cy: point.y },
        x: point.x, y: point.y, width: 0, height: 0,
      }
    } else if (current.lines.length < 2) {
      current.drawing = { sx: point.x, sy: point.y, cx: point.x, cy: point.y }
    }
    return
  }
}

function scheduleHover(view, point) {
  if (mode.value !== "volume" || !props.caseId) return
  clearTimeout(hoverTimer)
  hoverTimer = setTimeout(async () => {
    try {
      const res = await request.get("/mri/" + props.caseId + "/voxel", {
        params: { view, index: sliceIndices.value[view], nx: point.x, ny: point.y },
      })
      const data = res.data.data
      hoverInfo.value = "值 " + Math.round(data.value) + " · (" + data.voxel.x + "," + data.voxel.y + "," + data.voxel.z + ")"
    } catch (e) {
      /* ignore */
    }
  }, 150)
}

function onPointerMove(view, point) {
  scheduleHover(view, point)
  if (panStart.value && activeTool.value === "pan") {
    panPerView.value[view] = {
      x: panStart.value.panX + point.clientX - panStart.value.clientX,
      y: panStart.value.panY + point.clientY - panStart.value.clientY,
    }
    return
  }
  if (zoomDrag.value && activeTool.value === "zoom") {
    const delta = point.clientY - zoomDrag.value.clientY
    zoomPerView.value[view] = clamp(zoomDrag.value.zoom - delta * 0.01, 0.5, 8)
    return
  }
  if (wlDrag.value && activeTool.value === "windowlevel") {
    const span = volumeMeta.value ? volumeMeta.value.max - volumeMeta.value.min : 625
    const dx = point.clientX - wlDrag.value.clientX
    const dy = point.clientY - wlDrag.value.clientY
    const nextWw = Math.max(1, wlDrag.value.ww + dx * (span / 300))
    const nextWl = wlDrag.value.wl - dy * (span / 300)
    wlDrag.value.pendingWw = nextWw
    wlDrag.value.pendingWl = nextWl
    clearTimeout(wlTimer)
    wlTimer = setTimeout(() => {
      windowWidth.value = nextWw
      windowLevel.value = nextWl
    }, 80)
    return
  }
  if (!draft.value || draft.value.view !== view) return
  if (["rectangle", "ellipse", "circle", "line"].includes(draft.value.tool)) {
    draft.value.x = point.x
    draft.value.y = point.y
  } else if (draft.value.tool === "freehand") {
    const last = draft.value.points[draft.value.points.length - 1]
    if (Math.hypot(point.x - last[0], point.y - last[1]) > 0.005) {
      draft.value.points.push([point.x, point.y])
    }
  } else if (draft.value.tool === "bidirectional") {
    if (draft.value.drawing) {
      draft.value.drawing.cx = point.x
      draft.value.drawing.cy = point.y
    }
  } else if (draft.value.tool === "angle") {
    if (draft.value.phase === "arm1") {
      draft.value.points[1] = [point.x, point.y]
    } else if (draft.value.phase === "arm2") {
      draft.value.points[2] = [point.x, point.y]
    }
  }
}

function onPointerUp(view, point) {
  if (wlDrag.value && wlDrag.value.pendingWw !== undefined) {
    windowWidth.value = wlDrag.value.pendingWw
    windowLevel.value = wlDrag.value.pendingWl
  }
  panStart.value = null
  zoomDrag.value = null
  wlDrag.value = null
  clearTimeout(wlTimer)
  if (!draft.value || draft.value.view !== view) return

  // bidirectional 特殊处理：两次拖拽
  if (draft.value.tool === "bidirectional") {
    const d = draft.value
    if (d.drawing) {
      const line = [d.drawing.sx, d.drawing.sy, d.drawing.cx, d.drawing.cy]
      if (Math.hypot(line[2] - line[0], line[3] - line[1]) > 0.005) {
        d.lines.push(line)
      }
      d.drawing = null
    }
    if (d.lines.length >= 2) {
      const annotation = withVoxel(baseAnnotation(view, "bidirectional", {
        x: d.lines[0][0], y: d.lines[0][1], width: 0, height: 0,
        points: JSON.stringify(d.lines),
      }))
      pendingAnnotations.value.push(annotation)
      draft.value = null
    }
    return
  }

  // angle：第一条边拖拽结束，进入第二条边预览
  if (draft.value.tool === "angle") {
    if (draft.value.phase === "arm1") {
      draft.value.points[1] = [point.x, point.y]
      draft.value.phase = "arm2"
      draft.value.points[2] = [point.x, point.y]
    }
    return
  }

  const { originX, originY, points, ...annotation } = draft.value
  if (annotation.tool === "rectangle" || annotation.tool === "ellipse" || annotation.tool === "circle") {
    annotation.x = Math.min(originX, annotation.x)
    annotation.y = Math.min(originY, annotation.y)
    annotation.width = Math.abs(annotation.x - originX)
    annotation.height = Math.abs(annotation.y - originY)
    if (annotation.width <= 0.005 || annotation.height <= 0.005) {
      draft.value = null
      return
    }
    pendingAnnotations.value.push(withVoxel(annotation))
  } else if (annotation.tool === "line") {
    const x1 = Math.min(originX, annotation.x)
    const y1 = Math.min(originY, annotation.y)
    annotation.x = x1
    annotation.y = y1
    annotation.width = Math.abs(annotation.x - originX)
    annotation.height = Math.abs(annotation.y - originY)
    if (Math.hypot(annotation.width, annotation.height) <= 0.005) {
      draft.value = null
      return
    }
    pendingAnnotations.value.push(withVoxel(annotation))
  } else if (annotation.tool === "freehand") {
    if (!points || points.length < 3) {
      draft.value = null
      return
    }
    const xs = points.map((p) => p[0])
    const ys = points.map((p) => p[1])
    annotation.x = Math.min(...xs)
    annotation.y = Math.min(...ys)
    annotation.width = Math.max(...xs) - annotation.x
    annotation.height = Math.max(...ys) - annotation.y
    annotation.points = JSON.stringify(points)
    pendingAnnotations.value.push(withVoxel(annotation))
  }
  draft.value = null
}

function onPointerLeave() {
  panStart.value = null
  zoomDrag.value = null
  wlDrag.value = null
  clearTimeout(wlTimer)
}

function onWheel(view, payload) {
  if (payload.ctrlKey) {
    const delta = payload.deltaY > 0 ? -0.1 : 0.1
    zoomPerView.value[view] = clamp(zoomPerView.value[view] + delta, 0.5, 8)
  } else {
    const step = payload.deltaY > 0 ? 1 : -1
    sliceIndices.value[view] = clamp(sliceIndices.value[view] + step, 0, viewMaxIndex(view))
  }
}

function onWindowLevelChange(payload) {
  windowWidth.value = payload.ww
  windowLevel.value = payload.wl
}

function zoomAll(amount) {
  views.forEach((view) => {
    zoomPerView.value[view] = clamp(zoomPerView.value[view] + amount, 0.5, 8)
  })
}

function resetView() {
  views.forEach((view) => {
    zoomPerView.value[view] = 1
    panPerView.value[view] = { x: 0, y: 0 }
  })
  if (mode.value === "volume" && volumeMeta.value) {
    windowWidth.value = volumeMeta.value.display_max - volumeMeta.value.display_min
    windowLevel.value = (volumeMeta.value.display_max + volumeMeta.value.display_min) / 2
  }
}

function toggleSegmentation() {
  showSegmentation.value = !showSegmentation.value
}

function toggleFullscreen() {
  workstationRef.value?.requestFullscreen?.()
}

function toggleLayout() {
  layoutMode.value = layoutMode.value === "1view" ? "3view" : "1view"
}

function onKeydown(event) {
  if (event.key === "Escape") {
    draft.value = null
    panStart.value = null
    zoomDrag.value = null
    wlDrag.value = null
    return
  }
  if (["ArrowUp", "ArrowLeft"].includes(event.key)) {
    sliceIndices.value.axial = clamp(sliceIndices.value.axial - 1, 0, viewMaxIndex("axial"))
    event.preventDefault()
  } else if (["ArrowDown", "ArrowRight"].includes(event.key)) {
    sliceIndices.value.axial = clamp(sliceIndices.value.axial + 1, 0, viewMaxIndex("axial"))
    event.preventDefault()
  }
}

async function saveAnnotations() {
  if (!props.caseId) {
    ElMessage.warning("缺少病例 ID，无法保存标注")
    return
  }
  try {
    await Promise.all(
      pendingAnnotations.value.map((item) =>
        request.post("/mri/" + props.caseId + "/annotations", {
          view: item.view,
          slice_index: item.slice_index,
          tool: item.tool,
          annotation_type: item.annotation_type || "other",
          color: item.color,
          x: item.x,
          y: item.y,
          width: item.width || 0,
          height: item.height || 0,
          points: item.points || null,
          voxel_coordinate: item.voxel_coordinate || null,
          note: item.note || null,
          created_by: item.created_by || null,
        }),
      ),
    )
    pendingAnnotations.value = []
    await loadAnnotations()
    ElMessage.success("医生标注已保存")
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || "标注保存失败")
  }
}

function undoPending() {
  pendingAnnotations.value.pop()
}

async function deleteAnnotation(annotationId) {
  try {
    await request.delete("/mri/" + props.caseId + "/annotations/" + annotationId)
    savedAnnotations.value = savedAnnotations.value.filter((item) => item.id !== annotationId)
  } catch (error) {
    ElMessage.error("标注删除失败")
  }
}

async function deleteAllAnnotations() {
  try {
    await ElMessageBox.confirm("确定删除该病例的全部标注？此操作不可恢复。", "删除全部标注", {
      type: "warning",
      confirmButtonText: "删除",
      cancelButtonText: "取消",
    })
  } catch (e) {
    return
  }
  deletingAll.value = true
  try {
    await request.delete("/mri/" + props.caseId + "/annotations")
    savedAnnotations.value = []
    pendingAnnotations.value = []
    ElMessage.success("已删除全部标注")
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || "删除失败")
  } finally {
    deletingAll.value = false
  }
}

watch(
  () => props.caseId,
  () => init(),
)

onMounted(() => {
  init()
  window.addEventListener("keydown", onKeydown)
})

onBeforeUnmount(() => {
  window.removeEventListener("keydown", onKeydown)
})
</script>

<style scoped>
.workstation { padding: 16px; color: #e2e8f0; background: #0b1220; border-radius: 8px; }
.workstation:fullscreen { overflow: auto; border-radius: 0; }
.workstation-header { display: flex; align-items: flex-start; justify-content: space-between; gap: 10px; margin-bottom: 14px; }
.workstation-header h3 { margin: 0; color: #f8fafc; }
.workstation-header p { margin: 4px 0 0; font-size: 12px; color: #94a3b8; }
.header-actions { display: flex; align-items: center; gap: 8px; }
.hover-info { font-size: 12px; color: #38bdf8; font-variant-numeric: tabular-nums; }
.viewport-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; }
.control-panel { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-top: 16px; align-items: start; }
.slice-controls { padding: 10px 12px; background: #172033; border-radius: 6px; }
.zoom-buttons { display: flex; gap: 6px; margin-top: 10px; }
.seg-disclaimer { margin: 10px 0 0; font-size: 12px; color: #fca5a5; }
.tool-hint { margin: 0 0 12px; padding: 6px 12px; background: #1e293b; border-left: 3px solid #38bdf8; border-radius: 4px; font-size: 12px; color: #94a3b8; }
.state { padding: 64px 16px; text-align: center; color: #cbd5e1; }
.error { color: #fca5a5; }
.annotation-list { margin-top: 16px; padding: 12px; background: #172033; border-radius: 6px; }
.annotation-list-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px; }
.annotation-list-header h4 { margin: 0; }
.annotation-list h4 { margin: 0 0 8px; }
.annotation-item { display: flex; justify-content: space-between; gap: 12px; align-items: center; padding: 6px 0; border-top: 1px solid #334155; font-size: 13px; }
.ann-note { color: #94a3b8; }
.source-link { display: inline-block; margin-top: 12px; font-size: 13px; }
@media (max-width: 960px) {
  .viewport-grid { grid-template-columns: 1fr; }
  .control-panel { grid-template-columns: 1fr; }
}
</style>
