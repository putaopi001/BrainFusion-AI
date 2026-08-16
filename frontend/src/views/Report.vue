<template>
  <div class="page report-page">
    <div class="report-toolbar">
      <div>
        <h1>诊断报告</h1>
        <p class="toolbar-sub">BrainFusion AI 教学科研原型 · 报告仅供科研参考</p>
      </div>
      <div class="toolbar-actions">
        <el-button @click="loadReport">刷新报告</el-button>
        <el-button type="primary" :loading="exporting" @click="exportPDF">导出 PDF</el-button>
      </div>
    </div>

    <!-- 报告主体（可导出为 PDF） -->
    <div id="report-paper" class="report-paper">
      <header class="paper-header">
        <div class="paper-brand">BrainFusion AI 诊断报告</div>
        <div class="paper-meta">
          <span>病例编号：{{ caseId }}</span>
          <span>生成时间：{{ time }}</span>
          <span>模型版本：{{ modelVersion }}</span>
        </div>
      </header>

      <section class="paper-section">
        <h2>一、患者基本信息</h2>
        <table class="kv-table">
          <tbody>
            <tr>
              <td class="kv-label">姓名</td><td>{{ patient.name || "—" }}</td>
              <td class="kv-label">年龄</td><td>{{ patient.age != null ? patient.age : "—" }}</td>
              <td class="kv-label">性别</td><td>{{ genderText }}</td>
            </tr>
          </tbody>
        </table>
      </section>

      <section class="paper-section">
        <h2>二、影像检查信息</h2>
        <table class="kv-table">
          <tbody>
            <tr>
              <td class="kv-label">影像文件</td><td>{{ mri.filename || "—" }}</td>
              <td class="kv-label">模态</td><td>{{ mri.modality || "MRI" }}</td>
            </tr>
          </tbody>
        </table>
      </section>

      <section class="paper-section">
        <h2>三、AI 多模态分析结果</h2>
        <table class="report-table">
          <thead>
            <tr><th>指标</th><th>模型</th><th>数值</th></tr>
          </thead>
          <tbody>
            <tr><td>MRI 肿瘤概率</td><td>MRI Baseline Model</td><td>{{ formatPct(mriProbability) }}</td></tr>
            <tr><td>临床风险评分</td><td>TabICL-v2</td><td>{{ formatPct(clinicalScore) }}</td></tr>
            <tr><td>融合评分</td><td>Multi-modal Fusion</td><td>{{ formatPct(fusionScore) }}</td></tr>
          </tbody>
        </table>
      </section>

      <section class="paper-section">
        <h2>四、综合风险评估</h2>
        <div class="risk-line">
          <el-tag :type="tagType" size="large" effect="dark">{{ riskText }}</el-tag>
        </div>
      </section>

      <section class="paper-section">
        <h2>五、AI 智能分析总结</h2>
        <ol class="report-list">
          <li v-for="item in summary" :key="item">{{ item }}</li>
        </ol>
        <p v-if="!summary.length" class="empty">暂无 AI 总结，请先运行 AI 分析。</p>
      </section>

      <section class="paper-section">
        <h2>六、推荐措施</h2>
        <ul class="report-list">
          <li v-for="item in recommendation" :key="item">{{ item }}</li>
        </ul>
        <p v-if="!recommendation.length" class="empty">暂无推荐措施。</p>
      </section>

      <section class="paper-section">
        <h2>七、医生意见</h2>
        <p class="opinion-text">{{ doctorOpinion.content || "（暂无医生意见）" }}</p>
        <p v-if="doctorOpinion.author" class="opinion-author">阅片医生：{{ doctorOpinion.author }}</p>
      </section>

      <footer class="paper-footer">
        <p>本报告由 BrainFusion AI 教学科研原型系统自动生成，仅供教学与科研参考，不构成临床诊断或治疗建议，最终判断请以具有执业资质的医生阅片意见为准。</p>
      </footer>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from "vue"
import { useRoute } from "vue-router"
import { ElMessage } from "element-plus"
import request from "../api/axios"

const route = useRoute()
const caseId = computed(() => String(route.query.case_id || ""))

const report = ref({})
const patient = ref({})
const mri = ref({})
const doctorOpinion = ref({})
const modelVersion = ref("未记录")
const time = ref("")
const mriProbability = ref(0)
const clinicalScore = ref(0)
const fusionScore = ref(0)
const summary = ref([])
const recommendation = ref([])
const exporting = ref(false)

const genderText = computed(() => {
  if (patient.value.gender === "male") return "男"
  if (patient.value.gender === "female") return "女"
  return patient.value.gender || "—"
})

const riskText = computed(() => {
  switch (report.value.risk_level) {
    case "high": return "高风险"
    case "medium": return "中风险"
    case "low": return "低风险"
    default: return "未知"
  }
})

const tagType = computed(() => {
  if (report.value.risk_level === "high") return "danger"
  if (report.value.risk_level === "medium") return "warning"
  return "success"
})

function parseList(value) {
  if (!value) return []
  if (typeof value === "string") {
    try {
      const parsed = JSON.parse(value)
      return Array.isArray(parsed) ? parsed : [value]
    } catch {
      return [value]
    }
  }
  return value
}

function formatPct(value) {
  const num = Number(value)
  if (!num) return "0.0%"
  return (num * 100).toFixed(1) + "%"
}

async function loadReport() {
  if (!caseId.value) return
  try {
    const res = await request.get("/cases/" + caseId.value + "/detail")
    const data = res.data.data || {}
    report.value = data.report || {}
    patient.value = data.patient || {}
    mri.value = data.mri || {}
    modelVersion.value = data.prediction?.model_version || "未记录"
    time.value = data.report?.created_time ? new Date(data.report.created_time).toLocaleString() : "未记录"
    summary.value = parseList(data.report?.summary)
    recommendation.value = parseList(data.report?.recommendation)
    if (data.prediction) {
      mriProbability.value = Number(data.prediction.tumor_probability)
      clinicalScore.value = Number(data.prediction.risk_score)
      fusionScore.value = Number(data.prediction.fusion_score)
    }
  } catch (e) {
    console.error(e)
    ElMessage.error("报告加载失败")
  }

  try {
    const res = await request.get("/cases/" + caseId.value + "/doctor-opinion")
    doctorOpinion.value = res.data.data || {}
  } catch (e) {
    /* ignore */
  }
}

async function exportPDF() {
  const element = document.getElementById("report-paper")
  if (!element) {
    ElMessage.warning("报告内容未就绪")
    return
  }
  exporting.value = true
  try {
    const mod = await import("html2pdf.js")
    const html2pdf = mod.default || mod
    const opt = {
      margin: [10, 10, 12, 10],
      filename: "BrainFusion_Report_case" + caseId.value + ".pdf",
      image: { type: "jpeg", quality: 0.98 },
      html2canvas: { scale: 2, useCORS: true, logging: false },
      jsPDF: { unit: "mm", format: "a4", orientation: "portrait" },
      pagebreak: { mode: ["avoid-all", "css", "legacy"] },
    }
    await html2pdf().set(opt).from(element).save()
    ElMessage.success("PDF 报告已导出")
  } catch (e) {
    console.error(e)
    ElMessage.error("PDF 导出失败")
  } finally {
    exporting.value = false
  }
}

onMounted(loadReport)
</script>

<style scoped>
.report-page { max-width: 860px; margin: 0 auto; padding: 24px; }
.report-toolbar { display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px; }
.report-toolbar h1 { margin: 0; font-size: 22px; }
.toolbar-sub { margin: 4px 0 0; font-size: 13px; color: #64748b; }
.toolbar-actions { display: flex; gap: 10px; }

.report-paper { background: #fff; color: #0f172a; border: 1px solid #e2e8f0; border-radius: 8px; padding: 32px 36px; }
.paper-header { border-bottom: 2px solid #0f172a; padding-bottom: 14px; margin-bottom: 18px; }
.paper-brand { font-size: 22px; font-weight: 700; }
.paper-meta { display: flex; gap: 20px; margin-top: 8px; font-size: 13px; color: #475569; flex-wrap: wrap; }

.paper-section { margin-bottom: 20px; }
.paper-section h2 { font-size: 16px; margin: 0 0 10px; border-left: 4px solid #0ea5e9; padding-left: 10px; }

.kv-table { width: 100%; border-collapse: collapse; font-size: 14px; }
.kv-table td { border: 1px solid #e2e8f0; padding: 8px 10px; }
.kv-table .kv-label { background: #f8fafc; width: 80px; color: #475569; font-weight: 600; }

.report-table { width: 100%; border-collapse: collapse; font-size: 14px; }
.report-table th, .report-table td { border: 1px solid #e2e8f0; padding: 8px 10px; text-align: left; }
.report-table th { background: #f1f5f9; }

.risk-line { padding: 4px 0; }
.report-list { margin: 0; padding-left: 20px; line-height: 1.9; }
.report-list li { margin: 2px 0; }
.empty { color: #94a3b8; font-size: 13px; }
.opinion-text { min-height: 60px; white-space: pre-wrap; line-height: 1.7; }
.opinion-author { color: #475569; font-size: 13px; }

.paper-footer { margin-top: 24px; padding-top: 12px; border-top: 1px dashed #cbd5e1; }
.paper-footer p { margin: 0; font-size: 12px; color: #64748b; line-height: 1.6; }
</style>
