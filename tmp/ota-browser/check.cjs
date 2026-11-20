const {chromium}=require('playwright-core');
const path=require('path');
const fs=require('fs');
(async()=>{
 const browser=await chromium.launch({channel:'msedge',headless:true});
 const page=await browser.newPage({viewport:{width:1440,height:1050}});
 const errors=[]; page.on('pageerror',e=>errors.push(e.message));
 const fixture={device_id:'ESP32_001',fresh:true,busy:false,age_seconds:1,
   chip:{version:'1.1.11',build:'visual-test-fixture',image_sha256:'a'.repeat(64),boot_id:'11111111-1111-1111-1111-111111111111',partition:'ota_0',confirmed:true,state:'idle'},
   prepared:null,job:null};
 await page.route('**/api/**',async route=>{
   const u=new URL(route.request().url()); let body={};
   if(u.pathname.endsWith('/auth/me'))body={user:{username:'Preview',role:'admin',must_change_password:false},csrf_token:'fixture'};
   else if(u.pathname.endsWith('/ota'))body=fixture;
   else if(u.pathname.endsWith('/ota/image')){fixture.prepared={upload_id:'image-fixture',filename:'app.bin',version:'1.2.0',size:1000000,image_sha256:'b'.repeat(64)};body=fixture.prepared;}
   else if(u.pathname.endsWith('/ota/start')){fixture.busy=true;fixture.job={state:'rebooting',progress:100,message:'Waiting for chip reboot (visual test fixture)',image:fixture.prepared};body=fixture.job;}
   else if(u.pathname.endsWith('/devices'))body={devices:[{device_id:'ESP32_001',online:true,controls:{A:0,B:0}}]};
   else if(u.pathname.endsWith('/latest'))body={received:null,persisted:null};
   else if(u.pathname.endsWith('/health'))body={mqtt_connected:true,database_connected:true};
   else if(u.pathname.endsWith('/commands'))body={commands:[]};
   else if(u.pathname.endsWith('/statistics'))body={available:false};
   await route.fulfill({json:body});
 });
 await page.routeWebSocket('**/ws/**',()=>{});
 await page.goto('http://127.0.0.1:5173/ota');
 await page.getByText('Live report from chip',{exact:true}).waitFor();
 await page.getByLabel('Firmware file',{exact:true}).setInputFiles({name:'app.bin',mimeType:'application/octet-stream',buffer:Buffer.from('visual-fixture')});
 await page.getByText('v1.2.0',{exact:true}).waitFor();
 const install=page.getByRole('button',{name:'Install firmware over Wi-Fi'});
 if(await install.isEnabled())throw Error('Install requires acknowledgement');
 await page.getByRole('checkbox').check();
 if(!await install.isEnabled())throw Error('Install should be available after acknowledgement');
 const out=path.resolve('output/testing/screenshots');fs.mkdirSync(out,{recursive:true});
 await page.screenshot({path:path.join(out,'ota-desktop-fixture.png'),fullPage:true});
 await install.click();
 await page.getByText('Update: rebooting',{exact:true}).waitFor();
 if(await page.getByText('Update confirmed by chip',{exact:true}).count())throw Error('False confirmation');
 fixture.job.state='confirmed';fixture.job.message='Confirmed test fixture';
 fixture.chip.version='1.2.0'; fixture.chip.image_sha256='b'.repeat(64);
 await page.getByText('Update confirmed by chip',{exact:true}).waitFor();
 await page.setViewportSize({width:390,height:844});
 await page.waitForFunction(()=>document.querySelector('.sidebar').getBoundingClientRect().right<=1);
 await page.screenshot({path:path.join(out,'ota-mobile-fixture.png'),fullPage:true});
 const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1);
 if(overflow)throw Error('Mobile overflow');
 if(errors.length)throw Error(errors.join(';'));
 console.log(JSON.stringify({page:'/ota',mocked_api:true,desktop:true,mobile:true,upload:true,confirmation_gate:true,no_false_success:true,no_page_errors:true}));
 await browser.close();
})().catch(e=>{console.error(e);process.exit(1)});
