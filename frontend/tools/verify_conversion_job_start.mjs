import { chromium } from '@playwright/test'
import fs from 'node:fs/promises'
import assert from 'node:assert/strict'

const out = process.argv[2]?.replaceAll('\\', '/')
assert.ok(out?.startsWith('E:/BrainFusion-Runtime/results/'))
await fs.mkdir(out)
const browser = await chromium.launch({ channel: 'msedge', headless: true })
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } })
const result = { status: 'running', scope: 'Actual frontend with synthetic HTTP fixtures; no real conversion, model or business writes', checks: [], writes: [], errors: [] }
const jobId = 'a'.repeat(32)
let authenticated = false, state = 'queued', attempt = 1, actionCount = 0, rejectStart = false
let releaseSession = null, sessionHeld = false, delaySession = false
const waitUntil = async predicate => { for (let i = 0; i < 100; i++) { if (predicate()) return; await page.waitForTimeout(50) }; throw Error('Condition not reached') }
page.on('pageerror', e => result.errors.push(e.message))
await page.route('http://127.0.0.1:8012/**', async route => {
  const request = route.request(), path = new URL(request.url()).pathname
  if (request.method() === 'POST') result.writes.push({ path, csrf: request.headers()['x-bf-csrf'] || null })
  const ok = data => route.fulfill({ status: 200, json: { code: 200, data } })
  const matchCase = path.match(/^\/cases\/(17|19)\/detail$/)
  if (matchCase) return ok({ case: { id: Number(matchCase[1]), description: 'SYNTHETIC conversion start', status: 'uploaded' }, patient: { name: 'SYNTHETIC', age: 40, gender: 'other' }, mri: { id: 1, filename: 'SYNTHETIC', preview_urls: [], preview_views: {}, has_preview: false }, analysis: null, prediction: null, report: null, legacy_outputs: { available: false } })
  if (/^\/cases\/(17|19)\/doctor-opinion$/.test(path)) return ok({ author: '', content: '' })
  if (path === '/pacs/status') return ok({ state: 'ready', read_available: true, message: 'SYNTHETIC archive' })
  if (/^\/pacs\/cases\/(17|19)\/(links|conversions)$/.test(path)) return ok({ items: [], message: 'SYNTHETIC no conversion versions' })
  if (path === '/pacs/import-candidates') return ok({ items: [] })
  if (path === '/pacs/cases/17/conversion-jobs') return ok({ items: [] })
  if (path === '/pacs/cases/19/conversion-jobs') return ok({ items: [{ job_id: jobId, case_id: 19, state, attempt, reason: state === 'failed' ? 'conversion_failed' : null }] })
  if (path === '/local-auth/session') {
    if (delaySession) { delaySession = false; sessionHeld = true; await new Promise(resolve => { releaseSession = resolve }) }
    return ok({ configured: true, user: authenticated ? { role: 'doctor', display_name: 'SYNTHETIC local doctor' } : null, csrf: authenticated ? 'synthetic-csrf' : null })
  }
  if (path === '/local-auth/login') { authenticated = true; return ok({ authenticated: true }) }
  if (path === `/pacs/cases/19/conversion-jobs/${jobId}/start` || path === `/pacs/cases/19/conversion-jobs/${jobId}/retry`) {
    assert.equal(request.headers()['x-bf-csrf'], 'synthetic-csrf')
    assert.deepEqual(request.postDataJSON(), { expected_attempt: attempt })
    actionCount++
    if (rejectStart && path.endsWith('/start')) return route.fulfill({ status: 409, json: { detail: { message: 'SYNTHETIC 来源已变更，请重新准备' } } })
    if (path.endsWith('/retry')) attempt++
    state = 'running'
    return ok({ job_id: jobId, case_id: 19, state: 'queued', attempt, reviewer_authenticated: true, professional_credential_verified: false, model_input_eligible: false, current_mri_replaced: false, inference_performed: false })
  }
  return route.fulfill({ status: 404, json: { detail: { message: 'Unexpected synthetic route' } } })
})
try {
  await page.goto('http://127.0.0.1:5179/case/19')
  const section = page.getByRole('region', { name: '持久DICOM转换作业' })
  await section.getByRole('button', { name: '启动转换', exact: true }).click()
  await page.getByRole('dialog', { name: '医生账户确认启动转换' }).waitFor()
  await page.getByLabel('转换操作医生账户名').fill('doctor-fixture')
  await page.getByLabel('转换操作医生账户密码').fill('SYNTHETIC-password')
  await page.getByRole('button', { name: '登录并启动', exact: true }).click()
  await section.getByText('正在转换', { exact: false }).waitFor()
  assert.equal(actionCount, 1)
  await section.screenshot({ path: out + '/started-job.png' })
  result.checks.push('Prepared queued job starts with doctor login, CSRF, case and unchanged attempt; no client file paths')
  state = 'failed'
  await section.getByRole('button', { name: '刷新作业', exact: true }).click()
  await section.getByRole('button', { name: '重新排队', exact: true }).click()
  await waitUntil(() => actionCount === 2)
  assert.equal(attempt, 2)
  result.checks.push('Existing failed job retries with attempt increment through the shared doctor flow')
  state = 'queued'; rejectStart = true
  await section.getByRole('button', { name: '刷新作业', exact: true }).click()
  await section.getByRole('button', { name: '启动转换', exact: true }).click()
  await section.getByText('SYNTHETIC 来源已变更，请重新准备', { exact: false }).waitFor()
  result.checks.push('Rejected start remains actionable and the server error survives status refresh')
  rejectStart = false; delaySession = true
  await section.getByRole('button', { name: '启动转换', exact: true }).click()
  await waitUntil(() => sessionHeld)
  const beforeSwitch = actionCount
  await page.evaluate(() => document.querySelector('#app').__vue_app__.config.globalProperties.$router.push('/case/17'))
  await page.getByRole('region', { name: '持久DICOM转换作业' }).getByText('此病例暂无准备好的转换作业', { exact: false }).waitFor()
  releaseSession()
  await page.waitForTimeout(500)
  assert.equal(actionCount, beforeSwitch)
  assert.ok(!result.writes.some(item => item.path.includes('/cases/17/conversion-jobs/')))
  assert.deepEqual(result.errors, [])
  result.checks.push('Case switch during session lookup cancels the pending old-case start')
  await page.screenshot({ path: out + '/case-switch.png', fullPage: true })
  result.status = 'passed'
} catch (e) {
  result.status = 'failed'; result.error = e.stack; process.exitCode = 1
  await page.screenshot({ path: out + '/failure.png', fullPage: true }).catch(() => {})
} finally {
  if (releaseSession) releaseSession()
  await fs.writeFile(out + '/validation.json', JSON.stringify(result, null, 2))
  await browser.close()
  console.log(JSON.stringify({ status: result.status, checks: result.checks, error: result.error }))
}
