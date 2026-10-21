// Label the actual screen direction in LPS world space, including oblique views.
export function lpsDirectionLabel(vector) {
  const scale = Math.hypot(...vector)
  if (!(scale > 0)) return ''
  const positive = ['L', 'P', 'S'], negative = ['R', 'A', 'I']
  return vector.map((v, axis) => ({ weight: Math.abs(v) / scale, label: v >= 0 ? positive[axis] : negative[axis] }))
    .filter(v => v.weight > .2).sort((a, b) => b.weight - a.weight).map(v => v.label).join('')
}

export function viewportOrientationLabels(viewport) {
  const center = [viewport.element.clientWidth / 2, viewport.element.clientHeight / 2]
  const origin = viewport.canvasToWorld(center)
  const right = viewport.canvasToWorld([center[0] + 10, center[1]]).map((v, i) => v - origin[i])
  const down = viewport.canvasToWorld([center[0], center[1] + 10]).map((v, i) => v - origin[i])
  return { right: lpsDirectionLabel(right), left: lpsDirectionLabel(right.map(v => -v)),
    bottom: lpsDirectionLabel(down), top: lpsDirectionLabel(down.map(v => -v)) }
}
