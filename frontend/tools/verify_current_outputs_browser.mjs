// Real public MRI workflow on a restored validation database; no training.
import { chromium } from '@playwright/test'
import fs from 'node:fs/promises'
import assert from 'node:assert/strict'

const output = process.env.BRAINFUSION_EVIDENCE_DIR
if (!output?.startsWith('E:/BrainFusion-Runtime/results/nightly/')) throw new Error('Use a unique nightly evidence directory')
await fs.mkdir(output, { recursive: true })
const web = process.env.BRAINFUSION_WEB_URL || 'http://127.0.0.1:5179'
const api = process.env.BRAINFUSION_API_URL || 'http://127.0.0.1:8012'
const legacyCase = Number(process.env.BRAINFUSION_LEGACY_CASE)
assert(legacyCase > 0, 'Requires an explicitly synthetic legacy fixture in the copied database')
const browser = await chromium.launch({ headless: true })
const context = await browser.newContext({ viewport: { width: 1440, height: 1100 }, acceptDownloads: true })
const page = await context.newPage()
page.setDefaultTimeout(30000)
const errors = [], checks = [], results = { status: 'in_progress', web, api, checks, errors }
page.on('pageerror', error => errors.push(error.message))
async function save() { await fs.writeFile(`${output}/browser-validation.json`, JSON.stringify(results, null, 2)) }
async function get(path) {
  const response = await context.request.get(api + path)
  assert.equal(response.status(), 200, await response.text())
  return (await response.json()).data
}
try {
  await page.goto(`${web}/case/${legacyCase}`)
  await page.getByText('此病例的历史占位结果已归档', { exact: false }).waitFor()
  assert.equal(await page.getByText('MRI肿瘤概率:', { exact: true }).count(), 0)
  await page.goto(`${web}/report?case_id=${legacyCase}`)
  await page.getByText('尚无当前成功分割报告；历史占位报告和失效版本不用于导出。', { exact: true }).waitFor()
  assert(await page.getByRole('button', { name: '导出 PDF', exact: true }).isDisabled())
  assert.equal(await page.locator('#report-paper').count(), 0)
  await page.screenshot({ path: `${output}/legacy-report-blocked.png`, fullPage: true })
  assert.equal((await context.request.get(`${api}/prediction/${legacyCase}`)).status(), 503)
  const archive = await context.request.get(`${api}/debug/predictions`)
  const archived = (await archive.json()).data.find(item => item.case_id === legacyCase)
  assert.equal(archived.source, 'legacy_unverified'); assert.equal(archived.current, false)
  checks.push('synthetic legacy API/archive/page/PDF exclusion')
  await save()

  // Read all five unchanged real cases with current server responses, not old pass flags.
  for (const id of [11, 12, 13, 14, 15]) {
    const detail = await get(`/cases/${id}/detail`)
    assert.equal(detail.analysis.state, 'succeeded')
    assert.equal(detail.report.analysis_run_id, detail.analysis.id)
    assert.equal(detail.prediction, null)
    await page.goto(`${web}/report?case_id=${id}`)
    await page.locator('#report-paper').waitFor()
    await page.getByText(`分析版本：${detail.analysis.id}`, { exact: true }).first().waitFor()
    assert(!(await page.getByRole('button', { name: '导出 PDF', exact: true }).isDisabled()))
    assert.equal(await page.getByText('高风险', { exact: true }).count(), 0)
  }
  checks.push('five existing real version-bound reports remain readable')

  // A request failure must clear a previously displayed report and disable export.
  await page.route(`**/cases/15/detail`, route => route.fulfill({ status: 500, json: { detail: 'Injected validation failure' } }))
  await page.getByRole('button', { name: '刷新报告', exact: true }).click()
  await page.getByText('报告加载失败，已停止显示和导出旧内容。请刷新重试。', { exact: true }).first().waitFor()
  assert.equal(await page.locator('#report-paper').count(), 0)
  assert(await page.getByRole('button', { name: '导出 PDF', exact: true }).isDisabled())
  await page.unroute(`**/cases/15/detail`)
  checks.push('failed refresh clears old report/PDF state (injected HTTP failure)')

  // Create through the actual UI, using the public source-patient clinical inputs.
  const source = await get('/research/patients/4')
  results.clinical_input = source.clinical_input
  let caseId = Number(process.env.BRAINFUSION_RESUME_CASE)
  if (caseId > 0) {
    results.new_case_id = caseId
    checks.push('resumed completed real case from earlier recorded attempt; no duplicate inference')
  } else {
  await page.goto(`${web}/cases`)
  await page.getByRole('button', { name: '创建病例', exact: true }).first().click()
  const dialog = page.getByRole('dialog')
  await dialog.getByPlaceholder('请输入患者姓名', { exact: true }).fill('公开样本4 · 夜间工程验证')
  await dialog.locator('.el-input-number input').fill(String(source.clinical_input.age))
  await dialog.locator('.el-input-number input').press('Tab')
  await dialog.locator('.el-select').click()
  await page.getByRole('option', { name: source.clinical_input.female ? '女' : '男', exact: true }).click()
  await dialog.getByPlaceholder('请输入病例描述', { exact: true }).fill('WAW-GliomAI 公共样本4；本轮隔离数据库全流程验收')
  const createdPromise = page.waitForResponse(r => r.url().endsWith('/cases/create') && r.request().method() === 'POST')
  await dialog.getByRole('button', { name: '创建病例', exact: true }).click()
  const created = await createdPromise
  assert.equal(created.status(), 200)
  caseId = (await created.json()).data.case_id
  results.new_case_id = caseId
  checks.push('patient/case creation via browser with linked public clinical inputs')
  await save()

  await page.goto(`${web}/analysis?case_id=${caseId}`)
  for (const [index, sequence] of ['t1c', 't1n', 't2w', 't2f'].entries()) {
    await page.locator('input[type=file]').nth(index).setInputFiles(`E:/BrainFusion-Data/WAW-GliomAI-v3/sample/images/gliomai_preop_scans_renamed/4/4_0_brain_${sequence}.nii.gz`)
  }
  const uploadPromise = page.waitForResponse(r => r.url().endsWith(`/studies/${caseId}`) && r.request().method() === 'POST')
  await page.getByRole('button', { name: '上传四序列', exact: true }).click()
  assert.equal((await uploadPromise).status(), 200)
  const analysisPromise = page.waitForResponse(r => r.url().endsWith(`/analysis/${caseId}`) && r.request().method() === 'POST')
  await page.getByRole('button', { name: '运行分割模型', exact: true }).click()
  assert.equal((await analysisPromise).status(), 202)
  await page.getByText('任务状态：完成', { exact: true }).waitFor({ timeout: 180000 })
  }
  const run = await get(`/analysis/${caseId}`)
  results.analysis = run
  checks.push(process.env.BRAINFUSION_RESUME_CASE ? 'current recorded MONAI analysis re-read; upload/inference evidence retained in prior attempt' : 'same-patient four-sequence upload and real MONAI inference/polling')
  await save()

  await page.goto(`${web}/case/${caseId}`)
  await page.getByText('真实窗宽窗位', { exact: true }).waitFor()
  await page.getByRole('button', { name: 'AI分割叠加', exact: true }).click()
  await page.waitForFunction(() => document.querySelectorAll('.mask-img').length > 0 && [...document.querySelectorAll('.mask-img')].every(img => img.complete && img.naturalWidth > 0))
  assert.equal(await page.getByText('当前 MRI 尚未完成 AI 分析', { exact: false }).count(), 0)
  const confirmation = page.getByRole('button', { name: '确认当前分割结果', exact: true })
  if (await confirmation.isVisible()) await confirmation.click()
  await page.getByText('医生已确认当前版本', { exact: true }).waitFor()
  await page.getByPlaceholder('记录阅片医生姓名', { exact: true }).fill('工程验收复核')
  await page.getByPlaceholder('此处仅保存医生手工录入的阅片意见，不会写入 AI 自动结论。', { exact: true }).fill('公开工程样本的分割边界已查看；此条为流程验证记录。')
  await page.getByRole('button', { name: '保存医生意见', exact: true }).click()
  await page.getByText('医生阅片意见已保存', { exact: true }).waitFor()
  await page.reload()
  await page.getByText('医生已确认当前版本', { exact: true }).waitFor()
  assert.equal(await page.getByPlaceholder('记录阅片医生姓名', { exact: true }).inputValue(), '工程验收复核')
  await page.screenshot({ path: `${output}/current-case-verified.png`, fullPage: true })
  checks.push('real mask overlay; current-version doctor confirmation and opinion survive refresh')

  await page.getByRole('button', { name: '自动掩膜特征研究', exact: true }).click()
  await page.waitForURL(`**/research?case_id=${caseId}`)
  await page.getByText('当前病例：自动掩膜特征研究', { exact: true }).waitFor()
  await page.locator('.case-age input').waitFor()
  const savedClinical = await get(`/research/cases/${caseId}/clinical-input`)
  assert.equal(Number(await page.locator('.case-age input').inputValue()), savedClinical.age)
  const featurePromise = page.waitForResponse(r => r.url().endsWith(`/research/cases/${caseId}/features`) && r.request().method() === 'POST')
  await page.getByRole('button', { name: '提取自动掩膜特征', exact: true }).click()
  const started = await featurePromise
  assert.equal(started.status(), 202, await started.text())
  const submitted = (await started.json()).data
  await page.waitForFunction(id => {
    const state = document.querySelector('.feature-state')
    return state?.dataset.jobId === id && state.textContent.includes('succeeded')
  }, submitted.id, { timeout: 180000 })
  const feature = await get(`/research/cases/${caseId}/features`)
  assert.equal(feature.analysis_run_id, run.id)
  assert.equal(feature.result.target, 'idh1/2=1')
  assert.equal(feature.result.feature_source, 'automatic model mask')
  assert.equal(Object.keys(feature.result.selected_features).length, 20)
  results.feature = feature
  await page.reload()
  await page.locator(`.feature-state[data-job-id="${feature.id}"]`).waitFor()
  await page.screenshot({ path: `${output}/current-automatic-features.png`, fullPage: true })
  checks.push('case-to-research entry, actual automatic features/IDH/fusion, version/refresh persistence')
  await save()

  await page.goto(`${web}/report?case_id=${caseId}`)
  await page.getByText('已确认当前版本', { exact: false }).waitFor()
  await page.getByText('公开工程样本的分割边界已查看；此条为流程验证记录。', { exact: true }).waitFor()
  const reportDetail = await get(`/cases/${caseId}/detail`)
  const expectedTime = new Date(reportDetail.report.created_time).toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai', hour12: false }) + '（北京时间）'
  await page.getByText(`生成时间：${expectedTime}`, { exact: true }).waitFor()
  results.report_created_utc = reportDetail.report.created_time
  results.report_display_beijing = expectedTime
  const downloadPromise = page.waitForEvent('download', { timeout: 60000 })
  await page.getByRole('button', { name: '导出 PDF', exact: true }).click()
  const download = await downloadPromise
  assert.equal(await download.failure(), null)
  await download.saveAs(`${output}/current-report.pdf`)
  const pdf = await fs.readFile(`${output}/current-report.pdf`)
  assert.equal(pdf.subarray(0, 5).toString(), '%PDF-')
  results.pdf_bytes = pdf.length
  await page.screenshot({ path: `${output}/current-report.png`, fullPage: true })
  checks.push('current successful report/PDF, version/volumes and independent doctor opinion')

  // Simulate a server rejecting the displayed version between open and export.
  let downloaded = false
  page.once('download', () => { downloaded = true })
  await page.route(`**/reports/${caseId}`, route => route.fulfill({ status: 404, json: { detail: 'No successful report for the current run' } }))
  await page.getByRole('button', { name: '导出 PDF', exact: true }).click()
  await page.getByText('No successful report for the current run', { exact: true }).waitFor()
  assert.equal(downloaded, false)
  await page.unroute(`**/reports/${caseId}`)
  checks.push('pre-export stale-version rejection (injected server 404), no download')
  assert.deepEqual(errors, [])
  results.status = 'passed'
  await save()
  console.log(JSON.stringify({ status: 'passed', new_case_id: caseId, checks, pdf_bytes: pdf.length }))
} catch (error) {
  results.status = 'failed'; results.error = String(error)
  await page.screenshot({ path: `${output}/browser-failure.png`, fullPage: true })
  await save()
  throw error
} finally { await browser.close() }
