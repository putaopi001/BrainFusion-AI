import { ref } from 'vue'
import { eventTarget } from '@cornerstonejs/core'
import { annotation, Enums, LengthTool, StackScrollTool } from '@cornerstonejs/tools'
import request from '../../api/axios'

export function createMeasurementSession({ caseId, frameId, engine, views, group, signal, getSequence, mriId, revisions, transport, sessionId = frameId }) {
  const rows = ref([]), saving = ref(false), drawing = ref(false), notice = ref(''), historicalCount = ref(0)
  const saved = new Map(), origins = new Map(), completed = new Set()
  let context, disposed = false, drawingUid
  const owned = () => annotation.state.getAllAnnotations().filter(a => a.metadata?.FrameOfReferenceUID === frameId && a.metadata?.toolName === LengthTool.toolName && a.metadata.bfMeasurementSession === sessionId)
  const pointDistance = points => Math.hypot(...points[1].map((v, i) => v - points[0][i]))
  function originFor(a) {
    const normal = a.metadata.viewPlaneNormal
    const view = views.find(v => engine.getViewport(v.id).getCamera().viewPlaneNormal.every((n, i) => Math.abs(n - normal?.[i]) < 1e-4))
    if (!view) throw Error('测量平面无法对应当前视图')
    return { sequence: getSequence() || null, view: view.id.split('-').at(-1) }
  }
  function syncRows() {
    if (disposed) return
    rows.value = owned().filter(a => completed.has(a.annotationUID) || saved.has(a.annotationUID)).map(a => {
      const points = a.data.handles.points
      const origin = origins.get(a.annotationUID)
      return { uid: a.annotationUID, savedId: saved.get(a.annotationUID)?.id,
        lengthMm: saved.get(a.annotationUID)?.length_mm ?? pointDistance(points),
        sequence: origin?.sequence, view: origin?.view }
    })
  }
  function onAdded(event) {
    const a = event.detail.annotation
    if (disposed || a?.metadata?.FrameOfReferenceUID !== frameId || a.metadata.toolName !== LengthTool.toolName || saved.has(a.annotationUID)) return
    if (!views.some(v => v.id === event.detail.viewportId)) return
    a.metadata.bfMeasurementSession = sessionId
    origins.set(a.annotationUID, originFor(a))
    drawingUid = a.annotationUID
    drawing.value = true
    group.setToolDisabled(StackScrollTool.toolName)
  }
  function onCompleted(event) {
    const a = event.detail.annotation
    if (disposed || a?.metadata?.bfMeasurementSession !== sessionId || a.metadata.toolName !== LengthTool.toolName) return
    completed.add(a.annotationUID)
    drawingUid = null; drawing.value = false
    if (!disposed) group.setToolActive(StackScrollTool.toolName, { bindings: [{ mouseButton: Enums.MouseBindings.Wheel }] })
    syncRows()
  }
  function cancelDrawing() {
    if (!drawingUid) return
    const uid = drawingUid, a = annotation.state.getAnnotation(uid)
    const view = views.find(v => v.id.endsWith('-' + origins.get(uid)?.view))
    if (a && view) group.getToolInstance(LengthTool.toolName).cancel(engine.getViewport(view.id).element)
    annotation.state.removeAnnotation(uid)
    completed.delete(uid); origins.delete(uid)
    drawingUid = null; drawing.value = false
    if (!disposed) group.setToolActive(StackScrollTool.toolName, { bindings: [{ mouseButton: Enums.MouseBindings.Wheel }] })
    syncRows()
  }
  function onKey(event) { if (event.key === 'Escape') cancelDrawing() }
  async function init() {
    const data = transport ? await transport.list() : (await request.get(`/mri/${caseId}/measurements`, { signal })).data.data
    if (disposed) return
    if (transport) transport.validate(data.context)
    else if (data.context.mri_id !== mriId || data.source_revisions[getSequence() || 'legacy'] !== revisions.get(getSequence() || null)) throw Error('测量参考影像版本已改变，请重新打开工作站')
    context = data.context
    historicalCount.value = data.items.filter(r => !r.current).length
    for (const item of data.items.filter(r => r.current)) {
      const uid = frameId + '-measurement-' + item.id
      saved.set(uid, item)
      origins.set(uid, { sequence: item.reference_sequence, view: item.view })
      const view = views.find(v => v.id.endsWith('-' + item.view))
      LengthTool.hydrate(view.id, item.points_lps, { annotationUID: uid, toolInstance: group.getToolInstance(LengthTool.toolName), viewplaneNormal: item.view_plane_normal, viewUp: item.view_up })
      annotation.state.getAnnotation(uid).metadata.bfMeasurementSession = sessionId
      annotation.locking.setAnnotationLocked(uid, true)
    }
    syncRows()
    eventTarget.addEventListener(Enums.Events.ANNOTATION_ADDED, onAdded)
    eventTarget.addEventListener(Enums.Events.ANNOTATION_COMPLETED, onCompleted)
    eventTarget.addEventListener(Enums.Events.ANNOTATION_MODIFIED, syncRows)
    eventTarget.addEventListener(Enums.Events.ANNOTATION_REMOVED, syncRows)
    window.addEventListener('keydown', onKey)
  }
  async function save() {
    if (saving.value || drawing.value || !context) return
    saving.value = true; notice.value = ''
    const drafts = owned().filter(a => completed.has(a.annotationUID) && !saved.has(a.annotationUID))
    try {
      for (const a of drafts) {
        const origin = origins.get(a.annotationUID)
        const payload = { context, client_uid: a.annotationUID, reference_sequence: origin.sequence, view: origin.view,
          points_lps: structuredClone(a.data.handles.points), view_plane_normal: [...a.metadata.viewPlaneNormal], view_up: [...a.metadata.viewUp] }
        const item = transport ? await transport.save(payload) : (await request.post(`/mri/${caseId}/measurements`, payload, { signal })).data.data
        if (disposed) return
        saved.set(a.annotationUID, item)
        annotation.locking.setAnnotationLocked(a.annotationUID, true)
        syncRows()
      }
      notice.value = '测量已保存；刷新后可恢复。已保存测量为只读，可删除后重新绘制。'
    } catch (e) { if (!disposed) notice.value = '保存失败，未保存的测量仍可重试：' + (e.response?.data?.detail?.message || e.response?.data?.detail || e.message) }
    finally { if (!disposed) saving.value = false }
  }
  async function remove(uid) {
    if (saving.value || drawing.value) return
    saving.value = true; notice.value = ''
    try {
      const record = saved.get(uid)
      if (record) {
        if (transport) await transport.remove(record.id, context)
        else await request.delete(`/mri/${caseId}/measurements/${record.id}`, { params: { mri_id: context.mri_id }, signal })
      }
      if (disposed) return
      annotation.state.removeAnnotation(uid)
      saved.delete(uid); completed.delete(uid); origins.delete(uid)
      syncRows()
      engine.render()
    } catch (e) { if (!disposed) notice.value = '删除失败：' + (e.response?.data?.detail?.message || e.response?.data?.detail || e.message) }
    finally { if (!disposed) saving.value = false }
  }
  function dispose() {
    disposed = true
    cancelDrawing()
    eventTarget.removeEventListener(Enums.Events.ANNOTATION_ADDED, onAdded)
    eventTarget.removeEventListener(Enums.Events.ANNOTATION_COMPLETED, onCompleted)
    eventTarget.removeEventListener(Enums.Events.ANNOTATION_MODIFIED, syncRows)
    eventTarget.removeEventListener(Enums.Events.ANNOTATION_REMOVED, syncRows)
    window.removeEventListener('keydown', onKey)
    owned().forEach(a => annotation.state.removeAnnotation(a.annotationUID))
    saved.clear(); origins.clear(); completed.clear()
  }
  return { rows, saving, drawing, notice, historicalCount, init, save, remove, dispose, getContext: () => structuredClone(context) }
}
