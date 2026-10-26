<template>
  <section class="archive-page">
    <header class="archive-heading">
      <div>
        <h1>隔离 DICOM 研究归档</h1>
        <p>浏览隔离 Stage7 Orthanc；仅已登记来源可在复核后确认导入。检查保持独立，不自动关联 NIfTI 病例；转换需完整四序列与空间审核，AI 提交未开放。</p>
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
      <template #header>已登记的研究来源</template>
      <el-alert title="核验会重查已保存的许可、准备清单、像素哈希和技术记录，不会导入数据、关联 NIfTI 病例或启用 AI。" type="info" :closable="false" />
      <el-empty v-if="!sourceCandidates.length" description="当前运行时没有已登记的本机来源；不会把归档列表自动转换成候选来源。" />
      <el-table v-else :data="sourceCandidates" row-key="candidate_id" border>
        <el-table-column label="来源" min-width="200"><template #default>已审核公开研究 MR 派生资料</template></el-table-column>
        <el-table-column prop="instance_count" label="登记实例数" width="110" />
        <el-table-column label="授权范围" min-width="200"><template #default="scope">{{ scope.row.scope }}</template></el-table-column>
        <el-table-column label="核验结果" min-width="220"><template #default="scope">{{ sourceChecks[scope.row.candidate_id]?.source_status || '尚未核验' }} · {{ sourceChecks[scope.row.candidate_id]?.archive_status || '—' }}</template></el-table-column>
        <el-table-column label="操作" width="140"><template #default="scope"><el-button size="small" :loading="sourceVerifying === scope.row.candidate_id" @click="verifySource(scope.row)">核验来源</el-button></template></el-table-column>
      </el-table>
      <el-alert v-if="sourceError" :title="sourceError" type="error" :closable="false" />
      <template v-if="verifiedSource">
        <div class="status-grid">
          <span>来源完整性：{{ verifiedSource.source_integrity }}</span><span>归档状态：{{ verifiedSource.archive_status }}</span>
          <span>Study 数：{{ verifiedSource.archive_study_count }}</span><span>Series 数：{{ verifiedSource.archive_series_count }}</span>
          <span>实例：{{ verifiedSource.archive_instance_count }} / {{ verifiedSource.source_instance_count }}</span><span>病例关联：{{ verifiedSource.case_link_status }}</span>
        </div>
        <template v-if="verifiedSource.archive_status === 'NOT_IMPORTED'">
          <el-checkbox v-model="sourceImportAck">我确认此已审核来源只导入到隔离 Stage7 研究归档，不关联病例、不进入正式 PACS、不提交 AI。</el-checkbox>
          <el-button type="primary" :disabled="!sourceImportAck || sourceImportBusy" :loading="sourceImportBusy" @click="importVerifiedSource">仅导入到隔离归档</el-button>
        </template>
        <el-alert v-if="sourceImportResult" :title="`隔离导入状态：${sourceImportResult.state}；已核验 ${sourceImportResult.verified}/${sourceImportResult.total} 个实例。`" :type="sourceImportResult.state === 'succeeded' ? 'success' : 'warning'" :closable="false" />
        <el-alert :title="verifiedSource.conversion_block_reason" type="warning" :closable="false" />
        <p>当前登记来源只包含一个 MR Series，不满足四序列转换方案。不会创建部分转换任务，也不会将检查挂到任何现有 NIfTI 病例。补齐同一检查下来源已核验的 T1/T1GD/T2/FLAIR 并通过空间审核后，才能使用现有受控转换流程。</p>
        <el-button v-if="studies.some(row => row.study_uid === verifiedSource.study_uid)" @click="selectStudy(studies.find(row => row.study_uid === verifiedSource.study_uid))">查看该归档检查</el-button>
      </template>
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
const status = ref(null), studies = ref([]), selectedStudy = ref(null), seriesRows = ref([]), sourceCandidates = ref([])
const loading = ref(false), seriesLoading = ref(false), error = ref(''), seriesError = ref(''), selection = ref(null)
const sourceChecks = ref({}), sourceError = ref(''), sourceVerifying = ref(''), verifiedSource = ref(null)
const sourceImportAck = ref(false), sourceImportBusy = ref(false), sourceImportResult = ref(null)
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
    try { sourceCandidates.value = (await request.get('/pacs/import-candidates')).data.data.items || [] }
    catch (candidateError) { sourceError.value = String(candidateError.response?.data?.detail?.message || candidateError.response?.data?.detail || candidateError.message) }
    selectedStudy.value = null; seriesRows.value = []; selection.value = null
  } catch (e) { error.value = String(e.response?.data?.detail?.message || e.response?.data?.detail || e.message) }
  finally { loading.value = false }
}

async function verifySource(row) {
  sourceVerifying.value = row.candidate_id; sourceError.value = ''
  try {
    const result = (await request.get(`/pacs/import-candidates/${encodeURIComponent(row.candidate_id)}/verify`)).data.data
    sourceChecks.value = { ...sourceChecks.value, [row.candidate_id]: result }
    verifiedSource.value = result
  } catch (e) { sourceError.value = String(e.response?.data?.detail?.message || e.response?.data?.detail || e.message) }
  finally { sourceVerifying.value = '' }
}

async function importVerifiedSource() {
  if (!sourceImportAck.value || !verifiedSource.value?.candidate_id) return
  sourceImportBusy.value = true; sourceError.value = ''; sourceImportResult.value = null
  try {
    sourceImportResult.value = (await request.post(`/pacs/imports/${encodeURIComponent(verifiedSource.value.candidate_id)}`, {
      acknowledge_reviewed_local_viewing_only: true,
    })).data.data
    const row = sourceCandidates.value.find(item => item.candidate_id === verifiedSource.value.candidate_id)
    if (row) await verifySource(row)
    sourceImportAck.value = false
  } catch (e) { sourceError.value = String(e.response?.data?.detail?.message || e.response?.data?.detail || e.message) }
  finally { sourceImportBusy.value = false }
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
