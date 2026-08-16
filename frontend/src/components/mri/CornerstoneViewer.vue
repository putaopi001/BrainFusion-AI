<template>
  <div class="cs-viewer">
    <div class="cs-toolbar">
      <span class="group-label">基础</span>
      <el-button size="small" :type="activeTool === 'WindowLevel' ? 'primary' : 'default'" @click="setTool('WindowLevel')">窗宽窗位</el-button>
      <el-button size="small" :type="activeTool === 'Pan' ? 'primary' : 'default'" @click="setTool('Pan')">平移</el-button>
      <el-button size="small" :type="activeTool === 'Zoom' ? 'primary' : 'default'" @click="setTool('Zoom')">缩放</el-button>
      <el-button size="small" :type="activeTool === 'Crosshairs' ? 'primary' : 'default'" @click="setTool('Crosshairs')">十字线</el-button>

      <span class="group-label">分割编辑</span>
      <el-button size="small" :type="activeTool === 'Brush' ? 'primary' : 'default'" :disabled="!hasSegmentation" @click="setTool('Brush')">笔刷</el-button>
      <el-button size="small" :type="activeTool === 'RectangleScissors' ? 'primary' : 'default'" :disabled="!hasSegmentation" @click="setTool('RectangleScissors')">矩形剪刀</el-button>
      <el-button size="small" :type="activeTool === 'CircleScissors' ? 'primary' : 'default'" :disabled="!hasSegmentation" @click="setTool('CircleScissors')">圆形剪刀</el-button>
      <el-button size="small" :type="activeTool === 'SphereScissors' ? 'primary' : 'default'" :disabled="!hasSegmentation" @click="setTool('SphereScissors')">球剪刀</el-button>
      <el-button size="small" :type="activeTool === 'PaintFill' ? 'primary' : 'default'" :disabled="!hasSegmentation" @click="setTool('PaintFill')">填充</el-button>
      <span v-if="hasSegmentation" class="brush-label">笔刷 {{ brushSize }}</span>
      <el-slider v-if="hasSegmentation" v-model="brushSize" :min="1" :max="20" style="width: 110px" @change="updateBrushSize" />
      <el-button size="small" :disabled="!hasSegmentation" @click="toggleSegmentation">{{ segmentationVisible ? "隐藏分割" : "显示分割" }}</el-button>
      <el-button size="small" @click="resetView">重置视图</el-button>
    </div>

    <div class="cs-note">
      <el-tag size="small" type="warning" effect="plain">Cornerstone3D 实验性渲染 · 滚轮切层</el-tag>
      <span v-if="!hasSegmentation" class="cs-note-text">（未检测到分割掩膜，仅三视图 MPR）</span>
    </div>

    <div v-if="error" class="cs-error">
      <p class="cs-error-title">Cornerstone3D 渲染不可用</p>
      <p>{{ error }}</p>
      <p class="cs-hint">请切换回「Canvas 渲染」继续阅片。此模式依赖浏览器 WebGL 支持。</p>
    </div>

    <div v-else class="cs-grid">
      <div v-for="view in views" :key="view.id" class="cs-panel">
        <div class="cs-header">{{ view.label }}</div>
        <div :id="view.id" class="cs-viewport"></div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { onBeforeUnmount, onMounted, ref } from "vue"
import { ElMessage } from "element-plus"
import {
  Enums as csEnums,
  RenderingEngine,
  cornerstoneStreamingImageVolumeLoader,
  getRenderingEngine,
  init as csInit,
  registerImageLoader,
  setVolumesForViewports,
  volumeLoader,
} from "@cornerstonejs/core"
import {
  Enums as csToolsEnums,
  addTool,
  BrushTool,
  CircleScissorsTool,
  CrosshairsTool,
  PaintFillTool,
  PanTool,
  RectangleScissorsTool,
  SphereScissorsTool,
  StackScrollTool,
  ToolGroupManager,
  WindowLevelTool,
  ZoomTool,
  init as csToolsInit,
  segmentation,
} from "@cornerstonejs/tools"
import {
  cornerstoneNiftiImageLoader,
  createNiftiImageIdsAndCacheMetadata,
  init as niftiInit,
} from "@cornerstonejs/nifti-volume-loader"
import request from "../../api/axios"

const props = defineProps({
  fileUrl: { type: String, default: "" },
  maskUrl: { type: String, default: "" },
})

const RENDERING_ENGINE_ID = "bf-cs-engine"
const TOOL_GROUP_ID = "bf-cs-toolgroup"
const VOLUME_ID = "bf-cs-volume"
const MASK_VOLUME_ID = "bf-cs-mask"
const SEGMENTATION_ID = "bf-cs-seg"

const views = [
  { id: "bf-cs-axial", label: "轴位 Axial", orientation: csEnums.OrientationAxis.AXIAL },
  { id: "bf-cs-sagittal", label: "矢状位 Sagittal", orientation: csEnums.OrientationAxis.SAGITTAL },
  { id: "bf-cs-coronal", label: "冠状位 Coronal", orientation: csEnums.OrientationAxis.CORONAL },
]
const viewportIds = views.map((v) => v.id)

const BASE_TOOLS = [WindowLevelTool, PanTool, ZoomTool, CrosshairsTool]
const SEG_TOOLS = [BrushTool, RectangleScissorsTool, CircleScissorsTool, SphereScissorsTool, PaintFillTool]

const activeTool = ref("WindowLevel")
const error = ref("")
const brushSize = ref(5)
const segmentationVisible = ref(true)
const hasSegmentation = ref(false)

let engine = null
let toolGroup = null

function resolveUrl(path) {
  if (!path) return ""
  if (new RegExp("^https?://", "i").test(path)) return path
  return new URL(path, request.defaults.baseURL).toString()
}

async function initViewer() {
  try {
    csInit()
    await csToolsInit()
    niftiInit()
    registerImageLoader("nifti", cornerstoneNiftiImageLoader)
    volumeLoader.registerVolumeLoader("cornerstoneStreamingImageVolume", cornerstoneStreamingImageVolumeLoader)
    volumeLoader.registerUnknownVolumeLoader(cornerstoneStreamingImageVolumeLoader)

    engine = new RenderingEngine(RENDERING_ENGINE_ID)
    engine.setViewports(
      views.map((view) => ({
        viewportId: view.id,
        type: csEnums.ViewportType.ORTHOGRAPHIC,
        element: document.getElementById(view.id),
        defaultOptions: { orientation: view.orientation },
      }))
    )

    ;[...BASE_TOOLS, ...SEG_TOOLS].forEach((tool) => addTool(tool))
    toolGroup = ToolGroupManager.createToolGroup(TOOL_GROUP_ID)
    viewportIds.forEach((id) => toolGroup.addViewport(id, RENDERING_ENGINE_ID))
    ;[...BASE_TOOLS, ...SEG_TOOLS].forEach((tool) => toolGroup.addTool(tool.toolName))

    toolGroup.setToolActive(WindowLevelTool.toolName, {
      bindings: [{ mouseButton: csToolsEnums.MouseBindings.Primary }],
    })
    toolGroup.setToolActive(StackScrollTool.toolName, {
      bindings: [{ mouseButton: csToolsEnums.MouseBindings.Wheel }],
    })

    // 加载基础体数据
    const imageIds = await createNiftiImageIdsAndCacheMetadata({ url: resolveUrl(props.fileUrl) })
    const volume = await volumeLoader.createAndCacheVolume(VOLUME_ID, { imageIds })
    await volume.load()

    await setVolumesForViewports(engine, [{ volumeId: VOLUME_ID }], viewportIds)
    engine.render()

    // 加载分割掩膜（labelmap）
    if (props.maskUrl) {
      try {
        const maskImageIds = await createNiftiImageIdsAndCacheMetadata({ url: resolveUrl(props.maskUrl) })
        await volumeLoader.createAndCacheVolume(MASK_VOLUME_ID, { imageIds: maskImageIds })
        await segmentation.addSegmentations([
          {
            segmentationId: SEGMENTATION_ID,
            representation: {
              type: csToolsEnums.SegmentationRepresentations.Labelmap,
              data: { volumeId: MASK_VOLUME_ID },
            },
          },
        ])
        await segmentation.addSegmentationRepresentations(TOOL_GROUP_ID, [
          {
            segmentationId: SEGMENTATION_ID,
            type: csToolsEnums.SegmentationRepresentations.Labelmap,
          },
        ])
        SEG_TOOLS.forEach((tool) => {
          toolGroup.setToolConfiguration(tool.toolName, { activeSegmentIndex: 1 })
        })
        toolGroup.setToolConfiguration(BrushTool.toolName, {
          brushSize: brushSize.value,
          activeSegmentIndex: 1,
        })
        hasSegmentation.value = true
        engine.render()
      } catch (segError) {
        console.error("segmentation load failed:", segError)
      }
    }
  } catch (e) {
    error.value = (e && e.message ? e.message : String(e)) || "初始化失败"
    ElMessage.warning("Cornerstone3D 渲染不可用，已回退到 Canvas 渲染")
  }
}

function setTool(toolName) {
  if (!toolGroup) return
  ;[...BASE_TOOLS, ...SEG_TOOLS].forEach((tool) => {
    try {
      toolGroup.setToolPassive(tool.toolName)
    } catch (e) {
      /* ignore */
    }
  })
  toolGroup.setToolActive(toolName, {
    bindings: [{ mouseButton: csToolsEnums.MouseBindings.Primary }],
  })
  activeTool.value = toolName
}

function updateBrushSize() {
  if (!toolGroup) return
  try {
    toolGroup.setToolConfiguration(BrushTool.toolName, {
      brushSize: brushSize.value,
      activeSegmentIndex: 1,
    })
  } catch (e) {
    /* ignore */
  }
}

function toggleSegmentation() {
  segmentationVisible.value = !segmentationVisible.value
  try {
    viewportIds.forEach((viewportId) => {
      segmentation.config.visibility.setSegmentationRepresentationVisibility(
        viewportId,
        { segmentationId: SEGMENTATION_ID, type: csToolsEnums.SegmentationRepresentations.Labelmap },
        segmentationVisible.value
      )
    })
  } catch (e) {
    /* ignore */
  }
}

function resetView() {
  try {
    const renderingEngine = getRenderingEngine(RENDERING_ENGINE_ID)
    if (renderingEngine) {
      viewportIds.forEach((id) => {
        const viewport = renderingEngine.getViewport(id)
        if (viewport) viewport.resetCamera()
      })
      renderingEngine.render()
    }
  } catch (e) {
    /* ignore */
  }
}

onMounted(() => {
  if (props.fileUrl) {
    initViewer()
  } else {
    error.value = "缺少 NIfTI 文件地址"
  }
})

onBeforeUnmount(() => {
  if (toolGroup) {
    try {
      toolGroup.removeViewports(RENDERING_ENGINE_ID)
    } catch (e) {
      /* ignore */
    }
    try {
      ToolGroupManager.destroyToolGroup(TOOL_GROUP_ID)
    } catch (e) {
      /* ignore */
    }
  }
  if (engine) {
    try {
      engine.destroy()
    } catch (e) {
      /* ignore */
    }
  }
})
</script>

<style scoped>
.cs-viewer { color: #e2e8f0; }
.cs-toolbar { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; flex-wrap: wrap; }
.group-label { font-size: 12px; color: #94a3b8; margin: 0 2px; }
.brush-label { font-size: 12px; color: #cbd5e1; }
.cs-note { display: flex; align-items: center; gap: 8px; margin-bottom: 10px; }
.cs-note-text { font-size: 12px; color: #94a3b8; }
.cs-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; }
.cs-panel { min-width: 0; border: 1px solid #334155; background: #020617; border-radius: 6px; overflow: hidden; }
.cs-header { padding: 8px 10px; font-size: 12px; background: #172033; color: #e2e8f0; }
.cs-viewport { width: 100%; height: 320px; background: #000; position: relative; }
.cs-error { padding: 40px 20px; text-align: center; color: #fca5a5; }
.cs-error-title { font-size: 15px; font-weight: 600; margin: 0 0 8px; }
.cs-hint { color: #94a3b8; font-size: 12px; }
@media (max-width: 960px) {
  .cs-grid { grid-template-columns: 1fr; }
}
</style>
