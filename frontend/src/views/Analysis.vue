<template>
  <div class="page">
    <h1>BrainFusion AI 智能分析</h1>

    <el-card>
      <p>病例编号: {{ caseId }}</p>
      <el-button type="primary" :loading="loading" @click="runAnalysis">
        {{ loading ? "AI分析中..." : "运行AI分析" }}
      </el-button>
    </el-card>

    <el-card v-if="steps.length" class="mt">
      <template #header>分析流程</template>
      <el-steps :active="activeStep" finish-status="success">
        <el-step title="MRI影像分析" />
        <el-step title="临床风险分析" />
        <el-step title="多模态融合" />
        <el-step title="Agent报告生成" />
      </el-steps>
      <p class="step-hint">四阶段为 AI 服务内部流程示意，实际在单次 /predict 调用中完成。</p>
    </el-card>

    <div v-if="analysisResult">
      <el-card class="mt">
        <template #header>MRI 分析结果</template>
        <p>模型: {{ analysisResult.results.imaging.model }}</p>
        <p>肿瘤概率: {{ percent(analysisResult.results.imaging.tumor_probability) }}</p>
        <el-progress :percentage="analysisResult.results.imaging.tumor_probability * 100" />
      </el-card>

      <el-card class="mt">
        <template #header>临床风险模型</template>
        <p>模型: {{ analysisResult.results.clinical.model }}</p>
        <el-progress :percentage="analysisResult.results.clinical.risk_score * 100" />
      </el-card>

      <el-card class="mt">
        <template #header>多模态融合结果</template>
        <p>融合评分: {{ percent(analysisResult.results.fusion.fusion_score) }}</p>
        <p>
          风险等级:
          <el-tag :type="riskType">{{ riskText }}</el-tag>
        </p>
      </el-card>

      <el-card class="mt">
        <template #header>Agent 智能解释</template>
        <p>决策: {{ analysisResult.report_agent.decision }}</p>
        <h3>分析依据</h3>
        <ul>
          <li v-for="item in analysisResult.report_agent.reason" :key="item">{{ item }}</li>
        </ul>
        <h3>推荐措施</h3>
        <ul>
          <li v-for="item in analysisResult.report_agent.recommendation" :key="item">{{ item }}</li>
        </ul>
      </el-card>

      <el-button class="mt" type="success" @click="openReport">查看诊断报告</el-button>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from "vue"
import { useRoute, useRouter } from "vue-router"
import { ElMessage } from "element-plus"
import request from "../api/axios"

const route = useRoute()
const router = useRouter()

const caseId = computed(() => String(route.query.case_id || ""))
const loading = ref(false)
const analysisResult = ref(null)
const activeStep = ref(0)
const steps = ref([])

function percent(value) {
  if (!value) return "0%"
  return (value * 100).toFixed(1) + "%"
}

async function runAnalysis() {
  if (!caseId.value) {
    ElMessage.warning("请先从病例列表选择病例")
    return
  }
  loading.value = true
  steps.value = ["MRI", "Clinical", "Fusion", "Agent"]
  activeStep.value = 0
  try {
    const res = await request.post("/predict/" + caseId.value)
    analysisResult.value = res.data.data
    activeStep.value = 4
    ElMessage.success("AI 分析完成")
  } catch (e) {
    console.error(e)
    ElMessage.error("AI 分析失败，请确认 MRI 已上传且后端服务正常")
  } finally {
    loading.value = false
  }
}

const riskText = computed(() => {
  const risk = analysisResult.value?.results.fusion.risk
  if (risk === "high") return "高风险"
  if (risk === "low") return "低风险"
  return "未知"
})

const riskType = computed(() => {
  if (riskText.value === "高风险") return "danger"
  if (riskText.value === "低风险") return "success"
  return "info"
})

function openReport() {
  router.push("/report?case_id=" + caseId.value)
}
</script>

<style scoped>
.page { padding: 24px; }
.mt { margin-top: 20px; }
.step-hint { margin: 12px 0 0; font-size: 12px; color: #64748b; }
</style>
