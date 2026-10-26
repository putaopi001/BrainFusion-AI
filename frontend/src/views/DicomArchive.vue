<template>
  <section class="archive-page">
    <header class="archive-heading">
      <div>
        <h1>隔离 DICOM 研究归档</h1>
        <p>只读浏览 Stage7 Orthanc；检查保持独立，不自动关联任何 NIfTI 病例，也不提供转换或 AI 提交。</p>
      </div>
      <el-button :loading="loading" @click="refresh">刷新归档</el-button>
    </header>

    <el-alert v-if="error" :title="error" type="error" :closable="false" />
    <el-card class="archive-card">
      <template #header><div class="card-header"><span>连接状态</span><el-tag :type="connected ? 'success' : 'info'">{{ connected ? '已连接 · 只读研究归档' : '不可用' }}</el-tag></div></template>
      <p>{{ status?.message || '正在读取隔离归档状态。' }}</p>
      <div class="status-grid">
        <span>归档：{{ status?.archive_id || '—' }}</span><span>Orthanc：{{ status?.orthanc_version || '—' }}</span>
        <span>检查：{{ studies.length }}</span><span>序列：{{ totalSeries }}</span><span>实例：{{ totalInstances }}</span>
      </div>
      <el-alert v-if="!status?.dicom_view_available" title="像素读取未在当前研究进程启用。检查列表仍可只读查看。" type="warning" :closable="false" />
      <el-alert v-else title="像素读取仅在隔离研究演示进程中启用；正式 PACS 配置与门控未修改。" type="info" :closable="false" />
    </el-card>

    <el-card class="archive-card">
      <template #header>已归档检查</template>
      <el-empty v-if="!loading && !studies.length" description="此隔离归档当前没有可查询检查" />
      <el-table v-else :data="studies" row-key="study_uid" border>
        <el-table-column prop="study_uid" label="Study UID" min-width="260" />
        <el-table-column label="模态"><template #default="scope">{{ scope.row.modalities?.join(', ') || '—' }}</template></el-table-column>
        <el-table-column prop="series_count" label="序列数" width="90" />
        <el-table-column prop="instance_count" label="实例数" width="90" />
        <el-table-column label="操作" width="130"><template #default="scope"><el-button size="small" @click="selectStudy(scope.row)">查看序列</el-button></template></el-table-column>
      </el-table>
    </el-card>

    <el-card v-if="selectedStudy" class="archive-card">
      <template #header><div>序列 · Study {{ selectedStudy.study_uid }}</div></template>
      <el-alert v-if="seriesError" :title="seriesError" type="error" :closable="false" />
      <el-table :data="seriesRows" row-key="series_uid" border>
        <el-table-column prop="series_number" label="Series #" width="100" />
        <el-table-column prop="modality" label="模态" width="100" />
        <el-table-column prop="series_uid" label="Series UID" min-width="260" />
        <el-table-column prop="instance_count" label="实例数" width="100" />
        <el-table-column label="操作" width="150">
          <template #default="scope"><el-button size="small" :disabled="!status?.dicom_view_available || Number(scope.row.instance_count) < 2" @click="openSeries(scope.row)">打开真实像素</el-button></template>
        </el-table-column>
      </el-table>
      <el-alert class="archive-note" title="三维阅片要求至少两张受支持的经典单帧 MR 切片。单实例、非 MR、多帧或几何不一致序列会被拒绝；不进行重采样、病例关联或 AI 推理。" type="info" :closable="false" />
    </el-card>

    <el-card v-if="selection" class="archive-card viewer-card">
      <template #header><div class="card-header"><span>隔离序列阅片 · {{ selection.seriesUid }}</span><el-button size="small" @click="selection = null">关闭阅片器</el-button></div></template>
      <CornerstoneViewer :key="selection.studyUid + ':' + selection.seriesUid" :dicom-selection="selection" archive-only />
    </el-card>
  </section>
</template>

<script setup>
import { computed, defineAsyncComponent, onMounted, ref } from 'vue'
import request from '../api/axios'

const CornerstoneViewer = defineAsyncComponent(() => import('../components/mri/CornerstoneViewer.vue'))
const status = ref(null), studies = ref([]), selectedStudy = ref(null), seriesRows = ref([])
const loading = ref(false), seriesLoading = ref(false), error = ref(''), seriesError = ref(''), selection = ref(null)
const connected = computed(() => status.value?.state === 'ready' && status.value?.read_available)
const totalSeries = computed(() => studies.value.reduce((sum, row) => sum + (Number(row.series_count) || 0), 0))
const totalInstances = computed(() => studies.value.reduce((sum, row) => sum + (Number(row.instance_count) || 0), 0))

async function refresh() {
  loading.value = true; error.value = ''; status.value = null; studies.value = []
  try {
    const [statusResponse, studiesResponse] = await Promise.all([
      request.get('/pacs/status'), request.get('/pacs/studies', { params: { limit: 100 } }),
    ])
    status.value = statusResponse.data.data
    if (!status.value?.read_available) throw new Error(status.value?.message || '隔离归档不可用。')
    studies.value = studiesResponse.data.data.items || []
    selectedStudy.value = null; seriesRows.value = []; selection.value = null
  } catch (e) { error.value = String(e.response?.data?.detail?.message || e.response?.data?.detail || e.message) }
  finally { loading.value = false }
}

async function selectStudy(study) {
  selectedStudy.value = study; seriesRows.value = []; selection.value = null; seriesError.value = ''; seriesLoading.value = true
  try { seriesRows.value = (await request.get(`/pacs/studies/${encodeURIComponent(study.study_uid)}/series`, { params: { limit: 100 } })).data.data.items || [] }
  catch (e) { seriesError.value = String(e.response?.data?.detail?.message || e.response?.data?.detail || e.message) }
  finally { seriesLoading.value = false }
}

function openSeries(row) {
  selection.value = { studyUid: selectedStudy.value.study_uid, seriesUid: row.series_uid }
}

onMounted(refresh)
</script>

<style scoped>
.archive-page { display: grid; gap: 16px; padding: 20px; }
.archive-heading,.card-header { display:flex; align-items:center; justify-content:space-between; gap:12px; }
.archive-heading h1 { margin:0 0 6px; }
.archive-heading p,.archive-card p { color:#64748b; }
.status-grid { display:flex; flex-wrap:wrap; gap:12px 24px; margin:12px 0; font-size:13px; }
.archive-note { margin-top:14px; }
.viewer-card { min-height:400px; }
</style>
