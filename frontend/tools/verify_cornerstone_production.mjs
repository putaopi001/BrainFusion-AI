// Read-only production HTTP verification, including an unsaved local measurement.
import { chromium } from '@playwright/test'
import fs from 'node:fs/promises'
import assert from 'node:assert/strict'
const root = process.argv[2]
const state = JSON.parse(await fs.readFile('E:/BrainFusion-Runtime/local/processes.json', 'utf8'))
assert.equal(state.frontend_mode, 'preview')
assert.ok(state.frontend_preview_dist.replaceAll('\\', '/').startsWith(root + '/preview-frontend/'))
const output = root + '/browser-production'
await fs.mkdir(output)
const browser = await chromium.launch({ headless: true })
const page = await browser.newPage({ viewport: { width: 1600, height: 1100 } })
const result = { status: 'running', pageErrors: [], consoleErrors: [], writes: [], checks: [] }
page.on('pageerror', e => result.pageErrors.push(e.message))
page.on('console', m => { if (m.type() === 'error') result.consoleErrors.push(m.text()) })
await page.route('**/*', async route => {
  if (['POST', 'PUT', 'PATCH', 'DELETE'].includes(route.request().method())) { result.writes.push(route.request().url()); await route.abort() }
  else await route.continue()
})
async function ready() {
  await page.waitForFunction(() => ['ready', 'error'].includes(document.querySelector('.cs-viewer')?.dataset.state))
  assert.equal(await page.locator('.cs-viewer').getAttribute('data-state'), 'ready', await page.locator('.cs-viewer').innerText())
}
try {
  await page.goto('http://127.0.0.1:5179/workstation/17?viewer=cornerstone')
  await ready()
  assert.equal(await page.locator('.cs-viewport canvas').count(), 3)
  for (const key of ['t1c', 't1n', 't2w', 't2f']) {
    await page.locator('.cs-toolbar select').selectOption(key)
    await page.waitForFunction(k => document.querySelector('.cs-viewer')?.dataset.sequence === k && document.querySelector('.cs-viewer')?.dataset.state === 'ready', key)
  }
  const expected = [{ top: 'A', bottom: 'P', left: 'R', right: 'L' }, { top: 'S', bottom: 'I', left: 'A', right: 'P' }, { top: 'S', bottom: 'I', left: 'R', right: 'L' }]
  for (let i = 0; i < 3; i++) for (const [side, label] of Object.entries(expected[i])) assert.equal(await page.locator('.cs-viewport').nth(i).locator(`[data-side="${side}"]`).innerText(), label)
  await page.getByRole('button', { name: '距离测量', exact: true }).click()
  const box = await page.locator('.cs-viewport').first().boundingBox()
  await page.mouse.move(box.x + 175, box.y + 170); await page.mouse.down(); await page.mouse.move(box.x + 225, box.y + 200, { steps: 10 }); await page.mouse.up()
  await page.locator('.cs-measurement-row').waitFor()
  assert.match(await page.locator('.cs-measurement-row').innerText(), /\d+\.\d+ mm.*未保存/)
  await page.screenshot({ path: output + '/real-case-measurement.png', fullPage: true })
  await page.getByRole('button', { name: '删除测量', exact: true }).click()
  await page.waitForFunction(() => !document.querySelector('.cs-measurement-row'))
  await page.getByText('Canvas（已验入口）', { exact: true }).click()
  await page.locator('.slice-img').first().waitFor()
  await page.getByText('Cornerstone3D（迁移验证）', { exact: true }).click()
  await ready()
  await page.screenshot({ path: output + '/production-workstation.png', fullPage: true })
  assert.deepEqual(result.pageErrors, [])
  assert.deepEqual(result.consoleErrors, [])
  assert.deepEqual(result.writes, [])
  const measurement = (await (await page.request.get('http://127.0.0.1:8012/mri/17/measurements')).json()).data
  const view = (await (await page.request.get('http://127.0.0.1:8012/mri/17/view-state')).json()).data
  assert.equal(measurement.items.length, 0)
  assert.equal(view.saved, null)
  result.checks.push('Final build real HTTP, 4 real sequences, 3 canvas and 12 direction labels, unsaved LengthTool mm, explicit Canvas switch/reopen; original new tables remain empty')
  result.status = 'passed'
} catch (e) {
  result.status = 'failed'; result.error = e.stack; process.exitCode = 1
  await page.screenshot({ path: output + '/failure.png', fullPage: true })
} finally {
  await fs.writeFile(output + '/validation.json', JSON.stringify(result, null, 2))
  await browser.close()
}
