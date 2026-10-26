<template>
  <div class="research-page">
    <h1>IDH 与融合研究</h1>
    <p>研究终点：IDH1/2 原始值 = 1；0/1 的生物学编码尚待核实。研究概率不用于通用风险、肿瘤检测或治疗建议。</p>
    <el-alert title="研究原型：分类模型在参考掩膜特征上拟合；自动掩膜输入仅作工程迁移验证，尚无独立临床评价。" type="warning" :closable="false" />
    <el-card class="panel survival-panel">
      <template #header>生存分析软件状态</template>
      <el-tag type="warning">{{ survivalStatus?.research_status || '读取状态中' }}</el-tag>
      <p>{{ survivalStatus?.reason || '正在读取生存数据条件。' }}</p>
      <p>KM 与 Cox 工程接口仅接收 SYNTHETIC_TEST 数据。研究模型若在隔离环境显式启用，则只用于研究者定义的 UPENN 候选终点；不能用于真实患者或临床决策。</p>
      <el-table v-if="survivalStatus" :data="survivalRows" border>
        <el-table-column prop="name" label="分析能力" />
        <el-table-column prop="status" label="软件状态" />
      </el-table>
      <el-alert title="官方 OS 字段定义仍未验证。生存模型是研究用途原型，不是临床验证模型；预测接口只接受显式合成测试请求，禁止输入真实患者资料。" type="warning" :closable="false" />
      <el-divider />
      <h3>研究 Cox 模型状态</h3>
      <el-tag :type="survivalModelStatus?.available ? 'warning' : 'info'">{{ survivalModelStatus?.status || '读取状态中' }}</el-tag>
      <p>{{ survivalModelStatus?.available ? '已从隔离运行时读取研究模型；模型版本和验证状态见所选模型。' : survivalModelStatus?.reason || '正在读取模型注册状态。' }}</p>
      <el-alert v-if="survivalModelError" :title="survivalModelError" type="error" :closable="false" />
      <el-alert v-if="survivalFusionUnavailableReason" :title="`融合模型不可用：${survivalFusionUnavailableReason}。需要 ${survivalRadiomicsFeatureNames.join('、')}；BrainFusion 20 项特征不兼容。`" type="info" :closable="false" />
      <template v-if="survivalModelStatus?.available && survivalModels.length">
        <label>研究模型
          <el-select v-model="survivalModelChoice" class="survival-model-select" aria-label="研究模型选择" style="width: 360px">
            <el-option value="upenn-clinical-cox-research" label="临床 Cox 基线" :disabled="!survivalModelAvailable('upenn-clinical-cox-research')" />
            <el-option value="upenn-clinical-captk-fusion-cox-research" label="临床 + CaPTk 四特征 Cox" :disabled="!survivalModelAvailable('upenn-clinical-captk-fusion-cox-research')" />
          </el-select>
        </label>
        <p v-if="survivalChosenModel">版本 {{ survivalChosenModel.model_version }} · {{ survivalChosenModel.endpoint_status }} · 五折内部 C-index {{ Number(survivalCvMean(survivalChosenModel)).toFixed(4) }}</p>
        <p>验证：仅患者级内部五折交叉验证。C-index 是排序指标，不是分类准确率；没有独立外部或临床验证。</p>
        <el-tag type="warning">研究模型演示仅限 SYNTHETIC_TEST</el-tag>
        <div class="survival-predict-inputs">
          <label>合成年龄（年）<el-input-number v-model="survivalAge" :min="18" :max="120" /></label>
          <el-select v-model="survivalGender" aria-label="合成性别" style="width: 130px">
            <el-option value="F" label="F（合成）" /><el-option value="M" label="M（合成）" />
          </el-select>
          <el-select v-model="survivalIdh" aria-label="合成 IDH1 状态" style="width: 190px">
            <el-option value="Wildtype" label="Wildtype（合成）" /><el-option value="Mutated" label="Mutated（合成）" />
            <el-option value="NOS/NEC" label="NOS/NEC（合成）" />
          </el-select>
          <el-select v-model="survivalGtr" aria-label="合成切除程度" style="width: 190px">
            <el-option value="N" label="≤90%（合成）" /><el-option value="Y" label=">90%（合成）" />
            <el-option value="UNKNOWN" label="UNKNOWN（合成）" />
          </el-select>
          <template v-if="survivalModelChoice === 'upenn-clinical-captk-fusion-cox-research'">
            <p>融合模型只接收以下官方 CaPTk 自动分割强度均值；不会读取或映射 BrainFusion 的 20 项特征。</p>
            <label>T1GD ET Mean（合成）<el-input-number v-model="survivalRadiomics.T1GD_ET_Intensity_Mean" /></label>
            <label>FLAIR ED Mean（合成）<el-input-number v-model="survivalRadiomics.FLAIR_ED_Intensity_Mean" /></label>
            <label>T2 ED Mean（合成）<el-input-number v-model="survivalRadiomics.T2_ED_Intensity_Mean" /></label>
            <label>T1 NC Mean（合成）<el-input-number v-model="survivalRadiomics.T1_NC_Intensity_Mean" /></label>
          </template>
          <el-input v-model="survivalTimes" aria-label="合成生存时间点（天）" placeholder="天数，逗号分隔" style="width: 220px" />
          <el-button type="primary" :disabled="!survivalCanPredict" :loading="survivalPredictionLoading" @click="predictSyntheticSurvival">运行合成研究示例</el-button>
        </div>
        <el-alert v-if="evaluationUser?.role !== 'doctor'" title="需先登录本地 doctor 角色账户；账户角色不代表临床资质。" type="warning" :closable="false" />
        <el-alert v-if="survivalPredictionError" :title="survivalPredictionError" type="error" :closable="false" />
        <template v-if="survivalPrediction">
          <p>输入范围：SYNTHETIC_TEST · 模型 {{ survivalPrediction.model_id }} / {{ survivalPrediction.model_version }} · 时间单位：天</p>
          <p>相对风险指数：{{ Number(survivalPrediction.relative_risk).toPrecision(5) }}（相对模型基线的 Cox 风险指数，不是患者级风险结论）</p>
          <figure class="survival-curve-figure">
            <figcaption>合成请求返回的研究生存曲线</figcaption>
            <svg viewBox="0 0 480 190" role="img" aria-label="合成生存曲线">
              <line x1="42" y1="20" x2="42" y2="160" class="survival-axis" />
              <line x1="42" y1="160" x2="460" y2="160" class="survival-axis" />
              <text x="4" y="25">100%</text><text x="12" y="94">50%</text><text x="23" y="164">0%</text>
              <polyline :points="survivalChartPoints" class="survival-curve-line" />
              <circle v-for="(point, index) in survivalPrediction.survival_curve" :key="`${point.time}-${index}`"
                :cx="survivalChartCoordinate(point, index).x" :cy="survivalChartCoordinate(point, index).y" r="4" class="survival-curve-point">
                <title>{{ point.time }} 天：{{ (point.survival_probability * 100).toFixed(1) }}%</title>
              </circle>
              <text x="42" y="184">{{ survivalPrediction.survival_curve[0]?.time }} 天</text>
              <text x="365" y="184">{{ survivalPrediction.survival_curve.at(-1)?.time }} 天</text>
            </svg>
          </figure>
          <el-table :data="survivalPrediction.survival_curve" border>
            <el-table-column label="时间点">
              <template #default="scope">{{ Number(scope.row.time / 365).toFixed(0) }} 年（{{ scope.row.time }} 天）</template>
            </el-table-column>
            <el-table-column label="研究者定义终点下的模型生存概率">
              <template #default="scope">{{ (scope.row.survival_probability * 100).toFixed(1) }}%</template>
            </el-table-column>
          </el-table>
          <el-alert title="这是由研究者定义、未验证 OS 终点计算的合成输入演示，不代表真实患者预测；结果未保存。" type="warning" :closable="false" />
        </template>
      </template>
    </el-card>
    <el-alert v-if="error" :title="error" type="error" :closable="false" class="panel" />
    <template v-if="summary">
      <el-card class="panel">
        <p>实验版本：{{ summary.run_id }}</p>
        <p>患者 {{ summary.audit.cohort_patients }} 名；训练 {{ summary.split_sizes.train }} / 验证 {{ summary.split_sizes.validation }} / 探索性测试 {{ summary.split_sizes.test }}；CPU 运行。</p>
        <p>五个工程样本已从拟合、验证和测试中排除；标签未知和提取错误患者已隔离。</p>
        <el-table :data="modelRows" border><el-table-column prop="name" label="方法" /><el-table-column prop="auc" label="探索性测试 AUC" /><el-table-column prop="accuracy" label="平衡准确率" /><el-table-column prop="brier" label="Brier" /></el-table>
        <p>TOPSIS 临床/影像组学权重：{{ summary.fusion.validation_topsis.weights.join(' / ') }}。权重只依据验证集；当前结果没有证明 TOPSIS 优于平均融合。</p>
      </el-card>
      <el-card class="panel">
        <template #header>五例开发样本：加载真实模型计算概率</template>
        <el-select v-model="selected" style="width: 200px" @change="loadPatient"><el-option v-for="id in ['4','13','16','17','19']" :key="id" :value="id" :label="`数据集患者 ${id}`" /></el-select>
        <el-button :loading="patientLoading" @click="loadPatient">计算研究结果</el-button>
        <template v-if="patient">
          <p>源患者 {{ patient.source_patient_id }}；年龄 {{ patient.clinical_input.age }}；female={{ patient.clinical_input.female }}；参考标签 {{ patient.reference_label ?? '缺失' }}</p>
          <p>目标：IDH1/2=1 的研究概率。</p>
          <el-table :data="probabilityRows" border><el-table-column prop="name" label="方法" /><el-table-column prop="value" label="概率" /></el-table>
          <p>{{ patient.disclaimer }}</p>
        </template>
      </el-card>
      <el-card class="panel">
        <template #header>临床基线输入</template>
        <label>年龄 <el-input-number v-model="age" :min="0" :max="120" /></label>
        <el-select v-model="female" style="width: 120px"><el-option :value="false" label="male" /><el-option :value="true" label="female" /></el-select>
        <el-button :loading="clinicalLoading" @click="predictClinical">计算临床概率</el-button>
        <p v-if="clinical">{{ (clinical.probability * 100).toFixed(1) }}% — {{ clinical.disclaimer }}</p>
      </el-card>
      <el-card class="panel">
        <template #header>当前病例：自动掩膜特征研究</template>
        <p>临床输入默认读取关联患者；可保存此病例独立的研究输入版本。特征在 CPU 上提取，绑定分割及临床输入版本。</p>
        <el-select v-model="featureCase" class="case-feature-select" style="width: 360px" placeholder="选择已分析病例" @change="changeFeatureCase">
          <el-option v-for="item in cases" :key="item.id" :value="item.id" :label="`病例 ${item.id} · ${item.patient_name}`" />
        </el-select>
        <div v-if="caseClinical" class="case-clinical-input">
          <p>患者编号 {{ caseClinical.patient_id }}；输入来源：{{ caseClinical.source === 'associated_patient' ? '关联患者资料' : '此病例研究输入（患者资料未修改）' }}；版本 {{ caseClinical.version }}</p>
          <label>病例研究年龄 <el-input-number v-model="caseAge" class="case-age" :min="0" :max="120" :disabled="featureBusy" /></label>
          <el-select v-model="caseFemale" class="case-sex" style="width: 160px" placeholder="性别未知，需确认" :disabled="featureBusy"><el-option :value="false" label="男（male）" /><el-option :value="true" label="女（female）" /></el-select>
          <el-button :disabled="!featureInputDirty || caseAge == null || caseFemale == null || featureBusy" :loading="clinicalSaving" @click="saveCaseClinical">保存病例研究输入</el-button>
          <el-alert v-if="!caseClinical.available" :title="caseClinical.reason" type="warning" :closable="false" />
          <el-alert v-if="featureInputDirty" title="研究输入已修改但尚未保存；旧概率暂不显示。保存后需按新版本重新计算。" type="warning" :closable="false" />
        </div>
        <el-button :disabled="!featureCase || featureBusy || clinicalSaving || !caseClinical?.available || featureInputDirty" :loading="featureSubmitting" @click="startFeatures">提取自动掩膜特征</el-button>
        <el-button :disabled="!featureCase" @click="refreshFeature">刷新任务</el-button>
        <el-alert v-if="featureError" :title="featureError" type="error" :closable="false" />
        <template v-if="featureJob">
          <p class="feature-state" :data-job-id="featureJob.id">特征任务：{{ featureJob.stale ? '结果已失效' : featureJob.state }}；分割版本 {{ featureJob.analysis_run_id }}；研究版本 {{ featureJob.research_run_id }}</p>
          <p>本次临床输入：年龄 {{ featureJob.clinical_input.age }}；female={{ featureJob.clinical_input.female }}；{{ featureJob.cache_hit ? '读取已存结果' : 'CPU 提取' }}</p>
          <el-alert v-if="featureJob.error" :title="featureJob.error" type="error" :closable="false" />
          <el-alert v-if="featureJob.stale" :title="`旧研究结果已失效，请重新提取。历史结果仍保留。原因：${featureJob.stale_reason}`" type="warning" :closable="false" />
          <template v-if="featureJob.result && !featureJob.stale && !featureInputDirty">
            <el-table :data="automaticRows" class="automatic-result" border><el-table-column prop="name" label="方法" /><el-table-column prop="value" label="自动掩膜输入研究概率" /></el-table>
            <p>{{ featureJob.result.disclaimer }}</p>
            <p>选中特征 {{ Object.keys(featureJob.result.selected_features).length }} 个；提取 {{ featureJob.result.extraction_seconds }} 秒；不写入病例诊断报告。</p>
            <el-button :loading="featureExporting" @click="exportFeatures">导出当前特征 CSV</el-button>
            <el-table :data="radiomicsRows" class="radiomics-result" border>
              <el-table-column prop="maskLabel" label="掩膜标签值" width="120" />
              <el-table-column prop="feature" label="PyRadiomics 特征" min-width="280" />
              <el-table-column prop="value" label="特征值" min-width="160" />
              <el-table-column prop="voxelCount" label="区域体素数" width="130" />
              <el-table-column prop="reason" label="不可计算原因" min-width="160" />
            </el-table>
            <p>特征记录 {{ featureJob.result.feature_record_id || '历史文件任务' }}；协议 {{ featureJob.result.protocol?.id || '版本化契约' }}；binWidth {{ featureJob.result.protocol?.radiomics_settings?.binWidth ?? '—' }}；契约摘要 {{ featureJob.result.contract_sha256?.slice(0, 12) || '—' }}</p>
          </template>
        </template>
      </el-card>
      <el-card class="panel segmentation-evaluation-panel">
        <template #header>分割模型评价（需要独立参考标注）</template>
        <p>仅比较当前分析任务的模型掩膜与已授权参考标签。当前本地账户用于操作归属，不验证专业资质或外部数据授权。没有参考标签时状态为 NOT_AVAILABLE。</p>
        <div class="evaluation-auth">
          <p v-if="evaluationUser">本地身份：{{ evaluationUser.display_name }}（{{ evaluationUser.role }}）<el-button :disabled="evaluationAuthBusy" @click="logoutEvaluation">退出</el-button></p>
          <template v-else>
            <p v-if="!evaluationAuthConfigured">本机未配置本地复核账户；需由本机维护者按既有账户流程配置。</p>
            <el-input v-model="evaluationUsername" aria-label="评价本地账户" autocomplete="username" placeholder="本地账户" :disabled="evaluationAuthBusy || !evaluationAuthConfigured" />
            <el-input v-model="evaluationPassword" aria-label="评价账户密码" type="password" autocomplete="current-password" placeholder="本地账户密码" :disabled="evaluationAuthBusy || !evaluationAuthConfigured" @keyup.enter="loginEvaluation" />
            <el-button :loading="evaluationAuthBusy" :disabled="!evaluationAuthConfigured || !evaluationUsername || !evaluationPassword" @click="loginEvaluation">登录本地复核账户</el-button>
          </template>
          <el-alert v-if="evaluationAuthError" :title="evaluationAuthError" type="error" :closable="false" />
        </div>
        <template v-if="evaluationUser?.role === 'doctor'">
          <el-select v-model="evaluationRunId" aria-label="分割评价分析任务" placeholder="选择当前成功的分析任务" style="width: 520px" @change="refreshEvaluation">
            <el-option v-for="run in evaluationRuns" :key="run.id" :value="run.id" :label="`${run.id} · ${run.state} · ${run.result?.model || '模型版本未知'}`" />
          </el-select>
          <el-button :disabled="!evaluationRunId" :loading="evaluationLoading" @click="refreshEvaluation">刷新评价状态</el-button>
          <el-tag v-if="evaluation" :type="evaluation.status === 'PASS' ? 'success' : 'info'">{{ evaluation.status }}</el-tag>
          <el-alert v-if="evaluationError" :title="evaluationError" type="error" :closable="false" />
          <p v-if="evaluation">病例 {{ evaluation.case_id }} · MRI {{ evaluation.mri_id }} · 分析任务 {{ evaluation.analysis_run_id }} · 模型 {{ evaluation.model_version || '未知' }}</p>
          <p v-if="evaluation && !evaluation.reference_annotation_available">尚无该任务的参考标注和评价记录。不会显示或推测 Dice/HD95。</p>
          <template v-if="evaluation?.record">
            <el-tag type="warning">{{ evaluation.record.scope === 'synthetic_engineering' ? 'SYNTHETIC_TEST' : '参考标注评价（授权声明未核验）' }}</el-tag>
            <p>数据集版本 {{ evaluation.record.dataset_version }} · 标注引用摘要 {{ evaluation.record.annotation_ref?.slice(0, 12) }} · 协议 {{ evaluation.record.protocol }} · HD95 单位 mm</p>
            <el-table :data="evaluationRows" border>
              <el-table-column prop="region" label="区域" width="90" />
              <el-table-column prop="dice" label="Dice" />
              <el-table-column prop="hd95" label="HD95 (mm)" />
              <el-table-column prop="hd95Reason" label="HD95 状态/原因" min-width="190" />
              <el-table-column prop="precision" label="Precision" />
              <el-table-column prop="recall" label="Recall" />
              <el-table-column prop="tp" label="TP (voxels)" />
              <el-table-column prop="fp" label="FP (voxels)" />
              <el-table-column prop="fn" label="FN (voxels)" />
            </el-table>
            <p>预测掩膜 SHA-256 {{ evaluation.record.prediction_mask_sha256 }} · 参考掩膜 SHA-256 {{ evaluation.record.reference_mask_sha256 }}</p>
            <el-button :loading="evaluationExporting" @click="exportEvaluation">导出评价 CSV</el-button>
          </template>
          <template v-if="evaluationRunId">
            <el-divider />
            <p>提交参考标注前，确认数据集许可及标注来源；API 会将标注保存在隔离上传 runtime，并记录版本、标注编号、授权凭据摘要和输入/掩膜哈希。重复提交相同材料是幂等的。</p>
            <el-input v-model="evaluationDatasetVersion" aria-label="评价数据集版本" placeholder="数据集/版本（合成工程测试请以 SYNTHETIC- 开头）" maxlength="160" />
            <el-input v-model="evaluationAnnotationId" aria-label="参考标注编号" placeholder="标注引用（原文仅参与哈希，不会保存）" maxlength="160" />
            <el-input v-model="evaluationAuthorizationReceipt" aria-label="授权凭据引用" placeholder="授权记录引用（仅保存摘要，不保存原文）" maxlength="512" />
            <input aria-label="参考分割 NIfTI" type="file" accept=".nii,.nii.gz,application/octet-stream" @change="selectReferenceMask" />
            <el-checkbox v-model="evaluationAuthorized">我确认该参考标注可用于此隔离工程评价，并已核实其来源、范围和许可。</el-checkbox>
            <el-button type="primary" :disabled="!evaluationReferenceFile || !evaluationDatasetVersion.trim() || !evaluationAnnotationId.trim() || !evaluationAuthorizationReceipt.trim() || !evaluationAuthorized" :loading="evaluationSubmitting" @click="submitEvaluation">提交评价</el-button>
          </template>
        </template>
        <el-alert v-else-if="evaluationUser" title="分割评价写入需要本地 doctor 角色会话；本地角色不代表专业资质核验。" type="warning" :closable="false" />
      </el-card>
      <el-card class="panel">
        <template #header>同构模拟联邦</template>
        <p>{{ summary.federated.rounds }} 轮，每轮本地 {{ summary.federated.local_steps }} 步；3 客户端；同一逻辑模型。</p>
        <el-table :data="federatedRows" border><el-table-column prop="name" label="方法" /><el-table-column prop="auc" label="探索性测试 AUC" /><el-table-column prop="sizes" label="客户端人数" /><el-table-column prop="weights" label="末轮聚合权重" /></el-table>
        <p>预处理在训练患者上集中拟合，TOPSIS 使用公共验证池。本功能模拟参数聚合，不提供真实跨院隐私保证。</p>
      </el-card>
    </template>
  </div>
</template>
<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import request from '../api/axios'
import { useRoute } from 'vue-router'
const route = useRoute()
const summary = ref(null), patient = ref(null), clinical = ref(null), error = ref(''), selected = ref('13')
const survivalStatus = ref(null), survivalModelStatus = ref(null), survivalModels = ref([])
const survivalModelUnavailable = ref({})
const survivalAge = ref(63), survivalGender = ref('F'), survivalIdh = ref('Wildtype'), survivalGtr = ref('N')
const survivalModelChoice = ref('upenn-clinical-cox-research')
const survivalRadiomics = ref({ T1GD_ET_Intensity_Mean: 1, FLAIR_ED_Intensity_Mean: 2, T2_ED_Intensity_Mean: 3, T1_NC_Intensity_Mean: 4 })
const survivalTimes = ref('365,730,1095'), survivalPrediction = ref(null), survivalPredictionLoading = ref(false)
const survivalPredictionError = ref(''), survivalModelError = ref('')
const age = ref(50), female = ref(false), patientLoading = ref(false), clinicalLoading = ref(false)
const cases = ref([]), featureCase = ref(null), featureJob = ref(null), featureSubmitting = ref(false), featureExporting = ref(false)
const caseClinical = ref(null), caseAge = ref(null), caseFemale = ref(null), clinicalSaving = ref(false)
const featureError = ref(''), featureStatusKnown = ref(false)
const evaluationUser = ref(null), evaluationAuthConfigured = ref(false), evaluationUsername = ref(''), evaluationPassword = ref(''), evaluationCsrf = ref('')
const evaluationAuthBusy = ref(false), evaluationAuthError = ref(''), evaluationRuns = ref([]), evaluationRunId = ref('')
const evaluation = ref(null), evaluationError = ref(''), evaluationLoading = ref(false), evaluationSubmitting = ref(false), evaluationExporting = ref(false)
const evaluationDatasetVersion = ref(''), evaluationAnnotationId = ref(''), evaluationAuthorizationReceipt = ref('')
const evaluationReferenceFile = ref(null), evaluationAuthorized = ref(false)
const featureInputDirty = computed(() => Boolean(caseClinical.value && (caseAge.value !== caseClinical.value.age || caseFemale.value !== caseClinical.value.female)))
let featureTimer = null, mounted = true, featureGeneration = 0
const featureBusy = computed(() => !featureStatusKnown.value || featureSubmitting.value || ['queued', 'running'].includes(featureJob.value?.state))
const labels = { clinical: '临床年龄/性别', reference_mask_radiomics: '参考掩膜影像组学', automatic_mask_radiomics: '自动掩膜影像组学', average: '平均融合', 'fixed_clinical_0.6_radiomics_0.4': '固定 0.6/0.4', fixed: '固定 0.6/0.4', validation_topsis: '验证集 TOPSIS' }
const modelRows = computed(() => Object.entries({ ...summary.value?.branch_models, ...summary.value?.fusion }).map(([key, value]) => ({ name: labels[key] || key, auc: value.test.auc.toFixed(4), accuracy: value.test.balanced_accuracy.toFixed(4), brier: value.test.brier.toFixed(4) })))
const probabilityRows = computed(() => Object.entries(patient.value?.probabilities || {}).map(([key, value]) => ({ name: labels[key] || key, value: (value * 100).toFixed(1) + '%' })))
const automaticRows = computed(() => Object.entries(featureJob.value?.result?.probabilities || {}).map(([key, value]) => ({ name: labels[key] || key, value: (value * 100).toFixed(1) + '%' })))
const radiomicsRows = computed(() => Object.entries(featureJob.value?.result?.selected_features || {}).map(([key, value]) => {
  const [maskLabel, ...parts] = key.split(':')
  return { maskLabel, feature: parts.join(':'), value: value == null ? '不可计算' : Number(value).toPrecision(6),
    voxelCount: featureJob.value?.result?.region_voxel_counts?.[maskLabel] ?? '—',
    reason: value == null ? '空掩膜区域' : '' }
}))
const federatedRows = computed(() => Object.entries(summary.value?.federated.methods || {}).map(([key, value]) => ({ name: key, auc: value.test.auc.toFixed(4), sizes: value.client_sizes?.join(' / ') || '集中式', weights: value.round_trace?.at(-1).weights.map(x => x.toFixed(3)).join(' / ') || '—' })))
const survivalRows = computed(() => Object.entries(survivalStatus.value?.software || {}).map(([key, status]) => ({
  name: ({ endpoint_validation: '终点契约校验', kaplan_meier: 'Kaplan–Meier', cox_ph: 'Cox PH', random_survival_forest: 'Random Survival Forest' })[key] || key,
  status: status === 'available' ? '可用' : status === 'not_available' ? '未安装/不可用' : '需通过数据契约'
})))
const survivalCanPredict = computed(() => Boolean(survivalModelStatus.value?.available
  && survivalModelAvailable(survivalModelChoice.value)
  && evaluationUser.value?.role === 'doctor' && evaluationCsrf.value
  && Number.isFinite(Number(survivalAge.value))
  && (survivalModelChoice.value !== 'upenn-clinical-captk-fusion-cox-research'
    || Object.values(survivalRadiomics.value).every(value => Number.isFinite(Number(value))))
  && survivalTimes.value.split(',').every(value => Number.isFinite(Number(value.trim())) && Number(value.trim()) > 0)))
const survivalChosenModel = computed(() => survivalModels.value.find(model => model.model_id === survivalModelChoice.value) || null)
const survivalFusionUnavailableReason = computed(() => survivalModelAvailable('upenn-clinical-captk-fusion-cox-research')
  ? '' : survivalModelUnavailable.value['upenn-clinical-captk-fusion-cox-research'] || '独立融合工件未配置')
const survivalRadiomicsFeatureNames = ['T1GD_ET_Intensity_Mean', 'FLAIR_ED_Intensity_Mean', 'T2_ED_Intensity_Mean', 'T1_NC_Intensity_Mean']
function survivalModelAvailable(modelId) { return survivalModels.value.some(model => model.model_id === modelId) }
function survivalCvMean(model) {
  return model?.validation?.mean_fold_harrell_c_index ?? model?.validation?.fusion_mean_fold_c_index ?? NaN
}
function survivalChartCoordinate(point) {
  const curve = survivalPrediction.value?.survival_curve || []
  const first = Number(curve[0]?.time || 0), last = Number(curve.at(-1)?.time || first)
  const x = last > first ? 42 + ((Number(point.time) - first) / (last - first)) * 418 : 251
  return { x, y: 20 + (1 - Number(point.survival_probability)) * 140 }
}
const survivalChartPoints = computed(() => (survivalPrediction.value?.survival_curve || [])
  .map(point => {
    const coordinate = survivalChartCoordinate(point)
    return `${coordinate.x},${coordinate.y}`
  }).join(' '))
const evaluationRows = computed(() => Object.entries(evaluation.value?.record?.regions || {}).map(([region, row]) => ({
  region, dice: row.dice ?? '不可用', hd95: row.hd95_mm ?? '不可用',
  hd95Reason: row.hd95_status === 'available' ? '可计算' : row.hd95_reason || 'NOT_AVAILABLE',
  precision: row.precision ?? '不可用', recall: row.recall ?? '不可用',
  tp: row.true_positive_voxels, fp: row.false_positive_voxels, fn: row.false_negative_voxels,
})))
const failure = e => { error.value = String(e.response?.data?.detail || e.message) }
async function loadPatient() {
  patientLoading.value = true; patient.value = null; error.value = ''
  try { patient.value = (await request.get(`/research/patients/${selected.value}`)).data.data } catch (e) { failure(e) } finally { patientLoading.value = false }
}
async function predictClinical() {
  clinicalLoading.value = true; clinical.value = null; error.value = ''
  try { clinical.value = (await request.post('/research/clinical', { age: age.value, female: female.value })).data.data } catch (e) { failure(e) } finally { clinicalLoading.value = false }
}
async function loadSurvivalModelStatus() {
  try {
    const [statusResponse, modelsResponse] = await Promise.all([
      request.get('/api/survival/status'), request.get('/api/survival/models'),
    ])
    survivalModelStatus.value = statusResponse.data.data
    survivalModels.value = modelsResponse.data.data.models || []
    survivalModelUnavailable.value = modelsResponse.data.data.unavailable_models || {}
    if (!survivalModelAvailable(survivalModelChoice.value) && survivalModels.value.length) {
      survivalModelChoice.value = survivalModels.value[0].model_id
    }
    survivalModelError.value = ''
  } catch (e) {
    survivalModelStatus.value = { available: false, status: 'NOT_AVAILABLE' }
    survivalModels.value = []
    survivalModelError.value = String(e.response?.data?.detail || e.message)
  }
}
async function predictSyntheticSurvival() {
  if (!survivalCanPredict.value) return
  survivalPredictionLoading.value = true
  survivalPredictionError.value = ''
  survivalPrediction.value = null
  const times = survivalTimes.value.split(',').map(value => Number(value.trim()))
  if (times.some((value, index) => index > 0 && value < times[index - 1])) {
    survivalPredictionError.value = '时间点请按天数从小到大填写。'
    survivalPredictionLoading.value = false
    return
  }
  try {
    const response = await request.post('/api/survival/predict', {
      declared_use_scope: 'SYNTHETIC_TEST',
      model_id: survivalModelChoice.value,
      clinical: { age_years: Number(survivalAge.value), gender: survivalGender.value,
        IDH1: survivalIdh.value, GTR_over90percent: survivalGtr.value },
      ...(survivalModelChoice.value === 'upenn-clinical-captk-fusion-cox-research'
        ? { radiomics: Object.fromEntries(Object.entries(survivalRadiomics.value).map(([name, value]) => [name, Number(value)])) }
        : {}),
      requested_times_days: times,
    }, { headers: { 'X-BF-CSRF': evaluationCsrf.value } })
    survivalPrediction.value = response.data.data
  } catch (e) {
    survivalPredictionError.value = String(e.response?.data?.detail || e.message)
  } finally { survivalPredictionLoading.value = false }
}
function scheduleFeatures() {
  clearTimeout(featureTimer)
  if (mounted && ['queued', 'running'].includes(featureJob.value?.state)) featureTimer = setTimeout(refreshFeature, 1500)
}
async function refreshFeature() {
  if (!featureCase.value) return
  clearTimeout(featureTimer)
  const id = featureCase.value, ticket = ++featureGeneration
  try {
    const [jobResponse, inputResponse] = await Promise.all([
      request.get(`/research/cases/${id}/features`), request.get(`/research/cases/${id}/clinical-input`)
    ])
    if (mounted && featureCase.value === id && ticket === featureGeneration) {
      const dirty = featureInputDirty.value
      caseClinical.value = inputResponse.data.data
      if (!dirty) { caseAge.value = caseClinical.value.age; caseFemale.value = caseClinical.value.female }
      featureJob.value = jobResponse.data.data; featureStatusKnown.value = true; featureError.value = ''; scheduleFeatures()
      return featureJob.value
    }
  } catch (e) {
    if (mounted && featureCase.value === id && ticket === featureGeneration) {
      featureJob.value = null; featureStatusKnown.value = false; featureError.value = String(e.response?.data?.detail || e.message)
    }
  }
}
async function changeFeatureCase() {
  ++featureGeneration; clearTimeout(featureTimer); featureJob.value = null; caseClinical.value = null; caseAge.value = null; caseFemale.value = null; error.value = ''; featureError.value = ''; featureStatusKnown.value = false
  const id = featureCase.value
  if (!id) return
  try {
    const input = (await request.get(`/research/cases/${id}/clinical-input`)).data.data
    if (!mounted || featureCase.value !== id) return
    caseClinical.value = input; caseAge.value = input.age; caseFemale.value = input.female
    await refreshFeature()
    await loadEvaluationRuns()
  } catch (e) { if (mounted && featureCase.value === id) failure(e) }
}
async function saveCaseClinical() {
  clinicalSaving.value = true; featureError.value = ''
  const id = featureCase.value
  try {
    const input = (await request.put(`/research/cases/${id}/clinical-input`, { age: caseAge.value, female: caseFemale.value })).data.data
    if (mounted && featureCase.value === id) {
      caseClinical.value = input; caseAge.value = input.age; caseFemale.value = input.female
      await refreshFeature()
    }
  } catch (e) { if (mounted && featureCase.value === id) featureError.value = String(e.response?.data?.detail || e.message) } finally { clinicalSaving.value = false }
}
async function startFeatures() {
  ++featureGeneration; clearTimeout(featureTimer); featureSubmitting.value = true; featureError.value = ''
  const id = featureCase.value
  try {
    const job = (await request.post(`/research/cases/${id}/features`)).data.data
    if (mounted && featureCase.value === id) { featureJob.value = job; scheduleFeatures() }
  } catch (e) {
    if (mounted && featureCase.value === id) {
      featureError.value = String(e.response?.data?.detail || e.message)
      if (e.response?.status === 409) {
        const job = await refreshFeature()
        if (mounted && featureCase.value === id && !['queued', 'running'].includes(job?.state)) featureError.value = String(e.response?.data?.detail || e.message)
      }
    }
  } finally { featureSubmitting.value = false }
}
async function exportFeatures() {
  if (!featureCase.value || featureJob.value?.state !== 'succeeded' || featureJob.value?.stale) return
  featureExporting.value = true; featureError.value = ''
  try {
    const response = await request.get(`/research/cases/${featureCase.value}/features.csv`, { responseType: 'blob' })
    const url = URL.createObjectURL(response.data)
    const link = document.createElement('a')
    link.href = url; link.download = `brainfusion-case-${featureCase.value}-features.csv`
    document.body.appendChild(link); link.click(); link.remove(); setTimeout(() => URL.revokeObjectURL(url), 1000)
  } catch (e) { featureError.value = String(e.response?.data?.detail || e.message) }
  finally { featureExporting.value = false }
}
async function loadEvaluationSession() {
  try {
    const state = (await request.get('/local-auth/session')).data.data
    evaluationUser.value = state.user; evaluationAuthConfigured.value = state.configured; evaluationCsrf.value = state.csrf || ''
    evaluationAuthError.value = ''
    if (state.user?.role === 'doctor' && featureCase.value) await loadEvaluationRuns()
  } catch (e) {
    evaluationUser.value = null; evaluationCsrf.value = ''
    evaluationAuthError.value = String(e.response?.data?.detail || e.message)
  }
}
async function loginEvaluation() {
  if (evaluationAuthBusy.value || !evaluationUsername.value || !evaluationPassword.value) return
  evaluationAuthBusy.value = true; evaluationAuthError.value = ''
  try {
    await request.post('/local-auth/login', { username: evaluationUsername.value, password: evaluationPassword.value })
    await loadEvaluationSession()
    if (evaluationUser.value?.role !== 'doctor') evaluationAuthError.value = '该账户不是本地 doctor 角色，不能写入评价。'
  } catch (e) { evaluationAuthError.value = String(e.response?.data?.detail || '本地账户登录失败。') }
  finally { evaluationPassword.value = ''; evaluationAuthBusy.value = false }
}
async function logoutEvaluation() {
  evaluationAuthBusy.value = true; evaluationAuthError.value = ''
  try { await request.post('/local-auth/logout', {}, { headers: { 'X-BF-CSRF': evaluationCsrf.value } }) }
  catch (e) { evaluationAuthError.value = String(e.response?.data?.detail || '本地会话退出失败。') }
  finally { await loadEvaluationSession(); evaluationAuthBusy.value = false }
}
async function loadEvaluationRuns() {
  if (!featureCase.value || evaluationUser.value?.role !== 'doctor') return
  evaluationError.value = ''; evaluation.value = null
  try {
    const response = await request.get(`/analysis/${featureCase.value}/history`)
    evaluationRuns.value = (response.data.data || []).filter(run => run.state === 'succeeded' && run.current)
    if (!evaluationRuns.value.some(run => run.id === evaluationRunId.value)) evaluationRunId.value = evaluationRuns.value[0]?.id || ''
    if (evaluationRunId.value) await refreshEvaluation()
  } catch (e) {
    evaluationRuns.value = []; evaluationRunId.value = ''
    evaluationError.value = String(e.response?.data?.detail || e.message)
  }
}
async function refreshEvaluation() {
  if (!featureCase.value || !evaluationRunId.value || evaluationUser.value?.role !== 'doctor') return
  evaluationLoading.value = true; evaluationError.value = ''
  try {
    evaluation.value = (await request.get(`/research/cases/${featureCase.value}/analysis/${evaluationRunId.value}/segmentation-evaluation`, {
      headers: { 'X-BF-CSRF': evaluationCsrf.value },
    })).data.data
  } catch (e) {
    evaluation.value = null; evaluationError.value = String(e.response?.data?.detail || e.message)
  } finally { evaluationLoading.value = false }
}
function selectReferenceMask(event) {
  evaluationReferenceFile.value = event.target.files?.[0] || null
}
async function submitEvaluation() {
  if (!evaluationReferenceFile.value || !evaluationRunId.value || !evaluationAuthorized.value) return
  evaluationSubmitting.value = true; evaluationError.value = ''
  const form = new FormData()
  form.append('reference_mask', evaluationReferenceFile.value)
  form.append('dataset_version', evaluationDatasetVersion.value.trim())
  form.append('annotation_id', evaluationAnnotationId.value.trim())
  form.append('authorization_receipt', evaluationAuthorizationReceipt.value.trim())
  form.append('research_use_authorized', 'true')
  try {
    const response = await request.post(`/research/cases/${featureCase.value}/analysis/${evaluationRunId.value}/segmentation-evaluation`, form, {
      headers: { 'X-BF-CSRF': evaluationCsrf.value }, timeout: 120000,
    })
    evaluation.value = {
      status: response.data.data.status, reference_annotation_available: true,
      case_id: response.data.data.case_id, analysis_run_id: response.data.data.analysis_run_id,
      mri_id: response.data.data.mri_id, model_version: response.data.data.model_version,
      record: response.data.data,
    }
    evaluationReferenceFile.value = null; evaluationAuthorized.value = false
    await refreshEvaluation()
  } catch (e) { evaluationError.value = String(e.response?.data?.detail || e.message) }
  finally { evaluationSubmitting.value = false }
}
async function exportEvaluation() {
  if (!featureCase.value || !evaluationRunId.value || !evaluation?.value?.record) return
  evaluationExporting.value = true; evaluationError.value = ''
  try {
    const response = await request.get(`/research/cases/${featureCase.value}/analysis/${evaluationRunId.value}/segmentation-evaluation.csv`, {
      responseType: 'blob', headers: { 'X-BF-CSRF': evaluationCsrf.value },
    })
    const url = URL.createObjectURL(response.data), link = document.createElement('a')
    link.href = url; link.download = `segmentation-evaluation-${evaluationRunId.value}.csv`
    document.body.appendChild(link); link.click(); link.remove(); setTimeout(() => URL.revokeObjectURL(url), 1000)
  } catch (e) { evaluationError.value = String(e.response?.data?.detail || e.message) }
  finally { evaluationExporting.value = false }
}
onMounted(async () => {
  request.get('/research/survival/status').then(response => { survivalStatus.value = response.data.data }).catch(failure)
  await loadSurvivalModelStatus()
  await loadEvaluationSession()
  try {
    summary.value = (await request.get('/research/summary')).data.data
    await loadPatient()
    cases.value = (await request.get('/cases/', { params: { status: 'analyzed' } })).data.data
    const requestedCase = Number(route.query.case_id)
    if (cases.value.some(item => item.id === requestedCase)) { featureCase.value = requestedCase; await changeFeatureCase() }
  } catch (e) { failure(e) }
})
onUnmounted(() => { mounted = false; ++featureGeneration; clearTimeout(featureTimer) })
</script>
<style scoped>
.research-page { padding: 24px; max-width: 1100px; margin: auto; } .panel { margin-top: 18px; } label { margin-right: 12px; }
.survival-curve-figure { max-width: 560px; margin: 16px 0; } .survival-curve-figure svg { width: 100%; overflow: visible; }
.survival-curve-figure text { fill: currentColor; font-size: 10px; } .survival-axis { stroke: #87909c; stroke-width: 1; }
.survival-curve-line { fill: none; stroke: #2775cf; stroke-width: 3; } .survival-curve-point { fill: #2775cf; }
</style>
