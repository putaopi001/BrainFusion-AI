// Explicit real local import -> refresh durable receipt -> existing case viewer.
import fs from 'node:fs/promises'
import assert from 'node:assert/strict'
import {chromium} from '@playwright/test'
const root=process.argv[2]
const items=JSON.parse(await fs.readFile(root+'/registered-candidates.json','utf8')).data.items
assert.equal(items.length,1)
const candidate=items[0]
const expected=JSON.parse(await fs.readFile(root+'/expected-volume.json','utf8'))
const browser=await chromium.launch({headless:true})
const result={status:'running',candidate_id:candidate.candidate_id,frames:[],writes:[],pageErrors:[],ai_activation:false}
let page
try {
  page=await browser.newPage({viewport:{width:1500,height:1100}})
  page.on('pageerror',error=>result.pageErrors.push(error.message))
  page.on('response',response=>{if(response.url().includes('/frames/1?')) result.frames.push(response.status())})
  const importPath='/pacs/imports/'+candidate.candidate_id
  await page.route('**/*',async route=>{
    const request=route.request()
    if(!['GET','HEAD'].includes(request.method())) {
      result.writes.push({method:request.method(),path:new URL(request.url()).pathname})
      assert.equal(request.method(),'POST')
      assert.equal(new URL(request.url()).pathname,importPath)
      assert.deepEqual(request.postDataJSON(),{acknowledge_reviewed_local_viewing_only:true})
      assert.equal(request.headers()['authorization'],undefined)
    }
    await route.continue()
  })
  const started=Date.now()
  await page.goto('http://127.0.0.1:5179/case/19')
  const importPanel=page.getByRole('region',{name:'受控本机DICOM导入'})
  // section[aria-label] has a region role; all actions use the actual UI.
  await importPanel.getByText('从已核对的本机资料导入',{exact:true}).waitFor()
  const button=importPanel.getByRole('button',{name:'导入所选资料',exact:true})
  await page.waitForFunction(()=>document.querySelector('.pacs-import .el-select')!==null)
  assert.equal(await button.isDisabled(),true)
  const previous=(await (await page.request.get('http://127.0.0.1:8012'+importPath)).json()).data
  await importPanel.getByText('已核对资料来源与像素处理范围，仅导入归档',{exact:true}).click()
  assert.equal(await importPanel.getByRole('checkbox',{name:'已核对资料来源与像素处理范围，仅导入归档',exact:true}).isChecked(),true)
  await page.waitForFunction(()=>!document.querySelector('.pacs-import .el-button').disabled)
  const requestStarted=page.waitForRequest(r=>new URL(r.url()).pathname===importPath && r.method()==='POST')
  await button.click()
  await requestStarted
  let state
  for(let i=0;i<100;i++) {
    const response=await page.request.get('http://127.0.0.1:8012'+importPath)
    assert.equal(response.status(),200)
    state=(await response.json()).data
    if(state && state.id!==previous?.id) break
    await page.waitForTimeout(100)
  }
  assert.ok(state && state.id!==previous?.id)
  result.observed_state_before_refresh=state.state
  result.id=state.id
  await page.reload()
  await page.locator(`.pacs-import-status[data-import-id="${state.id}"]`).waitFor({timeout:20000})
  await page.waitForFunction(()=>{
    const text=document.querySelector('.pacs-import-status')?.textContent || ''
    return text.includes('上次导入完成') || text.includes('上次导入失败')
  },undefined,{timeout:120000})
  const receipt=await page.request.get('http://127.0.0.1:8012'+importPath)
  result.receipt=(await receipt.json()).data
  assert.equal(result.receipt.id,result.id)
  assert.equal(result.receipt.state,'succeeded')
  assert.equal(result.receipt.verified,candidate.instance_count)
  // This known actual series was archived before this run: real reimport proves dedup.
  assert.equal(result.receipt.already_stored,candidate.instance_count)
  assert.equal(result.receipt.stored_new,0)
  result.refresh_restored_same_receipt=true
  result.import_and_receipt_observation_ms=Date.now()-started
  await page.locator('.pacs-import').screenshot({path:root+'/controlled-import-receipt.png'})
  const panel=page.locator('.pacs-panel')
  await panel.getByRole('button',{name:'查询检查',exact:true}).click()
  const study=panel.locator('.el-table').first().locator('.el-table__body tr').filter({hasText:candidate.study_uid})
  await study.waitFor()
  await page.waitForFunction(()=>!document.querySelector('.pacs-panel').classList.contains('is-busy'))
  await study.click()
  const series=panel.locator('.pacs-selection .el-table').first().locator('.el-table__body tr').filter({hasText:candidate.series_uid})
  await series.waitFor()
  await page.waitForFunction(()=>!document.querySelector('.pacs-panel').classList.contains('is-busy'))
  await series.click()
  await panel.getByRole('button',{name:'核对序列空间',exact:true}).click()
  await panel.getByRole('button',{name:'Cornerstone 阅片（工程验证）',exact:true}).click()
  await page.locator('.cs-viewer[data-source="dicom"][data-state="ready"]').waitFor({timeout:120000})
  assert.equal(await page.locator('.cs-viewport canvas').count(),3)
  result.volume=await page.evaluate(async()=>{
    const core=await import('/node_modules/.vite/deps/@cornerstonejs_core.js')
    const view=core.getRenderingEngines()[0].getViewports()[0]
    const volume=core.cache.getVolume(view.getVolumeId())
    const scalar=volume.voxelManager.getCompleteScalarDataArray()
    const raw=new Uint8Array(await crypto.subtle.digest('SHA-256',Float64Array.from(scalar).buffer))
    return {voxel_count:scalar.length,float64_le_sha256:[...raw].map(x=>x.toString(16).padStart(2,'0')).join('')}
  })
  assert.equal(result.volume.voxel_count,expected.voxel_count)
  assert.equal(result.volume.float64_le_sha256,expected.float64_le_sha256)
  assert.equal(result.frames.length,candidate.instance_count)
  assert.ok(result.frames.every(status=>status===200))
  assert.deepEqual(result.pageErrors,[])
  assert.equal(result.writes.length,1)
  await page.locator('.cs-viewer').screenshot({path:root+'/post-import-three-views.png'})
  result.status='passed'
  await fs.writeFile(root+'/controlled-import-browser.json',JSON.stringify(result,null,2),{flag:'wx'})
  console.log('Actual controlled import, durable refresh, dedup and all-voxel viewing passed.')
} catch(error) {
  result.status='failed';result.error=error.message
  if(page) result.visible_error=await page.locator('.pacs-panel').innerText().catch(()=>'')
  await fs.writeFile(root+'/controlled-import-browser-failed-'+Date.now()+'.json',JSON.stringify(result,null,2),{flag:'wx'})
  throw error
} finally {await browser.close()}
