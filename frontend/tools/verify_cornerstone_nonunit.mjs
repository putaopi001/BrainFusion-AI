import { chromium } from '@playwright/test'
import fs from 'node:fs/promises'
import assert from 'node:assert/strict'
const root = process.argv[2]
const state = JSON.parse(await fs.readFile('E:/BrainFusion-Runtime/local/processes.json', 'utf8'))
assert.equal(state.runtime_paths.DATABASE_PATH.replaceAll('\\', '/'), root + '/database-backup/restored-validation.db')
const fixture = JSON.parse(await fs.readFile(root + '/nonunit-fixture.json', 'utf8'))
const output = root + '/browser-nonunit'
await fs.mkdir(output)
const browser = await chromium.launch({ headless: true })
const page = await browser.newPage({ viewport: { width: 1600, height: 1100 } })
const result = { status: 'running', pageErrors: [], writes: [], scope: fixture.scope }
page.on('pageerror', e => result.pageErrors.push(e.message))
await page.route('**/*', async route => {
  const req = route.request()
  if (['POST', 'PUT', 'PATCH', 'DELETE'].includes(req.method())) {
    assert.match(new URL(req.url()).pathname, new RegExp(`^/mri/${fixture.case_id}/measurements(?:/\\d+)?$`))
    result.writes.push({ method: req.method(), path: new URL(req.url()).pathname })
  }
  await route.continue()
})
try {
  await page.goto(`http://127.0.0.1:5179/workstation/${fixture.case_id}?viewer=cornerstone`)
  await page.waitForFunction(() => ['ready', 'error'].includes(document.querySelector('.cs-viewer')?.dataset.state))
  assert.equal(await page.locator('.cs-viewer').getAttribute('data-state'), 'ready', await page.locator('.cs-viewer').innerText())
  const expectedLabels = [{ top: 'A', bottom: 'P', left: 'R', right: 'L' }, { top: 'S', bottom: 'I', left: 'A', right: 'P' }, { top: 'S', bottom: 'I', left: 'R', right: 'L' }]
  for (let i = 0; i < 3; i++) for (const [side, label] of Object.entries(expectedLabels[i])) {
    await page.locator('.cs-viewport').nth(i).locator(`[data-side="${side}"]`).getByText(label, { exact: true }).waitFor()
  }
  result.geometry = await page.evaluate(async fixture => {
    const core = await import(performance.getEntriesByType('resource').find(r => /\/\@cornerstonejs_core\.js/.test(r.name)).name)
    const viewport = core.getRenderingEngines()[0].getViewports()[0]
    const volume = core.cache.getVolume(viewport.getActors()[0].referencedId)
    return { spacing: volume.spacing, points: fixture.points.map(p => volume.imageData.indexToWorld(p.ijk)) }
  }, fixture)
  assert.deepEqual(result.geometry.spacing, [1.5, 2, 3])
  result.geometry.points.forEach((p, i) => p.forEach((v, j) => assert.ok(Math.abs(v - fixture.points[i].lps[j]) < 1e-5)))
  await page.getByRole('button', { name: '距离测量', exact: true }).click()
  const box = await page.locator('.cs-viewport').first().boundingBox()
  const start = [Math.round(box.x + box.width * .43), Math.round(box.y + box.height * .42)]
  const end = [start[0] + 30, start[1] + 20]
  const expected = await page.evaluate(async local => {
    const core = await import(performance.getEntriesByType('resource').find(r => /\/\@cornerstonejs_core\.js/.test(r.name)).name)
    const viewport = core.getRenderingEngines()[0].getViewports()[0]
    const points = local.map(p => viewport.canvasToWorld(p))
    return { points, distance: Math.hypot(...points[1].map((v, i) => v - points[0][i])) }
  }, [start, end].map(p => [p[0] - box.x, p[1] - box.y]))
  await page.mouse.move(...start); await page.mouse.down(); await page.mouse.move(...end, { steps: 10 }); await page.mouse.up()
  await page.locator('.cs-measurement-row').waitFor()
  await page.getByRole('button', { name: '保存测量', exact: true }).click()
  await page.locator('.cs-measurement-row:not([data-saved-id=""])').waitFor()
  const data = (await (await page.request.get(`http://127.0.0.1:8012/mri/${fixture.case_id}/measurements`)).json()).data
  assert.equal(data.items.length, 1)
  result.measurement = data.items[0]
  assert.ok(Math.abs(data.items[0].length_mm - expected.distance) < 1e-3)
  result.nifti_geometry_checks = 'Actual browser volume indexToWorld equals independent nibabel sform LPS at 3 points; original spacing preserved; 12 anatomical screen labels correct'
  await page.screenshot({ path: output + '/nonunit-measurement.png', fullPage: true })
  await page.getByRole('button', { name: '删除测量', exact: true }).click()
  await page.waitForFunction(() => !document.querySelector('.cs-measurement-row'))
  assert.equal((await (await page.request.get(`http://127.0.0.1:8012/mri/${fixture.case_id}/measurements`)).json()).data.items.length, 0)
  assert.deepEqual(result.pageErrors, [])
  result.status = 'passed'
} catch (e) {
  result.status = 'failed'; result.error = e.stack; process.exitCode = 1
  await page.screenshot({ path: output + '/failure.png', fullPage: true })
} finally {
  await fs.writeFile(output + '/validation.json', JSON.stringify(result, null, 2))
  await browser.close()
}
