<template>
  <div class="page">
    <div class="page-header">
      <div>
        <h1>病例管理</h1>
        <p>创建病例、上传 MRI 并进入 AI 分析流程。</p>
      </div>
      <el-button type="primary" @click="createDialogVisible = true">创建病例</el-button>
    </div>

    <div class="filter-bar">
      <el-input
        v-model="searchKeyword"
        placeholder="搜索病例描述或患者姓名"
        clearable
        style="width: 280px"
        @keyup.enter="loadCases"
        @clear="loadCases"
      />
      <el-select v-model="statusFilter" placeholder="全部状态" clearable style="width: 150px" @change="loadCases">
        <el-option v-for="(label, value) in statusLabels" :key="value" :label="label" :value="value" />
      </el-select>
      <el-button @click="resetFilters">重置</el-button>
    </div>

    <el-table v-loading="loading" :data="cases" border>
      <el-table-column prop="id" label="病例 ID" width="100" />
      <el-table-column prop="patient_id" label="患者 ID" width="100" />
      <el-table-column prop="patient_name" label="患者姓名" width="130">
        <template #default="{ row }">{{ row.patient_name || "-" }}</template>
      </el-table-column>
      <el-table-column prop="description" label="病例描述" min-width="280" />
      <el-table-column label="状态" width="130">
        <template #default="{ row }">
          <el-tag :type="statusType(row.status)">{{ statusText(row.status) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="330" fixed="right">
        <template #default="{ row }">
          <el-button size="small" @click="goDetail(row.id)">详情</el-button>
          <el-button size="small" type="success" @click="uploadMRI(row.id)">上传 MRI</el-button>
          <el-button size="small" type="warning" @click="analysis(row.id)">AI 分析</el-button>
          <el-button size="small" type="danger" @click="report(row.id)">报告</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-empty v-if="!loading && !cases.length" description="暂无病例" />

    <el-dialog v-model="createDialogVisible" title="创建病例" width="520px">
      <el-form label-width="90px">
        <el-form-item label="患者姓名">
          <el-input v-model="createForm.patient_name" placeholder="请输入患者姓名" />
        </el-form-item>
        <el-form-item label="年龄">
          <el-input-number v-model="createForm.age" :min="0" :max="120" />
        </el-form-item>
        <el-form-item label="性别">
          <el-select v-model="createForm.gender" style="width: 100%">
            <el-option label="男" value="male" />
            <el-option label="女" value="female" />
            <el-option label="其他" value="other" />
          </el-select>
        </el-form-item>
        <el-form-item label="病例描述">
          <el-input v-model="createForm.description" type="textarea" :rows="3" placeholder="请输入病例描述" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="creating" @click="submitCase">创建病例</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { onMounted, ref } from "vue"
import { ElMessage } from "element-plus"
import { useRouter } from "vue-router"
import request from "../api/axios"

const router = useRouter()
const cases = ref([])
const loading = ref(false)
const creating = ref(false)
const createDialogVisible = ref(false)
const searchKeyword = ref("")
const statusFilter = ref("")
const createForm = ref({ patient_name: "", age: 0, gender: "male", description: "" })

const statusLabels = {
  created: "待上传",
  uploaded: "已上传",
  preview_failed: "预览失败",
  analyzed: "已分析",
}

function statusText(status) {
  return statusLabels[status] || status || "未知"
}

function statusType(status) {
  if (status === "analyzed") return "success"
  if (status === "preview_failed") return "danger"
  if (status === "uploaded") return "warning"
  return "info"
}

async function loadCases() {
  loading.value = true
  try {
    const params = {}
    if (searchKeyword.value.trim()) params.search = searchKeyword.value.trim()
    if (statusFilter.value) params.status = statusFilter.value
    const response = await request.get("/cases/", { params })
    cases.value = response.data.data || []
  } catch (error) {
    ElMessage.error("病例加载失败")
  } finally {
    loading.value = false
  }
}

function resetFilters() {
  searchKeyword.value = ""
  statusFilter.value = ""
  loadCases()
}

function resetForm() {
  createForm.value = { patient_name: "", age: 0, gender: "male", description: "" }
}

async function submitCase() {
  if (!createForm.value.patient_name.trim() || !createForm.value.description.trim()) {
    ElMessage.warning("请填写患者姓名和病例描述")
    return
  }
  creating.value = true
  try {
    const response = await request.post("/cases/create", createForm.value)
    ElMessage.success(`病例创建成功：${response.data.data.case_id}`)
    createDialogVisible.value = false
    resetForm()
    await loadCases()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || "病例创建失败")
  } finally {
    creating.value = false
  }
}

function goDetail(id) { router.push({ name: "case-detail", params: { id } }) }
function uploadMRI(id) { router.push({ name: "upload-mri", params: { case_id: id } }) }
function analysis(id) { router.push(`/analysis?case_id=${id}`) }
function report(id) { router.push(`/report?case_id=${id}`) }

onMounted(loadCases)
</script>

<style scoped>
.page { padding: 24px; }
.page-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 20px; }
.page-header h1 { margin: 0 0 8px; }
.page-header p { margin: 0; color: #64748b; }
.filter-bar { display: flex; align-items: center; gap: 12px; margin-bottom: 16px; }
</style>
