// Authorized business writes are confined to this run's database copy.
import { chromium } from '@playwright/test'
import fs from 'node:fs/promises'
import assert from 'node:assert/strict'
const [root, mode, tag] = process.argv.slice(2)
if (!root?.startsWith('E:/BrainFusion-Runtime/results/nightly/') || !['create', 'restart'].includes(mode)) throw Error('Run root and create/restart mode required')
const state = JSON.parse(await fs.readFile('E:/BrainFusion-Runtime/local/processes.json', 'utf8'))
assert.equal(state.runtime_paths.DATABASE_PATH.replaceAll('\\', '/'), root + '/database-backup/restored-validation.db', 'Browser writes require this run isolated DB')
const output = root + '/browser-measurements-' + mode + (tag ? '-' + tag : '')
await fs.mkdir(output)
const browser = await chromium.launch({ headless: true })
const page = await browser.newPage({ viewport: { width: 1600, height: 1100 } })
const result = { status: 'running', mode, pageErrors: [], consoleErrors: [], consoleWarnings: [], writes: [], checks: [] }
page.on('pageerror', e => result.pageErrors.push(e.message))
page.on('console', m => { if (m.type() === 'error') result.consoleErrors.push(m.text()); if (m.type() === 'warning') result.consoleWarnings.push(m.text()) })
await page.route('**/*', async route => {
  const req = route.request()
  if (['POST', 'PUT', 'PATCH', 'DELETE'].includes(req.method())) {
    const url = new URL(req.url())
    assert.match(url.pathname, /^\/mri\/17\/measurements(?:\/\d+)?$/)
    result.writes.push({ method: req.method(), path: url.pathname, body: req.postDataJSON() })
  }
  await route.continue()
})
async function coreInspect() {
  return page.evaluate(async () => {
    const core = await import(performance.getEntriesByType('resource').find(r => /\/\@cornerstonejs_core\.js/.test(r.name)).name)
    const tools = await import(performance.getEntriesByType('resource').find(r => /\/\@cornerstonejs_tools\.js/.test(r.name)).name)
    const engine = core.getRenderingEngines()[0]
    return { engineId: engine?.id, annotations: tools.annotation.state.getAllAnnotations().filter(a => a.metadata.toolName === 'Length').map(a => ({ uid: a.annotationUID, points: a.data.handles.points, normal: a.metadata.viewPlaneNormal, locked: tools.annotation.locking.isAnnotationLocked(a.annotationUID), stats: a.data.cachedStats })) }
  })
}
async function measurements() {
  const res = await page.request.get('http://127.0.0.1:8012/mri/17/measurements')
  assert.equal(res.status(), 200)
  return (await res.json()).data
}
async function open() {
  await page.goto('http://127.0.0.1:5179/workstation/17')
  await page.getByText('Cornerstone3D（迁移验证）', { exact: true }).click()
  await page.waitForFunction(() => ['ready', 'error'].includes(document.querySelector('.cs-viewer')?.dataset.state))
  assert.equal(await page.locator('.cs-viewer').getAttribute('data-state'), 'ready', await page.locator('.cs-viewer').innerText())
}
function almostPoint(a, b) { a.forEach((v, i) => assert.ok(Math.abs(v - b[i]) < 1e-3, `${a} != ${b}`)) }
try {
  const oldCanvas = await (await page.request.get('http://127.0.0.1:8012/mri/17/annotations')).json()
  await open()
  if (mode === 'create') {
    assert.equal((await measurements()).items.length, 0)
    const expected = []
    let loseResponse = true
    await page.route('**/mri/17/measurements', async route => {
      if (route.request().method() === 'POST' && loseResponse) {
        loseResponse = false
        const response = await route.fetch()
        assert.equal(response.status(), 200, await response.text())
        result.committedLostResponse = await response.json()
        await route.abort()
      } else await route.fallback()
    })
    for (let index = 0; index < 3; index++) {
      await page.getByRole('button', { name: '距离测量', exact: true }).click()
      const box = await page.locator('.cs-viewport').nth(index).boundingBox()
      const start = [Math.round(box.x + box.width * .43), Math.round(box.y + box.height * .48)]
      const end = [Math.round(box.x + box.width * .56), start[1] + 24]
      const world = await page.evaluate(async ({ index, local }) => {
        const core = await import(performance.getEntriesByType('resource').find(r => /\/\@cornerstonejs_core\.js/.test(r.name)).name)
        const viewport = core.getRenderingEngines()[0].getViewports()[index]
        return local.map(p => viewport.canvasToWorld(p))
      }, { index, local: [start, end].map(p => [p[0] - box.x, p[1] - box.y]) })
      await page.mouse.move(...start); await page.mouse.down(); await page.mouse.move(...end, { steps: 12 }); await page.mouse.up()
      await page.waitForFunction(n => document.querySelectorAll('.cs-measurement-row').length === n, index + 1)
      await page.getByRole('button', { name: '保存测量', exact: true }).click()
      if (index === 0) {
        await page.getByText(/保存失败/).waitFor()
        assert.equal((await measurements()).items.length, 1, 'First save committed despite lost response')
        assert.equal(await page.locator('.cs-measurement-row[data-saved-id=""]').count(), 1)
        await page.getByRole('button', { name: '保存测量', exact: true }).click()
      }
      await page.waitForFunction(n => document.querySelectorAll('.cs-measurement-row:not([data-saved-id=""])').length === n, index + 1)
      const current = await measurements()
      assert.equal(current.items.length, index + 1)
      const item = current.items.at(-1)
      almostPoint(item.points_lps[0], world[0]); almostPoint(item.points_lps[1], world[1])
      const distance = Math.hypot(...world[1].map((v, i) => v - world[0][i]))
      assert.ok(Math.abs(item.length_mm - distance) < 1e-3)
      expected.push(item)
    }
    await page.waitForTimeout(400)
    const inspection = await coreInspect()
    assert.equal(inspection.annotations.length, 3)
    for (const a of inspection.annotations) {
      assert.equal(a.locked, true)
      const values = Object.values(a.stats || {})
      assert.ok(values.some(s => s.unit === 'mm' && Math.abs(s.length - Math.hypot(...a.points[1].map((v, i) => v - a.points[0][i]))) < 1e-3), JSON.stringify(a))
    }
    result.created = expected
    result.checks.push('Real mouse LengthTool on 3 planes; independent canvasToWorld distance and tool mm agree; lost-response retry deduplicates')
    await fs.writeFile(root + '/measurement-expected.json', JSON.stringify(expected, null, 2))
    await page.screenshot({ path: output + '/saved-three-planes.png', fullPage: true })
    await page.locator('.cs-toolbar select').selectOption('t1n')
    await page.waitForFunction(() => document.querySelector('.cs-viewer')?.dataset.state === 'ready' && document.querySelector('.cs-viewer')?.dataset.sequence === 't1n')
    assert.deepEqual((await measurements()).items, expected)
    await page.reload()
    await page.getByText('Cornerstone3D（迁移验证）', { exact: true }).click()
    await page.waitForFunction(() => document.querySelector('.cs-viewer')?.dataset.state === 'ready')
    assert.equal(await page.locator('.cs-measurement-row').count(), 3)
    result.reloaded = await coreInspect()
    assert.equal(result.reloaded.annotations.length, 3)
    for (const item of expected) assert.ok(result.reloaded.annotations.some(a => JSON.stringify(a.points) === JSON.stringify(item.points_lps) && a.locked))
    await page.screenshot({ path: output + '/after-refresh.png', fullPage: true })
    result.checks.push('Sequence change and browser refresh preserve 3 saved world-coordinate records and locked overlays')
  } else {
    const expected = JSON.parse(await fs.readFile(root + '/measurement-expected.json', 'utf8'))
    assert.deepEqual((await measurements()).items, expected)
    result.afterRestart = await coreInspect()
    assert.equal(result.afterRestart.annotations.length, 3)
    await page.screenshot({ path: output + '/after-service-restart.png', fullPage: true })
    for (const item of expected) {
      await page.locator(`.cs-measurement-row[data-saved-id="${item.id}"]`).getByRole('button', { name: '删除测量' }).click()
      await page.waitForFunction(id => !document.querySelector(`.cs-measurement-row[data-saved-id="${id}"]`), item.id)
    }
    assert.equal((await measurements()).items.length, 0)
    assert.equal((await coreInspect()).annotations.length, 0)
    await page.reload()
    await page.getByText('Cornerstone3D（迁移验证）', { exact: true }).click()
    await page.waitForFunction(() => document.querySelector('.cs-viewer')?.dataset.state === 'ready')
    assert.equal(await page.locator('.cs-measurement-row').count(), 0)
    await page.screenshot({ path: output + '/after-delete-refresh.png', fullPage: true })
    result.checks.push('Actual backend/frontend restart preserves world measurements; UI delete and refresh remove all 3')
  }
  assert.deepEqual(await (await page.request.get('http://127.0.0.1:8012/mri/17/annotations')).json(), oldCanvas)
  assert.deepEqual(result.pageErrors, [])
  assert.ok(result.consoleErrors.every(s => /net::ERR_FAILED/.test(s)), JSON.stringify(result.consoleErrors))
  assert.ok(result.consoleWarnings.every(s => /^CornerstoneRender: WebGL context lost/.test(s)), JSON.stringify(result.consoleWarnings))
  result.status = 'passed'
} catch (e) {
  result.status = 'failed'; result.error = e.stack
  await page.screenshot({ path: output + '/failure.png', fullPage: true })
  process.exitCode = 1
} finally {
  await fs.writeFile(output + '/validation.json', JSON.stringify(result, null, 2))
  await browser.close()
}
