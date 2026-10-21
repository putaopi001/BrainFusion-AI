// Real HTTP NIfTI rendering; all business writes are blocked.
import { chromium } from '@playwright/test'
import fs from 'node:fs/promises'
import assert from 'node:assert/strict'
const output = process.argv[2]
if (!output?.startsWith('E:/BrainFusion-Runtime/results/nightly/')) throw Error('Unique evidence directory on E required')
await fs.mkdir(output, { recursive: false })
const browser = await chromium.launch({ headless: true })
const page = await browser.newPage({ viewport: { width: 1600, height: 1000 } })
const result = { status: 'running', pageErrors: [], consoleErrors: [], consoleWarnings: [], writes: [], checks: [] }
const observedEngines = new Set()
async function inspect() {
  const snapshot = await page.evaluate(async () => {
    const url = performance.getEntriesByType('resource').find(r => /\/\@cornerstonejs_core\.js/.test(r.name))?.name
    if (!url) throw Error('Loaded core module URL not found')
    const core = await import(url)
    const engines = core.getRenderingEngines()
    return { cacheBytes: core.cache.getCacheSize(), engines: engines.map(e => ({ id: e.id, viewports: e.getViewports().map(v => ({ id: v.id, volumeIds: v.getAllVolumeIds(), frame: v.getFrameOfReferenceUID(), camera: v.getCamera(), voi: v.getProperties()?.voiRange, actors: v.getActors().map(a => a.uid), actorVolumes: v.getActors().map(a => a.referencedId), centerWorld: v.canvasToWorld([v.element.clientWidth / 2, v.element.clientHeight / 2]) })) })) }
  })
  snapshot.engines.forEach(e => observedEngines.add(e.id))
  return snapshot
}
page.on('pageerror', e => result.pageErrors.push(e.message))
page.on('console', m => { if (m.type() === 'error') result.consoleErrors.push(m.text()); if (m.type() === 'warning') result.consoleWarnings.push(m.text()) })
await page.route('**/*', route => {
  if (['POST', 'PUT', 'PATCH', 'DELETE'].includes(route.request().method())) {
    result.writes.push(route.request().url()); return route.abort()
  }
  return route.continue()
})
try {
  await page.goto('http://127.0.0.1:5179/workstation/17')
  await page.locator('.slice-img').first().waitFor({ timeout: 30000 })
  const started = performance.now()
  await page.getByText('Cornerstone3D（迁移验证）', { exact: true }).click()
  await page.waitForFunction(() => ['ready', 'error'].includes(document.querySelector('.cs-viewer')?.dataset.state), { timeout: 60000 })
  result.loadMs = performance.now() - started
  result.text = await page.locator('.cs-viewer').innerText()
  await page.screenshot({ path: output + '/initial.png', fullPage: true })
  assert.equal(await page.locator('.cs-viewer').getAttribute('data-state'), 'ready', result.text)
  assert.equal(await page.locator('.cs-viewport canvas').count(), 3)
  result.initial = await inspect()
  const viewport = page.locator('.cs-viewport').first(), box = await viewport.boundingBox()
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2)
  await page.mouse.wheel(0, 180)
  await page.waitForTimeout(200)
  result.afterScroll = await inspect()
  assert.notDeepEqual(result.afterScroll.engines[0].viewports[0].camera.focalPoint, result.initial.engines[0].viewports[0].camera.focalPoint)
  const beforeDrag = await inspect()
  await page.mouse.down(); await page.mouse.move(box.x + box.width / 2 + 40, box.y + box.height / 2 + 20, { steps: 10 }); await page.mouse.up()
  const afterDrag = await inspect()
  assert.notDeepEqual(afterDrag.engines[0].viewports[0].voi, beforeDrag.engines[0].viewports[0].voi)
  for (const [label, property] of [['平移', 'focalPoint'], ['缩放', 'parallelScale']]) {
    await page.getByRole('button', { name: label, exact: true }).click()
    const before = await inspect()
    await page.mouse.move(box.x + 160, box.y + 180); await page.mouse.down()
    await page.mouse.move(box.x + 200, box.y + 230, { steps: 10 }); await page.mouse.up()
    const after = await inspect()
    assert.notDeepEqual(after.engines[0].viewports[0].camera[property], before.engines[0].viewports[0].camera[property])
  }
  result.checks.push('Real mouse wheel, window/level, pan and zoom change viewport state')
  await page.getByRole('button', { name: '重置视图', exact: true }).click()
  await page.getByRole('button', { name: '十字线', exact: true }).click()
  await page.waitForTimeout(400)
  const beforeCrosshair = await inspect()
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2)
  await page.mouse.down()
  await page.mouse.move(box.x + box.width * .65, box.y + box.height * .6, { steps: 12 })
  await page.mouse.up()
  await page.waitForTimeout(200)
  const afterCrosshair = await inspect()
  result.crosshair = { before: beforeCrosshair, after: afterCrosshair }
  assert.notDeepEqual(afterCrosshair.engines[0].viewports.map(v => v.camera.focalPoint), beforeCrosshair.engines[0].viewports.map(v => v.camera.focalPoint))
  result.checks.push('Crosshair center drag changes linked planes')
  const beforeSwitch = await inspect()
  for (const key of ['t1c', 't1n', 't2w', 't2f']) {
    await page.locator('.cs-toolbar select').selectOption(key)
    await page.waitForFunction(k => document.querySelector('.cs-viewer')?.dataset.sequence === k && document.querySelector('.cs-viewer')?.dataset.state === 'ready', key)
    await page.screenshot({ path: `${output}/${key}.png`, fullPage: true })
    result.checks.push(`Actual sequence ${key} loaded`)
    const current = await inspect()
    current.engines[0].viewports.forEach((v, i) => {
      for (const property of ['focalPoint', 'position', 'parallelScale', 'viewUp', 'viewPlaneNormal']) assert.deepEqual(v.camera[property], beforeSwitch.engines[0].viewports[i].camera[property])
      assert.equal(v.actors.length, 2, 'MRI plus read-only labelmap must stay attached')
    })
  }
  const reference = JSON.parse(await fs.readFile(process.argv[3], 'utf8'))
  const point = reference.records.find(r => r.name === 'mask').points.at(-1)
  result.nonemptyMaskPoint = point
  await page.getByRole('button', { name: '窗宽窗位', exact: true }).click()
  await page.evaluate(async point => {
    const core = await import(performance.getEntriesByType('resource').find(r => /\/\@cornerstonejs_core\.js/.test(r.name)).name)
    const engine = core.getRenderingEngines()[0]
    for (const v of engine.getViewports()) {
      const camera = v.getCamera(), normal = camera.viewPlaneNormal
      const distance = point.lps.reduce((s, n, i) => s + (n - camera.focalPoint[i]) * normal[i], 0)
      const delta = normal.map(n => n * distance)
      v.setCamera({ focalPoint: camera.focalPoint.map((n, i) => n + delta[i]), position: camera.position.map((n, i) => n + delta[i]) })
    }
    engine.render()
  }, point)
  await page.waitForTimeout(250)
  const visibleMask = await page.locator('.cs-grid').screenshot({ path: output + '/nonempty-overlay.png' })
  await page.getByText('隐藏分割', { exact: true }).click()
  await page.waitForFunction(() => document.querySelector('.cs-viewer')?.dataset.state === 'ready')
  await page.waitForTimeout(250)
  const hiddenState = await inspect()
  hiddenState.engines[0].viewports.forEach(v => {
    assert.equal(v.actors.length, 1, 'Hidden segmentation must remove the entire mask actor')
    assert.equal(v.actorVolumes.length, 1)
    assert.ok(!v.actorVolumes[0].endsWith('-mask'))
  })
  const hiddenMask = await page.locator('.cs-grid').screenshot({ path: output + '/overlay-hidden.png' })
  assert.notDeepEqual(visibleMask, hiddenMask, 'Nonempty mask toggle must change actual pixels')
  await page.getByText('显示分割', { exact: true }).click()
  await page.waitForFunction(() => document.querySelector('.cs-viewer')?.dataset.state === 'ready')
  ;(await inspect()).engines[0].viewports.forEach(v => assert.equal(v.actors.length, 2))
  await page.getByText('Canvas（已验入口）', { exact: true }).click()
  await page.locator('.slice-img').first().waitFor()
  result.afterUnmount = await inspect()
  assert.deepEqual(result.afterUnmount.engines, [])
  assert.equal(result.afterUnmount.cacheBytes, 0)
  await page.getByText('Cornerstone3D（迁移验证）', { exact: true }).click()
  await page.waitForFunction(() => document.querySelector('.cs-viewer')?.dataset.state === 'ready')
  result.checks.push('Explicit Canvas switch and Cornerstone remount')
  await inspect()
  await page.reload()
  await page.locator('.slice-img').first().waitFor()
  assert.equal(await page.locator('.cs-viewer').count(), 0, 'Default remains the accepted Canvas entry')
  await page.getByText('Cornerstone3D（迁移验证）', { exact: true }).click()
  await page.waitForFunction(() => document.querySelector('.cs-viewer')?.dataset.state === 'ready')
  await inspect()
  await page.route('**/mri/17/volume?sequence=t1c', route => route.fulfill({ status: 422, contentType: 'application/json', body: JSON.stringify({ detail: 'TEST ONLY: incompatible affine' }) }))
  await page.locator('.cs-toolbar select').selectOption('t1c')
  await page.locator('.cs-error').waitFor()
  assert.match(await page.locator('.cs-error').innerText(), /incompatible affine/)
  assert.equal(await page.locator('.slice-img').count(), 0, 'No silent Canvas fallback')
  await page.screenshot({ path: output + '/explicit-error.png', fullPage: true })
  result.checks.push('Controlled rejection is explicit; no silent fallback; refresh defaults to Canvas')
  await page.unroute('**/mri/17/volume?sequence=t1c')
  await page.getByText('Canvas（已验入口）', { exact: true }).click()
  await page.locator('.slice-img').first().waitFor()
  let releaseRequest, requestSeen
  const heldRequest = new Promise(resolve => { releaseRequest = resolve })
  const seenRequest = new Promise(resolve => { requestSeen = resolve })
  await page.route('**/mri/17/nifti?**', async route => {
    requestSeen()
    await heldRequest
    await route.abort()
  })
  await page.getByText('Cornerstone3D（迁移验证）', { exact: true }).click()
  await Promise.race([seenRequest, new Promise((_, reject) => setTimeout(() => reject(Error('No NIfTI request observed')), 10000))])
  await inspect()
  await page.getByText('Canvas（已验入口）', { exact: true }).click()
  releaseRequest()
  await page.waitForTimeout(250)
  const cancelled = await inspect()
  assert.deepEqual(cancelled.engines, [])
  assert.equal(cancelled.cacheBytes, 0)
  await page.unroute('**/mri/17/nifti?**')
  await page.getByText('Cornerstone3D（迁移验证）', { exact: true }).click()
  await page.waitForFunction(() => document.querySelector('.cs-viewer')?.dataset.state === 'ready')
  await inspect()
  await page.getByRole('button', { name: '返回病例详情', exact: true }).click()
  await page.waitForURL('**/case/17')
  const exited = await inspect()
  assert.deepEqual(exited.engines, [])
  assert.equal(exited.cacheBytes, 0)
  result.checks.push('Controlled pending fetch cancellation, subsequent reopen, and SPA route exit clean engine/cache')
  assert.deepEqual(result.pageErrors, [])
  assert.ok(result.consoleErrors.every(s => /422/.test(s)), JSON.stringify(result.consoleErrors))
  // WEBGL_lose_context emits the library warning after an intentional teardown.
  // Allow only owned, observed, now-destroyed engines; context exhaustion fails.
  assert.ok(result.consoleWarnings.every(s => {
    const match = s.match(/^CornerstoneRender: WebGL context lost \(renderingEngine=(bf-cs-[a-f0-9-]+), context=0\)$/)
    return match && observedEngines.has(match[1]) && !exited.engines.some(e => e.id === match[1])
  }), JSON.stringify(result.consoleWarnings))
  result.expectedTeardownWarnings = result.consoleWarnings.length
  assert.deepEqual(result.writes, [])
  result.status = 'passed'
} catch (e) {
  result.status = 'failed'; result.error = e.stack
  await page.screenshot({ path: output + '/failure.png', fullPage: true })
  process.exitCode = 1
} finally {
  await fs.writeFile(output + '/validation.json', JSON.stringify(result, null, 2))
  await browser.close()
}
