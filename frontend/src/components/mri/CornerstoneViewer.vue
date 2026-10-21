<template>
  <div class="cs-viewer" :data-source="dicomSource ? 'dicom' : 'nifti'" :data-state="error ? 'error' : loading ? 'loading' : 'ready'" :data-sequence="activeSequence">
    <div class="cs-toolbar">
      <label v-if="!dicomSource">当前序列 <select v-model="requestedSequence" :disabled="loading || measurementDrawing || measurementSaving" @change="switchSequence(requestedSequence)">
        <option v-for="key in availableSequences" :key="key" :value="key">{{ labels[key] }}</option>
        <option v-if="!availableSequences.length" value="">旧单序列：身份未标识</option>
      </select></label>
      <el-button v-for="tool in visibleTools" :key="tool.toolName" size="small" :disabled="loading || !!error || measurementDrawing || measurementSaving" :type="activeTool === tool.toolName ? 'primary' : 'default'" @click="setTool(tool.toolName)">{{ toolLabels[tool.toolName] }}</el-button>
      <el-button v-if="!dicomSource" size="small" :disabled="!hasSegmentation || loading || measurementDrawing || measurementSaving" @click="toggleSegmentation">{{ segmentationVisible ? '隐藏分割' : '显示分割' }}</el-button>
      <el-button size="small" :disabled="loading || !!error || measurementDrawing || measurementSaving" @click="resetView">重置视图</el-button>
      <el-button v-if="!dicomSource || dicomMeasurementsAvailable" size="small" :disabled="loading || !!error || measurementDrawing || measurementSaving || !measurementRows.some(r => !r.savedId)" @click="measurements.save()">保存测量</el-button>
      <el-button v-if="!dicomSource || dicomViewAvailable" size="small" :disabled="loading || !!error || measurementDrawing || measurementSaving || viewSaving" @click="saveView">保存视图</el-button>
    </div>
    <p v-if="dicomSource" class="cs-note">Cornerstone3D · DICOM 患者原空间 · 滚轮切层 · 序列身份待确认；不自动配准或重采样。<span v-if="dicomMeasurementsAvailable">默认三正交平面距离按毫米保存并绑定病例、归档与序列元数据版本；旋转平面请先重置视图。</span><span v-else>当前来源仅阅片，测量保存未启用。</span>掩膜叠加、编辑与 AI 提交尚未开放。</p>
    <p v-else class="cs-note">Cornerstone3D · NIfTI 原空间 · 滚轮切层 · 四序列须已同网格、1 mm；不自动配准或重采样。</p>
    <p v-if="!dicomSource" class="cs-note">{{ segmentationNote }} {{ analysisId ? '分析版本：' + analysisId : '' }} · 掩膜只读；测量按物理毫米保存；保存视图后可恢复当前序列、位置和窗值。</p>
    <p v-if="dicomSource" class="cs-note">Series UID：{{ props.dicomSelection.seriesUid }} · {{ dicomRevision }}</p>
    <p v-if="viewNotice" class="cs-note" role="status">{{ viewNotice }}</p>
    <p class="cs-note cs-drawing-state">{{ measurementDrawing ? '正在绘制测量；按 Esc 取消。' : '' }}</p>
    <p v-if="measurementNotice" class="cs-measurement-notice" role="status">{{ measurementNotice }}</p>
    <p v-if="historicalMeasurements" class="cs-note">{{ historicalMeasurements }} 条旧版本测量保留在历史记录，不叠加到当前版本。</p>
    <p v-if="loading" role="status">正在加载 {{ labels[requestedSequence] || '影像' }}…</p>
    <div v-if="error" class="cs-error" role="alert">Cornerstone3D 渲染不可用：{{ error }}。{{ dicomSource ? 'DICOM 未加载成功，请返回病例检查来源。' : '可在顶部手动选择 Canvas。' }}</div>
    <div class="cs-grid" :style="{ visibility: error ? 'hidden' : 'visible' }">
      <div v-for="view in views" :key="view.id" class="cs-panel">
        <div class="cs-header">{{ view.label }} · {{ dicomSource ? 'DICOM · 身份待确认' : labels[activeSequence] || '序列未标识' }}</div>
        <div :id="view.id" class="cs-viewport" @contextmenu.prevent>
          <span v-for="side in ['top', 'bottom', 'left', 'right']" :key="side" :class="['cs-direction', 'cs-direction-' + side]" :data-side="side">{{ directionLabels[view.id]?.[side] }}</span>
        </div>
      </div>
    </div>
    <div v-if="measurementRows.length" class="cs-measurements">
      <div v-for="row in measurementRows" :key="row.uid" class="cs-measurement-row" :data-saved-id="row.savedId || ''">
        <span>{{ labels[row.sequence] || '单序列' }} · {{ row.view }} · {{ row.lengthMm.toFixed(2) }} mm · {{ row.savedId ? '已保存 #' + row.savedId : '未保存' }}</span>
        <el-button size="small" :disabled="measurementDrawing || measurementSaving" @click="measurements.remove(row.uid)">删除测量</el-button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { Enums, TiledRenderingEngine as RenderingEngine, cache, eventTarget, getRenderingEngines, init, metaData, utilities, setVolumesForViewports, volumeLoader } from '@cornerstonejs/core'
import { Enums as toolEnums, addTool, CrosshairsTool, LengthTool, PanTool, StackScrollTool, ToolGroupManager, WindowLevelTool, ZoomTool, init as initTools, segmentation } from '@cornerstonejs/tools'
import request from '../../api/axios'
import { parseNiftiVolume, sameGeometry } from './niftiGeometry'
import { createMeasurementSession } from './cornerstoneMeasurements'
import { viewportOrientationLabels } from './orientationLabels'

const props = defineProps({ caseId: { type: Number, required: true }, dicomSelection: { type: Object, default: null } })
const dicomSource = Boolean(props.dicomSelection)
const dicomRevision = ref('')
let dicomSession
const emit = defineEmits(['view-saved'])
const id = 'bf-cs-' + crypto.randomUUID()
const views = [
  { id: id + '-axial', label: '轴位 Axial', orientation: Enums.OrientationAxis.AXIAL },
  { id: id + '-sagittal', label: '矢状位 Sagittal', orientation: Enums.OrientationAxis.SAGITTAL },
  { id: id + '-coronal', label: '冠状位 Coronal', orientation: Enums.OrientationAxis.CORONAL },
]
const labels = { t1c: 'T1c · 增强 T1', t1n: 'T1n · 平扫 T1', t2w: 'T2w · T2', t2f: 'FLAIR', dicom: 'DICOM · 身份待确认' }
const primaryTools = [WindowLevelTool, PanTool, ZoomTool, CrosshairsTool, LengthTool]
const dicomMeasurementsAvailable = ref(false)
const dicomViewAvailable = ref(false)
const visibleTools = computed(() => primaryTools.filter(tool => !dicomSource || dicomMeasurementsAvailable.value || tool !== LengthTool))
const toolLabels = { WindowLevel: '窗宽窗位', Pan: '平移', Zoom: '缩放', Crosshairs: '十字线', Length: '距离测量' }
const activeTool = ref('WindowLevel'), error = ref(''), loading = ref(true)
const activeSequence = ref(''), requestedSequence = ref(''), availableSequences = ref([])
const hasSegmentation = ref(false), segmentationVisible = ref(true), segmentationNote = ref('分割状态待核查'), analysisId = ref('')
const controller = new AbortController(), volumes = new Map(), windows = new Map()
const revisions = new Map()
let engine, group, observer, disposed = false, baseGeometry, segmentationAdded = false, mriId
let measurements
let measurementRows = ref([]), measurementDrawing = ref(false), measurementSaving = ref(false), measurementNotice = ref(''), historicalMeasurements = ref(0)
const viewSaving = ref(false), viewNotice = ref('')
let pendingView
let dicomManifest
let dicomViewContext

function dicomSeriesEndpoint() {
  return `/pacs/cases/${props.caseId}/studies/${dicomManifest.study_uid}/series/${dicomManifest.series_uid}`
}

function validateDicomContext(context) {
  const manifest = dicomManifest
  if (context.metadata_sha256 !== manifest.metadata_sha256 || context.archive_fingerprint !== manifest.archive_fingerprint
      || context.study_uid !== manifest.study_uid || context.series_uid !== manifest.series_uid
      || context.archive_id !== manifest.archive_id || context.frame_of_reference_uid !== manifest.geometry.frame_of_reference_uid) {
    throw Error('DICOM来源版本已变化，请重新打开序列')
  }
}
const directionLabels = ref({})
const viewportIds = views.map(v => v.id)

async function fetchVolume(url, key, labelmap = false) {
  const response = await request.get(url, { responseType: 'arraybuffer', signal: controller.signal })
  if (disposed) throw Error('阅片器已关闭')
  const geometry = parseNiftiVolume(response.data, { labelmap, referenceGeometry: labelmap ? baseGeometry : null })
  if (baseGeometry && !sameGeometry(baseGeometry, geometry)) throw Error('影像或掩膜空间不一致，已拒绝叠加/切换')
  const volume = volumeLoader.createLocalVolume(id + '-' + key, {
    ...geometry,
    metadata: { Modality: 'MR', FrameOfReferenceUID: id, PhotometricInterpretation: 'MONOCHROME2' },
  })
  volumes.set(key, volume)
  volume.imageIds.forEach((imageId, k) => {
    utilities.genericMetadataProvider.add(imageId, { type: 'imagePlaneModule', metadata: {
      ...metaData.get('imagePlaneModule', imageId), frameOfReferenceUID: id,
      imageOrientationPatient: geometry.direction.slice(0, 6),
      imagePositionPatient: geometry.origin.map((v, j) => v + k * geometry.spacing[2] * geometry.direction[6 + j]),
      sliceThickness: geometry.spacing[2],
    } })
  })
  return { volume, geometry }
}

async function loadSequence(key, preserve = false) {
  const meta = (await request.get(`/mri/${props.caseId}/volume`, { params: { sequence: key || undefined }, signal: controller.signal })).data.data
  if (disposed) return
  if (mriId !== undefined && mriId !== meta.id) throw Error('影像版本已改变，请重新打开工作站')
  mriId = meta.id
  if (revisions.has(meta.sequence) && revisions.get(meta.sequence) !== meta.source_revision) throw Error('序列文件已改变，请重新打开工作站')
  revisions.set(meta.sequence, meta.source_revision)
  if (preserve && hasSegmentation.value) {
    const current = (await request.get(`/mri/${props.caseId}/segmentation`, { signal: controller.signal })).data.data
    if (!current.available || (current.analysis_run_id || '') !== analysisId.value) throw Error('分割版本已失效或改变，请重新打开工作站')
  }
  if (disposed) return
  const cameras = preserve ? viewportIds.map(v => structuredClone(engine.getViewport(v).getCamera())) : null
  if (preserve) windows.set(activeSequence.value, viewportIds.map(v => engine.getViewport(v).getProperties().voiRange))
  const selected = meta.sequence || ''
  let volume = volumes.get(selected)
  if (!volume) {
    const loaded = await fetchVolume(meta.nifti_url, selected)
    volume = loaded.volume
    baseGeometry ||= loaded.geometry
  }
  if (disposed) return
  if (preserve) group.setToolDisabled(CrosshairsTool.toolName)
  await setVolumesForViewports(engine, [{ volumeId: volume.volumeId }], viewportIds)
  if (disposed) return
  const savedWindow = windows.get(selected)
  viewportIds.forEach((v, i) => {
    const viewport = engine.getViewport(v)
    if (cameras) viewport.setCamera(cameras[i])
    viewport.setProperties({ voiRange: savedWindow?.[i] || { lower: meta.display_min, upper: meta.display_max } })
  })
  availableSequences.value = meta.available_sequences
  activeSequence.value = requestedSequence.value = selected
  if (hasSegmentation.value) await waitForSegmentation()
  if (disposed) return
  if (preserve) {
    if (activeTool.value === CrosshairsTool.toolName) group.setToolActive(CrosshairsTool.toolName, { bindings: [{ mouseButton: toolEnums.MouseBindings.Primary }] })
    else group.setToolPassive(CrosshairsTool.toolName)
    // Tool activation and segmentation attachment can initialize the slice
    // center. Restore the physical cameras after both have completed.
    viewportIds.forEach((v, i) => engine.getViewport(v).setCamera(cameras[i]))
  }
  engine.render()
}

function attachSegmentation() {
  for (const viewportId of viewportIds) {
    if (!segmentationVisible.value) {
      if (segmentation.state.getSegmentationRepresentations(viewportId).some(r => r.segmentationId === id)) segmentation.removeLabelmapRepresentation(viewportId, id, true)
      continue
    }
    // v5 representations belong to viewports, not to a tool group.
    if (!segmentation.state.getSegmentationRepresentations(viewportId).some(r => r.segmentationId === id)) {
      segmentation.addLabelmapRepresentationToViewport(viewportId, [{ segmentationId: id }])
    }
    segmentation.config.visibility.setSegmentationRepresentationVisibility(viewportId, { segmentationId: id }, segmentationVisible.value)
  }
}

function waitForSegmentation() {
  if (!segmentationVisible.value) {
    attachSegmentation()
    engine.render()
    return Promise.resolve()
  }
  return new Promise((resolve, reject) => {
    const pending = new Set(viewportIds)
    const finish = (error) => {
      clearTimeout(timer)
      eventTarget.removeEventListener(toolEnums.Events.SEGMENTATION_RENDERED, onRendered)
      controller.signal.removeEventListener('abort', onAbort)
      error ? reject(error) : resolve()
    }
    const onAbort = () => finish(Error('阅片器已关闭'))
    const onRendered = event => {
      if (event.detail.segmentationId !== id) return
      pending.delete(event.detail.viewportId)
      if (!pending.size) finish()
    }
    const timer = setTimeout(() => finish(Error('分割叠加渲染超时')), 15000)
    eventTarget.addEventListener(toolEnums.Events.SEGMENTATION_RENDERED, onRendered)
    controller.signal.addEventListener('abort', onAbort, { once: true })
    attachSegmentation()
    engine.render()
  })
}

async function switchSequence(key) {
  if (loading.value || key === activeSequence.value) return
  loading.value = true
  error.value = ''
  try { await loadSequence(key, true) }
  catch (e) { if (!disposed) { error.value = e.response?.data?.detail || e.message; requestedSequence.value = activeSequence.value } }
  finally { if (!disposed) loading.value = false }
}

function setTool(name) {
  if (!group) return
  primaryTools.forEach(t => group.setToolPassive(t.toolName))
  group.setToolActive(name, { bindings: [{ mouseButton: toolEnums.MouseBindings.Primary }] })
  activeTool.value = name
}
async function toggleSegmentation() {
  const cameras = viewportIds.map(v => structuredClone(engine.getViewport(v).getCamera()))
  segmentationVisible.value = !segmentationVisible.value
  loading.value = true
  group.setToolDisabled(CrosshairsTool.toolName)
  try {
    await waitForSegmentation()
    if (disposed) return
    if (activeTool.value === CrosshairsTool.toolName) group.setToolActive(CrosshairsTool.toolName, { bindings: [{ mouseButton: toolEnums.MouseBindings.Primary }] })
    else group.setToolPassive(CrosshairsTool.toolName)
    viewportIds.forEach((v, i) => engine.getViewport(v).setCamera(cameras[i]))
    engine.render()
  } catch (e) { if (!disposed) error.value = e.message }
  finally { if (!disposed) loading.value = false }
}
function resetView() {
  viewportIds.forEach(v => engine.getViewport(v).resetCamera())
  engine.render()
}

function updateDirections(event) {
  if (disposed) return
  const viewport = engine.getViewport(event.detail.viewportId)
  const labels = viewportOrientationLabels(viewport)
  if (JSON.stringify(directionLabels.value[viewport.id]) !== JSON.stringify(labels)) directionLabels.value = { ...directionLabels.value, [viewport.id]: labels }
}

function viewSnapshot() {
  const cameras = Object.fromEntries(views.map(view => {
    const c = engine.getViewport(view.id).getCamera()
    return [view.id.split('-').at(-1), { focal_point: [...c.focalPoint], position: [...c.position],
      view_plane_normal: [...c.viewPlaneNormal], view_up: [...c.viewUp], parallel_scale: c.parallelScale }]
  }))
  const ranges = new Map(windows)
  ranges.set(activeSequence.value, viewportIds.map(v => structuredClone(engine.getViewport(v).getProperties().voiRange)))
  return { context: dicomSource ? dicomViewContext : measurements.getContext(), sequence: activeSequence.value || null, segmentation_visible: segmentationVisible.value,
    cameras, window_ranges: Object.fromEntries([...ranges].map(([key, value]) => [key || 'legacy', value])) }
}

async function saveView() {
  if (viewSaving.value || loading.value || measurementDrawing.value || measurementSaving.value) return
  viewSaving.value = true
  try {
    let snapshot = viewSnapshot()
    if (dicomSource) snapshot = { context: snapshot.context, cameras: snapshot.cameras, window_ranges: snapshot.window_ranges.dicom }
    const signature = JSON.stringify(snapshot)
    if (pendingView?.signature !== signature) pendingView = { signature, payload: { ...snapshot, client_uid: crypto.randomUUID() } }
    const endpoint = dicomSource ? dicomSeriesEndpoint() + '/view-state' : `/mri/${props.caseId}/view-state`
    const saved = (await request.post(endpoint, pendingView.payload, { signal: controller.signal })).data.data
    if (disposed) return
    viewNotice.value = `视图已保存 #${saved.id}，刷新后恢复。`
    emit('view-saved')
    pendingView = null
  } catch (e) { if (!disposed) viewNotice.value = '视图保存失败，可重试：' + (e.response?.data?.detail?.message || e.response?.data?.detail || e.message) }
  finally { if (!disposed) viewSaving.value = false }
}

async function restoreView() {
  const endpoint = dicomSource ? dicomSeriesEndpoint() + '/view-state' : `/mri/${props.caseId}/view-state`
  const data = (await request.get(endpoint, { signal: controller.signal })).data.data
  if (disposed) return
  if (dicomSource) {
    validateDicomContext(data.context)
    if (measurements && JSON.stringify(data.context) !== JSON.stringify(measurements.getContext())) throw Error('DICOM病例关联或来源版本已变化，请重新打开序列')
    dicomViewContext = data.context
  }
  if (!data.saved) return
  if (!data.saved.current || (!dicomSource && JSON.stringify(data.context) !== JSON.stringify(measurements.getContext()))) {
    viewNotice.value = dicomSource ? '旧DICOM视图属于其他归档、病例关联或序列元数据版本，当前按默认视图打开。' : '旧视图属于其他影像或分析版本，当前按默认视图打开。'
    return
  }
  const state = dicomSource ? { ...data.saved.state, window_ranges: { dicom: data.saved.state.window_ranges }, sequence: 'dicom', segmentation_visible: false } : data.saved.state
  Object.entries(state.window_ranges).forEach(([key, value]) => windows.set(key === 'legacy' ? '' : key, value))
  segmentationVisible.value = state.segmentation_visible
  if (!dicomSource) {
    if ((state.sequence || '') !== activeSequence.value) await loadSequence(state.sequence || '')
    else if (hasSegmentation.value) await waitForSegmentation()
  }
  if (disposed) return
  group.setToolDisabled(CrosshairsTool.toolName)
  const cameras = views.map(view => {
    const c = state.cameras[view.id.split('-').at(-1)]
    return { focalPoint: c.focal_point, position: c.position, viewPlaneNormal: c.view_plane_normal, viewUp: c.view_up, parallelScale: c.parallel_scale }
  })
  group.setToolPassive(CrosshairsTool.toolName)
  viewportIds.forEach((v, i) => {
    engine.getViewport(v).setCamera(cameras[i])
    engine.getViewport(v).setProperties({ voiRange: state.window_ranges[state.sequence || 'legacy'][i] })
  })
  engine.render()
  viewNotice.value = `已恢复保存视图 #${data.saved.id}。`
}
function releaseVolume(volume) {
  const images = [...volume.imageIds]
  if (cache.getVolume(volume.volumeId)) cache.removeVolumeLoadObject(volume.volumeId)
  for (const imageId of images) if (cache.getImage(imageId)) cache.removeImageLoadObject(imageId)
}

onMounted(async () => {
  try {
    await init()
    await initTools()
    if (disposed) return
    engine = new RenderingEngine(id)
    engine.setViewports(views.map(view => ({ viewportId: view.id, type: Enums.ViewportType.ORTHOGRAPHIC, element: document.getElementById(view.id), defaultOptions: { orientation: view.orientation } })))
    viewportIds.forEach(v => engine.getViewport(v).element.addEventListener(Enums.Events.IMAGE_RENDERED, updateDirections))
    ;[...primaryTools, StackScrollTool].forEach(addTool)
    group = ToolGroupManager.createToolGroup(id)
    ;[...primaryTools, StackScrollTool].forEach(t => group.addTool(t.toolName))
    viewportIds.forEach(v => group.addViewport(v, id))
    if (dicomSource) {
      const selection = props.dicomSelection
      const manifest = (await request.get('/pacs/cases/' + props.caseId + '/studies/' + selection.studyUid + '/series/' + selection.seriesUid + '/view-manifest', { signal: controller.signal })).data.data
      dicomManifest = manifest
      if (disposed) return
      const { createDicomSession } = await import('./dicomVolume')
      if (disposed) return
      dicomSession = createDicomSession(controller.signal)
      const volume = await dicomSession.load(manifest, { caseId: props.caseId, ...selection, baseURL: request.defaults.baseURL, sessionId: id, volumeId: id + '-dicom-' + manifest.metadata_sha256 })
      if (disposed) return
      volumes.set('dicom', volume)
      await setVolumesForViewports(engine, [{ volumeId: volume.volumeId }], viewportIds)
      activeSequence.value = 'dicom'
      dicomRevision.value = '元数据版本：' + manifest.metadata_sha256
      viewNotice.value = manifest.data_role?.toLowerCase().startsWith('synthetic') ? 'SYNTHETIC 合成协议夹具：仅工程验证，不是真实采集或队列验收。' : '成组 DICOM 阅片；用于 AI 分析前，仍需确认四序列身份与空间条件。'
    } else {
      await loadSequence('')
    }
    if (disposed) return
    setTool('WindowLevel')
    group.setToolActive(StackScrollTool.toolName, { bindings: [{ mouseButton: toolEnums.MouseBindings.Wheel }] })
    if (!dicomSource) {
    const info = (await request.get(`/mri/${props.caseId}/segmentation`, { signal: controller.signal })).data.data
    analysisId.value = info.analysis_run_id || ''
    segmentationNote.value = info.disclaimer || '当前没有可用分割'
    if (info.available && info.mask_url) {
      const mask = (await fetchVolume(info.mask_url, 'mask', true)).volume
      segmentation.addSegmentations([{ segmentationId: id, representation: { type: toolEnums.SegmentationRepresentations.Labelmap, data: { volumeId: mask.volumeId } } }])
      segmentationAdded = true
      hasSegmentation.value = true
      await waitForSegmentation()
    }
    if (disposed) return
    measurements = createMeasurementSession({ caseId: props.caseId, frameId: id, engine, views, group, signal: controller.signal, getSequence: () => activeSequence.value, mriId, revisions })
    measurementRows = measurements.rows; measurementDrawing = measurements.drawing; measurementSaving = measurements.saving
    measurementNotice = measurements.notice; historicalMeasurements = measurements.historicalCount
    await measurements.init()
    if (disposed) return
    await restoreView()
    }
    if (dicomSource && dicomManifest.saved_dicom_annotations_available) {
      const manifest = dicomManifest
      const endpoint = dicomSeriesEndpoint() + '/measurements'
      const transport = {
        list: async () => (await request.get(endpoint, { signal: controller.signal })).data.data,
        validate: validateDicomContext,
        save: async payload => { const { reference_sequence, ...body } = payload; return (await request.post(endpoint, body, { signal: controller.signal })).data.data },
        remove: (itemId, context) => request.delete(endpoint + '/' + itemId, { data: { context }, signal: controller.signal }),
      }
      measurements = createMeasurementSession({ caseId: props.caseId, frameId: manifest.geometry.frame_of_reference_uid,
        sessionId: id, engine, views, group, signal: controller.signal, getSequence: () => 'dicom', transport })
      measurementRows = measurements.rows; measurementDrawing = measurements.drawing; measurementSaving = measurements.saving
      measurementNotice = measurements.notice; historicalMeasurements = measurements.historicalCount
      await measurements.init()
      dicomMeasurementsAvailable.value = true
    }
    if (dicomSource && dicomManifest.dicom_view_state_available) {
      await restoreView()
      dicomViewAvailable.value = true
    }
    if (disposed) return
    observer = new ResizeObserver(() => { if (!disposed) engine.resize(true, true) })
    observer.observe(document.getElementById(views[0].id).parentElement.parentElement)
    engine.render()
  } catch (e) {
    dicomSession?.dispose()
    if (!disposed) error.value = e.response?.data?.detail?.message || e.response?.data?.detail || e.message
  }
  finally { if (!disposed) loading.value = false }
})

onBeforeUnmount(() => {
  disposed = true
  measurements?.dispose()
  controller.abort()
  dicomSession?.dispose()
  observer?.disconnect()
  if (engine) viewportIds.forEach(v => engine.getViewport(v)?.element.removeEventListener(Enums.Events.IMAGE_RENDERED, updateDirections))
  if (segmentationAdded) segmentation.removeSegmentation(id)
  if (group) { group.setToolDisabled(CrosshairsTool.toolName); ToolGroupManager.destroyToolGroup(id) }
  // Three modest MPR viewports share one WebGL context. Explicitly release
  // that owned context after teardown rather than waiting for browser GC.
  const gl = engine?.getOffscreenMultiRenderWindow()?.getOpenGLRenderWindow()?.get3DContext()
  engine?.destroy()
  gl?.getExtension('WEBGL_lose_context')?.loseContext()
  volumes.forEach(releaseVolume)
  volumes.clear()
  if (!getRenderingEngines().length && cache.getCacheSize() === 0) utilities.genericMetadataProvider.clear()
  baseGeometry = null
})
</script>

<style scoped>
.cs-viewer { color: #e2e8f0; }
.cs-toolbar { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.cs-toolbar select { background: #172033; color: #e2e8f0; padding: 6px; }
.cs-note { font-size: 12px; color: #94a3b8; overflow-wrap: anywhere; }
.cs-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; }
.cs-panel { min-width: 0; border: 1px solid #334155; background: #020617; border-radius: 6px; overflow: hidden; }
.cs-header { padding: 8px 10px; font-size: 12px; background: #172033; }
.cs-viewport { width: 100%; height: 420px; background: #000; position: relative; touch-action: none; }
.cs-error { padding: 20px; color: #fca5a5; }
.cs-measurements { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 8px; }
.cs-measurement-row { display: flex; align-items: center; gap: 8px; padding: 6px; background: #172033; font-size: 12px; }
.cs-measurement-notice { font-size: 12px; color: #fbbf24; }
.cs-drawing-state { min-height: 16px; line-height: 16px; }
.cs-direction { position: absolute; z-index: 2; color: #f8fafc; font: bold 13px monospace; pointer-events: none; text-shadow: 0 1px 2px #000; }
.cs-direction-top { top: 5px; left: 50%; transform: translateX(-50%); }
.cs-direction-bottom { bottom: 5px; left: 50%; transform: translateX(-50%); }
.cs-direction-left { left: 5px; top: 50%; transform: translateY(-50%); }
.cs-direction-right { right: 5px; top: 50%; transform: translateY(-50%); }
@media (max-width: 960px) { .cs-grid { grid-template-columns: 1fr; } }
</style>
