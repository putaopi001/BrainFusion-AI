<template>
  <div class="dashboard">
    <section class="hero">
      <h1>BrainFusion AI</h1>
      <h2>脑胶质瘤 AI 辅助诊疗平台</h2>
      <p class="lead">病例管理 · MRI 影像阅片 · AI 分析 · 诊断报告 · 医生确认闭环</p>
      <p class="disclaimer">科研原型：真实模型分割结果需医生复核，不构成临床诊断建议。</p>
      <div class="hero-actions">
        <el-button type="primary" size="large" @click="$router.push('/cases')">进入病例管理</el-button>
        <el-button size="large" @click="$router.push('/patients')">患者管理</el-button>
        <el-button size="large" @click="$router.push('/research')">研究演示与生存模型</el-button>
      </div>
    </section>

    <section class="demo-route">
      <el-card shadow="never">
        <template #header>隔离研究演示路线</template>
        <el-steps :active="0" align-center>
          <el-step title="病例管理" description="查看隔离工程病例" />
          <el-step title="MRI 阅片" description="四序列与已有掩膜" />
          <el-step title="报告" description="既有 WT/TC/ET 结果" />
          <el-step title="研究分析" description="影像组学与探索性结果" />
          <el-step title="合成预测" description="合成输入、研究 Cox" />
        </el-steps>
        <p class="demo-route-note">不同页面中的工程病例、队列研究和 SYNTHETIC_TEST 生存预测来自不同数据流程；演示时不将它们解释为同一患者的临床闭环。</p>
      </el-card>
    </section>

    <section class="stat-grid">
      <el-card shadow="hover">
        <div class="stat-num">{{ stats.cases }}</div>
        <div class="stat-label">病例总数</div>
      </el-card>
      <el-card shadow="hover">
        <div class="stat-num">{{ stats.patients }}</div>
        <div class="stat-label">患者总数</div>
      </el-card>
      <el-card shadow="hover">
        <div class="stat-num">{{ version }}</div>
        <div class="stat-label">系统版本</div>
      </el-card>
      <el-card shadow="hover">
        <div class="stat-num">{{ stats.models }}</div>
        <div class="stat-label">已接入模型</div>
      </el-card>
    </section>

    <section class="pipeline-card">
      <el-card shadow="never">
        <template #header>诊疗工作流</template>
        <el-steps :active="6" finish-status="success" align-center>
          <el-step title="病例创建" />
          <el-step title="MRI 上传" />
          <el-step title="影像解析" />
          <el-step title="阅片工作站" />
          <el-step title="AI 分析" />
          <el-step title="报告生成" />
          <el-step title="医生确认" />
        </el-steps>
      </el-card>
    </section>
  </div>
</template>

<script setup>
import { onMounted, ref } from "vue"
import request from "../api/axios"

const stats = ref({ cases: 0, patients: 0, models: 0 })
const version = ref("v0.1.0")

async function loadStats() {
  try {
    const casesRes = await request.get("/cases/")
    stats.value.cases = (casesRes.data.data || []).length
  } catch (e) {
    /* ignore */
  }
  try {
    const patientsRes = await request.get("/patients/")
    stats.value.patients = (patientsRes.data.data || []).length
  } catch (e) {
    /* ignore */
  }
  try {
    const sysRes = await request.get("/debug/system")
    const data = sysRes.data.data || {}
    if (data.version) version.value = data.version.replace("BrainFusion-AI ", "")
    stats.value.models = (data.models || []).filter(model => model.status === "ready").length
  } catch (e) {
    /* ignore */
  }
}

onMounted(loadStats)
</script>

<style scoped>
.dashboard { max-width: 1080px; margin: 0 auto; padding: 28px 24px; }
.hero {
  background: linear-gradient(135deg, #0ea5e9, #6366f1);
  color: #fff;
  border-radius: 14px;
  padding: 32px 36px;
  margin-bottom: 20px;
}
.hero h1 { margin: 0 0 6px; font-size: 30px; }
.hero h2 { margin: 0 0 10px; font-size: 18px; font-weight: 500; opacity: 0.95; }
.hero .lead { margin: 0 0 8px; font-size: 14px; opacity: 0.9; }
.hero .disclaimer { margin: 0 0 18px; font-size: 12px; opacity: 0.8; }
.hero-actions { display: flex; gap: 10px; }

.stat-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; margin-bottom: 20px; }
.stat-num { font-size: 28px; font-weight: 700; color: #0f172a; }
.stat-label { font-size: 13px; color: #64748b; margin-top: 4px; }

.pipeline-card :deep(.el-step__title) { font-size: 12px; }
.demo-route { margin-bottom: 20px; }
.demo-route-note { margin: 12px 0 0; color: #64748b; font-size: 13px; }
@media (max-width: 900px) {
  .stat-grid { grid-template-columns: repeat(2, 1fr); }
}
</style>
