import { test, expect } from '@playwright/test'
import { copyFileSync } from 'node:fs'

// See here how to get started:
// https://playwright.dev/docs/intro
test('visits the app root url', async ({ page }) => {
  await page.goto('/')
  await expect(page.locator('h1')).toHaveText('BrainFusion AI')
})

test('analysis requires a selected case and four sequences', async ({ page }) => {
  await page.goto('/analysis')
  await expect(page.locator('input[type=file]')).toHaveCount(4)
  await expect(page.getByRole('button', { name: '上传四序列', exact: true })).toBeDisabled()
  await expect(page.getByRole('button', { name: '运行分割模型', exact: true })).toBeDisabled()
})

test('resampling is opt-in and preview clearly stays engineering-only', async ({ page }) => {
  const caseId = 987654
  const studyUid = '2.25.987654'
  const roles = ['t1c', 't1n', 't2w', 't2f']
  const geometries = Object.fromEntries(roles.map((role, index) => [role, {
    dimensions: index === 2 ? [512, 512, 26] : [256, 256, 26],
    spacing_xyz_mm: index === 2 ? [0.4296875, 0.4296875, 6.5] : [0.859375, 0.859375, 6.5],
  }]))
  await page.route('**/cases/987654/detail', route => route.fulfill({ json: { code: 200, data: {
    case: { id: caseId, description: 'Synthetic UI fixture', status: 'created' },
    patient: { name: 'SYNTHETIC', age: 40, gender: 'other' }, mri: null, analysis: null, report: null,
  } } }))
  await page.route('**/cases/987654/doctor-opinion', route => route.fulfill({ json: { code: 200, data: { author: '', content: '' } } }))
  await page.route('**/pacs/status', route => route.fulfill({ json: { code: 200, data: { read_available: false, message: 'Synthetic API fixture' } } }))
  await page.route('**/pacs/cases/987654/links', route => route.fulfill({ json: { code: 200, data: { items: [
    { study_uid: studyUid, archive_matches_config: true },
  ] } } }))
  await page.route('**/pacs/cases/987654/conversions', route => route.fulfill({ json: { code: 200, data: { items: [] } } }))
  await page.route('**/pacs/cases/987654/conversion-jobs', route => route.fulfill({ json: { code: 200, data: { items: [] } } }))
  await page.route('**/local-auth/session', route => route.fulfill({ json: { code: 200, data: {
    user: { role: 'doctor', display_name: 'SYNTHETIC reviewer' }, csrf: 'f'.repeat(32),
  } } }))
  await page.route(`**/pacs/studies/${studyUid}/series`, route => route.fulfill({ json: { code: 200, data: { items: roles.map((role, index) => ({
    series_uid: `2.25.${index + 1}`, modality: 'MR', series_number: index + 1, instance_count: 26,
  })) } } }))
  let previewPayload
  await page.route(`**/pacs/cases/${caseId}/conversion-plans/preview`, async route => {
    previewPayload = route.request().postDataJSON()
    const resampling = previewPayload.resample_to_t1c_1mm === true
    await route.fulfill({ json: { code: 200, data: {
      draft_id: 'd'.repeat(32), plan_revision: 'e'.repeat(64), study_uid: studyUid,
      dimensions: resampling ? [220, 220, 163] : [256, 256, 26],
      spacing_xyz_mm: resampling ? [1, 1, 1] : [0.859375, 0.859375, 6.5],
      resampling_applied: resampling, resampling: resampling ? { reference_role: 't1c', interpolation: 'linear' } : null,
      source_geometries: geometries,
      assignments: roles.map((role, index) => ({ role, series_uid: `2.25.${index + 1}`, instance_count: 26 })),
      metadata_geometry_contract_passed: true, source_bytes_captured: false, model_input_eligible: false,
      current_mri_replaced: false, inference_performed: false,
    } } })
  })

  await page.goto(`/case/${caseId}`)
  await page.getByRole('button', { name: '创建转换方案' }).click()
  await expect(page.getByRole('dialog', { name: '创建四序列转换方案' })).toBeVisible()
  const resamplingToggle = page.getByLabel('显式重采样到T1增强1毫米网格')
  await expect(resamplingToggle).not.toBeChecked()
  for (let index = 0; index < roles.length; index += 1) {
    await page.getByRole('dialog', { name: '创建四序列转换方案' }).locator('.el-form-item .el-select').nth(index).click()
    await page.getByRole('option', { name: new RegExp(`2\\.25\\.${index + 1}$`) }).last().click()
  }
  await page.getByLabel('来源说明').fill('SYNTHETIC-protocol-2026')
  await resamplingToggle.check()
  await expect(page.getByText(/不证明胶质瘤模型效能/)).toBeVisible()
  await page.getByRole('button', { name: '检查转换方案' }).click()
  await expect(page.getByText('网格：220 × 220 × 163；间距：1 / 1 / 1 mm')).toBeVisible()
  await expect(page.getByText(/不会自动激活模型输入或启动推理/)).toBeVisible()
  expect(previewPayload.resample_to_t1c_1mm).toBe(true)
})

test('synthetic role review keeps approval and model-input activation as explicit steps', async ({ page }) => {
  const caseId = 987654
  const versionId = 'synthetic-version-20261018'
  const studyUid = '2.25.987654'
  const roles = ['t1c', 't1n', 't2w', 't2f']
  const digest = 'a'.repeat(64)
  const planRevision = 'b'.repeat(64)
  const assignmentDigest = 'c'.repeat(64)
  let loggedIn = false
  let roleReviewPayload
  let activationPayload

  await page.route(`**/cases/${caseId}/detail`, route => route.fulfill({ json: { code: 200, data: {
    case: { id: caseId, description: 'Synthetic role-review fixture', status: 'created' },
    patient: { name: 'SYNTHETIC', age: 40, gender: 'other' }, mri: null, analysis: null, report: null,
  } } }))
  await page.route(`**/cases/${caseId}/doctor-opinion`, route => route.fulfill({ json: { code: 200, data: { author: '', content: '' } } }))
  await page.route('**/pacs/status', route => route.fulfill({ json: { code: 200, data: { read_available: false, message: 'Synthetic API fixture' } } }))
  await page.route(`**/pacs/cases/${caseId}/links`, route => route.fulfill({ json: { code: 200, data: { items: [] } } }))
  await page.route(`**/pacs/cases/${caseId}/conversion-jobs`, route => route.fulfill({ json: { code: 200, data: { items: [] } } }))
  await page.route(`**/pacs/cases/${caseId}/conversions`, route => route.fulfill({ json: { code: 200, data: {
    items: [{ version_id: versionId, study_uid: studyUid, archive_binding_matches_config: true, original_byte_check_enabled: true }],
  } } }))
  await page.route('**/local-auth/session', route => route.fulfill({ json: { code: 200, data: {
    configured: true,
    user: loggedIn ? { role: 'doctor', display_name: 'SYNTHETIC reviewer' } : null,
    csrf: loggedIn ? 'f'.repeat(32) : '',
  } } }))
  await page.route('**/local-auth/login', async route => {
    loggedIn = true
    await route.fulfill({ json: { code: 200, data: { authenticated: true } } })
  })
  await page.route(`**/pacs/cases/${caseId}/conversions/${versionId}/role-review`, async route => {
    if (route.request().method() === 'GET') {
      await route.fulfill({ json: { code: 200, data: {
        review_allowed: true, data_role: 'dicom-metadata-snapshot', version_id: versionId,
        plan_revision: planRevision, assignment_set_sha256: assignmentDigest,
        model_input_eligible: false, current_mri_replaced: false,
        assignments: roles.map((role, index) => ({ role, study_uid: studyUid,
          series_uid: `2.25.${index + 1}`, series_metadata_sha256: digest,
          evidence: { basis: 'SYNTHETIC fixture', evidence_reference: `fixture-${index + 1}` },
        })), history: [],
      } } })
      return
    }
    roleReviewPayload = route.request().postDataJSON()
    await route.fulfill({ json: { code: 200, data: {
      review_id: 'synthetic-review-id', decision: 'approve', review_status: 'approved',
      plan_revision: planRevision, assignment_set_sha256: assignmentDigest,
      model_input_eligible: false, current_mri_replaced: false,
      reviewer_authenticated: true, professional_credential_verified: false,
      reviewer: { display_name: 'SYNTHETIC reviewer' }, reviewed_utc: '2026-10-18T00:00:00Z',
    } } })
  })
  await page.route(`**/pacs/cases/${caseId}/conversions/${versionId}/activate-model-input`, async route => {
    activationPayload = route.request().postDataJSON()
    await route.fulfill({ json: { code: 200, data: {
      mri_id: 17, conversion_version_id: versionId, model_input_eligible: true,
      current_mri_replaced: true, inference_performed: false, original_dicom_modified: false,
      previous_mri_and_analysis_history_preserved: true,
    } } })
  })

  await page.goto(`/case/${caseId}`)
  await page.getByRole('button', { name: '查看角色审核' }).click()
  const dialog = page.getByRole('dialog', { name: 'DICOM 四序列角色审核' })
  await expect(dialog).toBeVisible()
  await expect(dialog.locator('.role-review-assignments')).toContainText('t1c')
  await expect(dialog.locator('.role-review-assignments')).toContainText('t2f')
  await dialog.getByLabel('本地审核账户名').fill('synthetic-doctor')
  await dialog.getByLabel('本地审核账户密码').fill('synthetic-password')
  await dialog.getByRole('button', { name: '登录本地账户' }).click()
  await expect(dialog.getByText(/当前本地账户：SYNTHETIC reviewer/)).toBeVisible()
  await dialog.getByText('我已逐项核对四个序列角色与来源声明', { exact: true }).click()
  await dialog.getByRole('button', { name: '确认角色映射' }).click()
  await expect(dialog.getByRole('region', { name: '角色审核历史' })).toContainText('已确认')
  await expect(dialog.getByText('角色映射已记录；当前MRI与AI输入保持不变。')).toBeVisible()
  expect(roleReviewPayload).toMatchObject({ decision: 'approve', plan_revision: planRevision,
    assignment_set_sha256: assignmentDigest, confirm_roles: true })

  const activate = dialog.getByRole('button', { name: '审核后切换AI输入' })
  await expect(activate).toBeDisabled()
  await dialog.getByText('我确认切换当前模型输入并保留旧结果为历史', { exact: true }).click()
  await activate.click()
  await expect(dialog.getByText('已切换当前四序列MRI输入；未运行分割或预测，旧结果保留为历史。')).toBeVisible()
  expect(activationPayload).toMatchObject({ plan_revision: planRevision,
    assignment_set_sha256: assignmentDigest, confirm_activation: true })
})

test('analysis page shows archived runs without presenting their old result payload', async ({ page }) => {
  const caseId = 2468
  const oldRunId = 'archived-run-20261018'
  await page.route(`**/analysis/${caseId}`, route => route.fulfill({ json: { code: 200, data: null } }))
  await page.route(`**/analysis/${caseId}/history`, route => route.fulfill({ json: { code: 200, data: [{
    id: oldRunId, case_id: caseId, state: 'succeeded', current: false,
    created_time: '2026-10-18T08:00:00+00:00',
    result: { note: 'OLD_SECRET_RESULT_MUST_NOT_BE_SHOWN' },
  }] } }))

  await page.goto(`/analysis?case_id=${caseId}`)
  const history = page.locator('.analysis-history')
  await expect(history).toContainText('分析历史')
  const archived = history.locator(`[data-run-id="${oldRunId}"]`)
  await expect(archived).toContainText('历史版本')
  await expect(archived).toContainText('完成')
  await expect(archived).toContainText('已保留为历史')
  await expect(archived).not.toContainText('OLD_SECRET_RESULT_MUST_NOT_BE_SHOWN')
})

test('analysis history stays available when current status endpoint fails', async ({ page }) => {
  const caseId = 'status-unavailable'
  await page.route(`**/analysis/${caseId}`, route => route.fulfill({ status: 503, json: { detail: 'Synthetic status outage' } }))
  await page.route(`**/analysis/${caseId}/history`, route => route.fulfill({ json: { code: 200, data: [
    { id: 'archived-during-outage', case_id: caseId, state: 'succeeded', current: false },
  ] } }))

  await page.goto(`/analysis?case_id=${caseId}`)
  const history = page.locator('.analysis-history')
  await expect(page.locator('.el-alert--error')).toContainText('Synthetic status outage')
  await expect(history.locator('[data-run-id="archived-during-outage"]')).toBeVisible()
  await expect(history.locator('.el-alert--warning')).toHaveCount(0)
})

test('analysis history ignores late responses after case switch', async ({ page }) => {
  let releaseCaseA
  let caseAHistoryRequested
  const caseARequested = new Promise(resolve => { caseAHistoryRequested = resolve })
  const delayedCaseA = new Promise(resolve => { releaseCaseA = resolve })
  await page.route('**/analysis/*/history', async route => {
    const url = new URL(route.request().url())
    const id = url.pathname.split('/')[2]
    if (id === 'case-a') {
      caseAHistoryRequested()
      await delayedCaseA
      await route.fulfill({ json: { code: 200, data: [{ id: 'run-case-a', case_id: id, state: 'succeeded', current: false }] } })
      return
    }
    await route.fulfill({ json: { code: 200, data: [{ id: 'run-case-b', case_id: id, state: 'succeeded', current: true }] } })
  })
  await page.route('**/analysis/case-a', route => route.fulfill({ json: { code: 200, data: null } }))
  await page.route('**/analysis/case-b', route => route.fulfill({ json: { code: 200, data: null } }))

  await page.goto('/analysis?case_id=case-a')
  await caseARequested
  await page.goto('/analysis?case_id=case-b')
  const history = page.locator('.analysis-history')
  await expect(history.locator('[data-run-id="run-case-b"]')).toBeVisible()
  releaseCaseA()
  await expect(history.locator('[data-run-id="run-case-b"]')).toBeVisible()
  await expect(history.locator('[data-run-id="run-case-a"]')).toHaveCount(0)
})
test('current report shows model and input artifact digests without filesystem paths', async ({ page }) => {
  const modelRevision = 'c'.repeat(40)
  const checkpointDigest = 'a'.repeat(64)
  const maskDigest = 'b'.repeat(64)
  const inputDigests = { t1c: '1'.repeat(64), t1n: '2'.repeat(64), t2w: '3'.repeat(64), t2f: '4'.repeat(64) }
  await page.route('**/cases/123/detail', route => route.fulfill({ json: { code: 200, data: {
    case: { id: 123, description: 'Synthetic report fixture', status: 'analyzed' },
    patient: { name: 'Synthetic', age: 50, gender: 'female' },
    mri: { id: 7, filename: 'fixture.nii.gz', modality: 'MRI', doctor_verified: false },
    report: { id: 9, analysis_run_id: 'run-current-123', summary: ['Synthetic segmentation only'],
      recommendation: ['Review boundaries'], created_time: '2026-10-13T14:00:00+00:00' },
    analysis: { id: 'run-current-123', state: 'succeeded', stale: false, result: {
      model: 'Synthetic MONAI contract', revision: modelRevision, checkpoint_sha256: checkpointDigest, mask_sha256: maskDigest,
      input_sha256: inputDigests, volumes_ml: { WT: 1.25 },
    } },
  } } }))
  await page.route('**/cases/123/doctor-opinion', route => route.fulfill({ json: { code: 200, data: { author: '', content: '' } } }))
  await page.route('**/reports/123', route => route.fulfill({ json: { code: 200, data: {
    id: 9, analysis_run_id: 'run-current-123', summary: ['Synthetic segmentation only'],
    recommendation: ['Review boundaries'],
  } } }))
  await page.goto('/report?case_id=123')

  const provenance = page.locator('.provenance-section')
  await expect(provenance).toContainText('run-current-123')
  await expect(provenance).toContainText('模型修订标识')
  await expect(provenance).toContainText(modelRevision)
  await expect(provenance).toContainText('模型权重 SHA-256')
  await expect(provenance).toContainText(checkpointDigest)
  await expect(provenance).toContainText(maskDigest)
  for (const digest of Object.values(inputDigests)) await expect(provenance).toContainText(digest)
  await expect(page.locator('#report-paper')).toContainText('Synthetic MONAI contract')
  await expect(provenance).not.toContainText('E:/')
  await expect(provenance).not.toContainText('C:/')
  const [download] = await Promise.all([
    page.waitForEvent('download'),
    page.getByRole('button', { name: '导出 PDF' }).click(),
  ])
  if (process.env.BRAINFUSION_REPORT_PDF_PATH) {
    const downloadedPath = await download.path()
    if (!downloadedPath) throw new Error('Browser did not retain the synthetic PDF download')
    copyFileSync(downloadedPath, process.env.BRAINFUSION_REPORT_PDF_PATH)
  }
  if (process.env.BRAINFUSION_REPORT_EVIDENCE_PATH) {
    await provenance.screenshot({ path: process.env.BRAINFUSION_REPORT_EVIDENCE_PATH })
  }
})

test('configured live report uses the actual model checkpoint digest', async ({ page }) => {
  const caseId = process.env.BRAINFUSION_LIVE_REPORT_CASE_ID
  test.skip(!caseId, 'Set BRAINFUSION_LIVE_REPORT_CASE_ID only for an approved local case')
  await page.goto(`/report?case_id=${encodeURIComponent(caseId)}`)
  const provenance = page.locator('.provenance-section')
  await expect(provenance).toContainText('模型修订标识')
  await expect(provenance).toContainText('模型权重 SHA-256')
  const digests = provenance.locator('code')
  await expect(digests).toHaveCount(7)
  const values = (await digests.allTextContents()).map(digest => digest.trim())
  expect(values[0]).toMatch(/^[a-f0-9]{40}$/i) // Model source revision.
  for (const digest of values.slice(1)) expect(digest).toMatch(/^[a-f0-9]{64}$/i)
  await expect(provenance).not.toContainText('E:/')
  await expect(provenance).not.toContainText('C:/')
  if (process.env.BRAINFUSION_LIVE_REPORT_PDF_PATH) {
    const [download] = await Promise.all([
      page.waitForEvent('download'),
      page.getByRole('button', { name: '导出 PDF' }).click(),
    ])
    const downloadedPath = await download.path()
    if (!downloadedPath) throw new Error('Browser did not retain the configured live report PDF')
    copyFileSync(downloadedPath, process.env.BRAINFUSION_LIVE_REPORT_PDF_PATH)
  }
})
