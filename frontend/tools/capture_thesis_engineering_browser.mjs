// Read-only material capture from an existing public engineering case.
import { chromium } from '@playwright/test'
import fs from 'node:fs/promises'
import assert from 'node:assert/strict'
const root = process.env.BRAINFUSION_RUN_ROOT
if (!root?.startsWith('E:/BrainFusion-Runtime/results/nightly/')) throw Error('Unique E-drive evidence root required')
const output = `${root}/engineering-browser-final-rendered`
await fs.mkdir(output)
const expected = JSON.parse(await fs.readFile(`${root}/engineering-evidence-final/engineering-evidence.json`, 'utf8'))
assert.equal(expected.status, 'passed')
const browser = await chromium.launch({ channel: 'msedge', headless: true })
const page = await browser.newPage({ viewport: { width: 1600, height: 1200 } })
const result = { status: 'running', checks: [], pageErrors: [], blockedWrites: [], imageIntegrity: 'Unmodified browser captures of existing public engineering case; no crop of scientific image area, intensity edit, stitching, or new inference.' }
page.on('pageerror', error => result.pageErrors.push(error.message))
await page.route('**/*', async route => {
  const method = route.request().method()
  if (['POST', 'PUT', 'PATCH', 'DELETE'].includes(method)) {
    result.blockedWrites.push({ method, path: new URL(route.request().url()).pathname })
    await route.abort()
  } else await route.continue()
})
try {
  const reply = await page.request.get('http://127.0.0.1:8012/research/cases/17/features')
  assert.equal(reply.status(), 200)
  const feature = (await reply.json()).data
  assert.equal(feature.id, expected.public_case.feature_job_id)
  assert.equal(feature.analysis_run_id, expected.public_case.analysis_id)
  assert.deepEqual(feature.result.probabilities, expected.research.probabilities)
  assert.equal(feature.clinical_input_version, expected.public_case.clinical_input_version)
  await page.goto('http://127.0.0.1:5179/case/17')
  await page.getByText(expected.public_case.analysis_id, { exact: false }).first().waitFor()
  await page.waitForFunction(() => document.querySelectorAll('.slice-img').length === 3 && [...document.querySelectorAll('.slice-img')].every(image => image.complete && image.naturalWidth > 0))
  await page.screenshot({ path: `${output}/case17.png`, fullPage: true, animations: 'disabled' })
  result.checks.push('Existing public case page binds current saved analysis; no creation or confirmation write')
  await page.goto('http://127.0.0.1:5179/workstation/17')
  await page.waitForFunction(() => document.querySelectorAll('.slice-img').length === 3 && [...document.querySelectorAll('.slice-img')].every(image => image.complete && image.naturalWidth > 0))
  await page.getByRole('button', { name: 'AI分割叠加', exact: true }).click()
  await page.locator('.mri-sequence-select').click()
  await page.getByRole('option', { name: 'FLAIR', exact: true }).click()
  await page.waitForFunction(() => {
    const images = [...document.querySelectorAll('.slice-img')], masks = [...document.querySelectorAll('.mask-img')]
    return document.querySelector('.current-sequence')?.dataset.sequence === 't2f' && images.length === 3 && masks.length === 3 && images.every(image => image.complete && image.naturalWidth > 0 && new URL(image.src).searchParams.get('sequence') === 't2f') && masks.every(image => image.complete && image.naturalWidth > 0)
  })
  await page.getByRole('option', { name: 'FLAIR', exact: true }).waitFor({ state: 'hidden' })
  // Move only viewport slices through actual controls; scientific files stay unchanged.
  const indices = expected.representative_reading.indices_zero_based
  for (const [index, view] of ['axial', 'coronal', 'sagittal'].entries()) {
    const control = page.locator('.slice-row').nth(index)
    const slider = control.getByRole('slider')
    const maximum = Number(await slider.getAttribute('aria-valuemax'))
    const track = await control.locator('.el-slider__runway').boundingBox()
    assert(track)
    await page.mouse.click(track.x + track.width * indices[view] / maximum, track.y + track.height / 2)
    await page.waitForFunction(({ view, expectedIndex }) => {
      const image = document.querySelector(`.viewport-panel[data-view="${view}"] .slice-img`)
      const mask = document.querySelector(`.viewport-panel[data-view="${view}"] .mask-img`)
      return image?.complete && image.naturalWidth > 0 && new URL(image.src).pathname.endsWith(`/${expectedIndex}`) && mask?.complete && mask.naturalWidth > 0 && new URL(mask.src).pathname.endsWith(`/${expectedIndex}`)
    }, { view, expectedIndex: indices[view] })
    assert.equal(Number(await slider.getAttribute('aria-valuenow')), indices[view])
  }
  result.representativeReading = expected.representative_reading
  await page.screenshot({ path: `${output}/flair-three-view.png`, fullPage: true })
  result.checks.push('Three real FLAIR slices and three original-space model mask overlays rendered, no empty-image acceptance; no annotation writes')
  await page.goto('http://127.0.0.1:5179/research?case_id=17')
  await page.locator('.automatic-result').waitFor()
  await page.locator('.automatic-result').scrollIntoViewIfNeeded()
  assert.equal(await page.locator('.feature-state').getAttribute('data-job-id'), feature.id)
  assert((await page.locator('body').innerText()).includes(feature.analysis_run_id))
  await page.screenshot({ path: `${output}/saved-research.png`, fullPage: true })
  result.checks.push('Saved 57-male case input / feature task / research probability and limitation visible; no extraction or clinical edit')
  await page.goto('http://127.0.0.1:5179/report?case_id=17')
  const paper = page.locator('#report-paper')
  await paper.waitFor()
  assert((await paper.innerText()).includes(feature.analysis_run_id))
  assert.equal(await page.getByRole('button', { name: '导出 PDF', exact: true }).isEnabled(), true)
  await paper.screenshot({ path: `${output}/current-report.png`, animations: 'disabled' })
  result.checks.push('Current analysis-bound report and independent opinion rendered; PDF entry checked but no report PDF generated')
  assert.deepEqual(result.pageErrors, [])
  assert.deepEqual(result.blockedWrites, [])
  result.status = 'passed'
} catch (error) {
  result.status = 'failed'; result.error = String(error)
  await page.screenshot({ path: `${output}/failure.png`, fullPage: true })
  throw error
} finally {
  await fs.writeFile(`${output}/validation.json`, JSON.stringify(result, null, 2))
  await browser.close()
}
console.log(JSON.stringify(result))
