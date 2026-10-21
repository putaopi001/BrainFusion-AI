// Actual local Orthanc -> FastAPI -> Cornerstone; no mocked responses.
import fs from 'node:fs/promises'
import assert from 'node:assert/strict'
import { chromium } from '@playwright/test'
const root = process.argv[2]
const sample = JSON.parse(await fs.readFile(root + '/actual-viewing-case.json', 'utf8'))
const expected = JSON.parse(await fs.readFile(root + '/expected-volume.json', 'utf8'))
const target = 'http://127.0.0.1:5179/workstation/' + sample.case_id
  + '?viewer=cornerstone&source=dicom&study_uid=' + sample.study_uid + '&series_uid=' + sample.series_uid
const browser = await chromium.launch({ headless: true })
const result = { status: 'running', frames: [], pageErrors: [], writes: [],
  source: 'actual public MR metadata derivative via actual Orthanc', ai_activation: false }
let page
try {
  page = await browser.newPage({ viewport: { width: 1500, height: 1050 } })
  page.on('pageerror', e => result.pageErrors.push(e.message))
  page.on('response', r => {
    if (r.url().includes('/frames/1?')) result.frames.push(r.status())
  })
  await page.route('**/*', async route => {
    if (!['GET', 'HEAD'].includes(route.request().method())) {
      result.writes.push(route.request().method()); await route.abort(); return
    }
    await route.continue()
  })
  const started = Date.now()
  await page.goto('http://127.0.0.1:5179/case/' + sample.case_id)
  const panel = page.locator('.pacs-panel')
  await panel.getByRole('button', { name: '查询检查', exact: true }).click()
  const studyRow = panel.locator('.el-table').first().locator('.el-table__body tr').filter({ hasText: sample.study_uid })
  await studyRow.waitFor()
  await page.waitForFunction(() => !document.querySelector('.pacs-panel').classList.contains('is-busy'))
  await studyRow.click()
  const seriesRow = panel.locator('.pacs-selection .el-table').first().locator('.el-table__body tr').filter({ hasText: sample.series_uid })
  await seriesRow.waitFor()
  await page.waitForFunction(() => !document.querySelector('.pacs-panel').classList.contains('is-busy'))
  await seriesRow.click()
  await panel.getByRole('button', { name: '核对序列空间', exact: true }).click()
  await panel.getByRole('button', { name: 'Cornerstone 阅片（工程验证）', exact: true }).click()
  await page.locator('.cs-viewer[data-source="dicom"][data-state="ready"]').waitFor({ timeout: 120000 })
  assert.equal(new URL(page.url()).pathname, '/workstation/' + sample.case_id)
  assert.equal(new URL(page.url()).searchParams.get('series_uid'), sample.series_uid)
  result.actual_case_panel_entry = true
  assert.equal(await page.locator('.cs-viewport canvas').count(), 3)
  result.first_ready_ms = Date.now() - started
  result.volume = await page.evaluate(async () => {
    const core = await import('/node_modules/.vite/deps/@cornerstonejs_core.js')
    const view = core.getRenderingEngines()[0].getViewports()[0]
    const volume = core.cache.getVolume(view.getVolumeId())
    const scalar = volume.voxelManager.getCompleteScalarDataArray()
    const normalized = Float64Array.from(scalar)
    const sha = new Uint8Array(await crypto.subtle.digest('SHA-256', normalized.buffer))
    return { dimensions: volume.dimensions, spacing: volume.spacing, voxel_count: scalar.length,
      float64_le_sha256: [...sha].map(x => x.toString(16).padStart(2, '0')).join(''),
      origin: volume.imageData.indexToWorld([0, 0, 0]) }
  })
  assert.equal(result.volume.voxel_count, expected.voxel_count)
  assert.equal(result.volume.float64_le_sha256, expected.float64_le_sha256)
  assert.deepEqual(result.volume.dimensions, expected.geometry.dimensions)
  assert.ok(result.volume.spacing.every((v, i) => Math.abs(v - expected.geometry.spacing_xyz_mm[i]) < 0.00001))
  const view = page.locator('.cs-viewport').first()
  const box = await view.boundingBox()
  const inspect = () => page.evaluate(async () => {
    const core = await import('/node_modules/.vite/deps/@cornerstonejs_core.js')
    return core.getRenderingEngines()[0].getViewports().map(v => ({ index: v.getCurrentImageIdIndex(),
      scale: v.getCamera().parallelScale, focal: v.getCamera().focalPoint, voi: v.getProperties().voiRange }))
  })
  const before = await inspect()
  await page.mouse.move(box.x + box.width * .5, box.y + box.height * .5)
  await page.mouse.wheel(0, 120)
  await page.waitForTimeout(500)
  const after = await inspect()
  assert.notEqual(before[0].index, after[0].index)
  result.scroll_changed = true
  await page.getByRole('button', { name: '窗宽窗位', exact: true }).click()
  const voiBefore = await inspect()
  await page.mouse.move(box.x + box.width * .4, box.y + box.height * .4)
  await page.mouse.down()
  await page.mouse.move(box.x + box.width * .55, box.y + box.height * .55, { steps: 8 })
  await page.mouse.up()
  await page.waitForTimeout(500)
  const voiAfter = await inspect()
  assert.notDeepEqual(voiBefore[0].voi, voiAfter[0].voi)
  result.window_changed = true
  await page.getByRole('button', { name: '重置视图', exact: true }).click()
  await page.locator('.cs-viewer').screenshot({ path: root + '/real-dicom-three-views.png' })
  assert.equal(result.frames.length, sample.instance_count)
  assert.ok(result.frames.every(s => s === 200))
  assert.deepEqual(result.pageErrors, [])
  assert.deepEqual(result.writes, [])
  result.status = 'passed'
  await fs.writeFile(root + '/real-dicom-browser.json', JSON.stringify(result, null, 2), { flag: 'wx' })
  console.log('Actual DICOM viewing, all voxels, 192 frames, scroll/window: passed.')
} catch (error) {
  result.status = 'failed'; result.error = error.message
  if (page) result.visible_error = await page.locator('.cs-error').innerText().catch(() => '')
  await fs.writeFile(root + '/real-dicom-browser-failed-' + Date.now() + '.json', JSON.stringify(result, null, 2))
  throw error
} finally { await browser.close() }
