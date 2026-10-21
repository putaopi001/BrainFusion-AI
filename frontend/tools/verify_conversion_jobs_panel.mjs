import { chromium } from '@playwright/test'
import fs from 'node:fs/promises'
import assert from 'node:assert/strict'

const out = process.argv[2]?.replaceAll('\\', '/')
assert.ok(out?.startsWith('E:/BrainFusion-Runtime/results/nightly/'))
await fs.mkdir(out)
const browser = await chromium.launch({ channel: 'msedge', headless: true })
const page = await browser.newPage({ viewport: { width: 1500, height: 1100 } })
const result = { status: 'running', scope: 'Actual local frontend, synthetic API job/auth fixtures only; no real DICOM conversion or activation', browser: await browser.version(), checks: [], writes: [], errors: [] }
let authenticated = false
let state = 'failed'
let attempt = 1
page.on('pageerror', error => result.errors.push(error.message))
await page.route('http://127.0.0.1:8012/**', async route => {
  const request = route.request(), url = new URL(request.url()), path = url.pathname
  if (request.method() === 'POST') result.writes.push({ path, csrf: request.headers()['x-bf-csrf'] || null })
  if (path === '/cases/19/detail') return route.fulfill({ status: 200, json: { code: 200, data: {
    case: { id: 19, description: 'SYNTHETIC conversion job fixture', status: 'uploaded' },
    patient: { name: 'SYNTHETIC', age: 40, gender: 'other' },
    mri: { id: 1, filename: 'SYNTHETIC MRI', file_url: null, preview_urls: [], preview_views: { axial: [], coronal: [], sagittal: [] }, has_preview: false },
    prediction: null, analysis: null, report: null, legacy_outputs: { available: false, has_prediction: false, has_report: false }
  } } })
  if (path === '/cases/19/doctor-opinion') return route.fulfill({ status: 200, json: { code: 200, data: { author: '', content: '' } } })
  if (path === '/pacs/status') return route.fulfill({ status: 200, json: { code: 200, data: { state: 'ready', read_available: true, import_available: false, message: 'SYNTHETIC local UI fixture' } } })
  if (path === '/pacs/cases/19/links') return route.fulfill({ status: 200, json: { code: 200, data: { items: [] } } })
  if (path === '/pacs/cases/19/conversions') return route.fulfill({ status: 200, json: { code: 200, data: { state: 'not_registered', message: 'SYNTHETIC no registered conversion', items: [], model_input_eligible: false, current_mri_replaced: false } } })
  if (path === '/pacs/cases/19/conversion-jobs') return route.fulfill({ status: 200, headers: { 'cache-control': 'no-store' }, json: { code: 200, data: { items: [{ job_id: 'a'.repeat(32), case_id: 19, version_id: 'SYNTHETIC', state, attempt, reason: state === 'failed' ? 'conversion_job_input_changed' : null, registered: false, model_input_eligible: false, current_mri_replaced: false, inference_performed: false }] } } })
  if (path === '/pacs/import-candidates') return route.fulfill({ status: 200, json: { code: 200, data: { items: [] } } })
  if (path === '/local-auth/session') return route.fulfill({ status: 200, json: { code: 200, data: { configured: true, user: authenticated ? { id: 'b'.repeat(32), username: 'doctor-fixture', display_name: 'SYNTHETIC reviewer', role: 'doctor' } : null, csrf: authenticated ? 'csrf-synthetic' : null } } })
  if (path === '/local-auth/login') { authenticated = true; return route.fulfill({ status: 200, json: { code: 200, data: { authenticated: true } } }) }
  if (path === '/pacs/cases/19/conversion-jobs/' + 'a'.repeat(32) + '/retry') {
    const body = request.postDataJSON()
    assert.deepEqual(body, { expected_attempt: 1 })
    assert.equal(request.headers()['x-bf-csrf'], 'csrf-synthetic')
    state = 'queued'; attempt = 2
    return route.fulfill({ status: 200, headers: { 'cache-control': 'no-store' }, json: { code: 200, data: { job_id: 'a'.repeat(32), case_id: 19, version_id: 'SYNTHETIC', state, attempt, reason: null, reviewer_authenticated: true, professional_credential_verified: false, model_input_eligible: false, current_mri_replaced: false, inference_performed: false } } })
  }
  return route.fulfill({ status: 404, json: { code: 404, message: 'Unexpected synthetic route', data: null } })
})
try {
  await page.goto('http://127.0.0.1:5179/case/19')
  const section = page.getByRole('region', { name: '持久DICOM转换作业' })
  await section.getByText('转换失败，可重试', { exact: false }).waitFor()
  await section.getByRole('button', { name: '重新排队' }).click()
  await page.getByRole('dialog', { name: '医生账户确认转换重试' }).waitFor()
  await page.getByLabel('重试医生账户名').fill('doctor-fixture')
  await page.getByLabel('重试医生账户密码').fill('SYNTHETIC-password')
  await page.getByRole('button', { name: '登录并重试' }).click()
  await section.getByText('等待执行', { exact: false }).waitFor()
  assert.equal(await section.getByText('尝试 2', { exact: false }).count(), 1)
  assert.deepEqual(result.writes.map(row => row.path), ['/local-auth/login', '/pacs/cases/19/conversion-jobs/' + 'a'.repeat(32) + '/retry'])
  assert.equal(result.writes[1].csrf, 'csrf-synthetic')
  assert.deepEqual(result.errors, [])
  result.checks.push('Failed conversion input is visibly actionable; login uses local doctor account; retry is case/job/attempt bound and CSRF protected')
  result.checks.push('Retry response remains queued and explicitly confirms no MRI activation or inference')
  await section.screenshot({ path: out + '/conversion-jobs.png' })
  result.status = 'passed'
} catch (error) {
  result.status = 'failed'; result.error = error.stack
  await page.screenshot({ path: out + '/failure.png', fullPage: true }).catch(() => {})
  process.exitCode = 1
} finally {
  await fs.writeFile(out + '/validation.json', JSON.stringify(result, null, 2))
  await browser.close()
  console.log(JSON.stringify({ status: result.status, browser: result.browser, checks: result.checks, error: result.error }))
}
