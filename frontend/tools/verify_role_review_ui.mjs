// B1 role-review interaction with isolated API fixtures; no business writes.
import { chromium } from '@playwright/test'
import fs from 'node:fs/promises'
import assert from 'node:assert/strict'

const root=process.argv[2]?.replaceAll('\\','/')
assert.ok(root?.startsWith('E:/BrainFusion-Runtime/results/nightly/'))
const out=root+'/role-review-ui'
await fs.mkdir(out)
const browser=await chromium.launch({channel:'msedge',headless:true})
const page=await browser.newPage({viewport:{width:1500,height:1000}})
const result={status:'running',browser:await browser.version(),checks:[],writes:[],errors:[],posted:null,activation:null}
page.on('pageerror',error=>result.errors.push(error.message))
const assignments=['t1c','t1n','t2w','t2f'].map((role,index)=>({
  role,study_uid:'2.25.100',series_uid:'2.25.'+(200+index),series_metadata_sha256:String(index+1).repeat(64),
  frame_of_reference_uid:'2.25.900',geometry_sha256:'a'.repeat(64),
  evidence:{basis:'acquisition_record',evidence_sha256:'b'.repeat(64),evidence_reference:'SYNTHETIC.ui-fixture',confirmed_at:'2026-10-17T00:00:00Z'}
}))
const preview={plan_revision:'c'.repeat(64),data_role:'dicom-metadata-snapshot',assignments,
  assignment_set_sha256:'d'.repeat(64),review_allowed:true,role_confirmation_status:'awaiting_authenticated_local_review',
  model_input_eligible:false,current_mri_replaced:false,history:[]}
await page.route('http://127.0.0.1:8012/cases/19/detail',route=>route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({code:200,data:{
  case:{id:19,description:'SYNTHETIC browser fixture',status:'uploaded'},patient:{name:'SYNTHETIC',age:40,gender:'other'},
  mri:{id:1,filename:'SYNTHETIC MRI',file_url:null,preview_urls:[],preview_views:{axial:[],coronal:[],sagittal:[]},has_preview:false},
  prediction:null,analysis:null,report:null,legacy_outputs:{available:false,has_prediction:false,has_report:false}}})}))
await page.route('http://127.0.0.1:8012/cases/19/doctor-opinion',route=>route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({code:200,data:{author:'',content:''}})}))
await page.route('http://127.0.0.1:8012/local-auth/session',route=>route.fulfill({status:200,contentType:'application/json',
  body:JSON.stringify({code:200,data:{configured:true,user:{id:'a'.repeat(32),username:'doctor-fixture',display_name:'SYNTHETIC reviewer',role:'doctor'},
  csrf:'csrf-fixture',professional_credential_verified:false}})}))
await page.route('http://127.0.0.1:8012/pacs/cases/19/conversions',route=>route.fulfill({status:200,contentType:'application/json',
  body:JSON.stringify({code:200,data:{state:'registered',message:'SYNTHETIC UI fixture',items:[{version_id:'review-fixture',
  study_uid:'2.25.100',archive_binding_matches_config:true,original_byte_check_enabled:true,
  integrity_status:'not_rechecked',model_input_eligible:false}]}})}))
await page.route('http://127.0.0.1:8012/pacs/cases/19/conversions/review-fixture/role-review',async route=>{
  if(route.request().method()==='GET'){await route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({code:200,data:preview})});return}
  if(route.request().method()==='POST'){
    const request=route.request();result.posted={body:request.postDataJSON(),csrf:request.headers()['x-bf-csrf'],method:request.method()}
    result.writes.push(new URL(request.url()).pathname)
    await route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({code:200,data:{
      review_id:'e'.repeat(32),decision:'approve',review_status:'approved',
      binding:{version_id:'review-fixture',report_sha256:'f'.repeat(64),proposal_sha256:'1'.repeat(64),snapshots_sha256:'2'.repeat(64)},
      plan_revision:preview.plan_revision,assignment_set_sha256:preview.assignment_set_sha256,
      reviewer:{id:'a'.repeat(32),username:'doctor-fixture',display_name:'SYNTHETIC reviewer',role:'doctor',professional_credential_verified:false},
      reviewer_authenticated:true,professional_credential_verified:false,model_input_eligible:false,current_mri_replaced:false,reviewed_utc:'2026-10-17T00:00:00Z'
    }})});return
  }
  await route.fallback()
})
await page.route('http://127.0.0.1:8012/pacs/cases/19/conversions/review-fixture/activate-model-input',async route=>{
  if(route.request().method()!=='POST'){await route.fallback();return}
  result.activation={body:route.request().postDataJSON(),csrf:route.request().headers()['x-bf-csrf'],method:route.request().method()}
  result.writes.push(new URL(route.request().url()).pathname)
  await route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({code:200,data:{
    mri_id:77,status:'preview_ready',input_source:'dicom-conversion',conversion_version_id:'review-fixture',
    plan_revision:preview.plan_revision,model_input_eligible:true,current_mri_replaced:true,inference_performed:false,
    original_dicom_modified:false,previous_mri_and_analysis_history_preserved:true,annotations_marked_obsolete:true
  }})})
})
try{
  await page.goto('http://127.0.0.1:5179/case/19')
  await page.getByText('病例ID: 19',{exact:false}).waitFor()
  await page.getByRole('button',{name:'查看角色审核',exact:true}).click()
  await page.getByRole('dialog',{name:'DICOM 四序列角色审核'}).waitFor()
  assert.equal(await page.locator('.role-review-assignments .el-table__row').count(),4)
  for(const role of ['t1c','t1n','t2w','t2f'])assert.ok((await page.locator('.role-review-assignments').innerText()).includes(role))
  assert.ok((await page.getByRole('dialog').innerText()).includes('不验证执业资质'))
  result.checks.push('Four explicit role rows and scope disclaimer render in the existing case panel')
  await page.getByRole('dialog').locator('.el-checkbox').click()
  assert.equal(await page.getByRole('button',{name:'审核后切换AI输入',exact:true}).count(),0)
  await page.getByRole('button',{name:'确认角色映射',exact:true}).click()
  await page.getByText('角色映射已记录；当前MRI与AI输入保持不变。',{exact:true}).waitFor()
  assert.equal(result.posted?.method,'POST')
  assert.equal(result.posted?.csrf,'csrf-fixture')
  assert.deepEqual(result.posted?.body,{decision:'approve',plan_revision:preview.plan_revision,
    assignment_set_sha256:preview.assignment_set_sha256,confirm_roles:true})
  const activation=page.getByRole('button',{name:'审核后切换AI输入',exact:true})
  await activation.waitFor()
  assert.equal(await activation.isDisabled(),true)
  await page.getByRole('dialog').locator('.el-checkbox').nth(1).click()
  assert.equal(await activation.isDisabled(),false)
  await activation.click()
  await page.getByText('已切换当前四序列MRI输入；未运行分割或预测，旧结果保留为历史。',{exact:true}).waitFor()
  assert.equal(result.activation?.method,'POST')
  assert.equal(result.activation?.csrf,'csrf-fixture')
  assert.deepEqual(result.activation?.body,{plan_revision:preview.plan_revision,assignment_set_sha256:preview.assignment_set_sha256,confirm_activation:true})
  assert.deepEqual(result.writes,['/pacs/cases/19/conversions/review-fixture/role-review','/pacs/cases/19/conversions/review-fixture/activate-model-input'])
  assert.deepEqual(result.errors,[])
  result.checks.push('Approval does not activate; separate explicit acknowledgement gates version-bound activation, with no inference')
  await page.getByRole('dialog').screenshot({path:out+'/review-dialog.png'})
  result.status='passed'
}catch(error){
  result.status='failed';result.error=error.stack
  await page.screenshot({path:out+'/failure.png'}).catch(()=>{})
  process.exitCode=1
}finally{
  await fs.writeFile(out+'/validation.json',JSON.stringify(result,null,2),{flag:'wx'})
  await browser.close()
  console.log(JSON.stringify({status:result.status,browser:result.browser,checks:result.checks,error:result.error}))
}




