<template>

<div class="page">


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

<p v-if="detail.mri?.doctor_verified">
医生确认:
<el-tag type="success" size="small">已确认 AI 结果</el-tag>
</p>


</el-card>







<!-- MRI Viewer -->


<el-card
class="box"
>


<template #header>
MRI影像浏览
</template>



<MRIViewer

v-if="detail.mri?.file_url"

:case-id="Number(caseId)"

:file-url="detail.mri.file_url"

:slice-url="detail.mri.slice_url"

:preview-urls="detail.mri.preview_urls"

:preview-views="detail.mri.preview_views"

:filename="detail.mri.filename"

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

v-if="!detail.prediction"

class="box"

title="当前 MRI 尚未完成 AI 分析；请点击“重新 AI 分析”生成结果。"

type="info"

:closable="false"

/>


<el-card
class="box"

v-if="detail.prediction"
>


<template #header>

BrainFusion AI分析结果

</template>



<el-alert

class="ai-disclaimer"

type="info"

:closable="false"

title="教学与原型工具：AI 分析结果仅用于演示，不构成临床诊断建议，请以医生阅片意见为准。"

/>



<p>

模型版本:

{{ detail.prediction?.model_version || "未记录" }}

</p>



<p>

生成时间:

{{ formatTime(detail.prediction?.created_time) }}

</p>



<p>

MRI肿瘤概率:

{{percent(detail.prediction?.tumor_probability)}}

</p>



<el-progress

:percentage="safePercent(detail.prediction?.tumor_probability)"

/>





<p>

临床风险评分:

{{percent(detail.prediction?.risk_score)}}

</p>



<el-progress

:percentage="safePercent(detail.prediction?.risk_score)"

/>





<p>

融合评分:

{{percent(detail.prediction?.fusion_score)}}

</p>



<el-progress

:percentage="safePercent(detail.prediction?.fusion_score)"

/>







<p>
风险等级:
</p>



<el-tag

v-if="detail.prediction?.risk_level==='high'"

type="danger"

>

高风险

</el-tag>



<el-tag

v-else-if="detail.prediction?.risk_level==='medium'"

type="warning"

>

中风险

</el-tag>



<el-tag

v-else

type="success"

>

低风险

</el-tag>


<div class="verify-row">

<el-button

v-if="detail.mri && !detail.mri.doctor_verified"

type="primary"

size="small"

:loading="verifying"

@click="verifyAI"

>
确认 AI 结果
</el-button>

<el-tag v-else-if="detail.mri?.doctor_verified" type="success" size="small">医生已确认 AI 结果</el-tag>

<small class="verify-hint">医生确认后记录 doctor_verified，仅作为阅片闭环记录。</small>

</div>



</el-card>








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

风险等级:

{{riskText}}

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




</div>


</template>









<script setup>
import { ref, computed, onMounted, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import request from "../api/axios";
import MRIViewer from "../components/mri/MRIViewer.vue";
import { ElMessage } from "element-plus";
import { useCaseStore } from "../stores/case";
import { useMriStore } from "../stores/mri";
import { useAiStore } from "../stores/ai";
import { useReportStore } from "../stores/report";

const route = useRoute();
const router = useRouter();

const detail = ref({});
const doctorOpinion = ref({ author: "", content: "", updated_time: null });
const savingOpinion = ref(false);
const verifying = ref(false);

const caseStore = useCaseStore();
const mriStore = useMriStore();
const aiStore = useAiStore();
const reportStore = useReportStore();

const caseId = computed(() => String(route.params.id || ""));

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

// --- 业务逻辑函数 ---

async function loadDetail() {
  try {
    let res = await request.get(`/cases/${caseId.value}/detail`);
    console.log("CASE DETAIL:", res.data);
    detail.value = res.data.data;
    // 同步到 Pinia 全局状态
    caseStore.setCurrentCase(Number(caseId.value), detail.value);
    mriStore.setMri(detail.value.mri);
    aiStore.setPrediction(detail.value.prediction);
    reportStore.setReport(detail.value.report);
    // 加载完详情后，加载医生意见
    await loadDoctorOpinion();
  } catch (error) {
    console.error("加载病例失败", error);
  }
}

function goAnalysis() {
  router.push(`/analysis?case_id=${caseId.value}`);
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

async function loadDoctorOpinion() {
  if (!caseId.value) return;
  try {
    const response = await request.get(`/cases/${caseId.value}/doctor-opinion`);
    doctorOpinion.value = response.data.data;
  } catch (error) {
    console.error("doctor opinion load failed", error);
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
    await request.post("/mri/" + caseId.value + "/verify");
    await loadDetail();
    ElMessage.success("已确认 AI 结果");
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || "确认失败");
  } finally {
    verifying.value = false;
  }
}

function formatTime(value) {
  return value ? new Date(value).toLocaleString() : "";
}

// --- 生命周期 ---

onMounted(() => {
  if (caseId.value) {
    loadDetail();
  }
});

watch(caseId, (id) => {
  if (id) {
    loadDetail();
  }
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

.verify-hint{

font-size:12px;

color:#64748b;

}



</style>
