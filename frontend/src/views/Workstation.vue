<template>
  <div class="ws-page">
    <!-- PACS 顶部患者/检查信息栏 -->
    <header class="ws-banner">
      <div class="ws-brand">BrainFusion AI · 阅片工作站</div>
      <div class="ws-patient">
        <span class="ws-name">{{ patient.name || "—" }}</span>
        <span class="ws-meta">{{ genderText }} · {{ patient.age != null ? patient.age + " 岁" : "—" }}</span>
        <span class="ws-meta">病例 #{{ caseId }}</span>
      </div>
      <div class="ws-study">
        <el-tag size="small" type="info" effect="plain">{{ mri.modality || "MRI" }}</el-tag>
        <span class="ws-filename">{{ dicomRequested ? 'DICOM · Series ' + dicomSelection.seriesUid : mri.filename || '—' }}</span>
      </div>
      <div class="ws-actions">
        <el-radio-group v-model="renderer" size="small" aria-label="阅片引擎">
          <el-radio-button value="canvas" :disabled="dicomRequested">Canvas（已验入口）</el-radio-button>
          <el-radio-button value="cornerstone">Cornerstone3D（迁移验证）</el-radio-button>
        </el-radio-group>
        <el-button v-if="dicomRequested && mri.file_url" size="small" @click="openNifti">打开当前病例 NIfTI</el-button>
        <el-button size="small" @click="goBack">{{ caseId ? "返回病例详情" : "返回病例管理" }}</el-button>
      </div>
    </header>

    <div class="ws-body">
      <el-alert v-if="loadError" :title="loadError" type="error" :closable="false" />
      <CornerstoneViewer v-if="!loadError && caseLoaded && (dicomRequested || mri.file_url) && renderer === 'cornerstone'" :key="caseId + ':' + mri.id + ':' + (dicomRequested ? dicomSelection.studyUid + ':' + dicomSelection.seriesUid : 'nifti')" :case-id="Number(caseId)" :dicom-selection="dicomRequested ? dicomSelection : null" @view-saved="rememberRenderer" />
      <MRIViewer
        v-else-if="!loadError && caseLoaded && !dicomRequested && mri.file_url"
        :key="caseId + ':' + mri.id"
        :case-id="Number(caseId)"
        :file-url="mri.file_url"
        :slice-url="mri.slice_url"
        :preview-urls="mri.preview_urls"
        :preview-views="mri.preview_views"
        :filename="mri.filename"
        :patient-name="patient.name"
      />
      <el-empty v-else-if="!loadError" :description="dicomRequested ? '正在核对 DICOM 所属病例' : '该病例暂无 MRI 影像，请先上传'" />
    </div>
  </div>
</template>

<script setup>
import { computed, defineAsyncComponent, h, ref, watch } from "vue"
import { useRoute, useRouter } from "vue-router"
import request from "../api/axios"
import MRIViewer from "../components/mri/MRIViewer.vue"
const CornerstoneViewer = defineAsyncComponent({
  loader: () => import('../components/mri/CornerstoneViewer.vue'),
  timeout: 45000,
  errorComponent: { render: () => h('p', { role: 'alert' }, 'Cornerstone3D 模块加载失败，请返回病例详情并查看服务日志。') },
})

const route = useRoute()
const router = useRouter()

const caseId = computed(() => {
  const id = String(route.params.id || "")
  return /^[1-9]\d*$/.test(id) && Number.isSafeInteger(Number(id)) ? id : ""
})
const dicomRequested = computed(() => route.query.source === 'dicom')
const dicomSelection = computed(() => ({ studyUid: String(route.query.study_uid || ''), seriesUid: String(route.query.series_uid || '') }))
const caseLoaded = ref(false)
const patient = ref({})
const mri = ref({})
const renderer = ref(dicomRequested.value || route.query.viewer === 'cornerstone' ? 'cornerstone' : 'canvas')
const loadError = ref('')
let loadVersion = 0

const genderText = computed(() => {
  if (patient.value.gender === "male") return "男"
  if (patient.value.gender === "female") return "女"
  return patient.value.gender || "—"
})

async function load() {
  const version = ++loadVersion
  mri.value = {}; patient.value = {}; loadError.value = ''
  caseLoaded.value = false
  if (!caseId.value) {
    loadError.value = '病例链接无效，请从病例管理选择病例。'
    return
  }
  try {
    const res = await request.get("/cases/" + caseId.value + "/detail")
    const data = res.data.data || {}
    if (version !== loadVersion) return
    patient.value = data.patient || {}
    mri.value = data.mri || {}
    caseLoaded.value = true
  } catch (e) {
    if (version === loadVersion) loadError.value = '病例加载失败：' + (e.response?.data?.detail || e.message)
  }
}

function goBack() {
  router.push(caseId.value ? "/case/" + caseId.value : "/cases")
}

function rememberRenderer() {
  router.replace({ query: { ...route.query, viewer: 'cornerstone' } })
}
function openNifti() {
  const query = { ...route.query, viewer: 'cornerstone' }
  delete query.source; delete query.study_uid; delete query.series_uid
  router.push({ query })
}
watch(renderer, value => {
  if (dicomRequested.value) { renderer.value = 'cornerstone'; return }
  if (value === 'canvas' && route.query.viewer) {
    const query = { ...route.query }; delete query.viewer
    router.replace({ query })
  }
})
watch(() => [route.query.viewer, route.query.source], () => {
  if (dicomRequested.value || route.query.viewer === 'cornerstone') renderer.value = 'cornerstone'
})

watch(caseId, load, { immediate: true })
</script>

<style scoped>
.ws-page { min-height: 100vh; background: #060b16; color: #e2e8f0; }
.ws-banner {
  display: flex;
  align-items: center;
  gap: 24px;
  padding: 10px 20px;
  background: #0b1220;
  border-bottom: 1px solid #1e293b;
  flex-wrap: wrap;
}
.ws-brand { font-size: 14px; font-weight: 700; color: #38bdf8; }
.ws-patient { display: flex; align-items: baseline; gap: 12px; }
.ws-name { font-size: 16px; font-weight: 600; color: #f8fafc; }
.ws-meta { font-size: 12px; color: #94a3b8; }
.ws-study { display: flex; align-items: center; gap: 8px; flex: 1; min-width: 200px; }
.ws-filename { font-size: 12px; color: #cbd5e1; }
.ws-actions { margin-left: auto; }
.ws-body { padding: 12px; }
</style>
