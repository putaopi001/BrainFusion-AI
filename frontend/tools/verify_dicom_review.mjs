// Actual public DICOM; all review/measurement writes confined to run-owned DB copy.
import {chromium} from '@playwright/test'
import fs from 'node:fs/promises'
import assert from 'node:assert/strict'
const [root,mode='save',tag]=process.argv.slice(2)
if(!root?.startsWith('E:/BrainFusion-Runtime/results/nightly/') || !['save','restart','readonly','long'].includes(mode)) throw Error('Run root and mode required')
const registered=JSON.parse(await fs.readFile('E:/BrainFusion-Runtime/local/processes.json','utf8'))
if(mode!=='readonly')assert.equal(registered.runtime_paths.DATABASE_PATH.replaceAll('\\','/'),root+'/database-backup/restored-validation.db')
const c=(await (await fetch('http://127.0.0.1:8012/pacs/import-candidates')).json()).data.items[0]
const prefix=`/pacs/cases/19/studies/${c.study_uid}/series/${c.series_uid}`
const endpoint=prefix+'/reviews',reportEndpoint=prefix+'/reading-report'
const url=`http://127.0.0.1:5179/report?case_id=19&source=dicom&study_uid=${c.study_uid}&series_uid=${c.series_uid}`
const output=root+'/dicom-review-'+mode+(tag?'-'+tag:'')
await fs.mkdir(output)
const browser=await chromium.launch({headless:true})
const page=await browser.newPage({viewport:{width:1600,height:1200},acceptDownloads:true})
const result={status:'running',mode,pageErrors:[],writes:[],downloads:[],checks:[]}
page.on('pageerror',e=>result.pageErrors.push(e.message))
page.on('download',d=>result.downloads.push(d.suggestedFilename()))
await page.route('**/*',async route=>{
 const req=route.request()
 if(!['GET','HEAD'].includes(req.method())){
  assert.notEqual(mode,'readonly','No write allowed in original runtime validation')
  assert.equal(req.method(),'POST');assert.equal(new URL(req.url()).pathname,endpoint)
  result.writes.push(req.postDataJSON())
 }
 await route.continue()
})
async function get(path){const response=await page.request.get('http://127.0.0.1:8012'+path);assert.equal(response.status(),200,await response.text());return (await response.json()).data}
async function ready(){
 await page.locator('#report-paper.dicom-report').waitFor({timeout:90000})
 await page.waitForFunction(()=>!document.querySelector('.report-toolbar .el-button.is-loading'))
 await page.locator('.review-editor').waitFor()
}
const button=()=>page.getByRole('button',{name:'保存本版本复核',exact:true})
async function fill(opinion){
 await page.getByRole('textbox',{name:'复核署名',exact:true}).fill('工程流程验收（非医生）')
 await page.getByRole('textbox',{name:'本版本复核意见',exact:true}).fill(opinion)
 if(!await page.locator('.review-editor .el-checkbox input').isChecked())
  await page.locator('.review-editor .el-checkbox__label').click()
}
async function exportPDF(name){
 const download=page.waitForEvent('download',{timeout:90000})
 await page.getByRole('button',{name:'导出 PDF',exact:true}).click()
 await (await download).saveAs(output+'/'+name)
 await page.waitForFunction(()=>!document.querySelector('.report-toolbar .el-button.is-loading'))
}
try{
 await page.goto(url);await ready()
 assert.equal(await button().isDisabled(),true)
 if(mode==='readonly'){
  const report=await get(reportEndpoint)
  assert.equal(report.latest_review,null);assert.equal(report.review_history_count,0)
  assert.equal(await page.locator('.review-history-row').count(),0)
  assert.ok((await page.locator('.review-editor').innerText()).includes('未进行身份或医师资质认证'))
  const select=page.locator('.review-editor .el-select')
  await select.click();await page.getByRole('option',{name:'记录需修改',exact:true}).click()
  assert.ok((await select.innerText()).includes('记录需修改'));assert.equal(await button().isDisabled(),true)
  await select.click();await page.getByRole('option',{name:'已核对本页记录',exact:true}).click()
  await page.screenshot({path:output+'/original-runtime-unreviewed.png',fullPage:true})
  await page.locator('.review-editor').screenshot({path:output+'/original-review-form.png'})
  result.checks.push('Original runtime: no test review, acknowledgment defaults unchecked, save disabled; actual decision dropdown changes and returns without writes')
 }else if(mode==='save'){
  const before=await get(reportEndpoint);assert.equal(before.latest_review,null);assert.equal(before.measurements.length,3)
  await fill('工程流程核对：检查本页来源与三条工程距离。此条仅验收版本绑定，不是医生或临床意见。')
  let drop=true
  await page.route('**'+endpoint,async route=>{
   if(route.request().method()==='POST' && drop){
    drop=false;result.writes.push(route.request().postDataJSON())
    const response=await route.fetch();assert.equal(response.status(),200,await response.text())
    result.lostResponseCommitted=(await response.json()).data.id;await route.abort()
   }else await route.fallback()
  })
  await button().click();await page.locator('.review-editor .el-alert').getByText(/复核保存失败/).waitFor()
  assert.equal((await get(endpoint)).total,1)
  await button().click();await page.locator('.review-save-message').getByText(/已保存/).waitFor();await ready()
  assert.equal(result.writes[0].client_uid,result.writes[1].client_uid)
  const first=await get(reportEndpoint)
  assert.equal(first.latest_review.id,result.lostResponseCommitted);assert.equal(first.review_history_count,1)
  assert.equal(first.content_sha256,before.content_sha256);assert.notEqual(first.export_sha256,before.export_sha256)
  assert.equal(first.latest_review.reviewer_authenticated,false)
  assert.ok((await page.locator('.dicom-review-paper').innerText()).includes('不是医生或临床意见'))
  await page.reload();await ready();assert.equal(await page.locator('.review-history-row').count(),1)
  await exportPDF('reviewed-three-distances.pdf')
  // A second immutable decision on the same source/content changes only export revision.
  const newBody={...result.writes[0],client_uid:'ENGINEERING-NEEDS-REVISION',decision:'needs_revision',opinion:'工程验收：同一内容上的第二条记录，仅验证需修改状态，非临床意见。'}
  const second=await page.request.post('http://127.0.0.1:8012'+endpoint,{data:newBody})
  assert.equal(second.status(),200,await second.text());result.writes.push(newBody)
  await page.getByRole('button',{name:'导出 PDF',exact:true}).click()
  await page.getByText('来源或记录版本已变化，请核对刷新后的报告再导出。',{exact:true}).waitFor();await ready()
  assert.equal(result.downloads.length,1)
  assert.ok((await page.locator('.review-status').innerText()).includes('需修改'))
  // A real saved-measurement deletion invalidates both preceding review snapshots.
  const item=first.measurements[0]
  const deleted=await page.request.delete('http://127.0.0.1:8012'+prefix+'/measurements/'+item.id,{data:{context:first.context}})
  assert.equal(deleted.status(),200,await deleted.text());result.deleted_measurement_id=item.id
  const stale=await page.request.post('http://127.0.0.1:8012'+endpoint,{data:result.writes[0]})
  assert.equal(stale.status(),409)
  await page.getByRole('button',{name:'刷新报告',exact:true}).click();await ready()
  assert.ok((await page.locator('.review-status').innerText()).includes('已过期'))
  assert.equal(await page.locator('.dicom-review-paper').count(),0)
  const history=await get(endpoint)
  assert.equal(history.total,2);assert.ok(history.items.every(row=>!row.current && row.reviewed_snapshot.measurements.length===3))
  await fill('工程流程复核：距离删除后重新核对当前两条记录。非医生意见，不构成临床认证。')
  await button().click();await page.locator('.review-save-message').getByText(/已保存/).waitFor();await ready()
  result.final=await get(reportEndpoint)
  assert.ok(result.final.latest_review.current);assert.equal(result.final.review_history_count,3)
  assert.equal(result.final.measurements.length,2)
  await fs.writeFile(root+'/review-before-restart.json',JSON.stringify(result.final,null,2),{flag:'wx'})
  await page.screenshot({path:output+'/current-and-history.png',fullPage:true})
  // A final render check must also reject a review-only revision change.
  let checks=0
  await page.route('**'+reportEndpoint,async route=>{
   checks++;const response=await route.fetch();const body=await response.json()
   if(checks===3)body.data.export_sha256='f'.repeat(64)
   await route.fulfill({response,json:body})
  })
  await page.getByRole('button',{name:'导出 PDF',exact:true}).click()
  await page.getByText('来源或记录版本已变化，请核对刷新后的报告再导出。',{exact:true}).waitFor();await ready()
  assert.ok(checks>=3);assert.equal(result.downloads.length,1)
  await page.unroute('**'+reportEndpoint)
  result.checks.push('Real source reviews: lost committed response retry once; same-content needs-revision supersedes; actual distance delete invalidates immutable history; re-review binds changed content; review-only export changes and post-render drift block old PDF')
 }else if(mode==='long'){
  const lines=Array.from({length:40},(_,i)=>{
   const prefix=`〔工程段${String(i+1).padStart(3,'0')}〕`
   const text='仅验证本机人工复核的长文本、来源版本与分页，不是医生意见，不构成临床诊断。'
   return (prefix+text.repeat(4)).slice(0,90)+`〔末${String(i+1).padStart(3,'0')}〕`
  })
  const opinion=lines.join('\n')
  assert.ok(opinion.length>3800 && opinion.length<=4000)
  await fill(opinion);await button().click()
  await page.locator('.review-save-message').getByText(/已保存/).waitFor();await ready()
  result.final=await get(reportEndpoint)
  assert.equal(result.final.latest_review.opinion,opinion)
  assert.equal(result.final.review_history_count,4)
  assert.equal((await page.locator('.manual-review-text').innerText()).replaceAll('\n',''),opinion.replaceAll('\n',''))
  await fs.writeFile(root+'/review-before-restart-long.json',JSON.stringify(result.final,null,2),{flag:'wx'})
  result.opinion_characters=opinion.length
  result.checks.push(`Near-limit ${opinion.length}-character/${lines.length}-paragraph engineering note saved through UI and displayed in full; immutable prior review history retained`)
 }else{
  const expected=JSON.parse(await fs.readFile(process.env.REVIEW_EXPECTED_FILE || root+'/review-before-restart.json','utf8'))
  const current=await get(reportEndpoint)
  assert.equal(current.export_sha256,expected.export_sha256)
  assert.deepEqual(current.latest_review,expected.latest_review)
  assert.equal(await page.locator('.review-history-row').count(),expected.review_history_count)
  await exportPDF('reviewed-current-after-restart.pdf')
  await page.screenshot({path:output+'/restored-current-review.png',fullPage:true})
  await page.evaluate(async()=>document.querySelector('#app').__vue_app__.config.globalProperties.$router.push('/report?case_id=17'))
  await page.locator('#report-paper:not(.dicom-report)').waitFor({timeout:60000})
  assert.equal(await page.locator('.review-editor').count(),0)
  assert.ok(!(await page.locator('#report-paper').innerText()).includes(c.study_uid))
  await page.evaluate(async path=>document.querySelector('#app').__vue_app__.config.globalProperties.$router.push(path),url.replace('http://127.0.0.1:5179',''))
  await ready();assert.equal(await page.locator('.review-history-row').count(),expected.review_history_count)
  result.checks.push('Actual service restart preserves latest review and immutable snapshots; current PDF exported; same-component NIfTI switch removes review UI and old DICOM identity')
 }
 assert.deepEqual(result.pageErrors,[]);result.status='passed'
}catch(e){result.status='failed';result.error=e.stack;await page.screenshot({path:output+'/failure.png',fullPage:true});process.exitCode=1}
finally{await fs.writeFile(output+'/validation.json',JSON.stringify(result,null,2));await browser.close()}
