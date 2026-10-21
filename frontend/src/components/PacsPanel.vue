<template>
  <el-card class="pacs-panel" :class="{ 'is-busy': busy }" aria-label="本地 DICOM 归档">
    <template #header><div class="pacs-header"><strong>本地 DICOM 归档</strong><el-button size="small" :loading="busy" @click="refresh">刷新归档状态</el-button></div></template>
    <el-alert :title="status.message || '正在检查归档状态…'" :type="status.read_available ? 'info' : 'warning'" :closable="false" />
    <p class="pacs-note">归档检查与当前 NIfTI 分别管理。核对病例关联后可浏览 DICOM 影像；AI 分析仍需完整四序列和输入检查。</p>
    <section class="pacs-import" aria-label="受控本机DICOM导入">
      <strong>从已核对的本机资料导入</strong>
      <p class="pacs-note">仅列出本机已登记、来源与像素处理范围有记录的公开 MR 派生资料。导入不自动关联病例，不替换 NIfTI，也不提交 AI。</p>
      <el-alert v-if="importError" :title="importError" type="warning" :closable="false" />
      <template v-if="importCandidates.length">
        <el-select v-model="importSelection" aria-label="已核对的本机导入资料" :disabled="busy" @change="selectImport">
          <el-option v-for="item in importCandidates" :key="item.candidate_id" :label="`${item.label} · ${item.instance_count} 层`" :value="item.candidate_id" />
        </el-select>
        <p v-if="selectedImport" class="pacs-note">{{ selectedImport.scope }}；来源 DOI：{{ selectedImport.collection_doi }}，许可 CC BY 4.0。技术核对不代表临床脱敏认证。</p>
        <el-checkbox v-model="importAcknowledge" :disabled="busy">已核对资料来源与像素处理范围，仅导入归档</el-checkbox>
        <el-button :disabled="busy || !status.import_available || !importSelection || !importAcknowledge" :loading="importSubmitting" @click="submitImport">导入所选资料</el-button>
        <div class="pacs-import-status" role="status" :data-import-id="importState?.id">
          {{ importStateLabel(importState?.state) }}
          <template v-if="importState"> · 已回读核对 {{ importState.verified }} / {{ importState.total }} 份；新增 {{ importState.stored_new }}，已存在 {{ importState.already_stored }}。</template>
          <p v-if="importState?.error" class="pacs-note">{{ importState.error }} 已归档内容保留，重试将逐份核对原字节。</p>
        </div>
      </template>
      <p v-else class="pacs-note">当前没有可选择的已登记资料。请先通过本机准备工具完成来源、像素范围核对及登记。</p>
    </section>
    <section class="pacs-conversions" aria-label="DICOM 转换来源">
      <strong>DICOM 转换来源</strong>
      <p class="pacs-note">{{ conversionStatus.message || '正在读取病例转换版本…' }}</p>
      <ul v-if="conversionVersions.length" class="pacs-links">
        <li v-for="version in conversionVersions" :key="version.version_id">
          {{ version.version_id }} · <code>{{ version.study_uid }}</code>
          <el-button size="small" :disabled="busy" @click="inspectConversion(version)">核对本地版本</el-button>
          <el-button size="small" :disabled="busy || !version.original_byte_check_enabled" @click="checkConversionSource(version)">核对当前归档来源</el-button>
          <el-button size="small" :disabled="busy || !version.archive_binding_matches_config" @click="openRoleReview(version)">查看角色审核</el-button>
          <p v-if="version.inspection" role="status">
            {{ inspectionLabel(version.inspection.status) }}：{{ version.inspection.message }}
          </p>
          <p v-if="version.sourceCheck" role="status" class="pacs-source-check">
            {{ sourceCheckLabel(version.sourceCheck.status) }}：{{ version.sourceCheck.message }}
          </p>
        </li>
      </ul>
      <section class="conversion-jobs" aria-label="持久DICOM转换作业">
        <div class="conversion-jobs-header"><strong>转换作业</strong><el-button size="small" :disabled="busy || !links.some(item => item.archive_matches_config)" @click="openConversionPlan">创建转换方案</el-button><el-button size="small" :disabled="busy" @click="refreshConversionJobs">刷新作业</el-button></div>
        <el-alert v-if="conversionJobsError" :title="conversionJobsError" type="warning" :closable="false" />
        <ul v-if="conversionJobs.length" class="pacs-links">
          <li v-for="job in conversionJobs" :key="job.job_id" :data-job-id="job.job_id" role="listitem">
            <span>{{ conversionJobStateLabel(job.state) }} · 尝试 {{ job.attempt }} · <code>{{ job.job_id }}</code></span>
            <span v-if="job.state === 'succeeded' && !job.registered" class="pacs-note">仅完成转换，尚未登记审核版本。</span>
            <span v-if="job.reason" class="pacs-note">{{ conversionJobReasonLabel(job.reason) }}</span>
            <el-button v-if="job.state === 'queued'" size="small" type="primary"
              :disabled="busy || Boolean(jobRetryingId)" :loading="jobRetryingId === job.job_id"
              @click="requestConversionAction(job, 'start')">启动转换</el-button>
            <el-button v-if="['failed', 'interrupted'].includes(job.state)" size="small"
              :disabled="busy || Boolean(jobRetryingId)" :loading="jobRetryingId === job.job_id"
              @click="retryConversionJob(job)">重新排队</el-button>
          </li>
        </ul>
        <p v-else class="pacs-note">此病例暂无准备好的转换作业。请先准备同一检查的四序列与来源核对资料；准备后可在这里启动转换。</p>
        <p class="pacs-note">启动仅使用已准备的来源，不替换当前影像。转换成功后仍需审核和单独激活；失败或中断可重新排队。</p>
        <el-dialog v-model="jobRetryLoginVisible" :title="jobRetryPending?.action === 'start' ? '医生账户确认启动转换' : '医生账户确认转换重试'" width="min(480px, 94%)" destroy-on-close>
          <p class="pacs-note">确认后执行已准备作业的来源核验与转换；不会激活MRI或运行模型推理。</p>
          <el-alert v-if="jobRetryLoginError" :title="jobRetryLoginError" type="warning" :closable="false" />
          <el-input v-model="jobRetryUsername" aria-label="转换操作医生账户名" autocomplete="username" placeholder="本地医生账户" />
          <el-input v-model="jobRetryPassword" aria-label="转换操作医生账户密码" type="password" autocomplete="current-password" placeholder="密码" @keyup.enter="loginForConversionRetry" />
          <template #footer><el-button :loading="jobRetryLoginBusy" :disabled="jobRetryLoginBusy || !jobRetryUsername || !jobRetryPassword" @click="loginForConversionRetry">{{ jobRetryPending?.action === 'start' ? '登录并启动' : '登录并重试' }}</el-button></template>
        </el-dialog>
      </section>
      <p class="pacs-note">转换版本默认不替换当前影像。只有当前归档原字节、角色审核和模型空间契约在激活时全部重新核对通过，才可切换输入；激活不会自动推理。</p>
    </section>
    <el-dialog v-model="planVisible" title="创建四序列转换方案" width="min(800px, 96%)" destroy-on-close @closed="closeConversionPlan">
      <p class="pacs-note">从已关联的同一检查中明确选择四个序列，并说明判断依据。系统会检查空间和来源；创建任务不会替换当前影像或启动AI。</p>
      <el-alert v-if="planError" :title="planError" type="warning" :closable="false" />
      <template v-if="jobRetryDoctor?.role !== 'doctor'">
        <p>请使用本地医生账户确认序列选择。该账户不代表执业资质认证。</p>
        <el-input v-model="planUsername" aria-label="方案医生账户名" autocomplete="username" placeholder="本地医生账户" :disabled="planBusy" />
        <el-input v-model="planPassword" aria-label="方案医生账户密码" type="password" autocomplete="current-password" placeholder="密码" :disabled="planBusy" />
        <el-button :loading="planBusy" :disabled="planBusy || !planUsername || !planPassword" @click="loginPlanDoctor">登录方案账户</el-button>
      </template>
      <p v-else>当前本地账户：{{ jobRetryDoctor.display_name }}</p>
      <el-select v-model="planStudy" aria-label="转换来源检查" placeholder="选择已关联检查" :disabled="planBusy" @change="loadPlanSeries">
        <el-option v-for="item in links.filter(link => link.archive_matches_config)" :key="item.study_uid" :label="item.study_uid" :value="item.study_uid" />
      </el-select>
      <p v-if="!planBusy && planSeries.length < 4" class="pacs-note">当前检查可用序列不足四个，不能创建模型转换方案；普通阅片不受影响。</p>
      <el-form label-width="120px">
        <el-form-item v-for="item in planAssignments" :key="item.role" :label="item.label">
          <el-select v-model="item.series_uid" :aria-label="'转换序列-' + item.role" placeholder="请按采集资料选择，不自动猜测" :disabled="planBusy" @change="invalidatePlanPreview">
            <el-option v-for="source in planSeries" :key="source.series_uid" :label="`${source.modality || 'MR'} · 序列 ${source.series_number ?? ''} · ${source.instance_count ?? '?'} 层 · ${source.series_uid}`" :value="source.series_uid" />
          </el-select>
        </el-form-item>
        <el-form-item label="判断依据">
          <el-select v-model="planBasis" aria-label="序列判断依据" :disabled="planBusy" @change="invalidatePlanPreview">
            <el-option label="采集记录" value="acquisition_record" /><el-option label="公开协议" value="published_protocol" /><el-option label="本地人工核对" value="local_manual_review" />
          </el-select>
        </el-form-item>
        <el-form-item label="来源说明">
          <el-input v-model="planEvidence" aria-label="序列来源说明" type="textarea" :rows="3" :maxlength="2000" placeholder="填写不含患者信息的采集/协议编号（8–128位字母、数字、点、冒号、下划线或短横线）" :disabled="planBusy" @input="invalidatePlanPreview" />
        </el-form-item>
        <el-form-item label="空间处理">
          <el-checkbox v-model="planResampleToT1c1mm" aria-label="显式重采样到T1增强1毫米网格" :disabled="planBusy" @change="invalidatePlanPreview">
            明确将四序列重采样到 T1 增强的 1 mm 网格
          </el-checkbox>
          <el-alert v-if="planResampleToT1c1mm" title="只对同一 Frame of Reference 做患者坐标插值，不执行图像配准。厚层影像（例如 6.5 mm）插值为 1 mm 不会恢复丢失的细节；该模式目前只用于可追溯的工程验收，不证明胶质瘤模型效能。" type="warning" :closable="false" />
        </el-form-item>
      </el-form>
      <section v-if="planPreview" aria-label="转换方案检查结果">
        <el-alert title="元数据与空间检查通过；创建任务时会从归档核对并保存原文件。角色仍需后续单独审核。" type="info" :closable="false" />
        <p>网格：{{ planPreview.dimensions.join(' × ') }}；间距：{{ planPreview.spacing_xyz_mm.join(' / ') }} mm</p>
        <el-alert v-if="planPreview.resampling_applied" title="此方案包含显式线性重采样。转换报告会保存源网格、目标网格、插值参数及逐体素复核结果；不会自动激活模型输入或启动推理。" type="warning" :closable="false" />
        <ul v-if="planPreview.resampling_applied">
          <li v-for="role in ['t1c','t1n','t2w','t2f']" :key="role">{{ role }}源矩阵 {{ planPreview.source_geometries[role].dimensions.join(' × ') }}；源间距 {{ planPreview.source_geometries[role].spacing_xyz_mm.join(' / ') }} mm</li>
        </ul>
        <ul><li v-for="item in planPreview.assignments" :key="item.role">{{ item.role }}：{{ item.instance_count }} 层</li></ul>
        <el-checkbox v-model="planAcknowledge" :disabled="planBusy">我已按来源资料核对四序列身份；创建后仅排队，需再手动启动转换</el-checkbox>
      </section>
      <template #footer>
        <el-button @click="planVisible = false">关闭</el-button>
        <el-button :loading="planBusy" :disabled="planBusy || !canPreviewPlan" @click="previewConversionPlan">检查转换方案</el-button>
        <el-button type="primary" :loading="planBusy" :disabled="planBusy || !planPreview || !planAcknowledge || jobRetryDoctor?.role !== 'doctor'" @click="createConversionPlanJob">创建转换任务</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="roleReviewVisible" title="DICOM 四序列角色审核" width="min(920px, 96%)" destroy-on-close>
      <p class="pacs-note">请按采集记录核对Study/Series与声明证据。本地账户仅记录复核身份，不验证执业资质；通过后仍不会替换当前MRI或提交AI。</p>
      <el-alert v-if="roleReviewError" :title="roleReviewError" type="warning" :closable="false" />
      <div v-if="roleReviewLoading" role="status">正在读取转换版本与审核记录…</div>
      <template v-if="roleReviewData">
        <el-alert v-if="!roleReviewData.review_allowed" title="该工程夹具或来源类型不能取得真实序列角色审批。" type="warning" :closable="false" />
        <el-table class="role-review-assignments" :data="roleReviewData.assignments" row-key="role">
          <el-table-column prop="role" label="模型角色" width="110" />
          <el-table-column prop="study_uid" label="Study UID" min-width="180" />
          <el-table-column prop="series_uid" label="Series UID" min-width="180" />
          <el-table-column label="声明依据" min-width="170"><template #default="{row}">{{ row.evidence.basis }} · {{ row.evidence.evidence_reference }}</template></el-table-column>
          <el-table-column label="元数据版本" min-width="115"><template #default="{row}">{{ row.series_metadata_sha256.slice(0, 12) }}</template></el-table-column>
        </el-table>
        <p class="pacs-note">计划版本：{{ roleReviewData.plan_revision }}<br>角色集合：{{ roleReviewData.assignment_set_sha256 }}</p>
        <div class="role-review-auth">
          <template v-if="roleReviewUser">
            <span>当前本地账户：{{ roleReviewUser.display_name }}（{{ roleReviewUser.role }}）</span>
            <el-button size="small" :disabled="roleReviewBusy" @click="logoutRoleReviewer">退出账户</el-button>
            <p v-if="roleReviewUser.role !== 'doctor'" class="pacs-note">研究员账户可查阅，不能提交角色审核决定。</p>
          </template>
          <template v-else>
            <strong>本地审核账户</strong>
            <el-input v-model="roleReviewUsername" aria-label="本地审核账户名" autocomplete="username" placeholder="账户名" :disabled="roleReviewBusy" />
            <el-input v-model="roleReviewPassword" aria-label="本地审核账户密码" type="password" autocomplete="current-password" placeholder="密码" :disabled="roleReviewBusy" @keyup.enter="loginRoleReviewer" />
            <el-button :loading="roleReviewBusy" :disabled="roleReviewBusy || !roleReviewConfigured || !roleReviewUsername || !roleReviewPassword" @click="loginRoleReviewer">登录本地账户</el-button>
            <span v-if="!roleReviewConfigured" class="pacs-note">本机尚未配置审核账户。</span>
          </template>
        </div>
        <template v-if="roleReviewUser?.role === 'doctor'">
          <el-checkbox v-model="roleReviewAcknowledge" :disabled="roleReviewBusy">我已逐项核对四个序列角色与来源声明</el-checkbox>
          <div class="role-review-actions">
            <el-button :disabled="roleReviewBusy || !roleReviewAcknowledge" :loading="roleReviewBusy && roleReviewDecision === 'reject'" @click="submitRoleReview('reject')">驳回当前角色映射</el-button>
            <el-button type="primary" :disabled="roleReviewBusy || !roleReviewData.review_allowed || !roleReviewAcknowledge" :loading="roleReviewBusy && roleReviewDecision === 'approve'" @click="submitRoleReview('approve')">确认角色映射</el-button>
          </div>
        </template>
        <section v-if="roleReviewData.history?.length" class="role-review-history" aria-label="角色审核历史">
          <strong>本版本审核历史</strong>
          <ul><li v-for="item in roleReviewData.history" :key="item.review_id">{{ item.decision === 'approve' ? '已确认' : '已驳回' }} · {{ item.reviewer.display_name }} · {{ item.reviewed_utc }}</li></ul>
        </section>
        <section v-if="activationApproved" class="role-review-activation" aria-label="审核后切换模型输入">
          <el-alert title="此步骤会把已核对的四序列设为当前MRI输入，使旧分析不再作为当前结果；不会启动分割或预测。" type="warning" :closable="false" />
          <el-checkbox v-model="activationAcknowledge" :disabled="roleReviewBusy">我确认切换当前模型输入并保留旧结果为历史</el-checkbox>
          <el-button type="danger" :disabled="roleReviewBusy || !activationAcknowledge || activationDone" :loading="roleReviewBusy && roleReviewDecision === 'activate'" @click="activateModelInput">审核后切换AI输入</el-button>
        </section>
        <el-alert v-if="roleReviewResult" :title="roleReviewResult" type="success" :closable="false" />
      </template>
      <template #footer><el-button @click="roleReviewVisible = false">关闭</el-button></template>
    </el-dialog>
    <el-alert v-if="error" :title="error" type="error" :closable="false" />
    <div v-if="status.read_available" class="pacs-query">
      <el-input v-model="studyFilter" placeholder="检查 UID（留空列出检查）" aria-label="检查 UID" clearable />
      <el-button :disabled="busy" @click="queryStudies(0)">查询检查</el-button>
    </div>
    <el-table v-if="studies.length" :data="studies" highlight-current-row @current-change="selectStudy">
      <el-table-column prop="study_uid" label="Study UID" min-width="250" />
      <el-table-column prop="study_date" label="检查日期" width="115" />
      <el-table-column label="模态" width="100"><template #default="{row}">{{ row.modalities?.join(' / ') || '—' }}</template></el-table-column>
      <el-table-column prop="series_count" label="序列数" width="90" />
    </el-table>
    <el-button v-if="studyNext !== null" :disabled="busy" @click="queryStudies(studyNext)">下一页检查</el-button>
    <div v-if="selectedStudy" class="pacs-selection">
      <p>当前检查：<code>{{ selectedStudy.study_uid }}</code></p>
      <el-checkbox v-model="acknowledge">已核对该检查与当前病例相符</el-checkbox>
      <el-button :disabled="busy || !acknowledge" @click="linkStudy">关联到病例 #{{ caseId }}</el-button>
      <el-table v-if="series.length" :data="series" highlight-current-row @current-change="selectSeries">
        <el-table-column prop="series_uid" label="Series UID" min-width="250" />
        <el-table-column prop="modality" label="模态" width="90" />
        <el-table-column prop="series_number" label="序列编号" width="100" />
        <el-table-column prop="instance_count" label="实例数" width="90" />
      </el-table>
      <el-button v-if="seriesNext !== null" :disabled="busy" @click="querySeries(seriesNext)">下一页序列</el-button>
      <div v-if="selectedSeries">
        <p>当前序列：<code>{{ selectedSeries.series_uid }}</code>（仅元数据清单）</p>
        <el-button :disabled="busy" @click="checkGeometry">核对序列空间</el-button>
        <div v-if="geometryManifest" class="pacs-geometry" role="status">
          <strong>空间核对通过（仅元数据）</strong>
          <el-button :disabled="busy || !canViewDicom" size="small" @click="openDicom">Cornerstone 阅片（工程验证）</el-button>
          <el-button :disabled="busy || !canViewDicom" size="small" @click="openDicomReport">DICOM 阅片记录 / PDF</el-button>
          <p v-if="!canViewDicom" class="pacs-note">阅片需要检查已关联到当前病例、归档标识已固定且后台允许读取像素。</p>
          <p>{{ geometryManifest.instance_count }} 层 · 间距 X / Y / Z：
            {{ geometryManifest.geometry.spacing_xyz_mm.map(v => Number(v).toFixed(3)).join(' / ') }} mm</p>
          <p class="pacs-note">按患者物理层位排序。尚未加载像素或指定模型序列角色；此结果不代表 DICOM 阅片或 AI 输入已验收。</p>
          <el-table :data="geometryManifest.instances">
            <el-table-column prop="instance_uid" label="物理排序后的 SOP UID" min-width="250" />
            <el-table-column label="层位投影（mm）" width="160"><template #default="{row}">{{ Number(row.projection_mm).toFixed(3) }}</template></el-table-column>
          </el-table>
        </div>
        <el-table :data="instances">
          <el-table-column prop="instance_uid" label="SOP Instance UID" min-width="250" />
          <el-table-column prop="frame_of_reference_uid" label="Frame of Reference UID" min-width="250" />
          <el-table-column prop="instance_number" label="实例编号" width="100" />
        </el-table>
        <el-button v-if="instanceNext !== null" :disabled="busy" @click="queryInstances(instanceNext)">下一页实例</el-button>
      </div>
    </div>
    <p v-if="!links.length" class="pacs-note">当前病例没有归档检查关联。</p>
    <ul v-else class="pacs-links"><li v-for="link in links" :key="link.id">
      {{ link.archive_id }} · <code>{{ link.study_uid }}</code>
      <el-tag size="small" :type="link.archive_matches_config ? 'info' : 'warning'">{{ link.archive_matches_config ? '配置对应' : '归档配置不匹配或不可用' }}</el-tag>
    </li></ul>
  </el-card>
</template>

<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import request from '../api/axios'
const props = defineProps({ caseId: { type: Number, required: true } })
const emit = defineEmits(['input-activated'])
const router = useRouter()
const status = ref({}), error = ref(''), busy = ref(false), studyFilter = ref('')
const studies = ref([]), series = ref([]), instances = ref([]), links = ref([])
const conversionStatus = ref({}), conversionVersions = ref([])
const conversionJobs = ref([]), conversionJobsError = ref(''), jobRetryingId = ref('')
const jobRetryLoginVisible = ref(false), jobRetryLoginBusy = ref(false), jobRetryLoginError = ref('')
const jobRetryUsername = ref(''), jobRetryPassword = ref(''), jobRetryPending = ref(null)
const jobRetryDoctor = ref(null), jobRetryCsrf = ref('')
const conversionJobStateLabel = value => ({ queued: '等待执行', running: '正在转换', succeeded: '转换完成', failed: '转换失败，可重试', interrupted: '服务中断，可重试' }[value] || '状态未知')
const conversionJobReasonLabel = value => ({ conversion_job_input_changed: '排队后输入字节发生变化，已拒绝处理', original_file_sha_mismatch: '原始DICOM校验失败', conversion_output_path_too_long: '输出目录过深，请缩短E盘路径后重新建作业', conversion_failed: '转换执行失败，原始输入保留', worker_interrupted_before_completion: '服务重启前作业未完成' }[value] || '作业未完成；原始输入与既有版本保留')
const roleReviewVisible = ref(false), roleReviewLoading = ref(false), roleReviewBusy = ref(false)
const roleReviewVersion = ref(''), roleReviewData = ref(null), roleReviewError = ref(''), roleReviewResult = ref('')
const roleReviewUser = ref(null), roleReviewCsrf = ref(''), roleReviewConfigured = ref(false)
const roleReviewUsername = ref(''), roleReviewPassword = ref(''), roleReviewAcknowledge = ref(false), roleReviewDecision = ref('')
const activationAcknowledge = ref(false), activationDone = ref(false)
const activationApproved = computed(() => Boolean(roleReviewData.value?.review_allowed
  && roleReviewData.value?.history?.at(-1)?.decision === 'approve'
  && roleReviewUser.value?.role === 'doctor' && roleReviewCsrf.value))

const importCandidates = ref([]), importSelection = ref(''), importAcknowledge = ref(false)
const importState = ref(null), importError = ref(''), importSubmitting = ref(false)
const selectedImport = computed(() => importCandidates.value.find(item => item.candidate_id === importSelection.value))
const importStateLabel = value => ({ queued: '等待导入', running: '正在导入与回读核对', succeeded: '上次导入完成（回读一致）', failed: '上次导入失败，可重试' }[value] || '尚未导入')
const inspectionLabel = value => ({ verified_readonly: '本地完整性通过（待来源审核）', stale: '来源已失效', unavailable: '当前不可用', invalid: '完整性核对失败' }[value] || '尚未核对')
const sourceCheckLabel = value => ({ matched_at_check: '归档原字节一致（本次观察，待审核）', stale: '归档来源不一致或已失效', unavailable: '归档来源当前不可核对', invalid: '归档来源核对失败' }[value] || '归档来源尚未核对')
const selectedStudy = ref(null), selectedSeries = ref(null), acknowledge = ref(false)
const geometryManifest = ref(null)
const canViewDicom = computed(() => Boolean(geometryManifest.value?.pixel_read_enabled
  && geometryManifest.value?.archive_server_identity_pinned
  && links.value.some(link => link.study_uid === selectedStudy.value?.study_uid && link.archive_matches_config)))
function openDicom() {
  if (!canViewDicom.value) return
  router.push({ path: '/workstation/' + props.caseId, query: { viewer: 'cornerstone', source: 'dicom', study_uid: selectedStudy.value.study_uid, series_uid: selectedSeries.value.series_uid } })
}
function openDicomReport() {
  if (!canViewDicom.value) return
  router.push({ path: '/report', query: { case_id: props.caseId, source: 'dicom', study_uid: selectedStudy.value.study_uid, series_uid: selectedSeries.value.series_uid } })
}
const studyNext = ref(null), seriesNext = ref(null), instanceNext = ref(null)
let generation = 0, controller = null
const message = e => e.response?.data?.detail?.message || e.response?.data?.message || e.message
async function run(action) {
  if (busy.value) return
  const version = generation; busy.value = true; error.value = ''
  controller = new AbortController()
  try { await action(controller.signal, version); return true }
  catch (e) { if (generation === version && !controller?.signal.aborted) error.value = message(e); return false }
  finally { if (generation === version) { busy.value = false; controller = null } }
}
async function refresh() {
  geometryManifest.value = null
  conversionStatus.value = {}; conversionVersions.value = []; conversionJobs.value = []; conversionJobsError.value = ''
  roleReviewVisible.value = false; roleReviewData.value = null; roleReviewVersion.value = ''; roleReviewError.value = ''; roleReviewResult.value = ''; roleReviewAcknowledge.value = false; activationAcknowledge.value = false; activationDone.value = false
  const started = generation
  const success = await run(async (signal, version) => {
    const [health, saved, converted, jobs] = await Promise.all([
      request.get('/pacs/status', { signal }), request.get(`/pacs/cases/${props.caseId}/links`, { signal }),
      request.get(`/pacs/cases/${props.caseId}/conversions`, { signal }),
      request.get(`/pacs/cases/${props.caseId}/conversion-jobs`, { signal }),
    ])
    if (version !== generation) return
    status.value = health.data.data; links.value = saved.data.data.items
    importError.value = ''; importCandidates.value = []; importSelection.value = ''; importState.value = null; importAcknowledge.value = false
    if (status.value.read_available) {
      try {
        const available = await request.get('/pacs/import-candidates', { signal })
        if (version !== generation) return
        importCandidates.value = available.data.data.items
        importSelection.value = importCandidates.value[0]?.candidate_id || ''
        selectImport()
      } catch (e) { if (version === generation && !signal.aborted) importError.value = message(e) }
    }
    conversionStatus.value = converted.data.data; conversionVersions.value = converted.data.data.items
    conversionJobs.value = jobs.data.data.items; conversionJobsError.value = ''
    await refreshJobDoctorSession()
    studies.value = []; selectedStudy.value = null; series.value = []; selectedSeries.value = null
    instances.value = []; studyNext.value = seriesNext.value = instanceNext.value = null; acknowledge.value = false
    geometryManifest.value = null
  })
  if (success === false && started === generation) {
    status.value = { read_available: false, message: '归档状态查询失败，请检查本地服务连接。' }
    conversionStatus.value = { message: '转换版本读取失败，请刷新重试。' }; conversionVersions.value = []
    conversionJobs.value = []; conversionJobsError.value = '转换作业读取失败，请刷新重试。'
    studies.value = []; selectedStudy.value = null; series.value = []; selectedSeries.value = null
    instances.value = []; studyNext.value = seriesNext.value = instanceNext.value = null
  }
}
let jobRefreshSequence = 0
const jobContext = () => ({ version: generation, caseId: props.caseId })
const currentJobContext = context => context.version === generation && context.caseId === props.caseId
async function refreshJobDoctorSession(context = jobContext()) {
  try {
    const response = await request.get('/local-auth/session')
    if (!currentJobContext(context)) return
    jobRetryDoctor.value = response.data.data.user || null
    jobRetryCsrf.value = response.data.data.csrf || ''
  } catch {
    if (currentJobContext(context)) { jobRetryDoctor.value = null; jobRetryCsrf.value = '' }
  }
}
async function refreshConversionJobs() {
  const context = jobContext(), sequence = ++jobRefreshSequence
  try {
    const response = await request.get(`/pacs/cases/${context.caseId}/conversion-jobs`)
    if (!currentJobContext(context) || sequence !== jobRefreshSequence) return
    conversionJobs.value = response.data.data.items
  } catch (e) {
    if (currentJobContext(context) && sequence === jobRefreshSequence) conversionJobsError.value = message(e) || '转换作业读取失败，请刷新重试。'
  }
}
async function performConversionAction(job, action, context) {
  if (!currentJobContext(context) || job.case_id !== context.caseId) return
  jobRetryingId.value = job.job_id; conversionJobsError.value = ''
  try {
    const response = await request.post(`/pacs/cases/${context.caseId}/conversion-jobs/${encodeURIComponent(job.job_id)}/${action}`,
      { expected_attempt: job.attempt }, { headers: { 'X-BF-CSRF': jobRetryCsrf.value } })
    if (!currentJobContext(context)) return
    const data = response.data.data
    if (data.job_id !== job.job_id || data.case_id !== context.caseId || data.state !== 'queued'
      || data.attempt !== job.attempt + (action === 'retry' ? 1 : 0)
      || data.reviewer_authenticated !== true || data.professional_credential_verified !== false
      || data.model_input_eligible !== false || data.current_mri_replaced !== false || data.inference_performed !== false) {
      throw Error('转换回执与当前病例、作业或未激活约束不符。')
    }
    await refreshConversionJobs()
  } catch (e) {
    if (!currentJobContext(context)) return
    const detail = message(e) || '转换操作失败；请刷新后核对作业状态。'
    await refreshConversionJobs()
    if (currentJobContext(context)) conversionJobsError.value = detail
  } finally { if (currentJobContext(context)) jobRetryingId.value = '' }
}
async function requestConversionAction(job, action) {
  if (busy.value || jobRetryingId.value || job.case_id !== props.caseId) return
  const context = jobContext()
  jobRetryingId.value = job.job_id
  await refreshJobDoctorSession(context)
  if (!currentJobContext(context)) return
  jobRetryingId.value = ''
  if (jobRetryDoctor.value?.role !== 'doctor' || !jobRetryCsrf.value) {
    jobRetryPending.value = { job: { ...job }, action, context }; jobRetryLoginError.value = ''
    jobRetryLoginVisible.value = true
    return
  }
  await performConversionAction(job, action, context)
}
async function retryConversionJob(job) { await requestConversionAction(job, 'retry') }
async function loginForConversionRetry() {
  const pending = jobRetryPending.value
  if (jobRetryLoginBusy.value || !pending || !currentJobContext(pending.context)) return
  jobRetryLoginBusy.value = true; jobRetryLoginError.value = ''
  try {
    await request.post('/local-auth/login', { username: jobRetryUsername.value, password: jobRetryPassword.value })
    if (!currentJobContext(pending.context)) return
    await refreshJobDoctorSession(pending.context)
    if (!currentJobContext(pending.context)) return
    jobRetryPassword.value = ''
    if (jobRetryDoctor.value?.role !== 'doctor' || !jobRetryCsrf.value) {
      jobRetryLoginError.value = '当前账户无医生转换操作权限。'
      return
    }
    jobRetryLoginVisible.value = false; jobRetryPending.value = null
    await performConversionAction(pending.job, pending.action, pending.context)
  } catch (e) {
    if (currentJobContext(pending.context)) jobRetryLoginError.value = message(e) || '本地登录失败。'
  } finally {
    if (currentJobContext(pending.context)) { jobRetryLoginBusy.value = false; jobRetryPassword.value = '' }
  }
}
const emptyPlanAssignments = () => [
  { role: 't1c', label: 'T1增强', series_uid: '' }, { role: 't1n', label: 'T1未增强', series_uid: '' },
  { role: 't2w', label: 'T2', series_uid: '' }, { role: 't2f', label: 'FLAIR', series_uid: '' },
]
const planVisible = ref(false), planBusy = ref(false), planError = ref(''), planStudy = ref('')
const planAssignments = ref(emptyPlanAssignments()), planSeries = ref([]), planPreview = ref(null), planAcknowledge = ref(false)
const planBasis = ref('local_manual_review'), planEvidence = ref(''), planUsername = ref(''), planPassword = ref('')
const planResampleToT1c1mm = ref(false)
let planFormVersion = 0
const canPreviewPlan = computed(() => Boolean(jobRetryDoctor.value?.role === 'doctor' && planStudy.value
  && planSeries.value.length >= 4 && planAssignments.value.every(item => item.series_uid)
  && new Set(planAssignments.value.map(item => item.series_uid)).size === 4 && planEvidence.value.trim().length >= 8))
function invalidatePlanPreview() { planFormVersion++; planPreview.value = null; planAcknowledge.value = false }
function closeConversionPlan() { invalidatePlanPreview(); planBusy.value = false; planPassword.value = '' }
const currentPlanContext = (context, version) => currentJobContext(context) && version === planFormVersion && planVisible.value
async function openConversionPlan() {
  invalidatePlanPreview(); planError.value = ''; planEvidence.value = ''; planSeries.value = []; planAssignments.value = emptyPlanAssignments()
  planResampleToT1c1mm.value = false
  planStudy.value = links.value.find(item => item.archive_matches_config)?.study_uid || ''
  planVisible.value = true
  const context = jobContext()
  await refreshJobDoctorSession(context)
  if (currentJobContext(context) && planVisible.value && planStudy.value) await loadPlanSeries()
}
async function loadPlanSeries() {
  invalidatePlanPreview(); planAssignments.value = emptyPlanAssignments(); planSeries.value = []; planError.value = ''
  const context = jobContext(), version = planFormVersion, study = planStudy.value
  if (!study) return
  planBusy.value = true
  try {
    const response = await request.get(`/pacs/studies/${encodeURIComponent(study)}/series`)
    if (currentPlanContext(context, version) && planStudy.value === study) planSeries.value = response.data.data.items
  } catch (e) { if (currentPlanContext(context, version)) planError.value = message(e) }
  finally { if (currentPlanContext(context, version)) planBusy.value = false }
}
async function loginPlanDoctor() {
  const context = jobContext(), version = planFormVersion
  planBusy.value = true; planError.value = ''
  try {
    await request.post('/local-auth/login', { username: planUsername.value, password: planPassword.value })
    if (!currentPlanContext(context, version)) return
    await refreshJobDoctorSession(context)
    if (currentPlanContext(context, version) && jobRetryDoctor.value?.role !== 'doctor') planError.value = '当前账户不能创建医生确认的转换方案。'
  } catch (e) { if (currentPlanContext(context, version)) planError.value = message(e) }
  finally { if (currentPlanContext(context, version)) { planBusy.value = false; planPassword.value = '' } }
}
async function previewConversionPlan() {
  if (!canPreviewPlan.value || planBusy.value) return
  const context = jobContext(), version = planFormVersion
  planBusy.value = true; planError.value = ''; planPreview.value = null; planAcknowledge.value = false
  try {
    const response = await request.post(`/pacs/cases/${context.caseId}/conversion-plans/preview`, {
      study_uid: planStudy.value, assignments: planAssignments.value.map(({ role, series_uid }) => ({ role, series_uid })),
      evidence_basis: planBasis.value, evidence_text: planEvidence.value.trim(),
      resample_to_t1c_1mm: planResampleToT1c1mm.value,
    }, { headers: { 'X-BF-CSRF': jobRetryCsrf.value }, timeout: 150000 })
    if (!currentPlanContext(context, version)) return
    const data = response.data.data
    if (data.metadata_geometry_contract_passed !== true || data.source_bytes_captured !== false
      || data.resampling_applied !== planResampleToT1c1mm.value
      || data.model_input_eligible !== false || data.current_mri_replaced !== false || data.inference_performed !== false) throw Error('方案检查回执无效，请重新检查。')
    planPreview.value = data
  } catch (e) { if (currentPlanContext(context, version)) planError.value = message(e) }
  finally { if (currentPlanContext(context, version)) planBusy.value = false }
}
async function createConversionPlanJob() {
  if (planBusy.value || !planPreview.value || !planAcknowledge.value) return
  const context = jobContext(), version = planFormVersion, preview = planPreview.value
  planBusy.value = true; planError.value = ''
  try {
    const response = await request.post(`/pacs/cases/${context.caseId}/conversion-plans/jobs`, {
      draft_id: preview.draft_id, plan_revision: preview.plan_revision, acknowledge_roles: true,
    }, { headers: { 'X-BF-CSRF': jobRetryCsrf.value }, timeout: 150000 })
    if (!currentPlanContext(context, version)) return
    const data = response.data.data
    if (data.case_id !== context.caseId || !data.job_id || data.model_input_eligible !== false
      || data.current_mri_replaced !== false || data.inference_performed !== false) throw Error('转换任务创建回执无效，请刷新任务列表。')
    planVisible.value = false; closeConversionPlan()
    await refreshConversionJobs()
  } catch (e) { if (currentPlanContext(context, version)) planError.value = message(e) }
  finally { if (currentPlanContext(context, version)) planBusy.value = false }
}

const conversionJobPoll = setInterval(() => {
  if (!busy.value && !jobRetryingId.value && conversionJobs.value.some(job => ['queued', 'running'].includes(job.state))) refreshConversionJobs()
}, 1500)

function selectImport() {
  importAcknowledge.value = false
  importState.value = selectedImport.value?.latest_import || null
}
async function submitImport() {
  const candidate = importSelection.value
  if (!candidate || !importAcknowledge.value) return
  importSubmitting.value = true
  try {
    const success = await run(async (signal, version) => {
      const result = await request.post(`/pacs/imports/${candidate}`, { acknowledge_reviewed_local_viewing_only: true }, { signal, timeout: 180000 })
      if (version !== generation || importSelection.value !== candidate) return
      importState.value = result.data.data
      const item = selectedImport.value
      if (item) item.latest_import = importState.value
      importAcknowledge.value = false
    })
    if (success && importState.value?.state === 'succeeded') {
      studyFilter.value = importState.value.study_uid
      await queryStudies(0)
    }
  } finally { importSubmitting.value = false }
}
const importPoll = setInterval(async () => {
  if (busy.value || !['queued', 'running'].includes(importState.value?.state)) return
  const candidate = importSelection.value
  await run(async (signal, version) => {
    const response = await request.get(`/pacs/imports/${candidate}`, { signal })
    if (version === generation && candidate === importSelection.value) importState.value = response.data.data
  })
}, 1000)
async function inspectConversion(versionRow) {
  versionRow.inspection = null
  await run(async (signal, version) => {
    const result = await request.get(`/pacs/cases/${props.caseId}/conversions/${encodeURIComponent(versionRow.version_id)}/inspection`, { signal })
    if (version !== generation) return
    if (result.data.data.version_id !== versionRow.version_id || result.data.data.model_input_eligible !== false) {
      throw Error('转换版本核对返回的身份或提交状态不一致。')
    }
    versionRow.inspection = result.data.data
  })
}
async function checkConversionSource(versionRow) {
  versionRow.sourceCheck = null
  await run(async (signal, version) => {
    const result = await request.get(`/pacs/cases/${props.caseId}/conversions/${encodeURIComponent(versionRow.version_id)}/source-check`, { signal, timeout: 180000 })
    if (version !== generation) return
    const data = result.data.data
    if (data.version_id !== versionRow.version_id || data.model_input_eligible !== false
      || (data.status === 'matched_at_check' && data.live_archive_reconciled !== true)) {
      throw Error('归档来源核对返回的版本或观察状态不一致。')
    }
    versionRow.sourceCheck = data
  })
}
async function openRoleReview(versionRow) {
  roleReviewVisible.value = true
  roleReviewVersion.value = versionRow.version_id
  roleReviewData.value = null; roleReviewError.value = ''; roleReviewResult.value = ''
  roleReviewAcknowledge.value = false; activationAcknowledge.value = false; activationDone.value = false; roleReviewLoading.value = true
  try {
    const [auth, review] = await Promise.all([
      request.get('/local-auth/session'),
      request.get(`/pacs/cases/${props.caseId}/conversions/${encodeURIComponent(versionRow.version_id)}/role-review`)
    ])
    if (String(props.caseId) !== String(Number(props.caseId)) || roleReviewVersion.value !== versionRow.version_id) return
    roleReviewConfigured.value = Boolean(auth.data.data.configured)
    roleReviewUser.value = auth.data.data.user || null
    roleReviewCsrf.value = auth.data.data.csrf || ''
    const data = review.data.data
    const expected = ['t1c', 't1n', 't2w', 't2f']
    if (data.assignments?.map(row => row.role).join(',') !== expected.join(',')
        || data.model_input_eligible !== false || data.current_mri_replaced !== false) {
      throw Error('角色审核数据与四序列/未激活约束不符。')
    }
    roleReviewData.value = data
  } catch (e) { roleReviewError.value = message(e) }
  finally { roleReviewLoading.value = false }
}
async function refreshRoleReviewer() {
  const state = (await request.get('/local-auth/session')).data.data
  roleReviewConfigured.value = Boolean(state.configured)
  roleReviewUser.value = state.user || null
  roleReviewCsrf.value = state.csrf || ''
}
async function loginRoleReviewer() {
  if (roleReviewBusy.value || !roleReviewUsername.value || !roleReviewPassword.value) return
  roleReviewBusy.value = true; roleReviewError.value = ''
  try {
    await request.post('/local-auth/login', { username: roleReviewUsername.value, password: roleReviewPassword.value })
    await refreshRoleReviewer()
    roleReviewPassword.value = ''
    if (roleReviewUser.value?.role !== 'doctor') roleReviewError.value = '当前账户为研究员角色，不能提交角色审核决定。'
  } catch (e) { roleReviewError.value = message(e) }
  finally { roleReviewBusy.value = false }
}
async function logoutRoleReviewer() {
  if (roleReviewBusy.value || !roleReviewCsrf.value) return
  roleReviewBusy.value = true
  try {
    await request.post('/local-auth/logout', {}, { headers: { 'X-BF-CSRF': roleReviewCsrf.value } })
    roleReviewUser.value = null; roleReviewCsrf.value = ''; roleReviewAcknowledge.value = false
  } catch (e) { roleReviewError.value = message(e) }
  finally { roleReviewBusy.value = false }
}
async function submitRoleReview(decision) {
  if (!roleReviewData.value || !roleReviewUser.value || roleReviewUser.value.role !== 'doctor'
      || !roleReviewCsrf.value || !roleReviewAcknowledge.value || roleReviewBusy.value) return
  roleReviewBusy.value = true; roleReviewDecision.value = decision; roleReviewError.value = ''; roleReviewResult.value = ''
  const version = roleReviewVersion.value
  try {
    const response = await request.post(`/pacs/cases/${props.caseId}/conversions/${encodeURIComponent(version)}/role-review`, {
      decision, plan_revision: roleReviewData.value.plan_revision,
      assignment_set_sha256: roleReviewData.value.assignment_set_sha256, confirm_roles: true
    }, { headers: { 'X-BF-CSRF': roleReviewCsrf.value }, timeout: 180000 })
    const data = response.data.data
    if (version !== roleReviewVersion.value || data.review_status !== (decision === 'approve' ? 'approved' : 'rejected')
        || data.model_input_eligible !== false || data.current_mri_replaced !== false
        || data.reviewer_authenticated !== true || data.professional_credential_verified !== false) {
      throw Error('审核回执版本、身份或未激活状态不符合预期。')
    }
    roleReviewData.value.history = [...(roleReviewData.value.history || []), data]
    roleReviewResult.value = decision === 'approve' ? '角色映射已记录；当前MRI与AI输入保持不变。' : '驳回决定已记录；当前MRI与AI输入保持不变。'
    roleReviewAcknowledge.value = false
  } catch (e) { roleReviewError.value = message(e) }
  finally { roleReviewBusy.value = false; roleReviewDecision.value = '' }
}


async function activateModelInput() {
  if (!activationApproved.value || !activationAcknowledge.value || activationDone.value || roleReviewBusy.value) return
  roleReviewBusy.value = true; roleReviewDecision.value = 'activate'; roleReviewError.value = ''; roleReviewResult.value = ''
  const version = roleReviewVersion.value
  try {
    const response = await request.post(`/pacs/cases/${props.caseId}/conversions/${encodeURIComponent(version)}/activate-model-input`, {
      plan_revision: roleReviewData.value.plan_revision,
      assignment_set_sha256: roleReviewData.value.assignment_set_sha256,
      confirm_activation: true
    }, { headers: { 'X-BF-CSRF': roleReviewCsrf.value }, timeout: 180000 })
    const data = response.data.data
    if (version !== roleReviewVersion.value || !Number.isInteger(data.mri_id) || data.mri_id < 1
        || data.conversion_version_id !== version || data.model_input_eligible !== true
        || data.current_mri_replaced !== true || data.inference_performed !== false
        || data.original_dicom_modified !== false || data.previous_mri_and_analysis_history_preserved !== true) {
      throw Error('激活回执版本或输入切换状态不符合预期。')
    }
    activationDone.value = true
    roleReviewResult.value = '已切换当前四序列MRI输入；未运行分割或预测，旧结果保留为历史。'
    emit('input-activated', data)
  } catch (e) { roleReviewError.value = message(e) }
  finally { roleReviewBusy.value = false; roleReviewDecision.value = '' }
}

async function queryStudies(offset) {
  await run(async (signal, version) => {
    const result = await request.get('/pacs/studies', { params: { study_uid: studyFilter.value.trim() || undefined, limit: 20, offset }, signal })
    if (version !== generation) return
    selectedStudy.value = null; selectedSeries.value = null; series.value = []; instances.value = []
    geometryManifest.value = null
    acknowledge.value = false; seriesNext.value = instanceNext.value = null
    studies.value = result.data.data.items; studyNext.value = result.data.data.next_offset
    if (!studies.value.length) error.value = '没有匹配的归档检查。'
  })
}
async function selectStudy(row) {
  if (!row || busy.value) return
  selectedStudy.value = row; selectedSeries.value = null; series.value = []; instances.value = []
  geometryManifest.value = null
  acknowledge.value = false; seriesNext.value = instanceNext.value = null
  await querySeries(0)
}
async function querySeries(offset) {
  await run(async (signal, version) => {
    const uid = selectedStudy.value.study_uid
    const result = await request.get(`/pacs/studies/${encodeURIComponent(uid)}/series`, { params: { limit: 20, offset }, signal })
    if (version !== generation) return
    series.value = result.data.data.items; seriesNext.value = result.data.data.next_offset
    selectedSeries.value = null; instances.value = []; instanceNext.value = null
    geometryManifest.value = null
  })
}
async function selectSeries(row) {
  if (!row || busy.value) return
  selectedSeries.value = row; instances.value = []; instanceNext.value = null
  geometryManifest.value = null
  await queryInstances(0)
}
async function queryInstances(offset) {
  await run(async (signal, version) => {
    const study = encodeURIComponent(selectedStudy.value.study_uid), seriesUid = encodeURIComponent(selectedSeries.value.series_uid)
    const result = await request.get(`/pacs/studies/${study}/series/${seriesUid}/instances`, { params: { limit: 20, offset }, signal })
    if (version !== generation) return
    instances.value = result.data.data.items; instanceNext.value = result.data.data.next_offset
  })
}
async function linkStudy() {
  await run(async (signal, version) => {
    const result = await request.post(`/pacs/cases/${props.caseId}/links`, { study_uid: selectedStudy.value.study_uid, acknowledge_case_match: acknowledge.value }, { signal })
    if (version !== generation) return
    const item = result.data.data
    if (!links.value.some(row => row.id === item.id)) links.value.push(item)
    acknowledge.value = false
  })
}
async function checkGeometry() {
  geometryManifest.value = null
  await run(async (signal, version) => {
    const study = selectedStudy.value.study_uid, seriesUid = selectedSeries.value.series_uid
    const result = await request.get('/pacs/studies/' + encodeURIComponent(study) + '/series/' + encodeURIComponent(seriesUid) + '/view-manifest', { signal })
    if (version !== generation || selectedStudy.value?.study_uid !== study || selectedSeries.value?.series_uid !== seriesUid) return
    const manifest = result.data.data
    if (manifest.format !== 'dicom-series-view-manifest-v1' || manifest.study_uid !== study || manifest.series_uid !== seriesUid) {
      throw Error('空间核对返回的序列身份不一致。')
    }
    geometryManifest.value = manifest
  })
}
watch(() => props.caseId, () => {
  generation++; controller?.abort(); busy.value = false
  planVisible.value = false; closeConversionPlan(); planError.value = ''; planSeries.value = []
  jobRefreshSequence++; jobRetryingId.value = ''; jobRetryPending.value = null; jobRetryLoginVisible.value = false
  jobRetryLoginBusy.value = false; jobRetryPassword.value = ''; jobRetryLoginError.value = ''
  studies.value = []; series.value = []; instances.value = []; links.value = []
  selectedStudy.value = selectedSeries.value = null; status.value = {}; error.value = ''
  conversionStatus.value = {}; conversionVersions.value = []
  roleReviewVisible.value = false; roleReviewData.value = null; roleReviewVersion.value = ''; roleReviewError.value = ''; roleReviewResult.value = ''; roleReviewAcknowledge.value = false; activationAcknowledge.value = false; activationDone.value = false
  importCandidates.value = []; importSelection.value = ''; importState.value = null; importError.value = ''; importAcknowledge.value = false
  geometryManifest.value = null
  refresh()
}, { immediate: true })
onBeforeUnmount(() => { generation++; controller?.abort(); clearInterval(importPoll); clearInterval(conversionJobPoll) })
</script>

<style scoped>
.pacs-panel { margin-top: 20px; }
.pacs-import { margin: 16px 0; padding: 12px; background: #f8fafc; }
.conversion-jobs { margin-top: 12px; padding: 12px; background: #f8fafc; }
.conversion-jobs-header { display: flex; justify-content: space-between; align-items: center; }
.conversion-jobs li { margin: 8px 0; }
.pacs-import .el-select { display: block; width: min(100%, 560px); margin: 10px 0; }
.pacs-import-status { margin-top: 10px; }
.pacs-panel.is-busy :deep(.el-table) { pointer-events: none; }
.pacs-header, .pacs-query { display: flex; align-items: center; gap: 12px; }
.pacs-header { justify-content: space-between; }
.pacs-query { margin: 14px 0; }
.pacs-note { color: #64748b; font-size: 13px; }
.pacs-selection { margin-top: 14px; }
.pacs-links { padding-left: 18px; overflow-wrap: anywhere; }
.pacs-geometry { margin: 12px 0; padding: 12px; background: #f8fafc; }
code { overflow-wrap: anywhere; }
</style>

