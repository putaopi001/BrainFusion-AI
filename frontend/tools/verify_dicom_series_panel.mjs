// Real unconfigured API/UI + explicit synthetic metadata UI; no archive/pixel acceptance.
import { chromium } from '@playwright/test'
import fs from 'node:fs/promises'
import assert from 'node:assert/strict'
const root=process.argv[2],out=root+'/browser-series-panel'+(process.argv[3]?'-'+process.argv[3]:'')
await fs.mkdir(out)
const manifest=JSON.parse(await fs.readFile(root+'/SYNTHETIC-browser-manifest.json','utf8'))
const study=manifest.study_uid,series=manifest.series_uid,other='2.25.600'
const browser=await chromium.launch({headless:true})
const page=await browser.newPage({viewport:{width:1500,height:1100}})
const result={status:'running',scope:'Actual unconfigured UI and clearly synthetic series geometry UI only',
              pageErrors:[],writes:[],pixelRequests:[],checks:[]}
page.on('pageerror',e=>result.pageErrors.push(e.message))
let mock=false,mode='valid'
await page.route('**/*',async route=>{
  const req=route.request(),url=new URL(req.url())
  if(['POST','PUT','DELETE','PATCH'].includes(req.method())){
    result.writes.push(req.url());await route.abort();return
  }
  if(url.pathname.includes('/frames/'))result.pixelRequests.push(req.url())
  if(!mock||!url.pathname.startsWith('/pacs/')){await route.continue();return}
  let data,code=200
  if(mode==='disconnected'&&url.pathname==='/pacs/status'){await route.abort('connectionrefused');return}
  if(url.pathname==='/pacs/status')data={state:'ready',read_available:true,pixel_read_enabled:false,
    message:'SYNTHETIC 成组空间协议夹具：仅界面验证，不是真实归档',import_available:false,dicom_view_available:false,ai_bridge_available:false}
  else if(url.pathname.endsWith('/links'))data={items:[]}
  else if(url.pathname.endsWith('/conversions'))data={state:'not_registered',items:[],message:'SYNTHETIC 无转换版本登记'}
  else if(url.pathname==='/pacs/studies')data={items:[{study_uid:study,modalities:['MR'],series_count:'2'}],next_offset:null}
  else if(url.pathname.endsWith('/series'))data={items:[{study_uid:study,series_uid:series,modality:'MR',series_number:'1'},
    {study_uid:study,series_uid:other,modality:'MR',series_number:'2'}],next_offset:null}
  else if(url.pathname.endsWith('/instances'))data={items:manifest.instances.map(row=>({instance_uid:row.instance_uid})),next_offset:null}
  else if(url.pathname.endsWith('/view-manifest')){
    if(mode==='fail'){code=422;data={message:'SYNTHETIC 层间距不均匀，未插值补层。',reason:'non_uniform_slice_spacing'}}
    else if(mode==='mismatch')data={...manifest,series_uid:other}
    else data=manifest
  }else throw Error('Unexpected SYNTHETIC route '+url.pathname)
  await route.fulfill({status:code,contentType:'application/json',body:JSON.stringify(code===200?{code,data}:{detail:data})})
})
const panel=page.locator('.pacs-panel')
try{
  await page.goto('http://127.0.0.1:5179/case/17')
  await panel.getByText('本地 PACS 尚未配置，DICOM 归档与阅片尚不可用。',{exact:true}).waitFor()
  assert.equal(await panel.getByRole('button',{name:'核对序列空间',exact:true}).count(),0)
  await panel.screenshot({path:out+'/actual-unconfigured.png'})
  result.checks.push('Actual unconfigured UI has no space-check button or misleading success')
  mock=true
  await panel.getByRole('button',{name:'刷新归档状态',exact:true}).click()
  await panel.getByText(/SYNTHETIC 成组空间协议夹具/).waitFor()
  await panel.getByRole('button',{name:'查询检查',exact:true}).click()
  await panel.locator('.el-table__body tr').first().click()
  await panel.getByText('当前检查：',{exact:false}).waitFor()
  await panel.getByText(series,{exact:true}).first().click()
  const check=panel.getByRole('button',{name:'核对序列空间',exact:true})
  await check.waitFor()
  await page.waitForFunction(()=>!document.querySelector('.pacs-panel')?.classList.contains('is-busy'))
  await check.click()
  const geometry=panel.locator('.pacs-geometry')
  await geometry.getByText('空间核对通过（仅元数据）',{exact:true}).waitFor()
  assert.match(await geometry.innerText(),/2.000 \/ 3.250 \/ 2.500/)
  const text=await geometry.locator('.el-table__body tr').allTextContents()
  assert.equal(text.length,3)
  for(let i=0;i<3;i++)assert.match(text[i],new RegExp('2\\.25\\.'+(500+i)))
  assert.match(await geometry.innerText(),/尚未加载像素/)
  await panel.screenshot({path:out+'/SYNTHETIC-spatial-order.png'})
  result.checks.push('SYNTHETIC-only: physical order/XYZ mm/read-only limitation displayed')
  mode='fail';await check.click()
  await panel.getByText('SYNTHETIC 层间距不均匀，未插值补层。',{exact:true}).waitFor()
  assert.equal(await geometry.count(),0)
  mode='mismatch';await check.click()
  await panel.getByText('空间核对返回的序列身份不一致。',{exact:true}).waitFor()
  assert.equal(await geometry.count(),0)
  mode='valid';await check.click()
  await geometry.waitFor()
  await panel.getByText(other,{exact:true}).first().click()
  await page.waitForFunction(()=>!document.querySelector('.pacs-panel')?.classList.contains('is-busy'))
  assert.equal(await geometry.count(),0)
  await page.evaluate(async()=>{
    // Use the router attached to this live app; a fresh module import after HMR
    // can create a second router which changes the URL without this app's route.
    const router=document.querySelector('#app').__vue_app__.config.globalProperties.$router
    await router.push('/case/1')
  })
  await page.waitForURL('**/case/1')
  await panel.locator('.pacs-selection').waitFor({state:'detached'})
  await panel.getByText('当前病例没有归档检查关联。',{exact:true}).waitFor()
  assert.equal(await panel.locator('.pacs-selection').count(),0)
  assert.equal(await geometry.count(),0)
  result.checks.push('Failure/wrong identity/series and SPA case switch clear prior geometry; retry restores result')
  await panel.getByRole('button',{name:'查询检查',exact:true}).click()
  await panel.locator('.el-table__body tr').first().click()
  await panel.getByText(series,{exact:true}).first().click()
  await page.waitForFunction(()=>!document.querySelector('.pacs-panel')?.classList.contains('is-busy'))
  await panel.getByRole('button',{name:'核对序列空间',exact:true}).click()
  await geometry.waitFor()
  mode='disconnected'
  await panel.getByRole('button',{name:'刷新归档状态',exact:true}).click()
  await panel.getByText('归档状态查询失败，请检查本地服务连接。',{exact:true}).waitFor()
  assert.equal(await geometry.count(),0)
  assert.equal(await panel.locator('.pacs-selection').count(),0)
  mode='valid'
  await panel.getByRole('button',{name:'刷新归档状态',exact:true}).click()
  await panel.getByText(/SYNTHETIC 成组空间协议夹具/).waitFor()
  result.checks.push('Refresh connection failure clears old space-check and selection; reconnect remains usable')
  assert.deepEqual(result.pageErrors,[]);assert.deepEqual(result.writes,[]);assert.deepEqual(result.pixelRequests,[])
  result.status='passed'
}catch(e){result.status='failed';result.error=e.stack;process.exitCode=1;await page.screenshot({path:out+'/failure.png',fullPage:true})}
finally{await fs.writeFile(out+'/validation.json',JSON.stringify(result,null,2));await browser.close()}
