<template>
  <div class="page report-page">
    <div class="report-toolbar">
      <div>
        <h1>{{ dicomMode ? "DICOM 阅片记录" : "诊断报告" }}</h1>
        <p class="toolbar-sub">BrainFusion AI 教学科研原型 · 报告仅供科研参考</p>
      </div>
      <div class="toolbar-actions">
        <el-button :disabled="exporting" :loading="loading" @click="loadReport">刷新报告</el-button>
        <el-button type="primary" :disabled="!reportReady || loading || reviewSaving" :loading="exporting" @click="exportPDF">导出 PDF</el-button>
      </div>
    </div>

    <!-- 报告主体（可导出为 PDF） -->
    <el-alert v-if="!reportReady && !loading" :title="reportError || '尚无当前成功分割报告，请先完成真实模型分析。'" type="info" :closable="false" />
    <div v-if="reportReady && dicomMode" id="report-paper" class="report-paper dicom-report">
      <header class="paper-header">
        <div class="paper-brand">BrainFusion AI · DICOM 阅片记录</div>
        <div class="paper-meta"><span>病例编号：{{ caseId }}</span><span>核对时间：{{ time }}</span></div>
        <p class="review-status">人工复核：{{ reviewStatus }}</p>
      </header>
      <section class="paper-section">
        <h2>一、归档来源与空间</h2>
        <p>归档：{{ dicomReport.context.archive_id }} · 病例检查关联：{{ dicomReport.context.case_link_id }}</p>
        <div v-for="key in ['study_uid', 'series_uid', 'frame_of_reference_uid']" :key="key" class="provenance-digest">
          <span>{{ { study_uid: 'Study UID', series_uid: 'Series UID', frame_of_reference_uid: 'Frame of Reference UID' }[key] }}</span><code>{{ dicomReport.context[key] }}</code>
        </div>
        <p>体积尺寸 X / Y / Z：{{ dicomReport.geometry.dimensions.join(' / ') }}</p>
        <p>体素间距 X / Y / Z：{{ dicomReport.geometry.spacing_xyz_mm.map(v => Number(v).toFixed(6)).join(' / ') }} mm</p>
        <p class="provenance-note">患者原空间 LPS 毫米；未自动配准或重采样。序列模型角色尚未确认。</p>
      </section>
      <section class="paper-section dicom-measurements-paper">
        <h2>二、当前来源的已保存距离</h2>
        <p v-if="!dicomReport.measurements.length">当前来源暂无已保存距离。</p>
        <table v-else class="report-table">
          <thead><tr><th>记录 / 平面</th><th>距离</th><th>患者 LPS 端点（mm）</th></tr></thead>
          <tbody><tr v-for="item in dicomReport.measurements" :key="item.id">
            <td>#{{ item.id }} · {{ {axial:'轴状', sagittal:'矢状', coronal:'冠状'}[item.view] }}</td>
            <td>{{ Number(item.length_mm).toFixed(3) }} mm</td>
            <td class="measurement-points">{{ item.points_lps.map(p => p.map(v => Number(v).toFixed(3)).join(', ')).join(' → ') }}</td>
          </tr></tbody>
        </table>
        <p class="provenance-note">仅记录人工工程线段，未经病灶身份或临床直径确认。未保存草稿不纳入；{{ dicomReport.excluded_historical_measurements }} 条旧来源距离已排除。</p>
      </section>
      <section class="paper-section dicom-opinion-paper">
        <div class="opinion-intro">
          <h2>三、病例医生意见（独立记录）</h2>
          <p class="opinion-paragraph">{{ dicomOpinionParagraphs[0] }}</p>
        </div>
        <div class="dicom-case-opinion"><p v-for="(paragraph, index) in dicomOpinionParagraphs.slice(1)" :key="index" class="opinion-paragraph">{{ paragraph }}</p></div>
        <p v-if="dicomReport.doctor_opinion?.author" class="opinion-author">记录人：{{ dicomReport.doctor_opinion.author }}</p>
        <p class="provenance-note">病例级意见，未绑定本序列与来源版本；不表示医生已确认本次测量或 AI 结果。</p>
      </section>
      <section class="paper-section provenance-section">
        <h2>四、版本核对与范围</h2>
        <div class="provenance-digest"><span>归档配置指纹 SHA-256</span><code>{{ dicomReport.context.archive_fingerprint }}</code></div>
        <div class="provenance-digest"><span>成组元数据 SHA-256</span><code>{{ dicomReport.context.metadata_sha256 }}</code></div>
        <div class="provenance-digest"><span>本记录内容 SHA-256</span><code>{{ dicomReport.content_sha256 }}</code></div>
        <div class="provenance-digest"><span>导出版本 SHA-256（含复核记录）</span><code>{{ dicomReport.export_sha256 }}</code></div>
        <p class="provenance-note">归档身份、病例关联和元数据版本核对；不代表逐次完整像素认证。保存的距离与病例意见参与内容版本核对。</p>
      </section>
      <section v-if="dicomReport.latest_review?.current" class="paper-section dicom-review-paper">
        <div class="review-intro">
        <h2>五、当前来源与内容的人工复核记录</h2>
        <p>记录 #{{ dicomReport.latest_review.id }} · {{ reviewStatus }}</p>
        <p>复核署名：{{ dicomReport.latest_review.reviewer }} · {{ dicomReport.latest_review.reviewer_authenticated ? "本地账户已验证" : "历史未认证署名" }}</p>
        <p>记录时间：{{ reviewTime(dicomReport.latest_review.created_time) }}</p>
        </div>
        <div class="manual-review-text"><p v-for="(paragraph, index) in reviewParagraphs" :key="index" class="review-paragraph">{{ paragraph }}</p></div>
        <div class="review-binding">
        <div class="provenance-digest"><span>复核绑定内容 SHA-256</span><code>{{ dicomReport.latest_review.content_sha256 }}</code></div>
        <p class="provenance-note">{{ dicomReport.latest_review.reviewer_authenticated ? "本地账户已登录验证；角色为本机授权，未核验医师资质。" : "历史本机自行署名，未进行身份或医师资质认证。" }}仅绑定本页来源及内容，不代表临床诊断、脱敏认证或模型复核。</p>
        </div>
      </section>
      <footer class="paper-footer"><p>教学科研阅片记录，不构成临床诊断或治疗建议。本记录未包含模型分割、IDH 预测或模型复核结果；四序列 AI 输入需另行审核。</p></footer>
    </div>
    <div v-else-if="reportReady" id="report-paper" class="report-paper">
      <header class="paper-header">
        <div class="paper-brand">BrainFusion AI 诊断报告</div>
        <div class="paper-meta">
          <span>病例编号：{{ caseId }}</span>
          <span>生成时间：{{ time }}</span>
          <span>分割模型：{{ modelVersion }}</span>
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
        <h2>三、MRI 分割分析结果</h2>
        <table class="report-table">
          <thead>
            <tr><th>指标</th><th>模型</th><th>数值</th></tr>
          </thead>
          <tbody>
            <tr v-for="(value, region) in analysis?.result?.volumes_ml" :key="region"><td>{{ region }} 体积</td><td>{{ analysis.result.model }}</td><td>{{ value }} mL</td></tr>
          </tbody>
        </table>
        <p>分析版本：{{ analysis?.id || '未运行' }}</p>
        <p>医生复核：{{ mri.doctor_verified && mri.verified_run_id === analysis?.id ? '已确认当前版本' : '待复核' }}</p>
      </section>

      <section class="paper-section">
        <h2>四、研究限制</h2>
        <div class="risk-line">
          <p>当前报告来自真实 MRI 分割，不提供临床风险或生存预测。IDH 研究结果需在研究页单独查看其输入来源、原始目标值及限制。</p>
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

      <section class="paper-section provenance-section">
        <h2>八、结果来源追溯</h2>
        <p>分析运行 ID：{{ analysis?.id || '未记录' }}</p>
        <div class="provenance-digest"><span>模型修订标识</span><code>{{ provenanceRevision(analysis?.result?.revision) }}</code></div>
        <div class="provenance-digest"><span>模型权重 SHA-256</span><code>{{ provenanceDigest(analysis?.result?.checkpoint_sha256) }}</code></div>
        <div class="provenance-digest"><span>分割掩膜 SHA-256</span><code>{{ provenanceDigest(analysis?.result?.mask_sha256) }}</code></div>
        <ul class="provenance-list">
          <li v-for="item in sourceSequenceHashes" :key="item.key">
            <span>{{ item.label }}输入 SHA-256</span><code>{{ provenanceDigest(item.digest) }}</code>
          </li>
        </ul>
        <p class="provenance-note">摘要仅用于核对本次报告绑定的模型与输入文件，不构成数据来源认证。</p>
      </section>

      <footer class="paper-footer">
        <p>本报告由 BrainFusion AI 教学科研原型系统自动生成，仅供教学与科研参考，不构成临床诊断或治疗建议，最终判断请以具有执业资质的医生阅片意见为准。</p>
      </footer>
    </div>
    <section v-if="dicomMode && reportReady" class="review-editor" aria-label="DICOM人工复核记录">
      <h2>记录本版本人工复核</h2>
      <p>复核绑定本页来源、已保存距离及病例级意见；需登录本地医生角色账户。账户验证不等于医师资质核验，不改变病例医生意见或 AI 复核状态。</p>
      <div class="local-auth-box">
        <p v-if="localUser">已登录：{{ localUser.display_name }}（{{ localUser.role === 'doctor' ? '本地医生角色' : '研究员角色，仅可阅片' }}）<el-button :disabled="authBusy || reviewSaving" @click="logoutLocal">退出账户</el-button></p>
        <template v-else>
          <p v-if="!authConfigured">尚未配置本地账户，请由本机维护者按账户操作说明建立账户。</p>
          <el-input v-model="loginName" aria-label="本地账户" placeholder="本地账户" autocomplete="username" :disabled="authBusy || !authConfigured" />
          <el-input v-model="loginPassword" aria-label="账户密码" type="password" placeholder="账户密码" autocomplete="current-password" :disabled="authBusy || !authConfigured" @keyup.enter="loginLocal" />
          <el-button :loading="authBusy" :disabled="!authConfigured || !loginName || !loginPassword" @click="loginLocal">登录复核账户</el-button>
        </template>
        <p v-if="authError" role="alert">{{ authError }}</p>
      </div>
      <el-alert v-if="reviewError || reviewHistoryError" :title="reviewError || reviewHistoryError" type="warning" :closable="false" />
      <el-input v-model="reviewName" aria-label="复核署名" placeholder="登录后由账户确定署名" :maxlength="120" readonly :disabled="reviewSaving || !localUser" />
      <el-select v-model="reviewDecision" aria-label="复核结果" :disabled="reviewSaving">
        <el-option value="checked" label="已核对本页记录" /><el-option value="needs_revision" label="记录需修改" />
      </el-select>
      <el-input v-model="reviewOpinion" type="textarea" :rows="4" aria-label="本版本复核意见" placeholder="填写本版本复核意见，不自动生成临床结论" :maxlength="4000" show-word-limit :disabled="reviewSaving" />
      <el-checkbox v-model="reviewAcknowledge" :disabled="reviewSaving">已核对本页当前来源及内容，仅记录本地账户人工复核</el-checkbox>
      <el-button type="primary" :loading="reviewSaving" :disabled="!canSaveReview" @click="saveDicomReview">保存本版本复核</el-button>
      <p v-if="reviewSavedMessage" role="status" class="review-save-message">{{ reviewSavedMessage }}</p>
      <h3>复核历史（{{ dicomReport.review_history_count || 0 }} 条）</h3>
      <p v-if="!reviewHistory.length && !reviewHistoryError">尚无序列复核记录。</p>
      <details v-for="item in reviewHistory" :key="item.id" class="review-history-row" :data-review-id="item.id">
        <summary>#{{ item.id }} · {{ item.reviewer }} · {{ item.current ? '对应当前内容' : '历史内容，当前不适用' }} · {{ item.reviewer_authenticated ? '本地账户' : '未认证历史' }} · {{ item.decision === 'checked' ? '已核对记录' : '需修改' }}</summary>
        <p class="opinion-text">{{ item.opinion }}</p>
        <p>记录时间：{{ reviewTime(item.created_time) }} · 已保存距离：{{ item.reviewed_snapshot.measurements.length }} 条</p>
        <p>复核绑定内容：<code>{{ item.content_sha256 }}</code></p>
        <p>复核时来源元数据：<code>{{ item.context.metadata_sha256 }}</code></p>
        <p v-for="measurement in item.reviewed_snapshot.measurements" :key="measurement.id">距离 #{{ measurement.id }}：{{ Number(measurement.length_mm).toFixed(3) }} mm</p>
      </details>
      <el-button v-if="reviewHistoryNext !== null" :disabled="reviewSaving" @click="loadReviewHistory(reportKey, reviewHistoryNext)">更多复核历史</el-button>
    </section>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, ref, watch } from "vue"
import { useRoute } from "vue-router"
import { ElMessage } from "element-plus"
import request from "../api/axios"

const route = useRoute()
const caseId = computed(() => String(route.query.case_id || ""))
const dicomMode = computed(() => route.query.source === 'dicom')
const reportKey = computed(() => JSON.stringify([caseId.value, route.query.source, route.query.study_uid, route.query.series_uid]))
const dicomReport = ref(null)
const reviewName = ref(''), reviewOpinion = ref(''), reviewDecision = ref('checked'), reviewAcknowledge = ref(false)
const localUser = ref(null), authConfigured = ref(false), authBusy = ref(false), authError = ref('')
const loginName = ref(''), loginPassword = ref('')
let authCsrf = ''
const reviewSaving = ref(false), reviewError = ref(''), reviewSavedMessage = ref('')
const reviewHistory = ref([]), reviewHistoryNext = ref(null), reviewHistoryError = ref('')
let pendingReview = null
const reviewStatus = computed(() => {
  const review = dicomReport.value?.latest_review
  if (!review) return '尚无本序列复核记录'
  if (!review.current) return '历史复核已过期，需重新核对当前内容'
  const attribution = review.reviewer_authenticated ? '本地账户' : '历史未认证署名'
  return review.decision === 'checked' ? `已记录本版本人工核对（${attribution}）` : `本版本记录需修改（${attribution}）`
})
const canSaveReview = computed(() => dicomMode.value && reportReady.value && !loading.value && !exporting.value
  && !reviewSaving.value && !authBusy.value && localUser.value?.role === 'doctor' && !reviewHistoryError.value && reviewAcknowledge.value && reviewName.value.trim() && reviewOpinion.value.trim())
const dicomRevision = data => data ? `${data.content_sha256}:${data.export_sha256}` : ''
const reviewTime = value => value ? new Date(value).toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai', hour12: false }) + '（北京时间）' : '未记录'
// Presentation blocks let long unbroken opinions paginate without cutting glyphs.
// The source text and its content digest remain unchanged.
function opinionBlocks(text) {
  const paragraphs = []
  for (const line of text.split(/\r?\n/)) {
    let chars = Array.from(line)
    if (!chars.length) paragraphs.push('\u00a0')
    while (chars.length) {
      let end = Math.min(120, chars.length)
      if (chars.length > 120) {
        const space = chars.slice(0, 120).lastIndexOf(' ')
        if (space >= 60) end = space + 1
      }
      paragraphs.push(chars.slice(0, end).join('')); chars = chars.slice(end)
    }
  }
  return paragraphs
}
const reviewParagraphs = computed(() => opinionBlocks(dicomReport.value?.latest_review?.opinion || ''))
const dicomOpinionParagraphs = computed(() => opinionBlocks(dicomReport.value?.doctor_opinion?.content || '（暂无病例医生意见）'))

const dicomEndpoint = () => `/pacs/cases/${encodeURIComponent(caseId.value)}/studies/${encodeURIComponent(String(route.query.study_uid || ''))}/series/${encodeURIComponent(String(route.query.series_uid || ''))}/reading-report`

const report = ref({})
const analysis = ref(null)
const patient = ref({})
const mri = ref({})
const doctorOpinion = ref({})
const modelVersion = ref("未记录")
const time = ref("")
const summary = ref([])
const recommendation = ref([])
const exporting = ref(false)
const loading = ref(false)
const reportError = ref("")
const reportReady = computed(() => dicomMode.value ? Boolean(dicomReport.value?.content_sha256 && dicomReport.value?.case_id === Number(caseId.value)) : Boolean(report.value.analysis_run_id && analysis.value?.state === 'succeeded' && !analysis.value.stale && analysis.value.result && report.value.analysis_run_id === analysis.value.id))
const sequenceLabels = { t1c: 'T1c', t1n: 'T1n', t2w: 'T2w', t2f: 'FLAIR' }
const sourceSequenceHashes = computed(() => Object.entries(sequenceLabels).map(([key, label]) => ({
  key,
  label,
  digest: analysis.value?.result?.input_sha256?.[key],
})))

function provenanceDigest(value) {
  return typeof value === 'string' && /^[a-f0-9]{64}$/i.test(value) ? value : '未记录'
}

function provenanceRevision(value) {
  return typeof value === 'string' && /^[a-f0-9]{7,64}$/i.test(value) ? value : '未记录'
}

const genderText = computed(() => {
  if (patient.value.gender === "male") return "男"
  if (patient.value.gender === "female") return "女"
  return patient.value.gender || "—"
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

async function loadLocalSession() {
  try {
    const state = (await request.get('/local-auth/session')).data.data
    if (localUser.value?.id !== state.user?.id) { pendingReview = null; reviewAcknowledge.value = false }
    localUser.value = state.user; authConfigured.value = state.configured; authCsrf = state.csrf || ''
    reviewName.value = state.user?.display_name || ''
  } catch (e) {
    localUser.value = null; authCsrf = ''; reviewName.value = ''; reviewAcknowledge.value = false
    authError.value = '账户状态读取失败，请刷新后重试。'
  }
}
async function loginLocal() {
  if (authBusy.value || !loginName.value || !loginPassword.value) return
  authBusy.value = true; authError.value = ''
  try {
    await request.post('/local-auth/login', { username: loginName.value, password: loginPassword.value })
    await loadLocalSession()
  } catch (e) { authError.value = e.response?.data?.message || '登录失败，请核对账户后重试。' }
  finally { loginPassword.value = ''; authBusy.value = false }
}
async function logoutLocal() {
  authBusy.value = true; authError.value = ''
  try { await request.post('/local-auth/logout', {}, { headers: { 'X-BF-CSRF': authCsrf } }) }
  catch (e) { authError.value = e.response?.data?.message || '退出失败，请刷新账户状态。' }
  finally { await loadLocalSession(); authBusy.value = false }
}

async function loadReviewHistory(key, offset = 0) {
  try {
    const result = (await request.get(dicomEndpoint().replace('/reading-report', '/reviews'), { params: { limit: 20, offset }, timeout: 90000 })).data.data
    if (key !== reportKey.value) return
    if (result.content_sha256 !== dicomReport.value?.content_sha256) throw Error('阅片内容已变化，请刷新后重新核对。')
    reviewHistory.value = offset ? [...reviewHistory.value, ...result.items] : result.items
    reviewHistoryNext.value = result.next_offset
    reviewHistoryError.value = ''
  } catch (e) {
    if (key === reportKey.value) {
      reviewHistory.value = []; reviewHistoryNext.value = null
      reviewHistoryError.value = '复核历史加载失败，请刷新后再记录复核。' + (e.response?.data?.detail?.message || e.message || '')
    }
  }
}

async function saveDicomReview() {
  if (!canSaveReview.value) return
  const key = reportKey.value
  const fields = { context: dicomReport.value.context, content_sha256: dicomReport.value.content_sha256,
    reviewer: reviewName.value.trim(), opinion: reviewOpinion.value.trim(), decision: reviewDecision.value,
    acknowledge_local_record_only: true }
  const signature = JSON.stringify(fields)
  if (!pendingReview || pendingReview.signature !== signature) pendingReview = { signature, payload: { ...fields, client_uid: crypto.randomUUID() } }
  const payload = pendingReview.payload
  const endpoint = dicomEndpoint().replace('/reading-report', '/reviews')
  reviewSaving.value = true; reviewError.value = ''; reviewSavedMessage.value = ''
  try {
    const saved = (await request.post(endpoint, payload, { timeout: 90000, headers: { 'X-BF-CSRF': authCsrf } })).data.data
    if (key !== reportKey.value) return
    if (saved.content_sha256 !== payload.content_sha256 || saved.reviewer_authenticated !== true || saved.identity?.id !== localUser.value?.id) throw Error('复核记录返回身份或版本不一致。')
    reviewSavedMessage.value = `复核记录 #${saved.id} 已保存（本地账户已验证，未核验医师资质）。`
    pendingReview = null; reviewAcknowledge.value = false
    await loadReport()
  } catch (e) {
    if (key === reportKey.value) {
      reviewError.value = '复核保存失败，可重试同一请求。' + (e.response?.data?.detail?.message || (typeof e.response?.data?.detail === 'string' ? e.response.data.detail : e.message || ''))
      if ([401, 403].includes(e.response?.status)) { await loadLocalSession(); reviewAcknowledge.value = false }
      if (e.response?.status === 409) { reviewAcknowledge.value = false; await loadReport() }
    }
  } finally { if (key === reportKey.value) reviewSaving.value = false }
}

async function loadReport() {
  const requestedCase = caseId.value
  const requestedKey = reportKey.value
  dicomReport.value = null
  report.value = {}; analysis.value = null; summary.value = []; recommendation.value = []
  patient.value = {}; mri.value = {}; doctorOpinion.value = {}; reportError.value = ""
  if (!requestedCase) return false
  loading.value = true
  try {
    if (dicomMode.value) {
      if (!/^[0-9.]+$/.test(String(route.query.study_uid || '')) || !/^[0-9.]+$/.test(String(route.query.series_uid || ''))) throw Error('缺少检查或序列标识。')
      const result = (await request.get(dicomEndpoint(), { timeout: 90000 })).data.data
      if (requestedKey !== reportKey.value) return false
      if (result.case_id !== Number(requestedCase) || result.context?.study_uid !== route.query.study_uid
          || result.context?.series_uid !== route.query.series_uid || result.ai_analysis_included !== false
          || !/^[a-f0-9]{64}$/.test(result.content_sha256) || !/^[a-f0-9]{64}$/.test(result.export_sha256)) throw Error('阅片记录来源不一致。')
      dicomReport.value = result
      time.value = new Date(result.observed_utc).toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai', hour12: false }) + '（北京时间）'
      await loadReviewHistory(requestedKey)
      return reportReady.value
    }
    const res = await request.get("/cases/" + requestedCase + "/detail")
    if (requestedKey !== reportKey.value) return false
    const data = res.data.data || {}
    analysis.value = data.analysis || null
    report.value = data.report || {}
    patient.value = data.patient || {}
    mri.value = data.mri || {}
    modelVersion.value = data.analysis?.result?.model || "未记录"
    time.value = data.report?.created_time ? new Date(data.report.created_time).toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai', hour12: false }) + '（北京时间）' : "未记录"
    summary.value = parseList(data.report?.summary)
    recommendation.value = parseList(data.report?.recommendation)
    if (!reportReady.value) reportError.value = data.analysis?.stale ? '当前分割已失效，报告/PDF不可用；历史保留。原因：' + data.analysis.stale_reason : "尚无当前成功分割报告；历史占位报告和失效版本不用于导出。"
    const opinion = await request.get("/cases/" + requestedCase + "/doctor-opinion")
    if (requestedKey !== reportKey.value) return false
    doctorOpinion.value = opinion.data.data || {}
    return reportReady.value
  } catch (e) {
    if (requestedKey === reportKey.value) {
      report.value = {}; analysis.value = null; dicomReport.value = null; summary.value = []; recommendation.value = []; doctorOpinion.value = {}
      reportError.value = dicomMode.value
        ? "DICOM 阅片记录当前不可用，已停止显示和导出旧内容。" + (e.response?.data?.detail?.message || e.message || '请刷新重试。')
        : "报告加载失败，已停止显示和导出旧内容。请刷新重试。"
      ElMessage.error(reportError.value)
    }
    return false
  } finally {
    if (requestedKey === reportKey.value) loading.value = false
  }
}

async function exportPDF() {
  const displayedRun = dicomMode.value ? dicomRevision(dicomReport.value) : report.value.analysis_run_id
  const isDicom = dicomMode.value
  const endpoint = isDicom ? dicomEndpoint() : `/reports/${caseId.value}`
  const revision = data => isDicom ? dicomRevision(data) : data.analysis_run_id
  const requestedCase = caseId.value
  const requestedKey = reportKey.value
  if (!reportReady.value || loading.value || exporting.value) return
  exporting.value = true
  try {
    // Re-read current state immediately before export; a stale open page cannot export its old result.
    const current = (await request.get(endpoint, { timeout: 90000 })).data.data
    if (revision(current) !== displayedRun) {
      await loadReport()
      ElMessage.warning("来源或记录版本已变化，请核对刷新后的报告再导出。")
      return
    }
    if (!(await loadReport()) || requestedKey !== reportKey.value || (isDicom ? dicomRevision(dicomReport.value) : report.value.analysis_run_id) !== displayedRun) {
      ElMessage.warning("来源或记录版本已变化，请核对刷新后的报告再导出。")
      return
    }
    await nextTick()
    const element = document.getElementById("report-paper")
    if (!element) return
    const mod = await import("html2pdf.js")
    const html2pdf = mod.default || mod
    const opt = {
      margin: [10, 10, 12, 10],
      filename: (isDicom ? "BrainFusion_DICOM_case" : "BrainFusion_Report_case") + requestedCase + ".pdf",
      image: { type: "jpeg", quality: 0.98 },
      html2canvas: {
        scale: 2, useCORS: true, logging: false,
        // A heading's decorative border can leave a fragment at a raster page break.
        // Keep the bold heading and spacing, but omit this decoration in the PDF clone.
        onclone: document => document.querySelectorAll('#report-paper .paper-section h2').forEach(
          heading => { heading.style.borderLeftColor = 'transparent' },
        ),
      },
      jsPDF: { unit: "mm", format: "a4", orientation: "portrait" },
      pagebreak: { mode: ["css", "legacy"], avoid: [".paper-header", ".paper-section:not(.dicom-review-paper):not(.dicom-measurements-paper):not(.dicom-opinion-paper)", ".dicom-report .report-table tr", ".dicom-measurements-paper h2", ".opinion-intro", ".opinion-paragraph", ".review-intro", ".review-paragraph", ".review-binding", ".paper-footer"] },
    }
    const pdf = await html2pdf().set(opt).from(element).toPdf().get('pdf')
    // Rendering is asynchronous. Recheck once more before triggering a download,
    // so a new analysis or file drift during rendering cannot export old content.
    const ready = (await request.get(endpoint, { timeout: 90000 })).data.data
    if (requestedKey !== reportKey.value || revision(ready) !== displayedRun) {
      await loadReport()
      ElMessage.warning("来源或记录版本已变化，请核对刷新后的报告再导出。")
      return
    }
    pdf.save(opt.filename)
    ElMessage.success("PDF 报告已导出")
  } catch (e) {
    await loadReport()
    ElMessage.error(e.response?.data?.detail?.message || (typeof e.response?.data?.detail === "string" ? e.response.data.detail : "PDF 导出失败，请核对当前报告后重试。"))
  } finally {
    exporting.value = false
  }
}

onMounted(async () => { await loadLocalSession(); await loadReport() })
watch(reportKey, () => {
  reviewName.value = localUser.value?.display_name || ''; reviewOpinion.value = ''; reviewAcknowledge.value = false; reviewDecision.value = 'checked'
  reviewError.value = ''; reviewSavedMessage.value = ''; reviewSaving.value = false; pendingReview = null
  reviewHistory.value = []; reviewHistoryNext.value = null; reviewHistoryError.value = ''
  loadReport()
})
</script>

<style scoped>
.local-auth-box { padding: 12px; margin: 12px 0; border: 1px solid #cbd5e1; border-radius: 6px; }
.local-auth-box .el-input { margin-bottom: 10px; }
.local-auth-box p { font-size: 13px; }
.review-editor { margin-top: 24px; padding: 20px; background: white; border: 1px solid #e2e8f0; border-radius: 8px; }
.review-editor > .el-input, .review-editor > .el-select, .review-editor > .el-textarea { margin-bottom: 12px; }
.review-editor > .el-checkbox { display: flex; width: 100%; height: auto; margin: 12px 0; }
.review-editor :deep(.el-checkbox__label) { white-space: normal; line-height: 1.6; }
.review-editor > p { font-size: 13px; color: #475569; }
.review-history-row { padding: 10px 0; border-top: 1px solid #e2e8f0; overflow-wrap: anywhere; }
.review-history-row .opinion-text { white-space: pre-wrap; }
.review-save-message { color: #047857 !important; }
.dicom-report .review-paragraph { margin: 0; white-space: pre-wrap; line-height: 1.7; }
.dicom-report .opinion-paragraph { margin: 0; white-space: pre-wrap; line-height: 1.7; }
.review-status { font-size: 13px; color: #475569; }
.measurement-points { font-size: 11px; overflow-wrap: anywhere; }
.dicom-report p { overflow-wrap: anywhere; }
.dicom-report { padding: 24px 30px; }
.dicom-report p { margin: 8px 0; }
.dicom-report .paper-section { margin-bottom: 14px; }
.dicom-report .opinion-text { min-height: 24px; }
.dicom-report .paper-footer { margin-top: 14px; }
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
.provenance-list { margin: 0; padding-left: 20px; font-size: 11px; line-height: 1.5; }
.provenance-list li { margin: 4px 0; }
.provenance-digest { margin: 5px 0; font-size: 12px; }
.provenance-digest code, .provenance-list code { display: block; padding: 2px 0; font-family: ui-monospace, SFMono-Regular, Consolas, monospace; font-size: 10px; line-height: 1.3; overflow-wrap: anywhere; word-break: break-all; }
.provenance-note { color: #64748b; font-size: 12px; }

.paper-footer { margin-top: 24px; padding-top: 12px; border-top: 1px dashed #cbd5e1; }
.paper-footer p { margin: 0; font-size: 12px; color: #64748b; line-height: 1.6; }
</style>
