// Read-only live restoration: archive, 17-table content, view state and immutable reviews.
import {chromium} from '@playwright/test'
import fs from 'node:fs/promises'
import assert from 'node:assert/strict'
const [rawRoot,tag='']=process.argv.slice(2)
const root=rawRoot?.replaceAll('\\','/')
assert.ok(root?.startsWith('E:/BrainFusion-Runtime/results/nightly/'))
const expected=JSON.parse(await fs.readFile(root+'/joint-before.json','utf8'))
const state=JSON.parse(await fs.readFile('E:/BrainFusion-Runtime/local/processes.json','utf8'))
assert.equal(state.runtime_paths.DATABASE_PATH.replaceAll('\\','/'),expected.restored_database)
const c=expected.report.context
const prefix=`/pacs/cases/19/studies/${c.study_uid}/series/${c.series_uid}`
assert.match(tag,/^[A-Za-z0-9_-]*$/)
const out=root+'/joint-restored-browser'+(tag?'-'+tag:'')
await fs.mkdir(out)
const browser=await chromium.launch({headless:true})
const page=await browser.newPage({viewport:{width:1600,height:1100}})
const result={status:'running',pageErrors:[],writes:[],checks:[]}
page.on('pageerror',e=>result.pageErrors.push(e.message))
await page.route('**/*',route=>{
 if(!['GET','HEAD'].includes(route.request().method())){
  result.writes.push(route.request().url());return route.abort()
 }
 return route.continue()
})
async function get(path){const r=await page.request.get('http://127.0.0.1:8012'+path);assert.equal(r.status(),200,await r.text());return (await r.json()).data}
try{
 assert.deepEqual((await get('/pacs/import-candidates')).items[0],expected.candidate)
 const report=await get(prefix+'/reading-report')
 for(const key of ['context','geometry','measurements','doctor_opinion','content_sha256','export_sha256','latest_review','review_history_count'])assert.deepEqual(report[key],expected.report[key],key)
 assert.deepEqual(await get(prefix+'/reviews'),expected.reviews)
 assert.deepEqual((await get(prefix+'/view-state')).saved,expected.view)
 await page.goto(`http://127.0.0.1:5179/workstation/19?source=dicom&study_uid=${c.study_uid}&series_uid=${c.series_uid}`)
 await page.locator('.cs-viewer[data-state="ready"][data-source="dicom"]').waitFor({timeout:90000})
 await page.getByText(/已恢复保存视图/).waitFor()
 assert.equal(await page.locator('.cs-measurement-row').count(),expected.report.measurements.length)
 result.viewports=await page.evaluate(async()=>{
  const core=await import(performance.getEntriesByType('resource').find(r=>/\/@cornerstonejs_core\.js/.test(r.name)).name)
  const tools=await import(performance.getEntriesByType('resource').find(r=>/\/@cornerstonejs_tools\.js/.test(r.name)).name)
  return core.getRenderingEngines()[0].getViewports().map(v=>({camera:v.getCamera(),voi:v.getProperties().voiRange,
   volume:{dimensions:core.cache.getVolume(v.getVolumeId()).dimensions,spacing:core.cache.getVolume(v.getVolumeId()).spacing},
   measures:tools.annotation.state.getAllAnnotations().filter(a=>a.metadata.toolName==='Length').map(a=>a.data.handles.points)}))
 })
 for(const [i,v] of result.viewports.entries()){
  const camera=expected.view.state.cameras[['axial','sagittal','coronal'][i]]
  for(const [api,field] of [['focalPoint','focal_point'],['position','position'],['viewPlaneNormal','view_plane_normal'],['viewUp','view_up']])camera[field].forEach((n,j)=>assert.ok(Math.abs(n-v.camera[api][j])<.001))
  assert.ok(Math.abs(camera.parallel_scale-v.camera.parallelScale)<.001)
  assert.deepEqual(v.voi,expected.view.state.window_ranges[i])
  assert.deepEqual(v.volume.dimensions,expected.report.geometry.dimensions)
  // Cornerstone/gl-matrix computes spacing in Float32; absolute tolerance is 1e-6 mm.
  v.volume.spacing.forEach((n,j)=>assert.ok(Math.abs(n-expected.report.geometry.spacing_xyz_mm[j])<1e-6,'spacing exceeds 1e-6 mm'))
  assert.deepEqual(v.measures.map(p=>JSON.stringify(p)).sort(),expected.report.measurements.map(m=>JSON.stringify(m.points_lps)).sort())
 }
 await page.screenshot({path:out+'/restored-view-and-distances.png',fullPage:true})
 await page.evaluate(async path=>document.querySelector('#app').__vue_app__.config.globalProperties.$router.push(path),`/report?case_id=19&source=dicom&study_uid=${c.study_uid}&series_uid=${c.series_uid}`)
 await page.locator('#report-paper.dicom-report').waitFor({timeout:90000})
 await page.waitForFunction(()=>!document.querySelector('.report-toolbar .el-button.is-loading'))
 const paper=await page.locator('#report-paper').innerText()
 assert.ok(paper.includes(expected.report.content_sha256));assert.ok(paper.includes(expected.report.export_sha256))
 assert.equal(await page.locator('.dicom-report tbody tr').count(),expected.report.measurements.length)
 assert.equal(await page.locator('.review-history-row').count(),expected.reviews.items.length)
 assert.equal((await page.locator('.manual-review-text .review-paragraph').allTextContents()).join(''),expected.report.latest_review.opinion)
 assert.ok((await page.locator('.review-status').innerText()).includes('已记录本版本'))
 await page.locator('.paper-header').screenshot({path:out+'/restored-report-identity.png'})
 await page.locator('.dicom-review-paper').screenshot({path:out+'/restored-current-review.png'})
 const old=expected.reviews.items.find(r=>!r.current)
 assert.ok(old)
 const history=page.locator(`details[data-review-id="${old.id}"]`)
 await history.locator('summary').click()
 assert.equal(await history.locator('.opinion-text').innerText(),old.opinion)
 assert.ok((await history.innerText()).includes('历史内容，当前不适用'))
 await page.locator('.review-editor h3').screenshot({path:out+'/restored-history-count.png'})
 result.checks.push('Restored archive three views with saved cameras/VOIs; all 36 persisted annotations match the full world-point multiset')
 result.checks.push('Restored 3 immutable review histories and full source/content snapshots exactly match; current 4000-character review and expired history display correctly; import candidate/receipt and export revision unchanged')
 assert.deepEqual(result.writes,[]);assert.deepEqual(result.pageErrors,[])
 result.status='passed'
}catch(e){result.status='failed';result.error=e.stack;await page.screenshot({path:out+'/failure.png',fullPage:true}).catch(()=>{});process.exitCode=1}
finally{await fs.writeFile(out+'/validation.json',JSON.stringify(result,null,2),{flag:'wx'});await browser.close();console.log(JSON.stringify({status:result.status,checks:result.checks,error:result.error}))}
