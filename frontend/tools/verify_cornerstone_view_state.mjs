import { chromium } from '@playwright/test'
import fs from 'node:fs/promises'
import assert from 'node:assert/strict'
const [root, mode, tag] = process.argv.slice(2)
if (!root?.startsWith('E:/BrainFusion-Runtime/results/nightly/') || !['save', 'restart'].includes(mode)) throw Error('Run root and mode required')
const state = JSON.parse(await fs.readFile('E:/BrainFusion-Runtime/local/processes.json', 'utf8'))
assert.equal(state.runtime_paths.DATABASE_PATH.replaceAll('\\', '/'), root + '/database-backup/restored-validation.db')
const output = `${root}/browser-view-${mode}${tag ? '-' + tag : ''}`
await fs.mkdir(output)
const browser = await chromium.launch({ headless: true })
const page = await browser.newPage({ viewport: { width: 1600, height: 1100 } })
const result = { status: 'running', pageErrors: [], consoleErrors: [], writes: [], checks: [] }
page.on('pageerror', e => result.pageErrors.push(e.message))
page.on('console', m => { if (m.type() === 'error') result.consoleErrors.push(m.text()) })
await page.route('**/*', async route => {
  const req = route.request()
  if (['POST', 'PUT', 'PATCH', 'DELETE'].includes(req.method())) {
    assert.equal(new URL(req.url()).pathname, '/mri/17/view-state')
    assert.equal(req.method(), 'POST')
    result.writes.push(req.postDataJSON())
  }
  await route.continue()
})
async function inspect() {
  return page.evaluate(async () => {
    const core = await import(performance.getEntriesByType('resource').find(r => /\/\@cornerstonejs_core\.js/.test(r.name)).name)
    return core.getRenderingEngines()[0].getViewports().map(v => ({ camera: v.getCamera(), voi: v.getProperties().voiRange, actors: v.getActors().map(a => a.referencedId) }))
  })
}
async function getSaved() {
  const res = await page.request.get('http://127.0.0.1:8012/mri/17/view-state')
  assert.equal(res.status(), 200)
  return (await res.json()).data.saved
}
async function ready() {
  await page.waitForFunction(() => ['ready', 'error'].includes(document.querySelector('.cs-viewer')?.dataset.state))
  assert.equal(await page.locator('.cs-viewer').getAttribute('data-state'), 'ready', await page.locator('.cs-viewer').innerText())
}
function compare(expected, actual) {
  actual.forEach((v, i) => {
    const view = ['axial', 'sagittal', 'coronal'][i], c = expected.state.cameras[view]
    for (const [camel, snake] of [['focalPoint', 'focal_point'], ['position', 'position'], ['viewPlaneNormal', 'view_plane_normal'], ['viewUp', 'view_up']]) {
      c[snake].forEach((n, j) => assert.ok(Math.abs(n - v.camera[camel][j]) < 1e-3, `${view} ${camel}`))
    }
    assert.ok(Math.abs(c.parallel_scale - v.camera.parallelScale) < 1e-3)
    assert.deepEqual(v.voi, expected.state.window_ranges[expected.state.sequence || 'legacy'][i])
    assert.equal(v.actors.length, expected.state.segmentation_visible ? 2 : 1)
  })
}
try {
  await page.goto('http://127.0.0.1:5179/workstation/17' + (mode === 'restart' ? '?viewer=cornerstone' : ''))
  if (mode === 'save') {
    await page.getByText('Cornerstone3D（迁移验证）', { exact: true }).click()
    await ready()
    await page.locator('.cs-toolbar select').selectOption('t1n')
    await page.waitForFunction(() => document.querySelector('.cs-viewer')?.dataset.sequence === 't1n' && document.querySelector('.cs-viewer')?.dataset.state === 'ready')
    const box = await page.locator('.cs-viewport').first().boundingBox()
    await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2); await page.mouse.wheel(0, 220)
    await page.waitForTimeout(250)
    for (const label of ['平移', '缩放', '窗宽窗位']) {
      await page.getByRole('button', { name: label, exact: true }).click()
      await page.mouse.move(box.x + 160, box.y + 160); await page.mouse.down()
      await page.mouse.move(box.x + 210, box.y + 185, { steps: 10 }); await page.mouse.up()
    }
    await page.getByText('隐藏分割', { exact: true }).click()
    await ready()
    result.beforeSave = await inspect()
    await page.getByRole('button', { name: '保存视图', exact: true }).click()
    await page.getByText(/视图已保存/).waitFor()
    await page.waitForURL('**/workstation/17?viewer=cornerstone')
    const saved = await getSaved()
    assert.equal(saved.current, true)
    assert.equal(saved.state.sequence, 't1n')
    assert.equal(saved.state.segmentation_visible, false)
    compare(saved, result.beforeSave)
    await fs.writeFile(root + '/view-expected.json', JSON.stringify(saved, null, 2))
    result.saved = saved
    await page.screenshot({ path: output + '/saved-view.png', fullPage: true })
    await page.reload()
    await ready()
    assert.equal(await page.locator('.cs-viewer').getAttribute('data-sequence'), 't1n')
    await page.getByText(/已恢复保存视图/).waitFor()
    result.afterRefresh = await inspect()
    compare(saved, result.afterRefresh)
    await page.screenshot({ path: output + '/restored-view.png', fullPage: true })
    result.checks.push('Explicit view save after real sequence/scroll/pan/zoom/window/mask controls; browser refresh restores physical cameras, VOI, sequence and hidden mask')
  } else {
    await ready()
    const expected = JSON.parse(await fs.readFile(root + '/view-expected.json', 'utf8'))
    assert.deepEqual(await getSaved(), expected)
    result.afterRestart = await inspect()
    compare(expected, result.afterRestart)
    assert.equal(await page.locator('.cs-viewer').getAttribute('data-sequence'), 't1n')
    await page.screenshot({ path: output + '/after-restart.png', fullPage: true })
    await page.getByText('Canvas（已验入口）', { exact: true }).click()
    await page.waitForURL('**/workstation/17')
    await page.reload()
    await page.locator('.slice-img').first().waitFor()
    assert.equal(await page.locator('.cs-viewer').count(), 0)
    result.checks.push('Actual service restart restores explicit saved view; explicit Canvas selection clears route preference and refresh stays Canvas')
  }
  assert.deepEqual(result.pageErrors, [])
  assert.deepEqual(result.consoleErrors, [])
  result.status = 'passed'
} catch (e) {
  result.status = 'failed'; result.error = e.stack; process.exitCode = 1
  await page.screenshot({ path: output + '/failure.png', fullPage: true })
} finally {
  await fs.writeFile(output + '/validation.json', JSON.stringify(result, null, 2))
  await browser.close()
}
