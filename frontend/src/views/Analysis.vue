<template>
  <div class="page">
    <h1>MRI 分割分析</h1>
    <el-alert title="上传同一患者、已配准的四个 MRI 序列。结果用于科研与医生复核。" :closable="false" />
    <el-card class="panel">
      <p>病例编号：{{ caseId || '请从病例详情进入' }}</p>
      <label v-for="item in sequences" :key="`${caseId}-${item.key}`" class="sequence">{{ item.label }} <input type="file" accept=".nii,.nii.gz" :disabled="busy" @change="files[item.key] = $event.target.files[0]" /></label>
      <el-button :disabled="!caseId || !complete || busy" :loading="uploading" @click="upload">上传四序列</el-button>
      <el-button type="primary" :disabled="!caseId || busy" :loading="starting" @click="start">{{ run?.state === 'failed' ? '重试分割模型' : '运行分割模型' }}</el-button>
      <el-button :disabled="!caseId || uploading || starting" @click="refresh">刷新任务</el-button>
      <p>任务状态：{{ stateText }}</p>
      <p v-if="run" class="analysis-state" :data-run-id="run.id">分析版本：{{ run.id }}</p>
      <el-alert v-if="error" :title="error" type="error" :closable="false" />
    </el-card>
    <section v-if="caseId" class="panel analysis-history" aria-label="分析历史">
      <div class="history-header"><strong>分析历史</strong><el-button :disabled="historyLoading" :loading="historyLoading" @click="refreshHistory()">刷新分析历史</el-button></div>
      <el-alert v-if="historyError" :title="historyError" type="warning" :closable="false" />
      <ul v-if="historyRows.length">
        <li v-for="item in historyRows" :key="item.id" :data-run-id="item.id">
          <span>{{ item.current ? '当前版本' : '历史版本' }} · {{ historyStateText(item.state) }}</span>
          <code>{{ item.id }}</code>
          <time v-if="item.created_time">{{ item.created_time }}</time>
          <p v-if="!item.current && item.state === 'succeeded'">已保留为历史，不用于当前结果、医生复核或报告。</p>
        </li>
      </ul>
      <p v-else>当前病例还没有分析记录。</p>
    </section>
    <el-card v-if="run?.state === 'succeeded' && !run.stale && run.result" class="panel">
      <p>模型：{{ run.result?.model }}</p><p>分析版本：{{ run.id }}</p>
      <table><thead><tr><th>区域</th><th>体积（mL）</th></tr></thead><tbody><tr v-for="(value, region) in run.result?.volumes_ml" :key="region"><td>{{ region }}</td><td>{{ value }}</td></tr></tbody></table>
      <p>WT：全肿瘤；TC：肿瘤核心；ET：增强肿瘤。</p>
      <el-button @click="router.push(`/case/${caseId}`)">阅片与医生复核</el-button>
      <el-button @click="router.push(`/research?case_id=${caseId}`)">自动掩膜特征研究</el-button>
    </el-card>
  </div>
</template>
<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import request from '../api/axios'
const route = useRoute(), router = useRouter()
const caseId = computed(() => String(route.query.case_id || ''))
const sequences = [{ key: 't1c', label: '增强 T1' }, { key: 't1n', label: '平扫 T1' }, { key: 't2w', label: 'T2' }, { key: 't2f', label: 'FLAIR' }]
const files = ref({}), run = ref(null), error = ref(''), uploading = ref(false), starting = ref(false)
const statusKnown = ref(false), historyRows = ref([]), historyError = ref(''), historyLoading = ref(false)
let historyGeneration = 0
const historyStateText = value => ({ queued: '排队中', running: '分析中', succeeded: '完成', failed: '失败' }[value] || '未知状态')
const complete = computed(() => sequences.every(item => files.value[item.key]))
const busy = computed(() => !statusKnown.value || uploading.value || starting.value || ['queued', 'running'].includes(run.value?.state))
const stateText = computed(() => !statusKnown.value ? '状态未确认，请刷新任务' : run.value?.stale ? '结果已失效，请重新分析（历史保留）' : ({ queued: '排队中', running: '分析中', succeeded: '完成', failed: '失败' }[run.value?.state] || '未启动'))
let timer, disposed = false, generation = 0
const message = e => String(e.response?.data?.detail || e.message || '请求失败')
async function refreshHistory(id = caseId.value) {
  if (!id || disposed) return
  const ticket = ++historyGeneration
  historyLoading.value = true; historyError.value = ''
  try {
    const response = await request.get(`/analysis/${id}/history`)
    if (disposed || caseId.value !== id || ticket !== historyGeneration) return
    historyRows.value = Array.isArray(response.data.data) ? response.data.data : []
  } catch (e) {
    if (!disposed && caseId.value === id && ticket === historyGeneration) historyError.value = message(e)
  } finally { if (ticket === historyGeneration) historyLoading.value = false }
}
async function refresh() {
  if (!caseId.value || disposed) return
  clearTimeout(timer)
  const id = caseId.value, ticket = ++generation
  const historyPromise = refreshHistory(id)
  try {
    const job = (await request.get(`/analysis/${id}`)).data.data
    if (disposed || caseId.value !== id || ticket !== generation) return
    run.value = job; statusKnown.value = true; error.value = job?.error || ''
    await historyPromise
    if (['queued', 'running'].includes(job?.state)) timer = setTimeout(refresh, 2000)
  } catch (e) {
    if (disposed || caseId.value !== id || ticket !== generation) return
    run.value = null; statusKnown.value = false; error.value = message(e)
    await historyPromise
  }
}
async function upload() {
  const id = caseId.value; ++generation
  uploading.value = true; error.value = ''; clearTimeout(timer)
  try {
    const form = new FormData(); sequences.forEach(item => form.append(item.key, files.value[item.key]))
    await request.post(`/studies/${id}`, form, { timeout: 120000 })
    if (!disposed && caseId.value === id) await refresh()
  } catch (e) {
    if (!disposed && caseId.value === id) { error.value = message(e); if (e.response?.status === 409) await refresh() }
  } finally { if (caseId.value === id) uploading.value = false }
}
async function start() {
  const id = caseId.value; ++generation
  starting.value = true; error.value = ''; clearTimeout(timer)
  try {
    const job = (await request.post(`/analysis/${id}`)).data.data
    if (!disposed && caseId.value === id) { run.value = job; await refresh() }
  } catch (e) {
    if (!disposed && caseId.value === id) {
      error.value = message(e)
      // Another tab may already have submitted; resume the existing task, not a new run.
      if (e.response?.status === 409) await refresh()
    }
  } finally { if (caseId.value === id) starting.value = false }
}
onMounted(refresh)
watch(caseId, () => { ++generation; ++historyGeneration; clearTimeout(timer); run.value = null; historyRows.value = []; historyError.value = ''; historyLoading.value = false; files.value = {}; error.value = ''; statusKnown.value = false; uploading.value = starting.value = false; refresh() })
onUnmounted(() => { disposed = true; ++generation; clearTimeout(timer) })
</script>
<style scoped>
.page { padding: 24px; } .panel { margin-top: 16px; } .sequence { display: block; margin: 14px 0; } th, td { padding: 8px 20px; text-align: left; } .history-header { display:flex; align-items:center; justify-content:space-between; gap:12px; } .analysis-history ul { padding-left:20px; } .analysis-history li { padding:8px 0; } .analysis-history code { margin-left:10px; overflow-wrap:anywhere; } .analysis-history time { display:block; color:#64748b; font-size:12px; }
</style>
