// Real unconfigured API/UI, then explicitly mocked protocol UI. No original DB writes.
import { chromium } from '@playwright/test'
import fs from 'node:fs/promises'
import assert from 'node:assert/strict'
const root = process.argv[2]
const output = root + '/browser-pacs' + (process.argv[3] ? '-' + process.argv[3] : '')
await fs.mkdir(output)
const browser = await chromium.launch({ headless: true })
const page = await browser.newPage({ viewport: { width: 1500, height: 1000 } })
const result = { status: 'running', scope: 'Actual unconfigured service, then explicitly mocked synthetic protocol UI; no Orthanc, real DICOM, or database linking acceptance', pageErrors: [], writesOutsideFixture: [], checks: [] }
page.on('pageerror', e => result.pageErrors.push(e.message))
let mock = false, conflict = false, disconnected = false, links = [], posts = 0
const study = '2.25.123456001', series = '2.25.123456002', instance = '2.25.123456003'
await page.route('**/*', async route => {
  const req = route.request(), url = new URL(req.url())
  if (['POST', 'PUT', 'PATCH', 'DELETE'].includes(req.method()) && !(mock && url.pathname.startsWith('/pacs/'))) {
    result.writesOutsideFixture.push(req.url()); await route.abort(); return
  }
  if (!mock || !url.pathname.startsWith('/pacs/')) { await route.continue(); return }
  if (disconnected && url.pathname === '/pacs/status') { await route.abort('connectionrefused'); return }
  let data, code = 200
  if (url.pathname === '/pacs/status') data = { state: 'ready', read_available: true, import_available: false,
    dicom_view_available: false, ai_bridge_available: false, message: 'SYNTHETIC PROTOCOL UI FIXTURE：仅页面测试，不是真实归档' }
  else if (url.pathname === '/pacs/studies') data = { archive_id: 'synthetic-ui-only', items: [{study_uid:study, study_date:'20000101', modalities:['MR'], series_count:'1'}], next_offset:null }
  else if (url.pathname.endsWith('/series')) data = { items:[{study_uid:study,series_uid:series,modality:'MR',series_number:'1',instance_count:'1'}],next_offset:null }
  else if (url.pathname.endsWith('/instances')) data = { items:[{study_uid:study,series_uid:series,instance_uid:instance,frame_of_reference_uid:'2.25.123456004',instance_number:'1'}],next_offset:null }
  else if (url.pathname.endsWith('/conversions')) data = { state:'not_registered',items:[],message:'SYNTHETIC 无转换版本登记' }
  else if (url.pathname.endsWith('/links')) {
    if (req.method() === 'POST') {
      posts++; const body = req.postDataJSON(); assert.equal(body.study_uid, study); assert.equal(body.acknowledge_case_match, true)
      if (conflict) { code = 409; data = null }
      else { const item = { id:1,case_id:17,archive_id:'synthetic-ui-only',study_uid:study,archive_matches_config:true }; links = [item]; data = item }
    } else data = { items: url.pathname.includes('/17/') ? links : [] }
  } else throw new Error('Unexpected protocol fixture route: ' + url.pathname)
  await route.fulfill({ status: code, contentType: 'application/json', body: JSON.stringify(code === 409 ? {code, detail:{message:'SYNTHETIC 该检查已关联其他病例，拒绝覆盖原关联。'}} : {code,data}) })
})
const panel = page.locator('.pacs-panel')
try {
  const state = await page.request.get('http://127.0.0.1:8012/pacs/status')
  assert.equal(state.status(),200); assert.equal((await state.json()).data.state,'unconfigured')
  assert.equal((await page.request.get('http://127.0.0.1:8012/pacs/studies')).status(),503)
  await page.goto('http://127.0.0.1:5179/case/17')
  await panel.getByText('本地 PACS 尚未配置，DICOM 归档与阅片尚不可用。', {exact:true}).waitFor()
  assert.equal(await panel.getByRole('button', {name:'查询检查',exact:true}).count(),0)
  assert.match(await panel.innerText(), /DICOM 导入、阅片与 AI 输入转换尚未开放/)
  await panel.screenshot({path:output+'/actual-unconfigured.png'})
  await panel.getByRole('button',{name:'刷新归档状态',exact:true}).click()
  await panel.getByText('本地 PACS 尚未配置，DICOM 归档与阅片尚不可用。',{exact:true}).waitFor()
  result.checks.push('Actual API unconfigured + list503; existing case panel unavailable, no DICOM/AI claim or query button')
  mock = true
  await page.reload()
  await panel.getByText(/SYNTHETIC PROTOCOL UI FIXTURE/).waitFor()
  await panel.getByRole('textbox',{name:'检查 UID',exact:true}).fill(study)
  await panel.getByRole('button',{name:'查询检查',exact:true}).click()
  await panel.locator('.el-table__body tr').first().click()
  await panel.getByText('当前检查：', {exact:false}).waitFor()
  await page.waitForFunction(() => !document.querySelector('.pacs-panel').classList.contains('is-busy'))
  const linkButton = panel.getByRole('button',{name:'关联到病例 #17',exact:true})
  assert.equal(await linkButton.isDisabled(),true)
  await panel.locator('.el-table').nth(1).locator('.el-table__body tr').first().click()
  await panel.getByText(instance,{exact:true}).first().waitFor()
  await panel.getByText('已核对该检查与当前病例相符',{exact:true}).click()
  await linkButton.click()
  await panel.locator('.pacs-links li').waitFor()
  assert.equal(posts,1)
  await panel.getByText('已核对该检查与当前病例相符',{exact:true}).click()
  await linkButton.click()
  await page.waitForFunction(() => !document.querySelector('.pacs-panel').classList.contains('is-busy'))
  assert.equal(posts,2); assert.equal(await panel.locator('.pacs-links li').count(),1)
  await page.reload()
  await panel.locator('.pacs-links li').waitFor()
  assert.equal(await panel.locator('.pacs-selection').count(),0)
  assert.equal(await panel.locator('.pacs-links li').count(),1)
  await panel.getByRole('button',{name:'查询检查',exact:true}).click()
  await panel.locator('.el-table__body tr').first().click()
  await page.waitForFunction(() => !document.querySelector('.pacs-panel').classList.contains('is-busy'))
  conflict = true
  await panel.getByText('已核对该检查与当前病例相符',{exact:true}).click()
  await linkButton.click()
  await panel.getByText('SYNTHETIC 该检查已关联其他病例，拒绝覆盖原关联。',{exact:true}).waitFor()
  assert.equal(await panel.locator('.pacs-links li').count(),1)
  await panel.screenshot({path:output+'/synthetic-protocol-conflict.png'})
  await page.evaluate(async () => { const {default:router} = await import('/src/router/index.js'); await router.push('/case/1') })
  await page.waitForURL('**/case/1')
  await panel.getByText('当前病例没有归档检查关联。',{exact:true}).waitFor()
  assert.equal(await panel.locator('.pacs-links li').count(),0)
  assert.equal(await panel.locator('.pacs-selection').count(),0)
  assert.equal(await panel.locator('.el-alert--error').count(),0)
  result.checks.push('SYNTHETIC ONLY: Study/Series/Instance hierarchy, explicit case match, retry UI dedupe, refresh list,409 kept record, SPA case cleanup')
  disconnected = true
  await panel.getByRole('button',{name:'刷新归档状态',exact:true}).click()
  await panel.getByText('归档状态查询失败，请检查本地服务连接。',{exact:true}).waitFor()
  assert.equal(await panel.getByRole('button',{name:'查询检查',exact:true}).count(),0)
  disconnected = false
  await panel.getByRole('button',{name:'刷新归档状态',exact:true}).click()
  await panel.getByText(/SYNTHETIC PROTOCOL UI FIXTURE/).waitFor()
  result.checks.push('Controlled frontend connection refusal is explicit; refresh reconnects, no stuck pending status or fake available archive')
  assert.deepEqual(result.pageErrors,[]); assert.deepEqual(result.writesOutsideFixture,[])
  assert.equal((await (await page.request.get('http://127.0.0.1:8012/pacs/cases/17/links')).json()).data.items.length,0)
  result.status = 'passed'
} catch(e) {result.status='failed'; result.error=e.stack; process.exitCode=1; await page.screenshot({path:output+'/failure.png',fullPage:true})}
finally {await fs.writeFile(output+'/validation.json',JSON.stringify(result,null,2)); await browser.close()}
