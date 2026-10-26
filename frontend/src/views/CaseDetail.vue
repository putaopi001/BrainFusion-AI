<template>

<div class="page">
<h1 v-if="!caseLoaded">病例详情</h1>
<el-alert v-if="loadError" :title="loadError" type="error" :closable="false" data-testid="case-load-error" />
<el-button v-if="loadError" @click="router.push('/cases')">返回病例管理</el-button>
<el-skeleton v-if="loadingDetail" :rows="4" animated />
<template v-if="caseLoaded">


<h1>
病例详情
</h1>



<!-- 病例信息 -->

<el-card>

<template #header>
病例信息
</template>


<p>
病例ID:
{{detail.case?.id}}
</p>


<p>
描述:
{{detail.case?.description}}
</p>


<p>
状态:
{{detail.case?.status}}
</p>


</el-card>





<!-- 患者信息 -->


<el-card
class="box"
>


<template #header>
患者信息
</template>


<p>
姓名:
{{detail.patient?.name}}
</p>


<p>
年龄:
{{detail.patient?.age}}
</p>


<p>
性别:
{{detail.patient?.gender}}
</p>


</el-card>







<!-- MRI信息 -->
<PacsPanel v-if="caseId" :key="caseId" :case-id="Number(caseId)" @input-activated="refreshAfterInputActivation" />


<el-card
class="box"
>


<template #header>
MRI影像信息
</template>



<p>
文件:
{{detail.mri?.filename}}
</p>



<p>
路径:
{{detail.mri?.file_url || "-"}}
</p>


<p>
状态:
<el-tag v-if="detail.mri" :type="mriStatusType" size="small">{{ mriStatusLabel }}</el-tag>
</p>

<p v-if="currentVerified">
医生确认:
<el-tag type="success" size="small">已确认 AI 结果</el-tag>
</p>


</el-card>







<!-- MRI Viewer -->


<el-card
class="box"
>


<template #header>
<div class="mri-header">
<span>MRI影像浏览</span>
<el-button size="small" type="primary" @click="goWorkstation">进入阅片工作站（全屏）</el-button>
</div>
</template>



<MRIViewer
:key="(detail.mri?.file_url || '') + (detail.analysis?.id || '') + (detail.analysis?.state || '')"

v-if="detail.mri?.file_url"

:case-id="Number(caseId)"

:file-url="detail.mri.file_url"

:slice-url="detail.mri.slice_url"

:preview-urls="detail.mri.preview_urls"

:preview-views="detail.mri.preview_views"

:filename="detail.mri.filename"
:patient-name="detail.patient?.name"

/>

<el-button

v-if="detail.mri?.file_url && !detail.mri?.has_preview"

class="preview-button"

size="small"

@click="regeneratePreview"

>

重新生成 MRI 预览

</el-button>

<el-alert

v-if="detail.mri?.preview_error"

class="preview-alert"

type="warning"

:title="`MRI 预览不可用：${detail.mri.preview_error}`"

:closable="false"

/>



<div v-if="!detail.mri?.file_url">

暂无MRI影像

</div>



</el-card>







<!-- AI结果 -->


<el-alert

v-if="!detail.analysis"

class="box"

title="当前 MRI 尚未完成 AI 分析；请点击“重新 AI 分析”生成结果。"

type="info"

:closable="false"

/>


<el-card class="box" v-if="detail.analysis">
  <template #header>真实 MRI 分割分析</template>
  <p>任务状态：{{ detail.analysis.state }}</p>
  <p>分析版本：{{ detail.analysis.id }}</p>
  <p v-if="detail.analysis.error">{{ detail.analysis.error }}</p>
  <p v-if="detail.analysis.stale">结果已失效，请重新分析；历史记录保留，不作为当前体积、医生确认或报告。</p>
  <template v-if="detail.analysis.state === 'succeeded' && !detail.analysis.stale && detail.analysis.result">
    <p>模型：{{ detail.analysis.result.model }}</p>
    <p v-for="(value, region) in detail.analysis.result.volumes_ml" :key="region">{{ region }}：{{ value }} mL</p>
    <div class="verify-row">
      <el-button v-if="!currentVerified" type="primary" :loading="verifying" @click="verifyAI">确认当前分割结果</el-button>
      <el-tag v-else type="success">医生已确认当前版本</el-tag>
      <el-button @click="router.push(`/research?case_id=${caseId}`)">自动掩膜特征研究</el-button>
      <el-button v-if="unifiedResearchDemo" @click="router.push('/research/upenn-sub002')">查看独立 UPENN sub-002 研究结果</el-button>
    </div>
  </template>
</el-card>

<el-alert v-if="detail.legacy_outputs?.has_prediction || detail.legacy_outputs?.has_report" class="box" title="此病例的历史占位结果已归档，不作为当前模型结果或报告。请完成四序列真实分析。" type="warning" :closable="false" />

<el-alert
  class="box survival-status"
  title="生存分析研究入口与本病例分开"
  description="研究页面提供仅限 SYNTHETIC_TEST 的 API 模型演示；不会自动将当前病例与 UPENN/UCSF 队列关联，也不会生成真实患者预测。"
  type="info"
  :closable="false"
  show-icon
/>








<!-- AI报告 -->


<el-card
class="box"

v-if="detail.report"
>


<template #header>

AI诊断报告

</template>



<p class="report-meta">

报告生成时间:

{{ formatTime(detail.report?.created_time) }}

</p>



<h3>

研究限制：当前分割不提供临床风险或生存预测。

</h3>



<h3>

AI总结

</h3>


<ul>

<li
v-for="item in summaries"

:key="item"

>

{{item}}

</li>

</ul>





<h3>

推荐措施

</h3>


<ul>

<li

v-for="item in recommendations"

:key="item"

>

{{item}}

</li>

</ul>



</el-card>









<el-card class="box"><template #header>生存分析研究</template><p>研究模型入口与当前病例分开。模型只接受明确标记的合成测试输入，不提供本病例预测。</p><el-button @click="router.push('/research#survival-models')">打开生存分析研究</el-button></el-card>

<!-- 操作 -->


<el-card
class="box"
>


<div class="opinion-card-header">

<span>医生阅片意见</span>

<el-tag size="small" type="info">手工录入</el-tag>

</div>

<p class="opinion-hint">

教学与原型工具：此处仅保存医生手工录入的阅片意见，不会写入 AI 自动结论。

</p>

<el-form label-width="90px" class="opinion-form">

<el-form-item label="医生姓名">

<el-input v-model="doctorOpinion.author" placeholder="记录阅片医生姓名" />

</el-form-item>

<el-form-item label="阅片意见">

<el-input v-model="doctorOpinion.content" type="textarea" :rows="4" placeholder="此处仅保存医生手工录入的阅片意见，不会写入 AI 自动结论。" />

</el-form-item>

<el-button :loading="savingOpinion" @click="saveDoctorOpinion">保存医生意见</el-button>

<small v-if="doctorOpinion.updated_time" class="opinion-time">最近保存：{{ formatTime(doctorOpinion.updated_time) }}</small>

</el-form>

<el-button

type="primary"

@click="goAnalysis"

>

重新AI分析

</el-button>




<el-button

type="success"

@click="goReport"

>

查看完整报告

</el-button>


</el-card>




</template>
</div>


</template>









<script setup>
import { ref, computed, onBeforeUnmount, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import request from "../api/axios";
import MRIViewer from "../components/mri/MRIViewer.vue";
import PacsPanel from "../components/PacsPanel.vue";
import { ElMessage } from "element-plus";
import { useCaseStore } from "../stores/case";
import { useMriStore } from "../stores/mri";
import { useAiStore } from "../stores/ai";
import { useReportStore } from "../stores/report";

const route = useRoute();
const router = useRouter();
const unifiedResearchDemo = import.meta.env.VITE_UNIFIED_RESEARCH_DEMO === 'true';

const detail = ref({});
const caseLoaded = ref(false);
const loadingDetail = ref(false);
const loadError = ref("");
let loadVersion = 0;
let detailController;
const doctorOpinion = ref({ author: "", content: "", updated_time: null });
const savingOpinion = ref(false);
const verifying = ref(false);
const survivalData = ref(null);
const loadingSurvival = ref(false);

const caseStore = useCaseStore();
const mriStore = useMriStore();
const aiStore = useAiStore();
const reportStore = useReportStore();

const caseId = computed(() => {
  const id = String(route.params.id || "");
  return /^[1-9]\d*$/.test(id) && Number.isSafeInteger(Number(id)) ? id : "";
});
const currentVerified = computed(() => Boolean(detail.value.mri?.doctor_verified && detail.value.analysis?.state === 'succeeded' && !detail.value.analysis.stale && detail.value.mri?.verified_run_id === detail.value.analysis.id));

// --- 辅助函数 ---

// 百分比文字
function percent(value) {
  if (value === undefined || value === null) return "0%";
  return (Number(value) * 100).toFixed(1) + "%";
}

// progress数值
function safePercent(value) {
  if (value === undefined || value === null) return 0;
  let num = Number(value) * 100;
  if (isNaN(num)) return 0;
  return num;
}

const summaries = computed(() => {
  let value = detail.value.report?.summary;
  if (!value) return [];
  if (typeof value === "string") {
    try {
      return JSON.parse(value);
    } catch {
      return [value];
    }
  }
  return value;
});

const recommendations = computed(() => {
  let value = detail.value.report?.recommendation;
  if (!value) return [];
  if (typeof value === "string") {
    try {
      return JSON.parse(value);
    } catch {
      return [value];
    }
  }
  return value;
});

const riskText = computed(() => {
  let level = detail.value.report?.risk_level;
  switch (level) {
    case "high": return "高风险";
    case "medium": return "中风险";
    case "low": return "低风险";
    default: return "未知";
  }
});

// MRI 阅片状态：根据 has_preview / preview_error / slice_url / status 推导，而非直接展示数据库原始状态
const mriStatusLabel = computed(() => {
  const mri = detail.value.mri;
  if (!mri) return "无 MRI";
  if (mri.preview_error) return "处理失败";
  if (mri.status === "analyzed") return "已分析";
  if (mri.has_preview || mri.slice_url) return "阅片就绪";
  if (mri.status === "processing") return "处理中";
  return "等待处理";
});

const mriStatusType = computed(() => {
  const label = mriStatusLabel.value;
  if (label === "阅片就绪" || label === "已分析") return "success";
  if (label === "处理失败") return "danger";
  if (label === "处理中") return "warning";
  return "info";
});

const survivalLevelText = computed(() => {
  const level = survivalData.value?.survival.risk_level;
  if (level === "high") return "高风险";
  if (level === "medium") return "中风险";
  if (level === "low") return "低风险";
  return "未知";
});

const survivalTagType = computed(() => {
  const level = survivalData.value?.survival.risk_level;
  if (level === "high") return "danger";
  if (level === "medium") return "warning";
  return "success";
});

// --- 业务逻辑函数 ---

function clearCaseContext() {
  caseLoaded.value = false;
  detail.value = {};
  doctorOpinion.value = { author: "", content: "", updated_time: null };
  survivalData.value = null;
  caseStore.clear();
  mriStore.clear();
  aiStore.clear();
  reportStore.clear();
}

async function loadDetail() {
  const id = caseId.value;
  const version = ++loadVersion;
  detailController?.abort();
  clearCaseContext();
  loadError.value = "";
  loadingDetail.value = false;
  if (!id) {
    loadError.value = "病例链接无效，请从病例管理选择病例。";
    return;
  }
  detailController = new AbortController();
  const signal = detailController.signal;
  loadingDetail.value = true;
  try {
    const res = await request.get(`/cases/${id}/detail`, { signal });
    if (version !== loadVersion || id !== caseId.value) return;
    const data = res.data.data;
    if (String(data?.case?.id) !== id) throw new Error("病例响应身份不一致");
    detail.value = data;
    caseStore.setCurrentCase(Number(id), data);
    mriStore.setMri(data.mri);
    aiStore.setPrediction(data.prediction);
    reportStore.setReport(data.report);
    caseLoaded.value = true;
    await loadDoctorOpinion(id, version, signal);
  } catch (error) {
    if (signal.aborted || version !== loadVersion || id !== caseId.value) return;
    clearCaseContext();
    loadError.value = error.response?.status === 404
      ? "病例不存在，请返回病例管理选择病例。"
      : "病例加载失败，请检查本机服务后重试。";
    // Diagnostic identity/status only; never log patient payloads or raw Axios objects.
    console.error("加载病例失败", { caseId: id, status: error.response?.status || null });
  } finally {
    if (version === loadVersion) loadingDetail.value = false;
  }
}


async function refreshAfterInputActivation() {
  const id = caseId.value;
  try {
    const res = await request.get(`/cases/${id}/detail`);
    const data = res.data.data;
    if (id !== caseId.value || String(data?.case?.id) !== id) return;
    // Refresh current MRI/results in place so the PACS dialog and audit context remain visible.
    detail.value = data;
    caseStore.setCurrentCase(Number(id), data);
    mriStore.setMri(data.mri);
    aiStore.setPrediction(data.prediction);
    reportStore.setReport(data.report);
  } catch (error) {
    if (id === caseId.value) loadError.value = '当前输入已切换；病例详情刷新失败，请手动刷新页面。';
  }
}

function goAnalysis() {
  router.push(`/analysis?case_id=${caseId.value}`);
}

function goWorkstation() {
  router.push({ name: "workstation", params: { id: caseId.value } });
}

function goReport() {
  router.push(`/report?case_id=${caseId.value}`);
}

// 【重点修复】这里补全了 regeneratePreview 的 catch 块
async function regeneratePreview() {
  try {
    await request.post(`/mri/${caseId.value}/preview`);
    await loadDetail();
  } catch (error) {
    console.error("MRI preview generation failed", error);
    ElMessage.error("预览生成失败");
  }
}

async function loadDoctorOpinion(id = caseId.value, version = loadVersion, signal = detailController?.signal) {
  if (!id) return;
  try {
    const response = await request.get(`/cases/${id}/doctor-opinion`, { signal });
    if (version === loadVersion && id === caseId.value && caseLoaded.value) doctorOpinion.value = response.data.data;
  } catch (error) {
    if (!signal?.aborted && version === loadVersion) console.error("医生意见加载失败", { caseId: id, status: error.response?.status || null });
  }
}

async function saveDoctorOpinion() {
  savingOpinion.value = true;
  try {
    const response = await request.put(`/cases/${caseId.value}/doctor-opinion`, {
      author: doctorOpinion.value.author,
      content: doctorOpinion.value.content
    });
    doctorOpinion.value.updated_time = response.data.data.updated_time;
    ElMessage.success("医生阅片意见已保存");
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || "医生意见保存失败");
  } finally {
    savingOpinion.value = false;
  }
}

async function verifyAI() {
  verifying.value = true;
  try {
    if (detail.value.analysis?.state !== "succeeded") throw new Error("请先完成真实模型分析");
    await request.post("/mri/" + caseId.value + "/verify", null, { params: { run_id: detail.value.analysis.id } });
    await loadDetail();
    ElMessage.success("已确认 AI 结果");
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || "确认失败");
  } finally {
    verifying.value = false;
  }
}

async function loadSurvival() {
  loadingSurvival.value = true;
  try {
    const response = await request.get("/cases/" + caseId.value + "/survival");
    survivalData.value = response.data.data;
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || "生存预测加载失败");
  } finally {
    loadingSurvival.value = false;
  }
}

function formatTime(value) {
  return value ? new Date(value).toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai', hour12: false }) + '（北京时间）' : "";
}

// --- 生命周期 ---

watch(caseId, loadDetail, { immediate: true });
onBeforeUnmount(() => {
  ++loadVersion;
  detailController?.abort();
});
</script>







<style scoped>


.page{

padding:20px;

}



.box{

margin-top:20px;

}



.el-card{

border-radius:10px;

}

.preview-alert{

margin-top:16px;

}

.preview-button{

margin-top:12px;

}

.opinion-card-header{

display:flex;

align-items:center;

gap:10px;

font-weight:600;

}

.opinion-hint{

margin:0 0 14px;

font-size:13px;

color:#64748b;

}

.ai-disclaimer{

margin-bottom:14px;

}

.report-meta{

margin:0 0 14px;

font-size:13px;

color:#64748b;

}

.verify-row{

display:flex;

align-items:center;

gap:12px;

margin-top:18px;

padding-top:14px;

border-top:1px dashed #334155;

}

.mri-header{

display:flex;

align-items:center;

justify-content:space-between;

}

.verify-hint{

font-size:12px;

color:#64748b;

}

.survival-box{

margin-top:16px;

}

.survival-risk{

display:flex;

align-items:center;

gap:10px;

margin-bottom:14px;

}

.survival-months{

color:#0f172a;

font-weight:600;

}

.survival-table{

width:100%;

border-collapse:collapse;

font-size:13px;

}

.survival-table td{

border:1px solid #e2e8f0;

padding:6px 10px;

}

.survival-table td:first-child{

width:160px;

background:#f8fafc;

color:#475569;

}

.survival-hint{

margin:12px 0 0;

font-size:12px;

color:#64748b;

}



</style>
