// Read-only new joint-restoration acceptance: actual archive, views, distances and report.
import {chromium} from '@playwright/test'
import fs from 'node:fs/promises'
import assert from 'node:assert/strict'
const [root]=process.argv.slice(2)
if(!root?.startsWith('E:/BrainFusion-Runtime/results/nightly/'))throw Error('Run evidence root required')
const expected=JSON.parse(await fs.readFile(root+'/joint-before.json','utf8'))
const c=expected.report.context
const prefix=`/pacs/cases/19/studies/${c.study_uid}/series/${c.series_uid}`
const out=root+'/joint-restored-browser'
await fs.mkdir(out)
const state=JSON.parse(await fs.readFile('E:/BrainFusion-Runtime/local/processes.json','utf8'))
assert.ok(state.runtime_paths.DATABASE_PATH.replaceAll('\\','/').startsWith('E:/BrainFusion-Runtime/backups/20261015T021538_p4report/restored/'))
const browser=await chromium.launch({headless:true})
const page=await browser.newPage({viewport:{width:1600,height:1100}})
const result={status:'running',pageErrors:[],writes:[],checks:[]}
page.on('pageerror',e=>result.pageErrors.push(e.message))
await page.route('**/*',route=>{
 if(!['GET','HEAD'].includes(route.request().method()))throw Error('No write authorized in restoration browser')
 return route.continue()
})
async function get(path){const r=await page.request.get('http://127.0.0.1:8012'+path);assert.equal(r.status(),200,await r.text());return (await r.json()).data}
try{
 const imports=await get('/pacs/import-candidates')
 assert.deepEqual(imports.items[0],expected.candidate)
 assert.equal((await get(prefix+'/reading-report')).content_sha256,expected.report.content_sha256)
 assert.deepEqual((await get(prefix+'/view-state')).saved,expected.view)
 await page.goto(`http://127.0.0.1:5179/workstation/19?source=dicom&study_uid=${c.study_uid}&series_uid=${c.series_uid}`)
 await page.locator('.cs-viewer[data-state="ready"][data-source="dicom"]').waitFor({timeout:90000})
 await page.getByText(/已恢复保存视图/).waitFor()
 assert.equal(await page.locator('.cs-measurement-row').count(),3)
 result.viewports=await page.evaluate(async()=>{
  const core=await import(performance.getEntriesByType('resource').find(r=>/\/@cornerstonejs_core\.js/.test(r.name)).name)
  const tools=await import(performance.getEntriesByType('resource').find(r=>/\/@cornerstonejs_tools\.js/.test(r.name)).name)
  const views=core.getRenderingEngines()[0].getViewports()
  return views.map(view=>({camera:view.getCamera(),voi:view.getProperties().voiRange,
   volume:{dimensions:core.cache.getVolume(view.getVolumeId()).dimensions,spacing:core.cache.getVolume(view.getVolumeId()).spacing},
   measures:tools.annotation.state.getAllAnnotations().filter(a=>a.metadata.toolName==='Length').map(a=>a.data.handles.points)}))
 })
 for(const [i,v] of result.viewports.entries()){
  const camera=expected.view.state.cameras[['axial','sagittal','coronal'][i]]
  for(const [api,field] of [['focalPoint','focal_point'],['position','position'],['viewPlaneNormal','view_plane_normal'],['viewUp','view_up']])camera[field].forEach((n,j)=>assert.ok(Math.abs(n-v.camera[api][j])<.001))
  assert.ok(Math.abs(camera.parallel_scale-v.camera.parallelScale)<.001)
  assert.deepEqual(v.voi,expected.view.state.window_ranges[i])
  assert.deepEqual(v.volume.dimensions,expected.report.geometry.dimensions)
  expected.report.measurements.forEach(m=>assert.ok(v.measures.some(points=>JSON.stringify(points)===JSON.stringify(m.points_lps))))
 }
 await page.screenshot({path:out+'/restored-view-and-distances.png',fullPage:true})
 await page.evaluate(async path=>document.querySelector('#app').__vue_app__.config.globalProperties.$router.push(path),`/report?case_id=19&source=dicom&study_uid=${c.study_uid}&series_uid=${c.series_uid}`)
 await page.locator('#report-paper.dicom-report').waitFor({timeout:90000})
 const text=await page.locator('#report-paper').innerText()
 assert.ok(text.includes(expected.report.content_sha256))
 for(const row of expected.report.measurements)assert.ok(text.includes(row.length_mm.toFixed(3)+' mm'))
 await page.screenshot({path:out+'/restored-reading-report.png',fullPage:true})
 result.checks.push('Restored import registry/receipt exactly equal; actual restored archive loads three MPR views; saved LPS cameras/VOIs and all 3 distance world points match; same report content revision')
 assert.deepEqual(result.pageErrors,[]);result.status='passed'
}catch(e){result.status='failed';result.error=e.stack;await page.screenshot({path:out+'/failure.png',fullPage:true});process.exitCode=1}
finally{await fs.writeFile(out+'/validation.json',JSON.stringify(result,null,2));await browser.close()}
