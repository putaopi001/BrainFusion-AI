import { chromium } from '@playwright/test'
import fs from 'node:fs/promises'
import assert from 'node:assert/strict'

const out = process.argv[2]?.replaceAll('\\', '/')
assert.ok(out?.startsWith('E:/BrainFusion-Runtime/results/'))
await fs.mkdir(out)
const browser = await chromium.launch({ channel: 'msedge', headless: true })
const page = await browser.newPage({ viewport: { width: 1440, height: 1100 } })
const result = { status: 'running', scope: 'Actual UI with synthetic HTTP fixtures; no archive reads, original files, conversion or business writes', checks: [], writes: [], errors: [] }
const study = '2.25.12345'
const series = ['2.25.201','2.25.202','2.25.203','2.25.204']
const job = 'b'.repeat(32)
let jobs = [], loggedIn = true, evidence = ''
page.on('pageerror', e => result.errors.push(String(e)))
page.on('console', msg => { if (msg.type() === 'error') result.errors.push(msg.text()) })
await page.route('**/cases/19/detail', async route => route.fulfill({status:200,json:{code:200,data:{case:{id:19,description:'SYNTHETIC plan fixture',status:'uploaded'},patient:{name:'SYNTHETIC',age:40,gender:'other'},mri:{id:1,filename:'SYNTHETIC',preview_urls:[],preview_views:{},has_preview:false},analysis:null,prediction:null,report:null,legacy_outputs:{available:false}}}}))
await page.route('**/cases/19/doctor-opinion', async route => route.fulfill({status:200,json:{code:200,data:{author:'',content:''}}}))
await page.route('**/pacs/**', async route => {
  const request = route.request(), path = new URL(request.url()).pathname
  const ok = data => route.fulfill({ status: 200, headers: { 'content-type': 'application/json', 'cache-control': 'no-store' }, body: JSON.stringify({ code:200, data }) })
  if (path === '/pacs/status') return ok({ read_available:true, import_available:false, message:'SYNTHETIC archive fixture' })
  if (path === '/pacs/cases/19/links') return ok({ items:[{ study_uid:study, archive_matches_config:true }] })
  if (path === '/pacs/cases/19/conversions') return ok({ items:[], message:'SYNTHETIC no registered conversion' })
  if (path === '/pacs/cases/19/conversion-jobs') return ok({ items:jobs })
  if (path === '/pacs/import-candidates') return ok({ items:[] })
  if (path === `/pacs/studies/${study}/series`) return ok({ items:series.map((series_uid,i)=>({series_uid,modality:'MR',series_number:i+1,instance_count:3})) })
  if (path === `/pacs/cases/19/conversion-plans/preview`) {
    assert.equal(request.method(),'POST'); assert.equal(request.headers()['x-bf-csrf'],'synthetic-csrf')
    const body=request.postDataJSON(); evidence=body.evidence_text
    assert.deepEqual(body.assignments.map(x=>x.series_uid),series)
    result.writes.push({ path, bodyKeys:Object.keys(body), containsClientPath:Object.values(body).some(x=>typeof x==='string'&&/^[A-Z]:[\\/]/i.test(x)) })
    return ok({ draft_id:'c'.repeat(32),plan_revision:'d'.repeat(64),study_uid:study,dimensions:[3,3,3],spacing_xyz_mm:[1,1,1],assignments:body.assignments.map((x,i)=>({role:x.role,series_uid:x.series_uid,instance_count:3})),metadata_geometry_contract_passed:true,source_bytes_captured:false,model_input_eligible:false,current_mri_replaced:false,inference_performed:false })
  }
  if (path === `/pacs/cases/19/conversion-plans/jobs`) {
    assert.equal(request.method(),'POST'); assert.equal(request.headers()['x-bf-csrf'],'synthetic-csrf')
    const body=request.postDataJSON(); assert.deepEqual(body,{draft_id:'c'.repeat(32),plan_revision:'d'.repeat(64),acknowledge_roles:true})
    result.writes.push({ path, bodyKeys:Object.keys(body), containsClientPath:false })
    jobs=[{job_id:job,case_id:19,state:'queued',attempt:1,registered:false,model_input_eligible:false,current_mri_replaced:false,inference_performed:false}]
    return ok(jobs[0])
  }
  return route.fulfill({status:404,json:{detail:{message:'Unexpected synthetic PACS route'}}})
})
await page.route('**/local-auth/**', async route => {
  const path=new URL(route.request().url()).pathname
  if(path==='/local-auth/session') return route.fulfill({status:200,headers:{'content-type':'application/json'},body:JSON.stringify({code:200,data:{user:loggedIn?{role:'doctor',display_name:'SYNTHETIC doctor'}:null,csrf:loggedIn?'synthetic-csrf':''}})})
  if(path==='/local-auth/login'){loggedIn=true;return route.fulfill({status:200,json:{code:200,data:{authenticated:true}}})}
  return route.fulfill({status:404,json:{}})
})
try {
  await page.goto('http://127.0.0.1:5179/case/19')
  const section=page.getByRole('region',{name:'持久DICOM转换作业'})
  await section.getByRole('button',{name:'创建转换方案'}).click()
  const dialog=page.getByRole('dialog',{name:'创建四序列转换方案'})
  await dialog.waitFor()
  for(const [index,[role,uid]] of [['t1c',series[0]],['t1n',series[1]],['t2w',series[2]],['t2f',series[3]]].entries()) {
    const combo=dialog.getByLabel(`转换序列-${role}`)
    await combo.click({force:true})
    await page.locator('.el-select-dropdown:visible .el-select-dropdown__item').filter({hasText:uid}).last().evaluate(el=>el.click())
    await page.waitForTimeout(300)
    const selected=await dialog.locator('.el-form-item').nth(index).locator('.el-select__selected-item:not(.el-select__input-wrapper)').innerText()
    assert.ok(selected.includes(uid),`Expected ${role} to select ${uid}; got ${selected}`)
  }
  await dialog.getByLabel('序列来源说明').fill('SYNTHETIC.protocol.v1')
  await dialog.getByRole('button',{name:'检查转换方案'}).click()
  await dialog.getByText(/元数据与空间检查通过/).waitFor()
  await dialog.locator('.el-checkbox__label').click()
  await dialog.getByRole('button',{name:'创建转换任务'}).click()
  await section.getByText(job,{exact:false}).waitFor()
  assert.equal(evidence,'SYNTHETIC.protocol.v1')
  assert.equal(result.writes.length,2)
  assert.ok(result.writes.every(x=>!x.containsClientPath))
  assert.deepEqual(result.errors,[])
  result.checks.push('Four roles are explicitly selected from one linked study; browser sends only UIDs and a non-identifying evidence reference')
  result.checks.push('Preview and create require doctor session/CSRF; successful response is queued and remains model-ineligible')
  await page.screenshot({path:out+'/conversion-plan.png',fullPage:true})
  result.status='passed'
} catch(e) { result.status='failed';result.error=e.stack;process.exitCode=1;await page.screenshot({path:out+'/failure.png',fullPage:true}).catch(()=>{}) }
finally { await fs.writeFile(out+'/validation.json',JSON.stringify(result,null,2));await browser.close();console.log(JSON.stringify({status:result.status,checks:result.checks,error:result.error})) }











