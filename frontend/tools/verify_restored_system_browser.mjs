import { chromium } from '@playwright/test'
import fs from 'node:fs/promises'
import assert from 'node:assert/strict'
import { createHash } from 'node:crypto'
const root = process.env.BRAINFUSION_RUN_ROOT
if (!root?.startsWith('E:/BrainFusion-Runtime/results/nightly/')) throw new Error('Unique nightly root required')
const mode = process.env.BRAINFUSION_RESTORE_MODE || 'capture'
const output = `${root}/${process.env.BRAINFUSION_ATTEMPT || 'restored-browser'}`
await fs.mkdir(output)
const api = 'http://127.0.0.1:8012', web = 'http://127.0.0.1:5179'
const browser = await chromium.launch({ headless: true })
const page = await browser.newPage({ viewport: { width: 1600, height: 1200 } })
const result = { mode, status: 'in_progress', checks: [], errors: [] }
page.on('pageerror', error => result.errors.push(error.message))
const get = async path => {
  const response = await page.request.get(api + path)
  assert.equal(response.status(), 200, await response.text())
  return (await response.json()).data
}
const noPaths = value => {
  if (Array.isArray(value)) return value.map(noPaths)
  if (value && typeof value === 'object') return Object.fromEntries(Object.entries(value)
    .filter(([key]) => !['mask_path', 'output_dir', 'sequences'].includes(key)).map(([key, child]) => [key, noPaths(child)]))
  return value
}
const signature = { cases: {}, images: {} }
try {
  const cases = await get('/cases/')
  for (const item of cases) {
    const detail = await get(`/cases/${item.id}/detail`)
    const analysis = detail.analysis
    signature.cases[item.id] = {
      patient: detail.patient, case: detail.case, analysis: noPaths(analysis),
      report: detail.report, doctor_verified: detail.mri?.doctor_verified,
      verified_run_id: detail.mri?.verified_run_id,
      doctor_opinion: await get(`/cases/${item.id}/doctor-opinion`),
    }
    if (detail.mri?.id) {
      signature.cases[item.id].annotations = await get(`/mri/${item.id}/annotations`)
      const features = await get(`/research/cases/${item.id}/features`)
      // cache_hit and path-bound cache_key are engineering metadata, not scientific output.
      signature.cases[item.id].features = features ? {
        id: features.id, state: features.state, clinical_input: features.clinical_input,
        clinical_input_version: features.clinical_input_version, stale: features.stale,
        result: noPaths(features.result),
      } : null
    }
    if (analysis?.state === 'succeeded' && !analysis.stale && analysis.result) {
      assert.equal((await get(`/reports/${item.id}`)).analysis_run_id, analysis.id)
      assert.equal((await get(`/mri/${item.id}/segmentation`)).available, true)
    }
  }
  signature.research_summary = await get('/research/summary')
  signature.reference_research = await get('/research/patients/4')
  signature.volume = await get('/mri/17/volume?sequence=t2f')
  for (const [view, index] of [['axial', 70], ['coronal', 100], ['sagittal', 100]]) {
    for (const type of ['slice', 'mask']) {
      const response = await page.request.get(`${api}/mri/17/${type}/${view}/${index}?ww=1200&wl=600&sequence=t2f`)
      assert.equal(response.status(), 200)
      signature.images[`${type}-${view}`] = createHash('sha256').update(await response.body()).digest('hex')
    }
  }
  if (mode === 'capture') {
    await fs.writeFile(`${root}/restore-baseline.json`, JSON.stringify(signature, null, 2), { flag: 'wx' })
    result.checks.push('Captured all18 cases, saved model/report/confirmation/opinion/annotations/features, reference research and real three-view image digests before shutdown')
  } else {
    assert.deepEqual(signature, JSON.parse(await fs.readFile(`${root}/restore-baseline.json`, 'utf8')))
    result.checks.push('All18 cases and scientific/version/clinical/report/confirmation/opinion/annotation/feature values identical to original baseline; reference research and three-view MRI/mask PNG SHA256 identical')
    const oldJob = signature.cases[17].features.id
    const response = await page.request.post(`${api}/research/cases/17/features`)
    assert.equal(response.status(), 202, await response.text())
    const cached = (await response.json()).data
    assert.equal(cached.id, oldJob); assert.equal(cached.cache_hit, true)
    assert.equal(cached.state, 'succeeded')
    result.checks.push('Restored paths recompute cache key correctly: actual POST reuses same stored job/probability, no new feature extraction')
    await page.goto(`${web}/workstation/17`)
    await page.waitForFunction(() => document.querySelectorAll('.slice-img').length === 3 && [...document.querySelectorAll('.slice-img')].every(i => i.complete && i.naturalWidth > 0))
    await page.getByRole('button', { name: 'AI分割叠加', exact: true }).click()
    await page.waitForFunction(() => document.querySelectorAll('.mask-img').length === 3 && [...document.querySelectorAll('.mask-img')].every(i => i.complete && i.naturalWidth > 0))
    for (const [key, label] of [['t1c', 'T1c · 增强 T1'], ['t1n','T1n · 平扫 T1'], ['t2w','T2w · T2'], ['t2f','FLAIR']]) {
      await page.locator('.mri-sequence-select').click(); await page.getByRole('option', { name: label, exact: true }).click()
      await page.waitForFunction(key => {
        const images = [...document.querySelectorAll('.slice-img')]
        const masks = [...document.querySelectorAll('.mask-img')]
        // A sequence change temporarily unmounts all viewports; [].every() is true.
        // Wait for three actual rendered images AND overlays, never an empty set.
        return document.querySelector('.current-sequence')?.dataset.sequence === key &&
          images.length === 3 && masks.length === 3 &&
          images.every(i => i.complete && i.naturalWidth > 0 && new URL(i.src).searchParams.get('sequence') === key) &&
          masks.every(i => i.complete && i.naturalWidth > 0)
      }, key)
      await page.getByRole('option', { name: label, exact: true }).waitFor({ state: 'hidden' })
      await page.screenshot({ path: `${output}/${key}.png`, fullPage: true })
    }
    const detail = await get('/cases/17/detail')
    const file = await page.request.get(api + detail.mri.file_url)
    assert.equal(file.status(), 200)
    assert.equal(createHash('sha256').update(await file.body()).digest('hex'), detail.analysis.result.input_sha256.t2f)
    result.checks.push('Configured restored static mount serves exact MRI bytes; actual restored four-sequence browser and overlay load successfully')
    await page.goto(`${web}/report?case_id=17`)
    await page.locator('#report-paper').waitFor()
    assert((await page.locator('#report-paper').innerText()).includes(detail.analysis.id))
    assert.equal(await page.getByRole('button', { name: '导出 PDF', exact: true }).isEnabled(), true)
    await page.screenshot({ path: `${output}/report.png`, fullPage: true })
    await page.goto(`${web}/research?case_id=17`)
    await page.locator('.automatic-result').waitFor(); await page.locator('.automatic-result').scrollIntoViewIfNeeded()
    await page.screenshot({ path: `${output}/research.png`, fullPage: true })
    result.checks.push('Restored current report/version and saved automatic-mask research probabilities visible; no PDF re-export or model inference repeated')
  }
  assert.deepEqual(result.errors, []); result.status = 'passed'
} catch (error) {
  result.status = 'failed'; result.error = String(error)
  await page.screenshot({ path: `${output}/failure.png`, fullPage: true }); throw error
} finally {
  await fs.writeFile(`${output}/validation.json`, JSON.stringify(result, null, 2)); await browser.close()
}
console.log(JSON.stringify(result))
