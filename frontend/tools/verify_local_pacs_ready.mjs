// Actual configured Orthanc + project UI; read-only, no synthetic routing.
import { chromium } from '@playwright/test'
import fs from 'node:fs/promises'
import assert from 'node:assert/strict'
const output = process.argv[2]
if (!output) throw new Error('Provide a fresh E: evidence directory')
const errors = [], writes = []
const browser = await chromium.launch({ headless: true })
try {
  const page = await browser.newPage()
  page.on('pageerror', error => errors.push(error.message))
  await page.route('**/*', async route => {
    if (!['GET', 'HEAD'].includes(route.request().method())) {
      writes.push(route.request().method()); await route.abort(); return
    }
    await route.continue()
  })
  const status = await page.request.get('http://127.0.0.1:8012/pacs/status')
  assert.equal(status.status(), 200)
  const data = (await status.json()).data
  assert.equal(data.state, 'ready')
  assert.equal(data.orthanc_version, '1.13.0')
  assert.equal(data.pixel_read_enabled, false)
  await page.goto('http://127.0.0.1:5179/case/17')
  const panel = page.locator('.pacs-panel')
  await panel.getByRole('button', { name: '查询检查', exact: true }).waitFor()
  const response = page.waitForResponse(r => r.url().includes('/pacs/studies') && r.request().method() === 'GET')
  await panel.getByRole('button', { name: '查询检查', exact: true }).click()
  assert.equal((await response).status(), 200)
  assert.deepEqual(errors, [])
  assert.deepEqual(writes, [])
  await fs.writeFile(output, JSON.stringify({ status: 'passed',
    actual_orthanc_connected: true, authenticated_query: true,
    ui_query_button_visible: true, actual_study_query_http: 200,
    page_errors: errors, writes, pixel_reads_enabled: false,
    real_dicom_import_or_viewer_accepted: false }, null, 2), { flag: 'wx' })
  console.log('Actual PACS + project UI readiness: passed; no data imported.')
} finally { await browser.close() }
