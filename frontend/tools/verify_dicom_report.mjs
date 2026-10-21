// Real archived MR report; all mutations must remain in this run's DB copy.
import {chromium} from '@playwright/test'
import fs from 'node:fs/promises'
import assert from 'node:assert/strict'
const [root,mode='export',tag]=process.argv.slice(2)
if(!root?.startsWith('E:/BrainFusion-Runtime/results/nightly/') || !['export','restart','readonly','pdf'].includes(mode)) throw Error('Run root and mode required')
const registered=JSON.parse(await fs.readFile('E:/BrainFusion-Runtime/local/processes.json','utf8'))
if(mode!=='readonly') assert.equal(registered.runtime_paths.DATABASE_PATH.replaceAll('\\','/'),root+'/database-backup/restored-validation.db')
const candidate=(await (await fetch('http://127.0.0.1:8012/pacs/import-candidates')).json()).data.items[0]
const prefix=`/pacs/cases/19/studies/${candidate.study_uid}/series/${candidate.series_uid}`
const endpoint=prefix+'/reading-report'
const url=`http://127.0.0.1:5179/report?case_id=19&source=dicom&study_uid=${candidate.study_uid}&series_uid=${candidate.series_uid}`
const out=root+'/dicom-report-'+mode+(tag?'-'+tag:'')
await fs.mkdir(out)
const browser=await chromium.launch({headless:true})
const page=await browser.newPage({viewport:{width:1600,height:1200},acceptDownloads:true})
const result={status:'running',mode,pageErrors:[],writes:[],downloads:[],checks:[]}
page.on('pageerror',e=>result.pageErrors.push(e.message))
page.on('download',d=>result.downloads.push(d.suggestedFilename()))
await page.route('**/*',async route=>{
 const req=route.request()
 if(!['GET','HEAD'].includes(req.method())) throw Error('Report page must be read-only: '+req.url())
 await route.continue()
})
const snapshot=async()=>{
 const response=await page.request.get('http://127.0.0.1:8012'+endpoint)
 assert.equal(response.status(),200,await response.text());return (await response.json()).data
}
async function loaded(){await page.locator('#report-paper.dicom-report').waitFor({timeout:90000})}
const btn=()=>page.getByRole('button',{name:'导出 PDF',exact:true})
try{
 if(mode==='readonly'){
  await page.goto('http://127.0.0.1:5179/case/19')
  const panel=page.locator('.pacs-panel')
  await panel.getByRole('button',{name:'查询检查',exact:true}).click()
  const study=panel.locator('.el-table').first().locator('.el-table__body tr').filter({hasText:candidate.study_uid})
  await study.waitFor();await page.waitForFunction(()=>!document.querySelector('.pacs-panel').classList.contains('is-busy'));await study.click()
  const series=panel.locator('.pacs-selection .el-table').first().locator('.el-table__body tr').filter({hasText:candidate.series_uid})
  await series.waitFor();await page.waitForFunction(()=>!document.querySelector('.pacs-panel').classList.contains('is-busy'));await series.click()
  await panel.getByRole('button',{name:'核对序列空间',exact:true}).click()
  const button=panel.getByRole('button',{name:'DICOM 阅片记录 / PDF',exact:true})
  await button.click();await loaded()
  result.checks.push('Actual existing case/PACS panel query, selection, geometry check and report button navigation; no writes')
 }else{await page.goto(url);await loaded()}
 result.initial=await snapshot()
 const expected=mode==='export'?JSON.parse(await fs.readFile(root+'/dicom-measurements-expected.json','utf8')).filter(row=>result.initial.measurements.some(item=>item.id===row.id)):null
 if(expected)assert.deepEqual(result.initial.measurements,expected)
 if(mode==='restart')assert.equal(result.initial.content_sha256,JSON.parse(await fs.readFile(root+'/report-before-restart.json','utf8')).content_sha256)
 if(mode==='readonly')assert.equal(result.initial.measurements.length,0)
 const text=await page.locator('#report-paper').innerText()
 for(const key of ['study_uid','series_uid','frame_of_reference_uid','metadata_sha256'])assert.ok(text.includes(result.initial.context[key]))
 for(const row of result.initial.measurements)assert.ok(text.includes(row.length_mm.toFixed(3)+' mm'))
 assert.ok(text.includes('未包含模型分割、IDH 预测'))
 assert.ok(text.includes('病例级意见，未绑定本序列'))
 await page.screenshot({path:out+'/report-page.png',fullPage:true})
 if(['export','pdf'].includes(mode)){
  const download=page.waitForEvent('download',{timeout:90000})
  await btn().click();await (await download).saveAs(out+'/dicom-reading-record.pdf')
  await page.getByText('PDF 报告已导出',{exact:true}).waitFor()
  assert.equal(result.downloads.length,1)
  result.checks.push('Real saved mm records, UIDs, geometry, source hash and content revision visible; real PDF exported')
 }
 if(mode==='export'){
  // An actual deletion after opening changes the revision: no stale export.
  const item=expected[0]
  const del=await page.request.delete('http://127.0.0.1:8012'+prefix+'/measurements/'+item.id,{data:{context:item.context}})
  assert.equal(del.status(),200,await del.text())
  result.writes.push({scope:'isolated DB only',method:'DELETE',measurement_id:item.id})
  await btn().click();await page.getByText('来源或记录版本已变化，请核对刷新后的报告再导出。',{exact:true}).waitFor()
  assert.equal(result.downloads.length,1)
  result.afterDelete=await snapshot();assert.equal(result.afterDelete.measurements.length,expected.length-1)
  await fs.writeFile(root+'/report-after-delete'+(tag?'-'+tag:'')+'.json',JSON.stringify(result.afterDelete,null,2),{flag:'wx'})
  // Force a changed revision only on the final post-raster check; actual archive untouched.
  let checks=0
  await page.route('**'+endpoint,async route=>{
   checks++;const response=await route.fetch();const body=await response.json()
   if(checks===3)body.data.content_sha256='f'.repeat(64)
   await route.fulfill({response,json:body})
  })
  await btn().click()
  await page.getByText('来源或记录版本已变化，请核对刷新后的报告再导出。',{exact:true}).waitFor()
  await page.waitForFunction(()=>!document.querySelector('.report-toolbar .el-button.is-loading'))
  assert.ok(checks>=3);assert.equal(result.downloads.length,1)
  await page.unroute('**'+endpoint)
  result.checks.push('Actual saved-distance deletion blocks stale open-page export; controlled final-render revision drift blocks download')
 }
 if(['export','restart'].includes(mode)){
  await page.route('**'+endpoint,route=>route.fulfill({status:409,contentType:'application/json',body:JSON.stringify({detail:{reason:'SYNTHETIC_report_unavailable',message:'受控来源变更检查'}})}))
  await page.getByRole('button',{name:'刷新报告',exact:true}).click()
  await page.locator('.el-alert').getByText(/DICOM 阅片记录当前不可用/).waitFor()
  assert.equal(await page.locator('#report-paper').count(),0);assert.equal(await btn().isDisabled(),true)
  await page.unroute('**'+endpoint)
  // Same Report component route switch must clear DICOM identity and preserve the model report.
  await page.evaluate(async()=>document.querySelector('#app').__vue_app__.config.globalProperties.$router.push('/report?case_id=17'))
  await page.locator('#report-paper:not(.dicom-report)').waitFor({timeout:60000})
  assert.ok((await page.locator('#report-paper').innerText()).includes('分析运行 ID'))
  assert.ok(!(await page.locator('#report-paper').innerText()).includes(candidate.study_uid))
  await page.evaluate(async url=>document.querySelector('#app').__vue_app__.config.globalProperties.$router.push(url),url.replace('http://127.0.0.1:5179',''))
  await loaded()
  result.checks.push('Unavailable source clears old report and disables PDF; same-component NIfTI/DICOM switch keeps identities separate')
 }
 assert.deepEqual(result.pageErrors,[])
 result.status='passed'
}catch(e){result.status='failed';result.error=e.stack;await page.screenshot({path:out+'/failure.png',fullPage:true});process.exitCode=1}
finally{await fs.writeFile(out+'/validation.json',JSON.stringify(result,null,2));await browser.close()}
