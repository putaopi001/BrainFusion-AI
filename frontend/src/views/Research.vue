<template>
  <div class="research-page">
    <h1>IDH 与融合研究</h1>
    <p>研究终点：IDH1/2 原始值 = 1；0/1 的生物学编码尚待核实。研究概率不用于通用风险、肿瘤检测或治疗建议。</p>
    <el-alert title="研究原型：分类模型在参考掩膜特征上拟合；自动掩膜输入仅作工程迁移验证，尚无独立临床评价。" type="warning" :closable="false" />
    <el-alert v-if="error" :title="error" type="error" :closable="false" class="panel" />
    <template v-if="summary">
      <el-card class="panel">
        <p>实验版本：{{ summary.run_id }}</p>
        <p>患者 {{ summary.audit.cohort_patients }} 名；训练 {{ summary.split_sizes.train }} / 验证 {{ summary.split_sizes.validation }} / 探索性测试 {{ summary.split_sizes.test }}；CPU 运行。</p>
        <p>五个工程样本已从拟合、验证和测试中排除；标签未知和提取错误患者已隔离。</p>
        <el-table :data="modelRows" border><el-table-column prop="name" label="方法" /><el-table-column prop="auc" label="探索性测试 AUC" /><el-table-column prop="accuracy" label="平衡准确率" /><el-table-column prop="brier" label="Brier" /></el-table>
        <p>TOPSIS 临床/影像组学权重：{{ summary.fusion.validation_topsis.weights.join(' / ') }}。权重只依据验证集；当前结果没有证明 TOPSIS 优于平均融合。</p>
      </el-card>
      <el-card class="panel">
        <template #header>五例开发样本：加载真实模型计算概率</template>
        <el-select v-model="selected" style="width: 200px" @change="loadPatient"><el-option v-for="id in ['4','13','16','17','19']" :key="id" :value="id" :label="`数据集患者 ${id}`" /></el-select>
        <el-button :loading="patientLoading" @click="loadPatient">计算研究结果</el-button>
        <template v-if="patient">
          <p>源患者 {{ patient.source_patient_id }}；年龄 {{ patient.clinical_input.age }}；female={{ patient.clinical_input.female }}；参考标签 {{ patient.reference_label ?? '缺失' }}</p>
          <p>目标：IDH1/2=1 的研究概率。</p>
          <el-table :data="probabilityRows" border><el-table-column prop="name" label="方法" /><el-table-column prop="value" label="概率" /></el-table>
          <p>{{ patient.disclaimer }}</p>
        </template>
      </el-card>
      <el-card class="panel">
        <template #header>临床基线输入</template>
        <label>年龄 <el-input-number v-model="age" :min="0" :max="120" /></label>
        <el-select v-model="female" style="width: 120px"><el-option :value="false" label="male" /><el-option :value="true" label="female" /></el-select>
        <el-button :loading="clinicalLoading" @click="predictClinical">计算临床概率</el-button>
        <p v-if="clinical">{{ (clinical.probability * 100).toFixed(1) }}% — {{ clinical.disclaimer }}</p>
      </el-card>
      <el-card class="panel">
        <template #header>当前病例：自动掩膜特征研究</template>
        <p>临床输入默认读取关联患者；可保存此病例独立的研究输入版本。特征在 CPU 上提取，绑定分割及临床输入版本。</p>
        <el-select v-model="featureCase" class="case-feature-select" style="width: 360px" placeholder="选择已分析病例" @change="changeFeatureCase">
          <el-option v-for="item in cases" :key="item.id" :value="item.id" :label="`病例 ${item.id} · ${item.patient_name}`" />
        </el-select>
        <div v-if="caseClinical" class="case-clinical-input">
          <p>患者编号 {{ caseClinical.patient_id }}；输入来源：{{ caseClinical.source === 'associated_patient' ? '关联患者资料' : '此病例研究输入（患者资料未修改）' }}；版本 {{ caseClinical.version }}</p>
          <label>病例研究年龄 <el-input-number v-model="caseAge" class="case-age" :min="0" :max="120" :disabled="featureBusy" /></label>
          <el-select v-model="caseFemale" class="case-sex" style="width: 160px" placeholder="性别未知，需确认" :disabled="featureBusy"><el-option :value="false" label="男（male）" /><el-option :value="true" label="女（female）" /></el-select>
          <el-button :disabled="!featureInputDirty || caseAge == null || caseFemale == null || featureBusy" :loading="clinicalSaving" @click="saveCaseClinical">保存病例研究输入</el-button>
          <el-alert v-if="!caseClinical.available" :title="caseClinical.reason" type="warning" :closable="false" />
          <el-alert v-if="featureInputDirty" title="研究输入已修改但尚未保存；旧概率暂不显示。保存后需按新版本重新计算。" type="warning" :closable="false" />
        </div>
        <el-button :disabled="!featureCase || featureBusy || clinicalSaving || !caseClinical?.available || featureInputDirty" :loading="featureSubmitting" @click="startFeatures">提取自动掩膜特征</el-button>
        <el-button :disabled="!featureCase" @click="refreshFeature">刷新任务</el-button>
        <el-alert v-if="featureError" :title="featureError" type="error" :closable="false" />
        <template v-if="featureJob">
          <p class="feature-state" :data-job-id="featureJob.id">特征任务：{{ featureJob.stale ? '结果已失效' : featureJob.state }}；分割版本 {{ featureJob.analysis_run_id }}；研究版本 {{ featureJob.research_run_id }}</p>
          <p>本次临床输入：年龄 {{ featureJob.clinical_input.age }}；female={{ featureJob.clinical_input.female }}；{{ featureJob.cache_hit ? '读取已存结果' : 'CPU 提取' }}</p>
          <el-alert v-if="featureJob.error" :title="featureJob.error" type="error" :closable="false" />
          <el-alert v-if="featureJob.stale" :title="`旧研究结果已失效，请重新提取。历史结果仍保留。原因：${featureJob.stale_reason}`" type="warning" :closable="false" />
          <template v-if="featureJob.result && !featureJob.stale && !featureInputDirty">
            <el-table :data="automaticRows" class="automatic-result" border><el-table-column prop="name" label="方法" /><el-table-column prop="value" label="自动掩膜输入研究概率" /></el-table>
            <p>{{ featureJob.result.disclaimer }}</p>
            <p>选中特征 {{ Object.keys(featureJob.result.selected_features).length }} 个；提取 {{ featureJob.result.extraction_seconds }} 秒；不写入病例诊断报告。</p>
          </template>
        </template>
      </el-card>
      <el-card class="panel">
        <template #header>同构模拟联邦</template>
        <p>{{ summary.federated.rounds }} 轮，每轮本地 {{ summary.federated.local_steps }} 步；3 客户端；同一逻辑模型。</p>
        <el-table :data="federatedRows" border><el-table-column prop="name" label="方法" /><el-table-column prop="auc" label="探索性测试 AUC" /><el-table-column prop="sizes" label="客户端人数" /><el-table-column prop="weights" label="末轮聚合权重" /></el-table>
        <p>预处理在训练患者上集中拟合，TOPSIS 使用公共验证池。本功能模拟参数聚合，不提供真实跨院隐私保证。</p>
      </el-card>
    </template>
  </div>
</template>
<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import request from '../api/axios'
import { useRoute } from 'vue-router'
const route = useRoute()
const summary = ref(null), patient = ref(null), clinical = ref(null), error = ref(''), selected = ref('13')
const age = ref(50), female = ref(false), patientLoading = ref(false), clinicalLoading = ref(false)
const cases = ref([]), featureCase = ref(null), featureJob = ref(null), featureSubmitting = ref(false)
const caseClinical = ref(null), caseAge = ref(null), caseFemale = ref(null), clinicalSaving = ref(false)
const featureError = ref(''), featureStatusKnown = ref(false)
const featureInputDirty = computed(() => Boolean(caseClinical.value && (caseAge.value !== caseClinical.value.age || caseFemale.value !== caseClinical.value.female)))
let featureTimer = null, mounted = true, featureGeneration = 0
const featureBusy = computed(() => !featureStatusKnown.value || featureSubmitting.value || ['queued', 'running'].includes(featureJob.value?.state))
const labels = { clinical: '临床年龄/性别', reference_mask_radiomics: '参考掩膜影像组学', automatic_mask_radiomics: '自动掩膜影像组学', average: '平均融合', 'fixed_clinical_0.6_radiomics_0.4': '固定 0.6/0.4', fixed: '固定 0.6/0.4', validation_topsis: '验证集 TOPSIS' }
const modelRows = computed(() => Object.entries({ ...summary.value?.branch_models, ...summary.value?.fusion }).map(([key, value]) => ({ name: labels[key] || key, auc: value.test.auc.toFixed(4), accuracy: value.test.balanced_accuracy.toFixed(4), brier: value.test.brier.toFixed(4) })))
const probabilityRows = computed(() => Object.entries(patient.value?.probabilities || {}).map(([key, value]) => ({ name: labels[key] || key, value: (value * 100).toFixed(1) + '%' })))
const automaticRows = computed(() => Object.entries(featureJob.value?.result?.probabilities || {}).map(([key, value]) => ({ name: labels[key] || key, value: (value * 100).toFixed(1) + '%' })))
const federatedRows = computed(() => Object.entries(summary.value?.federated.methods || {}).map(([key, value]) => ({ name: key, auc: value.test.auc.toFixed(4), sizes: value.client_sizes?.join(' / ') || '集中式', weights: value.round_trace?.at(-1).weights.map(x => x.toFixed(3)).join(' / ') || '—' })))
const failure = e => { error.value = String(e.response?.data?.detail || e.message) }
async function loadPatient() {
  patientLoading.value = true; patient.value = null; error.value = ''
  try { patient.value = (await request.get(`/research/patients/${selected.value}`)).data.data } catch (e) { failure(e) } finally { patientLoading.value = false }
}
async function predictClinical() {
  clinicalLoading.value = true; clinical.value = null; error.value = ''
  try { clinical.value = (await request.post('/research/clinical', { age: age.value, female: female.value })).data.data } catch (e) { failure(e) } finally { clinicalLoading.value = false }
}
function scheduleFeatures() {
  clearTimeout(featureTimer)
  if (mounted && ['queued', 'running'].includes(featureJob.value?.state)) featureTimer = setTimeout(refreshFeature, 1500)
}
async function refreshFeature() {
  if (!featureCase.value) return
  clearTimeout(featureTimer)
  const id = featureCase.value, ticket = ++featureGeneration
  try {
    const [jobResponse, inputResponse] = await Promise.all([
      request.get(`/research/cases/${id}/features`), request.get(`/research/cases/${id}/clinical-input`)
    ])
    if (mounted && featureCase.value === id && ticket === featureGeneration) {
      const dirty = featureInputDirty.value
      caseClinical.value = inputResponse.data.data
      if (!dirty) { caseAge.value = caseClinical.value.age; caseFemale.value = caseClinical.value.female }
      featureJob.value = jobResponse.data.data; featureStatusKnown.value = true; featureError.value = ''; scheduleFeatures()
      return featureJob.value
    }
  } catch (e) {
    if (mounted && featureCase.value === id && ticket === featureGeneration) {
      featureJob.value = null; featureStatusKnown.value = false; featureError.value = String(e.response?.data?.detail || e.message)
    }
  }
}
async function changeFeatureCase() {
  ++featureGeneration; clearTimeout(featureTimer); featureJob.value = null; caseClinical.value = null; caseAge.value = null; caseFemale.value = null; error.value = ''; featureError.value = ''; featureStatusKnown.value = false
  const id = featureCase.value
  if (!id) return
  try {
    const input = (await request.get(`/research/cases/${id}/clinical-input`)).data.data
    if (!mounted || featureCase.value !== id) return
    caseClinical.value = input; caseAge.value = input.age; caseFemale.value = input.female
    await refreshFeature()
  } catch (e) { if (mounted && featureCase.value === id) failure(e) }
}
async function saveCaseClinical() {
  clinicalSaving.value = true; featureError.value = ''
  const id = featureCase.value
  try {
    const input = (await request.put(`/research/cases/${id}/clinical-input`, { age: caseAge.value, female: caseFemale.value })).data.data
    if (mounted && featureCase.value === id) {
      caseClinical.value = input; caseAge.value = input.age; caseFemale.value = input.female
      await refreshFeature()
    }
  } catch (e) { if (mounted && featureCase.value === id) featureError.value = String(e.response?.data?.detail || e.message) } finally { clinicalSaving.value = false }
}
async function startFeatures() {
  ++featureGeneration; clearTimeout(featureTimer); featureSubmitting.value = true; featureError.value = ''
  const id = featureCase.value
  try {
    const job = (await request.post(`/research/cases/${id}/features`)).data.data
    if (mounted && featureCase.value === id) { featureJob.value = job; scheduleFeatures() }
  } catch (e) {
    if (mounted && featureCase.value === id) {
      featureError.value = String(e.response?.data?.detail || e.message)
      if (e.response?.status === 409) {
        const job = await refreshFeature()
        if (mounted && featureCase.value === id && !['queued', 'running'].includes(job?.state)) featureError.value = String(e.response?.data?.detail || e.message)
      }
    }
  } finally { featureSubmitting.value = false }
}
onMounted(async () => {
  try {
    summary.value = (await request.get('/research/summary')).data.data
    await loadPatient()
    cases.value = (await request.get('/cases/', { params: { status: 'analyzed' } })).data.data
    const requestedCase = Number(route.query.case_id)
    if (cases.value.some(item => item.id === requestedCase)) { featureCase.value = requestedCase; await changeFeatureCase() }
  } catch (e) { failure(e) }
})
onUnmounted(() => { mounted = false; ++featureGeneration; clearTimeout(featureTimer) })
</script>
<style scoped>
.research-page { padding: 24px; max-width: 1100px; margin: auto; } .panel { margin-top: 18px; } label { margin-right: 12px; }
</style>
