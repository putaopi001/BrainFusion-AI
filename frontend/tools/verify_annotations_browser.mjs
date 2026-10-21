import { chromium } from '@playwright/test'
import fs from 'node:fs/promises'
import assert from 'node:assert/strict'

const root = process.env.BRAINFUSION_EVIDENCE_DIR
if (!root?.startsWith('E:/BrainFusion-Runtime/results/nightly/')) throw new Error('Use unique nightly evidence')
const web = process.env.BRAINFUSION_WEB_URL || 'http://127.0.0.1:5179'
const api = process.env.BRAINFUSION_API_URL || 'http://127.0.0.1:8012'
const id = Number(process.env.BRAINFUSION_CASE_ID || 17)
await fs.mkdir(root, { recursive: true })
const browser = await chromium.launch({ headless: true })
const page = await browser.newPage({ viewport: { width: 1600, height: 1300 } })
const result = { status: 'in_progress', case_id: id, checks: [], tools: {}, events: [], errors: [] }
const owned = []
page.on('pageerror', e => result.errors.push(e.message))
const get = async path => {
  const r = await page.request.get(api + path); assert.equal(r.status(), 200, await r.text()); return (await r.json()).data
}
const ready = () => page.waitForFunction(() => document.querySelectorAll('.slice-img').length === 3 && [...document.querySelectorAll('.slice-img')].every(i => i.complete && i.naturalWidth > 0))
const close = (a, b) => assert(Math.abs(a - b) < .01, `Expected normalized coordinate ${b}, got ${a}`)
try {
  const original = await get(`/mri/${id}/annotations`)
  const meta = await get(`/mri/${id}/volume`)
  await page.goto(`${web}/workstation/${id}`); await ready()
  await page.locator('.viewport-panel[data-view="axial"]').evaluate(el => {
    window.annotationEvents = []
    for (const type of ['dragstart', 'pointercancel', 'pointerup']) el.addEventListener(type, e => window.annotationEvents.push({ type, x: e.clientX, y: e.clientY }))
  })
  const labels = { line: '测距', point: '标记点', rectangle: '矩形ROI', ellipse: '椭圆ROI', circle: '圆形ROI', freehand: '自由ROI', angle: '角度', bidirectional: '双向测量', text: '文字', probe: '探针' }
  for (const [tool, label] of Object.entries(labels)) {
    const note = `F4 ${tool} owned ${root.split('/').at(-2)}`
    await page.getByPlaceholder('标注说明', { exact: true }).fill(note)
    await page.getByRole('button', { name: label, exact: true }).click()
    const axial = page.locator('.viewport-panel[data-view="axial"]')
    await axial.locator('.image-box').scrollIntoViewIfNeeded()
    const box = await axial.locator('.image-box').boundingBox()
    const move = (x, y, steps = 1) => page.mouse.move(box.x + box.width * x, box.y + box.height * y, { steps })
    const drag = async (a, b) => { await move(...a); await page.mouse.down(); await move(...b, 8); await page.mouse.up() }
    if (['line', 'rectangle', 'ellipse', 'circle'].includes(tool)) await drag([.3, .35], [.65, .6])
    else if (tool === 'freehand') {
      await move(.3, .3); await page.mouse.down(); await move(.65, .3, 8); await move(.5, .65, 8); await move(.3, .3, 8); await page.mouse.up()
    } else if (tool === 'angle') { await drag([.4, .4], [.65, .4]); await move(.4, .65, 5); await page.mouse.down(); await page.mouse.up() }
    else if (tool === 'bidirectional') { await drag([.3, .35], [.65, .6]); await drag([.3, .6], [.65, .35]) }
    else { await move(.45, .45); await page.mouse.down(); await page.mouse.up() }
    const before = await get(`/mri/${id}/annotations`)
    const responsePromise = page.waitForResponse(r => r.url().endsWith(`/mri/${id}/annotations`) && r.request().method() === 'POST')
    await page.getByRole('button', { name: '保存标注', exact: true }).click()
    const response = await responsePromise; assert.equal(response.status(), 200, await response.text())
    const newId = (await response.json()).data.id; owned.push(newId)
    const all = await get(`/mri/${id}/annotations`)
    assert.equal(all.length, before.length + 1)
    const a = all.find(x => x.id === newId)
    assert.equal(a.tool, tool); assert.equal(a.coordinate_contract, 'LPS_DISPLAY_V1')
    if (tool === 'line') {
      const pts = JSON.parse(a.points)
      close(pts[0][0], .3); close(pts[0][1], .35); close(pts[1][0], .65); close(pts[1][1], .6)
    }
    if (['rectangle', 'ellipse', 'circle'].includes(tool)) { close(a.width, .35); close(a.height, .25) }
    if (tool === 'freehand') assert(JSON.parse(a.points).length >= 10)
    if (tool === 'angle') assert.equal(JSON.parse(a.points).length, 3)
    if (tool === 'bidirectional') assert.equal(JSON.parse(a.points).length, 2)
    if (tool === 'probe') assert.match(a.note, /^FLAIR 值 /)
    result.tools[tool] = a
    await page.reload(); await ready()
    assert.deepEqual((await get(`/mri/${id}/annotations`)).find(x => x.id === newId), a)
    const row = page.locator(`.annotation-item[data-annotation-id="${newId}"]`)
    await row.waitFor()
    const drawn = page.locator(`.annotation-svg g[data-annotation-id="${newId}"]`).first()
    await drawn.waitFor()
    const text = await drawn.textContent()
    const pw = (meta.shape[2] - 1) * meta.spacing[2], ph = (meta.shape[1] - 1) * meta.spacing[1]
    const length = (p, q) => Math.hypot((q[0] - p[0]) * pw, (q[1] - p[1]) * ph).toFixed(1)
    if (tool === 'line') { const [p, q] = JSON.parse(a.points); assert(text.includes(length(p, q) + ' mm')) }
    if (tool === 'bidirectional') { const lines = JSON.parse(a.points); assert(text.includes(lines.map(l => length(l.slice(0, 2), l.slice(2))).join(' / ') + ' mm')) }
    if (['rectangle', 'ellipse', 'circle', 'freehand'].includes(tool)) {
      let area = a.width * pw * a.height * ph
      if (tool === 'ellipse') area *= Math.PI / 4
      if (tool === 'circle') area = Math.PI * (Math.max(a.width * pw, a.height * ph) / 2) ** 2
      if (tool === 'freehand') {
        const points = JSON.parse(a.points)
        area = Math.abs(points.reduce((v, p, i) => { const q = points[(i + 1) % points.length]; return v + p[0] * q[1] - q[0] * p[1] }, 0)) / 2 * pw * ph
      }
      assert(text.includes(area.toFixed(1) + ' mm²'))
    }
    if (tool === 'angle') assert.match(text, /90°/)
    await page.screenshot({ path: `${root}/${tool}.png`, fullPage: true })
    const removed = page.waitForResponse(r => r.url().endsWith(`/mri/${id}/annotations/${newId}`) && r.request().method() === 'DELETE')
    await row.getByRole('button', { name: '删除', exact: true }).click(); assert.equal((await removed).status(), 200)
    owned.splice(owned.indexOf(newId), 1)
    assert.deepEqual(await get(`/mri/${id}/annotations`), original)
    result.checks.push(`${tool}: actual create/save/reload/render/delete, coordinate contract and applicable physical unit`)
  }
  // Partial saves must preserve the failed draft and must not resend earlier successes.
  await page.getByRole('button', { name: '标记点', exact: true }).click()
  const pointBox = await page.locator('.viewport-panel[data-view="axial"] .image-box').boundingBox()
  for (const x of [.35, .55]) { await page.mouse.move(pointBox.x + pointBox.width * x, pointBox.y + pointBox.height * .45); await page.mouse.down(); await page.mouse.up() }
  let posts = 0
  await page.route(`**/mri/${id}/annotations`, route => {
    if (route.request().method() !== 'POST') return route.continue()
    ++posts
    if (posts === 2) return route.fulfill({ status: 503, json: { detail: 'Controlled second annotation save failed' } })
    return route.continue()
  })
  await page.getByRole('button', { name: '保存标注', exact: true }).click()
  await page.getByText('Controlled second annotation save failed', { exact: true }).waitFor()
  const partial = (await get(`/mri/${id}/annotations`)).filter(x => !original.some(y => y.id === x.id))
  assert.equal(partial.length, 1); owned.push(partial[0].id); assert.equal(posts, 2)
  await page.unroute(`**/mri/${id}/annotations`)
  const retryResponse = page.waitForResponse(r => r.url().endsWith(`/mri/${id}/annotations`) && r.request().method() === 'POST')
  await page.getByRole('button', { name: '保存标注', exact: true }).click()
  const retried = await retryResponse; assert.equal(retried.status(), 200); owned.push((await retried.json()).data.id)
  assert.equal((await get(`/mri/${id}/annotations`)).length, original.length + 2)
  await page.reload(); await ready()
  for (const annId of [...owned]) {
    const removed = page.waitForResponse(r => r.url().endsWith(`/mri/${id}/annotations/${annId}`) && r.request().method() === 'DELETE')
    await page.locator(`.annotation-item[data-annotation-id="${annId}"]`).getByRole('button', { name: '删除', exact: true }).click()
    assert.equal((await removed).status(), 200); owned.splice(owned.indexOf(annId), 1)
  }
  assert.deepEqual(await get(`/mri/${id}/annotations`), original)
  result.checks.push('controlled second-save failure preserves one draft; retry creates only that draft, no duplicates; original records retained')
  await page.getByRole('button', { name: '测距', exact: true }).click()
  const cancelBox = await page.locator('.viewport-panel[data-view="axial"] .image-box').boundingBox()
  await page.mouse.move(cancelBox.x + cancelBox.width * .3, cancelBox.y + cancelBox.height * .3); await page.mouse.down()
  await page.locator('.viewport-panel[data-view="axial"] .viewport').dispatchEvent('pointercancel')
  await page.mouse.up()
  assert(await page.getByRole('button', { name: '保存标注', exact: true }).isDisabled())
  result.checks.push('pointer cancellation discards an unfinished distance instead of saving a shortened measurement')
  assert.deepEqual(result.errors, []); result.status = 'passed'; console.log(JSON.stringify({ status: result.status, checks: result.checks }))
} catch (e) {
  result.status = 'failed'; result.error = String(e)
  result.events = await page.evaluate(() => window.annotationEvents || [])
  await page.screenshot({ path: `${root}/failed.png`, fullPage: true }); throw e
} finally {
  result.cleanup = []
  for (const annId of owned) result.cleanup.push({ id: annId, status: (await page.request.delete(`${api}/mri/${id}/annotations/${annId}`)).status() })
  await fs.writeFile(`${root}/validation.json`, JSON.stringify(result, null, 2)); await browser.close()
}
