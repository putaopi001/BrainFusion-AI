import { chromium } from '@playwright/test'
import fs from 'node:fs/promises'
import assert from 'node:assert/strict'
const root = process.argv[2]
const state = JSON.parse(await fs.readFile('E:/BrainFusion-Runtime/local/processes.json', 'utf8'))
assert.equal(state.runtime_paths.DATABASE_PATH.replaceAll('\\', '/'), root + '/database-backup/restored-validation.db')
const output = root + '/browser-measurement-lifecycle'
await fs.mkdir(output)
const browser = await chromium.launch({ headless: true })
const page = await browser.newPage({ viewport: { width: 1600, height: 1100 } })
const result = { status: 'running', pageErrors: [], checks: [], controlledWrites: [] }
page.on('pageerror', e => result.pageErrors.push(e.message))
await page.route('**/*', async route => {
  if (['POST', 'PUT', 'PATCH', 'DELETE'].includes(route.request().method())) throw Error('No business writes expected in lifecycle probe')
  await route.continue()
})
async function ready(sequence) {
  await page.waitForFunction(() => ['ready', 'error'].includes(document.querySelector('.cs-viewer')?.dataset.state))
  assert.equal(await page.locator('.cs-viewer').getAttribute('data-state'), 'ready', await page.locator('.cs-viewer').innerText())
  if (sequence) assert.equal(await page.locator('.cs-viewer').getAttribute('data-sequence'), sequence)
}
async function inspect() {
  return page.evaluate(async () => {
    const core = await import(performance.getEntriesByType('resource').find(r => /\/\@cornerstonejs_core\.js/.test(r.name)).name)
    const tools = await import(performance.getEntriesByType('resource').find(r => /\/\@cornerstonejs_tools\.js/.test(r.name)).name)
    return { engines: core.getRenderingEngines().map(e => e.id), cacheBytes: core.cache.getCacheSize(), lengths: tools.annotation.state.getAllAnnotations().filter(a => a.metadata.toolName === 'Length').length }
  })
}
async function startDrawing(complete) {
  await page.getByRole('button', { name: '距离测量', exact: true }).click()
  const box = await page.locator('.cs-viewport').first().boundingBox()
  await page.mouse.move(box.x + box.width * .4, box.y + box.height * .4)
  await page.mouse.down()
  if (complete) await page.mouse.move(box.x + box.width * .48, box.y + box.height * .44, { steps: 8 })
  await page.mouse.up()
}
try {
  await page.goto('http://127.0.0.1:5179/workstation/17?viewer=cornerstone')
  await ready('t1n')
  assert.equal((await inspect()).lengths, 0)
  await startDrawing(false)
  await page.getByText('正在绘制测量；按 Esc 取消。', { exact: true }).waitFor()
  assert.equal(await page.locator('.cs-toolbar select').isDisabled(), true)
  assert.equal(await page.getByRole('button', { name: '重置视图', exact: true }).isDisabled(), true)
  await page.keyboard.press('Escape')
  assert.equal((await inspect()).lengths, 0)
  assert.equal(await page.locator('.cs-toolbar select').isDisabled(), false)
  await startDrawing(true)
  await page.locator('.cs-measurement-row').waitFor()
  const before = await inspect()
  assert.equal(before.lengths, 1)
  await page.route('**/mri/17/measurements', async route => {
    if (route.request().method() === 'POST') {
      result.controlledWrites.push(route.request().postDataJSON())
      await route.fulfill({ status: 409, contentType: 'application/json', body: JSON.stringify({ detail: 'TEST ONLY: analysis version changed' }) })
    } else await route.fallback()
  })
  await page.getByRole('button', { name: '保存测量', exact: true }).click()
  await page.getByText(/保存失败.*analysis version changed/).waitFor()
  assert.equal(await page.locator('.cs-measurement-row[data-saved-id=""]').count(), 1)
  result.checks.push('Single-click incomplete draw Esc cancellation clears tools; controlled stale save keeps an unsaved draft with explicit message')
  // Same Vue route component changes case ID; not a full document navigation.
  await page.evaluate(async () => { const { default: router } = await import('/src/router/index.js'); await router.push('/workstation/1?viewer=cornerstone') })
  await page.waitForURL('**/workstation/1?viewer=cornerstone')
  await ready('t2f')
  const other = await inspect()
  assert.equal(other.lengths, 0)
  assert.equal(other.engines.length, 1)
  assert.notEqual(other.engines[0], before.engines[0])
  assert.equal(await page.locator('.cs-measurement-row').count(), 0)
  await page.screenshot({ path: output + '/other-real-case.png', fullPage: true })
  await page.evaluate(async () => { const { default: router } = await import('/src/router/index.js'); await router.push('/workstation/17?viewer=cornerstone') })
  await page.waitForURL('**/workstation/17?viewer=cornerstone')
  await ready('t1n')
  assert.equal((await inspect()).lengths, 0)
  await page.getByText(/已恢复保存视图/).waitFor()
  result.checks.push('Real case17 -> case1 -> case17 via same SPA route clears frame, draft and engine; each case restores only its own view')
  const saved = (await (await page.request.get('http://127.0.0.1:8012/mri/17/view-state')).json()).data.saved
  await page.route('**/mri/17/view-state', route => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ data: { context: saved.context, saved: { ...saved, current: false } } }) }))
  await page.reload()
  await ready('t2f')
  await page.getByText('旧视图属于其他影像或分析版本，当前按默认视图打开。', { exact: true }).waitFor()
  await page.screenshot({ path: output + '/stale-view-rejected.png', fullPage: true })
  result.checks.push('Controlled old-version view is explicitly rejected; default original space opens; backend tests cover actual version changes')
  assert.deepEqual(result.pageErrors, [])
  result.status = 'passed'
} catch (e) {
  result.status = 'failed'; result.error = e.stack; process.exitCode = 1
  await page.screenshot({ path: output + '/failure.png', fullPage: true })
} finally {
  await fs.writeFile(output + '/validation.json', JSON.stringify(result, null, 2))
  await browser.close()
}
