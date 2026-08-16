import { VIEW_AXIS } from "./constants"

// 根据体数据 shape=[d0,d1,d2] 与视图，返回切片在图像中的宽/高（列/行）以及对应轴向。
// 与后端 extract_slice 的 numpy 数组 [row, col] 约定一致。
export function sliceDims(shape, view) {
  const axis = VIEW_AXIS[view]
  const rowAxis = axis === 0 ? 1 : axis === 1 ? 0 : 0
  const colAxis = axis === 0 ? 2 : axis === 1 ? 2 : 1
  return {
    width: shape[colAxis],
    height: shape[rowAxis],
    rowAxis,
    colAxis,
  }
}

const AXIS_VIEWS = ["axial", "coronal", "sagittal"]

// 三个正交视图交叉线（crosshair）：在某一视图内标记另外两个切面的交点。
export function crosshair(view, sliceIndices, shape) {
  const { rowAxis, colAxis } = sliceDims(shape, view)
  const colIndex = sliceIndices[AXIS_VIEWS[colAxis]]
  const rowIndex = sliceIndices[AXIS_VIEWS[rowAxis]]
  return {
    x: shape[colAxis] > 1 ? colIndex / (shape[colAxis] - 1) : 0.5,
    y: shape[rowAxis] > 1 ? rowIndex / (shape[rowAxis] - 1) : 0.5,
  }
}

// 由 视图 + 切面索引 + 归一化坐标 计算体素坐标 {x,y,z}（对应 shape 的 [d0,d1,d2]）。
export function voxelCoordinate(view, sliceIndex, nx, ny, shape) {
  const { rowAxis, colAxis } = sliceDims(shape, view)
  const coord = [0, 0, 0]
  coord[VIEW_AXIS[view]] = sliceIndex
  coord[colAxis] = Math.round(nx * (shape[colAxis] - 1))
  coord[rowAxis] = Math.round(ny * (shape[rowAxis] - 1))
  return { x: coord[0], y: coord[1], z: coord[2] }
}

// 测距标签：width/height 为归一化增量，换算为体素长度。
export function lineLengthLabel(annotation, shape, view) {
  if (!shape) return ""
  const { width, height } = sliceDims(shape, view)
  const px = Math.hypot(annotation.width * width, annotation.height * height)
  return px.toFixed(1) + " px"
}

// 角度（points = [[vx,vy],[a1x,a1y],[a2x,a2y]] 归一化）换算为度数。
export function angleDegrees(points) {
  if (!Array.isArray(points) || points.length < 3) return 0
  const [v, a, b] = points
  const v1 = { x: a[0] - v[0], y: a[1] - v[1] }
  const v2 = { x: b[0] - v[0], y: b[1] - v[1] }
  const m1 = Math.hypot(v1.x, v1.y)
  const m2 = Math.hypot(v2.x, v2.y)
  if (!m1 || !m2) return 0
  const cosine = Math.min(1, Math.max(-1, (v1.x * v2.x + v1.y * v2.y) / (m1 * m2)))
  return Math.round((Math.acos(cosine) * 180) / Math.PI)
}

// 椭圆 / 圆形 ROI 面积标签（体素单位）
export function roiAreaLabel(annotation, shape, view) {
  if (!shape) return ""
  const { width, height } = sliceDims(shape, view)
  const w = annotation.width * width
  const h = annotation.height * height
  const area = annotation.tool === "circle"
    ? Math.PI * (Math.max(w, h) / 2) * (Math.max(w, h) / 2)
    : Math.PI * (w / 2) * (h / 2)
  return area.toFixed(1) + " px²"
}

export function parsePoints(value) {
  if (!value) return []
  if (Array.isArray(value)) return value
  try {
    const parsed = JSON.parse(value)
    return Array.isArray(parsed) ? parsed : []
  } catch {
    return []
  }
}

export function clamp(value, min = 0, max = 1) {
  return Math.min(max, Math.max(min, value))
}
