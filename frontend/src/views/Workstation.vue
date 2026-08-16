<template>
  <div class="ws-page">
    <!-- PACS 顶部患者/检查信息栏 -->
    <header class="ws-banner">
      <div class="ws-brand">BrainFusion AI · 阅片工作站</div>
      <div class="ws-patient">
        <span class="ws-name">{{ patient.name || "—" }}</span>
        <span class="ws-meta">{{ genderText }} · {{ patient.age != null ? patient.age + " 岁" : "—" }}</span>
        <span class="ws-meta">病例 #{{ caseId }}</span>
      </div>
      <div class="ws-study">
        <el-tag size="small" type="info" effect="plain">{{ mri.modality || "MRI" }}</el-tag>
        <span class="ws-filename">{{ mri.filename || "—" }}</span>
      </div>
      <div class="ws-actions">
        <el-button size="small" @click="goBack">返回病例详情</el-button>
      </div>
    </header>

    <div class="ws-body">
      <MRIViewer
        v-if="mri.file_url"
        :case-id="Number(caseId)"
        :file-url="mri.file_url"
        :slice-url="mri.slice_url"
        :preview-urls="mri.preview_urls"
        :preview-views="mri.preview_views"
        :filename="mri.filename"
        :patient-name="patient.name"
      />
      <el-empty v-else description="该病例暂无 MRI 影像，请先上传" />
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from "vue"
import { useRoute, useRouter } from "vue-router"
import request from "../api/axios"
import MRIViewer from "../components/mri/MRIViewer.vue"

const route = useRoute()
const router = useRouter()

const caseId = computed(() => String(route.params.id || ""))
const patient = ref({})
const mri = ref({})

const genderText = computed(() => {
  if (patient.value.gender === "male") return "男"
  if (patient.value.gender === "female") return "女"
  return patient.value.gender || "—"
})

async function load() {
  try {
    const res = await request.get("/cases/" + caseId.value + "/detail")
    const data = res.data.data || {}
    patient.value = data.patient || {}
    mri.value = data.mri || {}
  } catch (e) {
    console.error(e)
  }
}

function goBack() {
  router.push("/case/" + caseId.value)
}

onMounted(load)
</script>

<style scoped>
.ws-page { min-height: 100vh; background: #060b16; color: #e2e8f0; }
.ws-banner {
  display: flex;
  align-items: center;
  gap: 24px;
  padding: 10px 20px;
  background: #0b1220;
  border-bottom: 1px solid #1e293b;
  flex-wrap: wrap;
}
.ws-brand { font-size: 14px; font-weight: 700; color: #38bdf8; }
.ws-patient { display: flex; align-items: baseline; gap: 12px; }
.ws-name { font-size: 16px; font-weight: 600; color: #f8fafc; }
.ws-meta { font-size: 12px; color: #94a3b8; }
.ws-study { display: flex; align-items: center; gap: 8px; flex: 1; min-width: 200px; }
.ws-filename { font-size: 12px; color: #cbd5e1; }
.ws-actions { margin-left: auto; }
.ws-body { padding: 12px; }
</style>
