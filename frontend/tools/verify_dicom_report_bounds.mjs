// Pagination fixtures on a real archived series; duplicated engineering lines are not clinical measurements.
import { chromium } from '@playwright/test'
import fs from 'node:fs/promises'
import assert from 'node:assert/strict'

const [root, mode = 'final', tag = ''] = process.argv.slice(2)
assert.ok(root?.startsWith('E:/BrainFusion-Runtime/results/nightly/'))
assert.ok(['baseline', 'final', 'review-max'].includes(mode))
const registry = JSON.parse(await fs.readFile('E:/BrainFusion-Runtime/local/processes.json', 'utf8'))
assert.equal(registry.runtime_paths.DATABASE_PATH.replaceAll('\\', '/'), root + '/database-backup/restored-validation.db')
const api = 'http://127.0.0.1:8012'
async function call(path, method = 'GET', data) {
  const response = await fetch(api + path, { method, headers: { 'Content-Type': 'application/json' }, body: data ? JSON.stringify(data) : undefined })
  assert.equal(response.status, 200, await response.clone().text())
  return (await response.json()).data
}
const candidate = (await call('/pacs/import-candidates')).items[0]
const prefix = `/pacs/cases/19/studies/${candidate.study_uid}/series/${candidate.series_uid}`
const endpoint = prefix + '/reading-report'
const url = `http://127.0.0.1:5179/report?case_id=19&source=dicom&study_uid=${candidate.study_uid}&series_uid=${candidate.series_uid}`
assert.match(tag, /^[A-Za-z0-9_-]*$/)
const output = root + '/report-bounds-' + mode + (tag ? '-' + tag : '')
await fs.mkdir(output)
const result = { status: 'running', mode, checks: [], pageErrors: [], downloads: [], browserWrites: [] }
const opinion = Array.from({ length: 50 }, (_, i) => {
  const n = String(i + 1).padStart(3, '0')
  return (`〔段${n}〕` + '工程分页验证文本，不是医生意见，不构成临床诊断或病灶确认。'.repeat(5)).slice(0, 94) + `〔末${n}〕`
}).join('')
assert.equal(opinion.length, 5000)
if (mode === 'baseline') {
  const initial = await call(endpoint)
  assert.equal(initial.measurements.length, 0)
  const templates = JSON.parse(await fs.readFile('E:/BrainFusion-Runtime/results/nightly/2026-10-15/20261015T032046_p4review/dicom-measurements-expected.json', 'utf8'))
  for (let i = 0; i < 36; i++) {
    const item = templates[i % templates.length]
    assert.deepEqual(item.context, initial.context)
    const payload = Object.fromEntries(['view', 'points_lps', 'view_plane_normal', 'view_up'].map(key => [key, item[key]]))
    await call(prefix + '/measurements', 'POST', { ...payload, context: initial.context, client_uid: `PAGINATION_ENGINEERING_${i + 1}` })
  }
  await call('/cases/19/doctor-opinion', 'PUT', { author: '分页工程验收（非医生）', content: opinion })
  const current = await call(endpoint)
  await call(prefix + '/reviews', 'POST', { context: current.context, content_sha256: current.content_sha256,
    client_uid: 'PAGINATION_ENGINEERING_REVIEW', reviewer: '分页工程验收（非医生）',
    opinion: '仅核对工程分页夹具的来源和内容，非医生及临床判断。', decision: 'checked', acknowledge_local_record_only: true })
  await fs.writeFile(root + '/pagination-fixture.json', JSON.stringify({ scope: '36 repetitions of previously mouse-created engineering lines, plus maximum 5000-character case opinion without newlines; not clinical records', opinion, report: await call(endpoint) }, null, 2), { flag: 'wx' })
}
if (mode === 'final' && (await call(endpoint)).doctor_opinion?.content !== opinion) {
  await call('/cases/19/doctor-opinion', 'PUT', { author: '分页工程验收（非医生）', content: opinion })
  const current = await call(endpoint)
  await call(prefix + '/reviews', 'POST', { context: current.context, content_sha256: current.content_sha256,
    client_uid: 'PAGINATION_RETRY_' + (tag || 'final'), reviewer: '分页工程验收（非医生）',
    opinion: '工程工具续验，非医生及临床判断。', decision: 'checked', acknowledge_local_record_only: true })
}
const reviewText = '〔工程复核开始〕' + '仅用于长复核分页工程验收，非医生或临床诊断。'.repeat(200).slice(0, 3984) + '〔工程复核结束〕'
assert.equal(reviewText.length, 4000)
if (mode === 'review-max') {
  const current = await call(endpoint)
  await call(prefix + '/reviews', 'POST', { context: current.context, content_sha256: current.content_sha256,
    client_uid: 'PAGINATION_MAX_REVIEW', reviewer: '分页工程验收（非医生）', opinion: reviewText,
    decision: 'checked', acknowledge_local_record_only: true })
}
const browser = await chromium.launch({ headless: true })
const page = await browser.newPage({ viewport: { width: 1600, height: 1200 }, acceptDownloads: true })
page.on('pageerror', e => result.pageErrors.push(e.message))
page.on('download', d => result.downloads.push(d.suggestedFilename()))
await page.route('**/*', async route => {
  if (!['GET', 'HEAD'].includes(route.request().method())) result.browserWrites.push(route.request().url())
  await route.continue()
})
const ready = async () => {
  await page.locator('#report-paper.dicom-report').waitFor({ timeout: 90000 })
  await page.waitForFunction(() => !document.querySelector('.report-toolbar .el-button.is-loading'))
}
const button = () => page.getByRole('button', { name: '导出 PDF', exact: true })
try {
  await page.goto(url); await ready()
  const report = await call(endpoint)
  assert.equal(report.measurements.length, 36)
  if (mode !== 'review-max') assert.equal(report.doctor_opinion.content, opinion)
  const shown = await page.locator('.dicom-opinion-paper .opinion-paragraph').allTextContents()
  if (mode === 'final') assert.equal(shown.join(''), opinion)
  await page.screenshot({ path: output + '/report.png', fullPage: true })
  const download = page.waitForEvent('download', { timeout: 120000 })
  await button().click(); await (await download).saveAs(output + (mode === 'review-max' ? '/maximum-review.pdf' : '/many-distances-long-case-opinion.pdf'))
  await ready()
  result.report = report
  result.checks.push(mode === 'review-max' ? '36 engineering rows with exact current 4000-character manual review; real PDF download' : '36 real-archive-bound engineering fixture rows and exact 5000-character case opinion; real product PDF download')
  if (mode === 'review-max') {
    assert.equal(report.latest_review.current, true)
    assert.equal(report.latest_review.reviewer_authenticated, false)
    assert.equal((await page.locator('.manual-review-text .review-paragraph').allTextContents()).join(''), reviewText)
    assert.equal((await call(prefix + '/reviews')).items[0].opinion, reviewText)
    result.checks.push('Presentation refactor preserves all 4000 review characters and local-only identity semantics')
  }
  if (mode === 'final') {
    // Actual independent case-opinion update: content/review invalidation, preserved old snapshot, no stale PDF.
    await call('/cases/19/doctor-opinion', 'PUT', { author: '分页工程验收（非医生）', content: '工程验收更新：旧长意见已更换，必须刷新再导出；非医生意见。' })
    await button().click()
    await page.getByText('来源或记录版本已变化，请核对刷新后的报告再导出。', { exact: true }).waitFor()
    await ready()
    assert.equal(result.downloads.length, 1)
    assert.equal(await page.locator('.dicom-review-paper').count(), 0)
    const updated = await call(endpoint)
    assert.notEqual(updated.content_sha256, report.content_sha256)
    assert.equal(updated.latest_review.current, false)
    const history = await call(prefix + '/reviews')
    assert.equal(history.items[0].reviewed_snapshot.doctor_opinion.content, opinion)
    assert.ok((await page.locator('#report-paper').innerText()).includes('旧长意见已更换'))
    await page.screenshot({ path: output + '/opinion-changed-review-expired.png', fullPage: true })
    result.afterOpinionChange = updated
    result.checks.push('Real case-opinion PUT invalidates source/content review; historical 5000-character snapshot retained; old open-page PDF blocked and current page refreshed')
    await page.evaluate(async () => document.querySelector('#app').__vue_app__.config.globalProperties.$router.push('/report?case_id=17'))
    await page.locator('#report-paper:not(.dicom-report)').waitFor({ timeout: 60000 })
    const text = await page.locator('#report-paper').innerText()
    assert.ok(text.includes('分析运行 ID')); assert.ok(!text.includes(candidate.study_uid))
    await page.screenshot({ path: output + '/nifti-report-unaffected.png', fullPage: true })
    result.checks.push('Same-component NIfTI report still loads without DICOM identity or engineering opinion')
  }
  assert.deepEqual(result.pageErrors, []); assert.deepEqual(result.browserWrites, [])
  result.status = 'passed'
} catch (e) {
  result.status = 'failed'; result.error = e.stack
  await page.screenshot({ path: output + '/failure.png', fullPage: true }).catch(() => {})
  process.exitCode = 1
} finally {
  await fs.writeFile(output + '/validation.json', JSON.stringify(result, null, 2), { flag: 'wx' })
  await browser.close()
  console.log(JSON.stringify({ status: result.status, output, checks: result.checks, error: result.error }))
}
