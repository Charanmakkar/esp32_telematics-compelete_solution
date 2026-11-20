const {chromium}=require('playwright-core');
const fs=require('fs');
const path=require('path');
const assert=require('assert');
(async()=>{
 const root=process.cwd(), session=JSON.parse(fs.readFileSync('.runtime/ota-session.json'));
 const image=path.resolve(process.argv[2]||'build/firmware.bin');
 const label=process.argv[3]||'bin-upgrade';
 const browser=await chromium.launch({channel:'msedge',headless:true});
 try {
  const context=await browser.newContext({viewport:{width:1440,height:1050}});
  await context.addCookies(Object.entries(session.cookie).map(([name,value])=>({name,value,url:'http://127.0.0.1:5173',httpOnly:true,sameSite:'Lax'})));
  const page=await context.newPage(); const errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  await page.goto('http://127.0.0.1:5173/ota');
  await page.getByText('Live report from chip',{exact:true}).waitFor({timeout:20000});
  const status=async()=>{const r=await context.request.get('http://127.0.0.1:5173/api/v1/ota');assert.equal(r.status(),200);return r.json()};
  const before=await status(); assert(before.fresh&&before.chip.confirmed&&before.chip.state==='idle'&&!before.busy);
  if(process.argv.includes('--drop')){
   const transfer=await page.evaluateHandle(({data,name})=>{
    const bytes=Uint8Array.from(atob(data),c=>c.charCodeAt(0));const dt=new DataTransfer();
    dt.items.add(new File([bytes],name,{type:'application/octet-stream'}));return dt;
   },{data:fs.readFileSync(image).toString('base64'),name:path.basename(image)});
   await page.getByTestId('firmware-drop-zone').dispatchEvent('drop',{dataTransfer:transfer});
   await transfer.dispose();
  }else await page.getByLabel('Firmware file',{exact:true}).setInputFiles(image);
  await page.getByText(path.basename(image),{exact:true}).waitFor({timeout:15000});
  const prepared=(await status()).prepared;
  const install=page.getByRole('button',{name:'Install firmware over Wi-Fi'});
  assert(!await install.isEnabled());
  await page.getByRole('checkbox').check();
  const startResponse=page.waitForResponse(r=>new URL(r.url()).pathname==='/api/v1/ota/start');
  await install.click(); const startedResponse=await startResponse;
  assert.equal(startedResponse.status(),200);const started=await startedResponse.json();
  let state='',after,history=[],start=Date.now();
  while(Date.now()-start<900000){
   after=await status();
   const job=after.job;
   if(job&&job.id===started.id){
    const current=job.state+':'+Math.floor(job.progress/10)*10;
    if(state!==current){state=current;history.push({elapsed_s:(Date.now()-start)/1000,state:job.state,progress:job.progress,message:job.message});console.log(JSON.stringify(history.at(-1)));}
    if(['confirmed','failed','unconfirmed'].includes(job.state))break;
   }
   await new Promise(r=>setTimeout(r,1000));
  }
  const result={label,live_hardware:true,drag_and_drop:process.argv.includes('--drop'),before:before.chip,prepared,after,history,page_errors:errors};
  fs.writeFileSync(`output/testing/ota-live-${label}.json`,JSON.stringify(result,null,2));
  assert.equal(after.job.state,'confirmed',after.job.message);
  assert.notEqual(after.chip.boot_id,before.chip.boot_id);
  assert.equal(after.chip.image_sha256,prepared.image_sha256);
  assert.equal(after.chip.version,prepared.version);
  assert.equal(after.chip.confirmed,true);
  await page.getByText('Update confirmed by chip',{exact:true}).waitFor();
  fs.mkdirSync('output/testing/screenshots',{recursive:true});
  await page.screenshot({path:`output/testing/screenshots/ota-live-${label}-desktop.png`,fullPage:true});
  await page.setViewportSize({width:390,height:844});
  await page.waitForFunction(()=>document.querySelector('.sidebar').getBoundingClientRect().right<=1);
  assert(!await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1),'Mobile overflow');
  await page.screenshot({path:`output/testing/screenshots/ota-live-${label}-mobile.png`,fullPage:true});
  assert.deepEqual(errors,[]);
  console.log(JSON.stringify({passed:true,label,version:after.chip.version,partition:after.chip.partition,ip:after.chip.ip_address}));
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
