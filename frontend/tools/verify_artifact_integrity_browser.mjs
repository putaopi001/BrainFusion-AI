import { chromium } from '@playwright/test'
import fs from 'node:fs/promises'
import assert from 'node:assert/strict'
import { execFileSync } from 'node:child_process'

const root = process.env.BRAINFUSION_RUN_ROOT
if (!root?.startsWith('E:/BrainFusion-Runtime/results/nightly/')) throw new Error('Use an owned nightly fixture')
const output = `${root}/${process.env.BRAINFUSION_ATTEMPT || 'e2-browser'}`
await fs.mkdir(output) // Never overwrite an earlier attempt.
const fixture = JSON.parse(await fs.readFile(`${root}/fixture.json`, 'utf8'))
const web = process.env.BRAINFUSION_WEB_URL || 'http://127.0.0.1:5179'
const api = process.env.BRAINFUSION_API_URL || 'http://127.0.0.1:8012'
const id = fixture.case_id
const result = { status: 'in_progress', case_id: id, fixture_scope: fixture.scope, checks: [], errors: [], actions: [] }
const change = action => {
  const message = execFileSync('E:/BrainFusion-AI/.conda/brainfusion/python.exe', ['-B',
    'E:/BrainFusion-AI/backend/tools/prepare_integrity_fixture.py', '--root', root, '--action', action],
  { windowsHide: true, encoding: 'utf8' })
  result.actions.push(JSON.parse(message))
}
const browser = await chromium.launch({ headless: true })
const context = await browser.newContext({ acceptDownloads: true, viewport: { width: 1600, height: 1200 } })
const page = await context.newPage()
page.on('pageerror', error => result.errors.push(error.message))
result.mask_requests = []
page.on('request', r => { if (r.resourceType() === 'image' && r.url().includes(`/mri/${id}/mask/`)) result.mask_requests.push(r.url()) })
let downloads = 0
page.on('download', () => downloads++)
const request = async (path, status = 200, method = 'get') => {
  const response = await context.request[method](api + path)
  assert.equal(response.status(), status, `${path}: ${await response.text()}`)
  return (await response.json()).data
}
const get = path => request(path)
const verify = status => request(`/mri/${id}/verify?run_id=${fixture.analysis_run_id}`, status, 'post')
const healthy = async () => {
  const analysis = await get(`/analysis/${id}`)
  assert.equal(analysis.stale, false); assert.equal(analysis.id, fixture.analysis_run_id)
  assert(analysis.result?.volumes_ml)
  assert.equal((await get(`/reports/${id}`)).analysis_run_id, analysis.id)
  const features = await get(`/research/cases/${id}/features`)
  assert.equal(features.stale, false); assert(features.result)
  return features.result
}
const stale = async label => {
  const analysis = await get(`/analysis/${id}`)
  assert.equal(analysis.state, 'succeeded'); assert.equal(analysis.stale, true)
  assert.equal(analysis.result, null); assert(analysis.stale_reason)
  const detail = await get(`/cases/${id}/detail`)
  assert.equal(detail.analysis.result, null); assert.equal(detail.report, null)
  assert.equal(detail.mri.doctor_verified, false)
  assert.equal((await get(`/mri/${id}`)).doctor_verified, false)
  await request(`/reports/${id}`, 404)
  await request(`/reports/generate/${id}`, 404, 'post')
  await verify(409)
  const segmentation = await get(`/mri/${id}/segmentation`)
  assert.equal(segmentation.available, false); assert.equal(segmentation.stale, true)
  await request(`/mri/${id}/mask/axial/70?version=${fixture.analysis_run_id}`, 409)
  const features = await get(`/research/cases/${id}/features`)
  assert.equal(features.stale, true); assert.equal(features.result, null)
  const history = await get(`/analysis/${id}/history`)
  assert.equal(history[0].current, false); assert(history[0].result?.volumes_ml)
  result.checks.push({ scenario: label, reason: analysis.stale_reason,
    current_analysis: 'hidden', confirmation: 409, report_read_and_generate: 404,
    model_mask: 409, feature_probability: 'hidden', historical_result: 'retained, not current' })
}
try {
  const sourceAnalysis = await get(`/analysis/${fixture.source_case}`)
  const sourceFeature = await get(`/research/cases/${fixture.source_case}/features`)
  const expectedFeatures = await healthy()
  await verify(200)
  await page.goto(`${web}/report?case_id=${id}`)
  await page.locator('#report-paper').waitFor()
  assert.equal(await page.getByRole('button', { name: '导出 PDF', exact: true }).isEnabled(), true)
  change('sequence-change')
  await stale('real owned MRI byte change, unchanged geometry')
  // This is an already-open healthy report, not a freshly loaded stale page.
  const rejection = page.waitForResponse(r => r.url() === `${api}/reports/${id}`)
  await page.getByRole('button', { name: '导出 PDF', exact: true }).click()
  assert.equal((await rejection).status(), 404)
  await page.getByText('当前分割已失效，报告/PDF不可用', { exact: false }).waitFor()
  assert.equal(await page.locator('#report-paper').count(), 0)
  assert.equal(await page.getByRole('button', { name: '导出 PDF', exact: true }).isDisabled(), true)
  assert.equal(downloads, 0)
  await page.screenshot({ path: `${output}/stale-open-report.png`, fullPage: true })
  await page.goto(`${web}/case/${id}`)
  await page.getByText('结果已失效，请重新分析；历史记录保留', { exact: false }).waitFor()
  assert.equal(await page.getByRole('button', { name: '确认当前分割结果', exact: true }).count(), 0)
  assert.equal(await page.getByRole('button', { name: 'AI分割叠加', exact: true }).isDisabled(), true)
  await page.getByText('结果已失效，请重新分析；历史记录保留', { exact: false }).scrollIntoViewIfNeeded()
  await page.screenshot({ path: `${output}/stale-case.png`, fullPage: true })
  await page.goto(`${web}/analysis?case_id=${id}`)
  await page.getByText('任务状态：结果已失效，请重新分析（历史保留）', { exact: true }).waitFor()
  assert.equal(await page.locator('table').count(), 0)
  await page.screenshot({ path: `${output}/stale-analysis.png`, fullPage: true })
  await page.goto(`${web}/research?case_id=${id}`)
  await page.getByText('旧研究结果已失效，请重新提取', { exact: false }).waitFor()
  assert.equal(await page.locator('.automatic-result').count(), 0)
  await page.getByText('旧研究结果已失效，请重新提取', { exact: false }).scrollIntoViewIfNeeded()
  await page.screenshot({ path: `${output}/stale-research.png`, fullPage: true })
  result.checks.push('Existing report export rechecks real current state; no PDF downloaded; case/analysis/research display explicit stale state without old output')
  change('restore'); assert.deepEqual(await healthy(), expectedFeatures)
  await page.goto(`${web}/case/${id}`)
  await page.waitForFunction(() => document.querySelectorAll('.slice-img').length === 3 && [...document.querySelectorAll('.slice-img')].every(i => i.complete && i.naturalWidth > 0))
  await page.getByRole('button', { name: 'AI分割叠加', exact: true }).click()
  await page.waitForFunction(() => document.querySelectorAll('.mask-img').length === 3 && [...document.querySelectorAll('.mask-img')].every(i => i.complete && i.naturalWidth > 0))
  change('mask-change')
  await stale('real owned mask byte change, unchanged geometry')
  // A new slice forces the browser to request an uncached mask from the actual API.
  // Hiding all masks on error can cancel image loading before a response event.
  // Assert the image request and actual UI outcome; stale() independently checks API 409.
  const maskRequest = page.waitForRequest(r => r.resourceType() === 'image' && r.url().includes(`/mri/${id}/mask/`))
  await page.locator('.viewport-panel[data-view="axial"] .viewport').hover()
  await page.mouse.wheel(0, 120)
  await maskRequest
  await page.getByText('模型分割已失效：', { exact: false }).first().waitFor()
  assert.equal(await page.locator('.mask-img').count(), 0)
  assert.equal(await page.getByRole('button', { name: 'AI分割叠加', exact: true }).isDisabled(), true)
  await page.screenshot({ path: `${output}/mask-change-live-viewer.png`, fullPage: true })
  result.checks.push('Previously enabled three-view overlay stops after real mask rejection on slice change, with visible reason and disabled toggle')
  change('restore'); assert.deepEqual(await healthy(), expectedFeatures)
  change('mask-missing'); await stale('owned mask temporarily moved to preserved evidence file')
  await page.getByRole('button', { name: '刷新分割状态', exact: true }).click()
  await page.getByText('模型分割已失效：', { exact: false }).first().waitFor()
  await page.screenshot({ path: `${output}/mask-missing.png`, fullPage: true })
  change('restore'); assert.deepEqual(await healthy(), expectedFeatures)
  assert.equal((await get(`/cases/${id}/detail`)).mri.doctor_verified, true)
  assert.deepEqual(await get(`/analysis/${fixture.source_case}`), sourceAnalysis)
  assert.deepEqual(await get(`/research/cases/${fixture.source_case}/features`), sourceFeature)
  for (const caseId of [11, 12, 13, 14, 15, 17]) await get(`/reports/${caseId}`)
  result.checks.push('Restored identical bytes revive the original linked output/probabilities/confirmation; source case17 and six original reports remain unchanged/readable')
  await page.goto(`${web}/report?case_id=${id}`)
  await page.locator('#report-paper').waitFor()
  let exportChecks = 0
  // Change actual owned bytes at the last check, after the PDF has rendered.
  await page.route(`${api}/reports/${id}`, async route => {
    if (++exportChecks === 2) change('sequence-change')
    await route.continue()
  })
  const renderRaceRejection = page.waitForResponse(r => r.url() === `${api}/reports/${id}` && r.status() === 404)
  await page.getByRole('button', { name: '导出 PDF', exact: true }).click()
  await renderRaceRejection
  await page.getByText('当前分割已失效，报告/PDF不可用', { exact: false }).waitFor()
  assert.equal(downloads, 0); assert.equal(exportChecks, 2)
  await page.screenshot({ path: `${output}/drift-during-pdf-render.png`, fullPage: true })
  await page.unroute(`${api}/reports/${id}`)
  change('restore'); assert.deepEqual(await healthy(), expectedFeatures)
  result.checks.push('Actual owned MRI drift after PDF rendering is rechecked before download: server rejection and zero stale PDFs')
  await page.goto(`${web}/report?case_id=${fixture.source_case}`)
  await page.locator('#report-paper').waitFor()
  assert((await page.locator('#report-paper').innerText()).includes(sourceAnalysis.id))
  assert((await page.locator('#report-paper').innerText()).includes(sourceAnalysis.result.revision))
  await page.getByText('已确认当前版本', { exact: false }).waitFor()
  const downloadPromise = page.waitForEvent('download', { timeout: 60000 })
  await page.getByRole('button', { name: '导出 PDF', exact: true }).click()
  const download = await downloadPromise
  await download.saveAs(`${output}/case17-current-report.pdf`)
  const pdf = await fs.readFile(`${output}/case17-current-report.pdf`)
  assert.equal(pdf.subarray(0, 5).toString(), '%PDF-'); assert(pdf.length > 10000)
  result.pdf = { path: `${output}/case17-current-report.pdf`, bytes: pdf.length, analysis_run_id: sourceAnalysis.id,
    revision: sourceAnalysis.result.revision, volumes_ml: sourceAnalysis.result.volumes_ml, visual_review: 'pending' }
  await page.screenshot({ path: `${output}/case17-current-report.png`, fullPage: true })
  await page.goto(`${web}/research?case_id=${fixture.source_case}`)
  await page.locator('.automatic-result').waitFor()
  await page.locator('.automatic-result').scrollIntoViewIfNeeded()
  await page.screenshot({ path: `${output}/case17-research-provenance.png`, fullPage: true })
  assert.deepEqual(result.errors, []); result.status = 'passed'
  console.log(JSON.stringify(result))
} catch (error) {
  result.status = 'failed'; result.error = String(error)
  await page.screenshot({ path: `${output}/failure.png`, fullPage: true })
  throw error
} finally {
  try { change('restore'); result.fixture_restored = true } catch (error) { result.restore_error = String(error) }
  await fs.writeFile(`${output}/validation.json`, JSON.stringify(result, null, 2))
  await browser.close()
}
