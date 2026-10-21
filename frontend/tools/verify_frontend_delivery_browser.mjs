// Real production assets in browser-only routing against existing read-only API.
// No second frontend/backend service or dataset/model writes.
import { chromium } from '@playwright/test'
import fs from 'node:fs/promises'
import path from 'node:path'
import crypto from 'node:crypto'
import assert from 'node:assert/strict'

const root = process.env.BRAINFUSION_RUN_ROOT
assert(root?.startsWith('E:/BrainFusion-Runtime/results/nightly/'))
const build = JSON.parse(await fs.readFile(`${root}/api-bound-build/validation.json`, 'utf8'))
assert.equal(build.status, 'passed_build_bound_to_actual_api_not_browser_or_server_deployment')
const label = process.env.BRAINFUSION_BROWSER_LABEL || 'frontend-browser'
assert(/^[a-z0-9-]+$/.test(label))
const output = `${root}/${label}`
await fs.mkdir(output)
const files = new Map(build.build_files.map(item => [item.path, item]))
const served = new Set()
const realHttp = process.env.BRAINFUSION_REAL_HTTP === '1'
const browser = await chromium.launch({ headless: true })
const page = await browser.newPage({ viewport: { width: 1600, height: 1200 }, serviceWorkers: 'block' })
const result = { status: 'running', real_http_preview: realHttp, pageErrors: [], consoleErrors: [], failedRequests: [], apiResponses: [], blockedWrites: [], checks: [], api_base: build.api_base, scope: realHttp ? 'Real HTTP Vite build preview on sole frontend port, unchanged real backend GETs. No browser security flags or permissions bypass, no new-machine/container or inference acceptance.' : 'Isolated real built assets via browser routing at existing frontend origin, real unchanged backend GETs. Not a newly deployed production HTTP server, new-machine installation or new inference.' }
page.on('pageerror', error => result.pageErrors.push(error.message))
page.on('console', event => { if (event.type() === 'error') result.consoleErrors.push(event.text()) })
page.on('requestfailed', request => result.failedRequests.push({ path: new URL(request.url()).pathname, error: request.failure()?.errorText }))
page.on('response', response => { if (response.url().startsWith(build.api_base)) result.apiResponses.push({ path: new URL(response.url()).pathname, status: response.status() }) })
await page.route('**/*', async route => {
  const request = route.request(), url = new URL(request.url())
  if (!['GET', 'HEAD'].includes(request.method())) {
    result.blockedWrites.push({ method: request.method(), path: url.pathname })
    return route.abort()
  }
  if (realHttp) return route.continue()
  if (url.origin !== 'http://127.0.0.1:5179') return route.continue()
  let relative = decodeURIComponent(url.pathname).replace(/^\/+/, '')
  if (!files.has(relative)) {
    assert(!url.pathname.startsWith('/assets/'), 'Missing production asset')
    assert(!url.pathname.startsWith('/src/'), 'Development asset requested')
    relative = 'index.html'
  }
  const item = files.get(relative)
  assert(item)
  const body = await fs.readFile(path.join(build.dist, relative))
  assert.equal(crypto.createHash('sha256').update(body).digest('hex'), item.sha256)
  served.add(relative)
  const extension = path.extname(relative)
  const mime = { '.html': 'text/html; charset=utf-8', '.js': 'application/javascript; charset=utf-8', '.css': 'text/css', '.ico': 'image/x-icon', '.png': 'image/png', '.svg': 'image/svg+xml', '.woff2': 'font/woff2' }
  return route.fulfill({ status: 200, contentType: mime[extension] || 'application/octet-stream', body })
})
try {
  if (realHttp) {
    for (const name of ['index.html', ...files.keys()].filter((name, index, values) => values.indexOf(name) === index)) {
      const response = await page.request.get(`http://127.0.0.1:5179/${name}`)
      assert.equal(response.status(), 200)
      assert.equal(crypto.createHash('sha256').update(await response.body()).digest('hex'), files.get(name).sha256)
      served.add(name)
    }
  }
  const reply = await page.request.get(`${build.api_base}/research/cases/17/features`)
  assert.equal(reply.status(), 200)
  const feature = (await reply.json()).data
  assert.equal(feature.id, 'c913b7963dbe4d9e8014ea6487069946')
  assert.equal(feature.analysis_run_id, 'a3ab2210c797490e960a9b6107fd61c8')
  result.feature_job_id = feature.id
  result.analysis_run_id = feature.analysis_run_id
  await page.goto('http://127.0.0.1:5179/case/17')
  await page.getByText(feature.analysis_run_id, { exact: false }).first().waitFor()
  await page.waitForFunction(() => document.querySelectorAll('.slice-img').length === 3 && [...document.querySelectorAll('.slice-img')].every(image => image.complete && image.naturalWidth > 0))
  await page.screenshot({ path: `${output}/case17-built.png`, fullPage: true, animations: 'disabled' })
  result.checks.push('Production build case binds saved real analysis and three MRI views')
  await page.goto('http://127.0.0.1:5179/workstation/17')
  await page.waitForFunction(() => document.querySelectorAll('.slice-img').length === 3 && [...document.querySelectorAll('.slice-img')].every(image => image.complete && image.naturalWidth > 0))
  await page.getByRole('button', { name: 'AI分割叠加', exact: true }).click()
  for (const [label, sequence] of [['T1c · 增强 T1', 't1c'], ['T1n · 平扫 T1', 't1n'], ['T2w · T2', 't2w'], ['FLAIR', 't2f']]) {
    await page.locator('.mri-sequence-select').click()
    await page.getByRole('option', { name: label, exact: true }).click()
    await page.waitForFunction(sequence => {
      const images = [...document.querySelectorAll('.slice-img')], masks = [...document.querySelectorAll('.mask-img')]
      return document.querySelector('.current-sequence')?.dataset.sequence === sequence && images.length === 3 && masks.length === 3 && images.every(image => image.complete && image.naturalWidth > 0 && new URL(image.src).searchParams.get('sequence') === sequence) && masks.every(image => image.complete && image.naturalWidth > 0)
    }, sequence)
    await page.getByRole('option', { name: label, exact: true }).waitFor({ state: 'hidden' })
  }
  await page.screenshot({ path: `${output}/four-sequence-built.png`, fullPage: true })
  result.checks.push('All four real sequence identities / MRI and mask images render; existing accepted spatial contract unchanged, no registration or new mask')
  await page.goto('http://127.0.0.1:5179/research?case_id=17')
  await page.locator('.automatic-result').waitFor()
  await page.locator('.automatic-result').scrollIntoViewIfNeeded()
  assert.equal(await page.locator('.feature-state').getAttribute('data-job-id'), feature.id)
  await page.screenshot({ path: `${output}/research-built.png`, fullPage: true })
  result.checks.push('Saved automatic feature task/clinical/research versions render without extraction')
  await page.goto('http://127.0.0.1:5179/report?case_id=17')
  const report = page.locator('#report-paper')
  await report.waitFor()
  assert((await report.innerText()).includes(feature.analysis_run_id))
  assert.equal(await page.getByRole('button', { name: '导出 PDF', exact: true }).isEnabled(), true)
  await report.screenshot({ path: `${output}/report-built.png`, animations: 'disabled' })
  result.checks.push('Actual built report binds saved analysis and independent opinion; PDF entry only, not new PDF')
  assert.deepEqual(result.pageErrors, [])
  assert.deepEqual(result.blockedWrites, [])
  assert([...served].some(name => name.endsWith('.js')))
  assert([...served].some(name => name.endsWith('.css')))
  result.status = 'passed'
} catch (error) {
  result.status = 'failed'; result.error = String(error)
  await page.screenshot({ path: `${output}/failure.png`, fullPage: true })
  throw error
} finally {
  result.served_built_assets = [...served].map(name => files.get(name))
  await fs.writeFile(`${output}/validation.json`, JSON.stringify(result, null, 2))
  await browser.close()
}
console.log(JSON.stringify(result))
