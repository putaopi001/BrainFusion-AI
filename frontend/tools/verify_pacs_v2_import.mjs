// Actual prepared-v2 import in an owned archive/database copy, then restart persistence.
import fs from 'node:fs/promises'
import assert from 'node:assert/strict'
import {chromium} from '@playwright/test'
const [rawRoot,mode='import']=process.argv.slice(2);const root=rawRoot?.replaceAll('\\','/')
assert.ok(root?.startsWith('E:/BrainFusion-Runtime/results/nightly/'));assert.ok(['import','resume','restart'].includes(mode))
const registry=JSON.parse(await fs.readFile('E:/BrainFusion-Runtime/local/processes.json','utf8'))
assert.equal(registry.runtime_paths.DATABASE_PATH.replaceAll('\\','/'),root+'/database-backup/restored-validation.db')
const candidates=JSON.parse(await fs.readFile(root+'/registered-candidates.json','utf8')).data.items;assert.equal(candidates.length,1)
const c=candidates[0],api='http://127.0.0.1:8012',importPath='/pacs/imports/'+c.candidate_id
const out=root+'/v2-browser-'+mode;await fs.mkdir(out)
const browser=await chromium.launch({headless:true});const page=await browser.newPage({viewport:{width:1600,height:1100}})
const result={status:'running',mode,checks:[],writes:[],pageErrors:[],frames:[]}
const get=async path=>{const r=await page.request.get(api+path);assert.equal(r.status(),200,await r.text());return (await r.json()).data}
page.on('pageerror',e=>result.pageErrors.push(e.message))
page.on('response',r=>{if(r.url().includes('/frames/1?'))result.frames.push(r.status())})
await page.route('**/*',async route=>{
 const r=route.request(),path=new URL(r.url()).pathname
 if(!['GET','HEAD'].includes(r.method())){
  result.writes.push({method:r.method(),path})
  assert.ok(['import','resume'].includes(mode));assert.equal(r.method(),'POST');if(mode==='resume')assert.notEqual(path,importPath)
  assert.ok([importPath,'/pacs/cases/19/links'].includes(path))
  assert.deepEqual(r.postDataJSON(),path===importPath?{acknowledge_reviewed_local_viewing_only:true}:{study_uid:c.study_uid,acknowledge_case_match:true})
  assert.equal(r.headers()['authorization'],undefined)
 }
 return route.continue()
})
try{
 await page.goto('http://127.0.0.1:5179/case/19')
 const panel=page.locator('.pacs-panel'),box=page.getByRole('region',{name:'受控本机DICOM导入'})
 await page.waitForFunction(()=>document.querySelector('.pacs-import .el-select')!==null)
 if(mode!=='restart'){
  if(mode==='import'){
  assert.equal(await box.getByRole('button',{name:'导入所选资料',exact:true}).isDisabled(),true)
  await box.getByText('已核对资料来源与像素处理范围，仅导入归档',{exact:true}).click()
  const requestStarted=page.waitForRequest(r=>r.method()==='POST' && new URL(r.url()).pathname===importPath)
  const began=Date.now();await box.getByRole('button',{name:'导入所选资料',exact:true}).click();await requestStarted
  let first
  for(let i=0;i<150;i++){
   first=await get(importPath);if(first)break;await page.waitForTimeout(100)
  }
  assert.ok(first?.id);result.observed_state_before_refresh=first.state
  await page.reload();await page.locator(`.pacs-import-status[data-import-id="${first.id}"]`).waitFor({timeout:30000})
  await page.waitForFunction(()=>/上次导入完成|上次导入失败/.test(document.querySelector('.pacs-import-status')?.textContent||''),undefined,{timeout:120000})
  const receipt=await get(importPath);assert.equal(receipt.state,'succeeded');assert.equal(receipt.id,first.id)
  assert.equal(receipt.verified,192);assert.equal(receipt.stored_new,192);assert.equal(receipt.already_stored,0)
  result.receipt=receipt;result.import_observation_ms=Date.now()-began
  await box.screenshot({path:out+'/v2-new-import-receipt.png'})
  }else{
   const first=JSON.parse(await fs.readFile(root+'/v2-browser-import/validation.json','utf8'))
   assert.deepEqual(await get(importPath),first.receipt)
   result.receipt=first.receipt;result.import_observation_ms=first.import_observation_ms
   result.checks.push('Resumed the already successful v2 import receipt; no duplicate import request')
   await box.screenshot({path:out+'/v2-existing-receipt.png'})
  }
  await panel.getByRole('button',{name:'查询检查',exact:true}).click()
  const study=panel.locator('.el-table').first().locator('.el-table__body tr').filter({hasText:c.study_uid})
  await study.waitFor();await page.waitForFunction(()=>!document.querySelector('.pacs-panel').classList.contains('is-busy'));await study.click()
  const selection=panel.locator('.pacs-selection')
  await selection.getByText('已核对该检查与当前病例相符',{exact:true}).click()
  await selection.getByRole('button',{name:'关联到病例 #19',exact:true}).click()
  await page.waitForFunction(()=>!document.querySelector('.pacs-panel').classList.contains('is-busy'))
  assert.ok((await get('/pacs/cases/19/links')).items.some(x=>x.study_uid===c.study_uid && x.archive_matches_config))
  const series=selection.locator('.el-table').first().locator('.el-table__body tr').filter({hasText:c.series_uid})
  await series.waitFor();await series.click()
  await panel.getByRole('button',{name:'核对序列空间',exact:true}).click()
  const view=panel.getByRole('button',{name:'Cornerstone 阅片（工程验证）',exact:true})
  await view.waitFor();const loadStart=Date.now();await view.click()
  await page.locator('.cs-viewer[data-source="dicom"][data-state="ready"]').waitFor({timeout:120000})
  result.first_viewer_load_ms=Date.now()-loadStart
  assert.equal(await page.locator('.cs-viewport canvas').count(),3)
  const expected=JSON.parse(await fs.readFile(root+'/expected-volume.json','utf8'))
  result.volume=await page.evaluate(async()=>{
   const core=await import(performance.getEntriesByType('resource').find(r=>/\/@cornerstonejs_core\.js/.test(r.name)).name)
   const volume=core.cache.getVolume(core.getRenderingEngines()[0].getViewports()[0].getVolumeId())
   const scalar=volume.voxelManager.getCompleteScalarDataArray()
   const digest=new Uint8Array(await crypto.subtle.digest('SHA-256',Float64Array.from(scalar).buffer))
   return {dimensions:volume.dimensions,voxel_count:scalar.length,float64_le_sha256:[...digest].map(b=>b.toString(16).padStart(2,'0')).join('')}
  })
  assert.equal(result.volume.voxel_count,expected.voxel_count);assert.equal(result.volume.float64_le_sha256,expected.float64_le_sha256)
  assert.deepEqual(result.volume.dimensions,expected.dimensions);assert.equal(result.frames.length,192);assert.ok(result.frames.every(s=>s===200))
  assert.equal(result.writes.length,mode==='resume'?1:2)
  await page.locator('.cs-viewer').screenshot({path:out+'/v2-three-views.png'})
  result.checks.push('Actual v2 import creates 192 new instances only in isolated archive, refresh restores same receipt; explicit UI case association; new UIDs loaded in Cornerstone three views, all voxels match independent source decode')
 }else{
  const previous=JSON.parse(await fs.readFile(root+'/v2-browser-resume/validation.json','utf8'))
  await page.locator(`.pacs-import-status[data-import-id="${previous.receipt.id}"]`).waitFor({timeout:30000})
  assert.deepEqual(await get(importPath),previous.receipt)
  assert.ok((await get('/pacs/cases/19/links')).items.some(x=>x.study_uid===c.study_uid && x.archive_matches_config))
  const manifest=await get(`/pacs/cases/19/studies/${c.study_uid}/series/${c.series_uid}/view-manifest`)
  assert.equal(manifest.instance_count,192);assert.equal(manifest.source_case_id,19)
  await box.screenshot({path:out+'/v2-restart-receipt.png'})
  assert.deepEqual(result.writes,[])
  result.checks.push('Actual backend and isolated Orthanc restart retains original v2 receipt, 192-instance manifest and explicit case association; zero duplicate import requests')
 }
 assert.deepEqual(result.pageErrors,[]);result.status='passed'
}catch(e){result.status='failed';result.error=e.stack;await page.screenshot({path:out+'/failure.png',fullPage:false}).catch(()=>{});process.exitCode=1}
finally{await fs.writeFile(out+'/validation.json',JSON.stringify(result,null,2),{flag:'wx'});await browser.close();console.log(JSON.stringify({status:result.status,error:result.error,checks:result.checks}))}
