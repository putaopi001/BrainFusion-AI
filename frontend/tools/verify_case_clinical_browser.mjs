import { chromium } from '@playwright/test'
import fs from 'node:fs/promises'
import assert from 'node:assert/strict'

const output = process.env.BRAINFUSION_EVIDENCE_DIR
if (!output?.startsWith('E:/BrainFusion-Runtime/results/nightly/')) throw new Error('Use a unique evidence directory')
await fs.mkdir(output, { recursive: true })
const caseId = Number(process.env.BRAINFUSION_CASE_ID)
assert(caseId > 0)
const web = process.env.BRAINFUSION_WEB_URL || 'http://127.0.0.1:5179'
const api = process.env.BRAINFUSION_API_URL || 'http://127.0.0.1:8012'
const browser = await chromium.launch({ headless: true })
const page = await browser.newPage({ viewport: { width: 1440, height: 1100 } })
const errors = [], checks = [], evidence = { status: 'in_progress', case_id: caseId, checks, errors }
page.on('pageerror', e => errors.push(e.message))
const get = async path => {
  const response = await page.request.get(api + path)
  assert.equal(response.status(), 200, await response.text())
  return (await response.json()).data
}
try {
  const before = await get(`/cases/${caseId}/detail`)
  const initial = await get(`/research/cases/${caseId}/clinical-input`)
  const old = await get(`/research/cases/${caseId}/features`)
  assert.equal(initial.source, 'associated_patient')
  assert.equal(initial.age, before.patient.age)
  assert.equal(initial.female, before.patient.gender === 'female')
  assert.equal(old.stale, false)
  evidence.before = { input: initial, job_id: old.id, probabilities: old.result.probabilities }
  await page.goto(`${web}/research?case_id=${caseId}`)
  await page.locator('.case-age input').waitFor()
  assert.equal(Number(await page.locator('.case-age input').inputValue()), initial.age)
  await page.locator('.automatic-result').waitFor()
  checks.push('case input defaults to the linked database patient; old matching legacy snapshot remains readable')

  await page.locator('.case-age input').fill(String(initial.age + 1))
  await page.locator('.case-age input').press('Tab')
  await page.getByText('研究输入已修改但尚未保存；旧概率暂不显示。保存后需按新版本重新计算。', { exact: true }).waitFor()
  assert.equal(await page.locator('.automatic-result').count(), 0)
  assert(await page.getByRole('button', { name: '提取自动掩膜特征', exact: true }).isDisabled())
  assert.equal((await get(`/research/cases/${caseId}/clinical-input`)).age, initial.age)
  checks.push('unsaved edits hide old probabilities, disable extraction and leave saved data unchanged')

  const savedResponse = page.waitForResponse(r => r.url().endsWith(`/research/cases/${caseId}/clinical-input`) && r.request().method() === 'PUT')
  await page.getByRole('button', { name: '保存病例研究输入', exact: true }).click()
  const saved = await savedResponse
  assert.equal(saved.status(), 200)
  const changed = (await saved.json()).data
  assert.notEqual(changed.version, initial.version)
  assert.equal(changed.source, 'case_research_override')
  assert.equal(changed.age, initial.age + 1)
  await page.getByText('旧研究结果已失效，请重新提取。历史结果仍保留。原因：', { exact: false }).waitFor()
  const stale = await get(`/research/cases/${caseId}/features`)
  assert.equal(stale.result, null); assert.equal(stale.stale, true)
  assert.equal(stale.id, old.id)
  await page.reload()
  await page.locator('.case-age input').waitFor()
  assert.equal(Number(await page.locator('.case-age input').inputValue()), changed.age)
  await page.getByText('旧研究结果已失效，请重新提取。历史结果仍保留。原因：', { exact: false }).waitFor()
  await page.screenshot({ path: `${output}/saved-input-stale-result.png`, fullPage: true })
  checks.push('save creates a durable case-only input version; old result is unavailable after page reload')

  const startedResponse = page.waitForResponse(r => r.url().endsWith(`/research/cases/${caseId}/features`) && r.request().method() === 'POST')
  await page.getByRole('button', { name: '提取自动掩膜特征', exact: true }).click()
  const started = await startedResponse
  assert.equal(started.status(), 202, await started.text())
  assert.equal(started.request().postData(), null)
  const newJob = (await started.json()).data
  assert.notEqual(newJob.id, old.id)
  await page.waitForFunction(id => document.querySelector('.feature-state')?.dataset.jobId === id && document.querySelector('.feature-state').textContent.includes('succeeded'), newJob.id, { timeout: 180000 })
  const completed = await get(`/research/cases/${caseId}/features`)
  assert.equal(completed.stale, false)
  assert.equal(completed.clinical_input_version, changed.version)
  assert.equal(completed.clinical_input.age, changed.age)
  assert.equal(completed.patient_id, initial.patient_id)
  assert.equal(completed.clinical_input_source, 'case_research_override')
  assert.equal(completed.analysis_run_id, old.analysis_run_id)
  assert.equal(completed.result.probabilities.automatic_mask_radiomics, old.result.probabilities.automatic_mask_radiomics)
  assert.notEqual(completed.result.probabilities.clinical, old.result.probabilities.clinical)
  const cachedResponse = await page.request.post(`${api}/research/cases/${caseId}/features`)
  assert.equal(cachedResponse.status(), 202)
  const cached = (await cachedResponse.json()).data
  assert.equal(cached.id, completed.id); assert.equal(cached.cache_hit, true)
  const after = await get(`/cases/${caseId}/detail`)
  assert.deepEqual(after.patient, before.patient)
  assert.deepEqual(after.report, before.report)
  assert.equal(after.mri.verified_run_id, before.mri.verified_run_id)
  const history = JSON.parse(await fs.readFile(`${process.env.BRAINFUSION_FEATURE_JOBS_DIR}/${caseId}/${old.analysis_run_id}/${old.id}/state.json`, 'utf8'))
  assert.deepEqual(history.result.probabilities, old.result.probabilities)
  evidence.after = { input: changed, job: completed, cache_hit: cached.cache_hit, original_patient: after.patient }
  checks.push('body-free submission uses saved input; new task/version/probabilities, cache hit and historical results preserved')
  checks.push('patient data, segmentation report and doctor confirmation remain unchanged')
  await page.reload()
  await page.locator(`.feature-state[data-job-id="${completed.id}"]`).waitFor()
  await page.locator('.automatic-result').waitFor()
  await page.screenshot({ path: `${output}/versioned-input-current-result.png`, fullPage: true })
  assert.deepEqual(errors, [])
  evidence.status = 'passed'
  console.log(JSON.stringify({ status: evidence.status, case_id: caseId, checks }))
} catch (e) {
  evidence.status = 'failed'; evidence.error = String(e)
  await page.screenshot({ path: `${output}/failure.png`, fullPage: true })
  throw e
} finally {
  await fs.writeFile(`${output}/validation.json`, JSON.stringify(evidence, null, 2))
  await browser.close()
}
