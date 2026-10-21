import { chromium } from '@playwright/test'
import fs from 'node:fs/promises'
import assert from 'node:assert/strict'
import { createHash } from 'node:crypto'

const root = process.env.BRAINFUSION_EVIDENCE_DIR
if (!root?.startsWith('E:/BrainFusion-Runtime/results/nightly/')) throw new Error('Use unique nightly evidence')
const web = process.env.BRAINFUSION_WEB_URL || 'http://127.0.0.1:5179'
const api = process.env.BRAINFUSION_API_URL || 'http://127.0.0.1:8012'
const id = Number(process.env.BRAINFUSION_CASE_ID || 17)
const tag = `F3 engineering measurement ${root.split('/').at(-2)}`
await fs.mkdir(root, { recursive: true })
const browser = await chromium.launch({ headless: true })
const page = await browser.newPage({ viewport: { width: 1600, height: 1200 } })
const result = { status: 'in_progress', case_id: id, checks: [], sequences: {}, errors: [] }
let ownedAnnotationId
page.on('pageerror', e => result.errors.push(e.message))
const get = async path => {
  const r = await page.request.get(api + path); assert.equal(r.status(), 200, await r.text())
  return (await r.json()).data
}
const loaded = async key => page.waitForFunction(key => {
  const imgs = [...document.querySelectorAll('.slice-img')]
  return imgs.length === 3 && imgs.every(img => img.complete && img.naturalWidth > 0 && new URL(img.src).searchParams.get('sequence') === key)
}, key)
const snapshot = () => page.locator('.viewport-panel').evaluateAll(items => items.map(el => ({
  view: el.dataset.view, index: el.querySelector('.panel-meta').textContent,
  orientation: [...el.querySelectorAll('.orient')].map(x => x.textContent),
  crosshair: [...el.querySelectorAll('.crosshair-line')].map(x => ['x1', 'x2', 'y1', 'y2'].map(a => x.getAttribute(a))),
  transform: el.querySelector('.stage').getAttribute('style'), mask: el.querySelector('.mask-img')?.src,
  measure: [...el.querySelectorAll('.label-text')].map(x => x.textContent),
})))
const choose = async (key, label) => {
  await page.locator('.mri-sequence-select').click()
  await page.getByRole('option', { name: label, exact: true }).click()
  await loaded(key)
  await page.waitForFunction(() => [...document.querySelectorAll('.mask-img')].every(i => i.complete && i.naturalWidth > 0))
}
try {
  const original = await get(`/mri/${id}/annotations`)
  const run = await get(`/analysis/${id}`)
  await page.goto(`${web}/case/${id}`); await loaded('t2f')
  await page.getByRole('button', { name: 'AI分割叠加', exact: true }).click()
  await page.waitForFunction(() => document.querySelectorAll('.mask-img').length === 3 && [...document.querySelectorAll('.mask-img')].every(i => i.complete && i.naturalWidth > 0))
  const axial = page.locator('.viewport-panel[data-view="axial"]')
  await axial.locator('.viewport').hover(); await page.mouse.wheel(0, 120)
  await loaded('t2f')
  await page.getByRole('button', { name: '放大', exact: true }).click()
  await page.getByRole('button', { name: '全窗', exact: true }).click()
  await loaded('t2f')
  const flareUrl = await axial.locator('.slice-img').getAttribute('src')
  const flareWindow = [new URL(flareUrl).searchParams.get('ww'), new URL(flareUrl).searchParams.get('wl')]
  await page.getByPlaceholder('标注说明', { exact: true }).fill(tag)
  await page.getByRole('button', { name: '测距', exact: true }).click()
  const box = await axial.locator('.image-box').boundingBox()
  await page.mouse.move(box.x + box.width * .3, box.y + box.height * .35)
  await page.mouse.down(); await page.mouse.move(box.x + box.width * .65, box.y + box.height * .6, { steps: 8 }); await page.mouse.up()
  const saveResponse = page.waitForResponse(r => r.url().endsWith(`/mri/${id}/annotations`) && r.request().method() === 'POST')
  await page.getByRole('button', { name: '保存标注', exact: true }).click()
  const response = await saveResponse; assert.equal(response.status(), 200)
  ownedAnnotationId = (await response.json()).data.id
  await page.getByText('医生标注已保存', { exact: true }).waitFor()
  const annotations = await get(`/mri/${id}/annotations`)
  const annotation = annotations.find(x => x.id === ownedAnnotationId)
  assert.equal(annotation.note, tag); assert.equal(annotation.coordinate_contract, 'LPS_DISPLAY_V1')
  const meta = await get(`/mri/${id}/volume?sequence=t2f`)
  const points = JSON.parse(annotation.points)
  const expectedLength = Math.hypot((points[1][0] - points[0][0]) * (meta.shape[2] - 1), (points[1][1] - points[0][1]) * (meta.shape[1] - 1)).toFixed(1) + ' mm'
  await axial.getByText(expectedLength, { exact: true }).waitFor()
  const fixed = await snapshot()
  result.measurement = { id: ownedAnnotationId, points, voxel: JSON.parse(annotation.voxel_coordinate), expected_length: expectedLength }
  const labels = { t1c: 'T1c · 增强 T1', t1n: 'T1n · 平扫 T1', t2w: 'T2w · T2', t2f: 'FLAIR' }
  for (const key of ['t1c', 't1n', 't2w', 't2f']) {
    await choose(key, labels[key])
    assert.deepEqual(await snapshot(), fixed)
    assert.equal(await page.locator('.sequence-identity').allTextContents().then(x => x.every(v => v === labels[key])), true)
    const urls = await page.locator('.slice-img').evaluateAll(items => items.map(i => i.src))
    const hashes = []
    for (const url of urls) {
      const img = await page.request.get(url); assert.equal(img.status(), 200)
      hashes.push(createHash('sha256').update(await img.body()).digest('hex'))
    }
    const index = Number(new URL(urls[0]).pathname.split('/').at(-1))
    result.sequences[key] = { urls, hashes, probe: await get(`/mri/${id}/voxel?sequence=${key}&view=axial&index=${index}&nx=.5&ny=.5`) }
    await page.screenshot({ path: `${root}/${key}.png`, fullPage: true })
  }
  assert(new Set(Object.values(result.sequences).map(x => x.hashes[0])).size > 1)
  const flareAfter = new URL(result.sequences.t2f.urls[0])
  assert.deepEqual([flareAfter.searchParams.get('ww'), flareAfter.searchParams.get('wl')], flareWindow)
  assert(Object.values(result.sequences).every(x => JSON.stringify(x.probe.voxel) === JSON.stringify(result.sequences.t2f.probe.voxel)))
  result.checks.push('real four-sequence switching changes MRI intensities while preserving three-view indices, orientation, crosshair, pan/zoom, mask URLs and physical measurement')
  result.checks.push('slice wheel, true window preset and per-sequence saved WW/WL work; probe reads the selected sequence at the same display voxel')
  await page.getByRole('button', { name: '隐藏分割', exact: true }).click(); assert.equal(await page.locator('.mask-img').count(), 0)
  await page.getByRole('button', { name: 'AI分割叠加', exact: true }).click()
  await choose('t1c', labels.t1c)
  await page.route(`**/mri/${id}/volume?sequence=t1n`, route => route.fulfill({ status: 422, json: { detail: 'Controlled affine mismatch; no resampling' } }))
  await page.locator('.mri-sequence-select').click(); await page.getByRole('option', { name: labels.t1n, exact: true }).click()
  await page.getByText('Controlled affine mismatch; no resampling', { exact: true }).waitFor()
  await loaded('t1c'); assert.equal(await page.locator('.current-sequence').getAttribute('data-sequence'), 't1c')
  await page.unroute(`**/mri/${id}/volume?sequence=t1n`)
  result.checks.push('overlay on/off persists across sequence changes; rejected geometry keeps the prior accepted sequence with an explicit error')
  await page.reload(); await loaded('t2f')
  // Default middle axial slice may differ by one after our wheel; scroll back to the saved layer.
  const current = Number(new URL(await axial.locator('.slice-img').getAttribute('src')).pathname.split('/').at(-1))
  if (current !== annotation.slice_index) { await axial.locator('.viewport').hover(); await page.mouse.wheel(0, (annotation.slice_index - current) * 120); await loaded('t2f') }
  await axial.getByText(expectedLength, { exact: true }).waitFor()
  await choose('t2w', labels.t2w); await axial.getByText(expectedLength, { exact: true }).waitFor()
  const deleted = page.waitForResponse(r => r.url().endsWith(`/mri/${id}/annotations/${ownedAnnotationId}`) && r.request().method() === 'DELETE')
  await page.locator('.annotation-item').filter({ hasText: tag }).getByRole('button', { name: '删除', exact: true }).click()
  assert.equal((await deleted).status(), 200)
  assert.deepEqual(await get(`/mri/${id}/annotations`), original)
  ownedAnnotationId = null
  assert.equal((await get(`/analysis/${id}`)).id, run.id)
  result.checks.push('saved distance coordinates/unit survive reload and switching; only this run measurement is deleted, original annotations and analysis retained')
  assert.deepEqual(result.errors, []); result.status = 'passed'; console.log(JSON.stringify(result))
} catch (e) { result.status = 'failed'; result.error = String(e); await page.screenshot({ path: `${root}/failed.png`, fullPage: true }); throw e }
finally {
  if (ownedAnnotationId) {
    // Exact ID created above, never bulk-delete other records.
    const cleanup = await page.request.delete(`${api}/mri/${id}/annotations/${ownedAnnotationId}`)
    result.owned_annotation_cleanup_status = cleanup.status()
  }
  await fs.writeFile(`${root}/validation.json`, JSON.stringify(result, null, 2)); await browser.close()
}
