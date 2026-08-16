// MRI 阅片工作站共享常量

export const VIEW_LABELS = { axial: "轴位", coronal: "冠状位", sagittal: "矢状位" }

export const VIEW_ORDER = ["axial", "coronal", "sagittal"]

// 与后端 app/services/mri_service.py::VIEW_AXIS 保持一致
export const VIEW_AXIS = { axial: 0, coronal: 1, sagittal: 2 }

export const TOOL_LABELS = {
  pan: "平移",
  zoom: "缩放",
  windowlevel: "窗宽窗位",
  line: "测距",
  angle: "角度",
  rectangle: "矩形ROI",
  ellipse: "椭圆ROI",
  circle: "圆形ROI",
  freehand: "自由ROI",
  point: "标记点",
  probe: "探针",
  bidirectional: "双向测量",
  text: "文字标注",
}

// 标注类别 -> 默认颜色（tumor红 / edema黄 / necrosis蓝 / blood深红 / other橙）
export const ANNOTATION_TYPES = [
  { value: "tumor", label: "肿瘤", color: "#ef4444" },
  { value: "edema", label: "水肿", color: "#f59e0b" },
  { value: "necrosis", label: "坏死", color: "#3b82f6" },
  { value: "blood", label: "出血", color: "#dc2626" },
  { value: "other", label: "其他", color: "#f97316" },
]

export const ANNOTATION_TYPE_COLORS = Object.fromEntries(
  ANNOTATION_TYPES.map((item) => [item.value, item.color]),
)

export const ANNOTATION_TYPE_LABELS = Object.fromEntries(
  ANNOTATION_TYPES.map((item) => [item.value, item.label]),
)
