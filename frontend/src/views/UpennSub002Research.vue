<template>
  <section class="research-case-page">
    <header class="page-heading">
      <div><h1>UPENN sub-002 分割研究结果</h1><p>独立、只读的研究入口；不会创建病例数据库记录，也不与相似编号的 DICOM 检查自动关联。</p></div>
      <el-button @click="router.push('/cases')">返回病例管理</el-button>
    </header>
    <el-alert v-if="error" :title="error" type="error" :closable="false" />
    <el-button v-if="error" @click="router.push('/research#survival-models')">前往研究页面登录本地复核会话</el-button>
    <template v-if="manifest">
      <el-alert title="既有一次性 SegResNet 推理；本页面只读取固定哈希的原始输入、预测和评价证据，不会重新推理。" type="info" :closable="false" />
      <el-card>
        <template #header>研究病例与运行</template>
        <div class="metadata-grid">
          <span>研究病例：{{ manifest.study_id }}</span><span>关联状态：未建立临床或 DICOM 映射</span>
          <span>模型：{{ manifest.inference.model }}</span><span>模型版本：{{ manifest.inference.revision }}</span>
          <span>设备：{{ manifest.inference.device }}</span><span>预测 SHA-256：{{ manifest.prediction.sha256 }}</span>
          <span>checkpoint SHA-256：{{ manifest.inference.checkpoint_sha256 }}</span>
          <span>空间质控：{{ manifest.spatial_qc.status }} · {{ manifest.spatial_qc.spacing_mm?.join(' × ') }} mm</span>
          <span v-if="manifest.geometry.spatial_unit_source === 'pinned_source_and_inference_spatial_qc'">NIfTI 头未标单位；显示依据为固定哈希输入和既有 1 mm 空间质控证据。</span>
        </div>
        <h3>区域体积</h3>
        <el-table :data="volumeRows" border>
          <el-table-column prop="region" label="区域" width="110" />
          <el-table-column prop="volume" label="预测体积 (mL)" />
        </el-table>
        <p class="hash-list">输入序列 SHA-256：<span v-for="item in manifest.inputs" :key="item.sequence">{{ item.sequence }}={{ item.sha256 }}　</span></p>
      </el-card>
      <el-card>
        <template #header>Cornerstone 三平面阅片</template>
        <CornerstoneViewer research-study="upenn-sub002" :research-csrf="researchCsrf" />
      </el-card>
      <el-card>
        <template #header>既有分割报告 · {{ manifest.reference_agreement.status }}</template>
        <p>{{ manifest.reference_agreement.scope }}</p>
        <p>类别分别按语义形成 WT / TC / ET 二值区；HD95 单位 mm。该单病例结果表示公开参考一致性。</p>
        <el-table :data="metricRows" border>
          <el-table-column prop="region" label="区域" width="80" />
          <el-table-column prop="dice" label="Dice" />
          <el-table-column prop="hd95" label="HD95 (mm)" />
          <el-table-column prop="precision" label="Precision" />
          <el-table-column prop="recall" label="Recall" />
          <el-table-column prop="tp" label="TP" />
          <el-table-column prop="fp" label="FP" />
          <el-table-column prop="fn" label="FN" />
          <el-table-column prop="volumes" label="预测 / 参考 (mL)" min-width="150" />
        </el-table>
        <el-button class="csv-button" @click="downloadMetrics">下载既有评价 CSV</el-button>
        <el-image v-if="overlayUrl" class="overlay-image" :src="overlayUrl" fit="contain" alt="预测、参考和重叠区域三平面评价图" />
        <el-alert title="PUBLIC_REFERENCE_AGREEMENT，不是独立外部验证；模型训练病例重叠未知，且无逐例具名专家签署。" type="warning" :closable="false" />
        <p class="limitations">{{ manifest.limitations.join(' ') }}</p>
      </el-card>
    </template>
    <el-skeleton v-else-if="loading" :rows="5" animated />
  </section>
</template>

<script setup>
import { computed, defineAsyncComponent, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import request from '../api/axios'

const router = useRouter()
const CornerstoneViewer = defineAsyncComponent(() => import('../components/mri/CornerstoneViewer.vue'))
const manifest = ref(null), loading = ref(true), error = ref(''), overlayUrl = ref(''), researchCsrf = ref('')
let overlayObjectUrl = ''
const volumeRows = computed(() => ['WT', 'TC', 'ET'].map(region => ({ region, volume: Number(manifest.value?.prediction?.volumes_ml?.[region]).toFixed(3) })))
const metricRows = computed(() => ['WT', 'TC', 'ET'].map(region => {
  const row = manifest.value?.reference_agreement?.regions?.[region] || {}
  return { region, dice: Number(row.dice).toFixed(6), hd95: row.hd95_mm == null ? `不可用：${row.hd95_reason || '未提供'}` : Number(row.hd95_mm).toFixed(3),
    precision: Number(row.precision).toFixed(6), recall: Number(row.recall).toFixed(6), tp: row.tp, fp: row.fp, fn: row.fn,
    volumes: `${row.prediction_volume_ml} / ${row.reference_volume_ml}` }
}))

onMounted(async () => {
  try {
    const session = (await request.get('/local-auth/session')).data.data
    if (session.user?.role !== 'doctor' || !session.csrf) throw Error('研究分割查看需要先登录本地 doctor 复核会话。')
    researchCsrf.value = session.csrf
    const headers = { 'X-BF-CSRF': researchCsrf.value }
    manifest.value = (await request.get('/api/research/upenn-sub002/manifest', { headers })).data.data
    const response = await request.get(manifest.value.overlay_url, { responseType: 'blob', headers })
    overlayObjectUrl = URL.createObjectURL(response.data)
    overlayUrl.value = overlayObjectUrl
  } catch (e) {
    error.value = String(e.response?.data?.detail || e.message || '无法读取研究结果。')
  } finally { loading.value = false }
})
async function downloadMetrics() {
  try {
    const response = await request.get(manifest.value.reference_agreement.csv_url, { responseType: 'blob', headers: { 'X-BF-CSRF': researchCsrf.value } })
    const url = URL.createObjectURL(response.data), anchor = document.createElement('a')
    anchor.href = url; anchor.download = 'upenn-sub002-public-reference-agreement.csv'; anchor.click()
    URL.revokeObjectURL(url)
  } catch (e) { error.value = String(e.response?.data?.detail || e.message || 'CSV 下载失败。') }
}
onBeforeUnmount(() => { if (overlayObjectUrl) URL.revokeObjectURL(overlayObjectUrl) })
</script>

<style scoped>
.research-case-page{display:grid;gap:16px;padding:20px}.page-heading{display:flex;align-items:center;justify-content:space-between;gap:16px}.page-heading h1{margin:0 0 6px}.page-heading p,.limitations{color:#64748b}.metadata-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:10px;font-size:13px;overflow-wrap:anywhere}.hash-list{font-size:12px;overflow-wrap:anywhere;color:#64748b}.overlay-image{width:100%;max-height:520px;margin-top:14px;background:#0f172a}.csv-button{margin:12px 0}
</style>
