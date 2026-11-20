import fs from 'node:fs/promises';
import {readFileSync} from 'node:fs';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {pathToFileURL} from 'node:url';

const applicationRoot=process.cwd();
const dependencies=process.env.NAVSPHERE_SLIDE_RUNTIME;
const skillDir=process.env.NAVSPHERE_SLIDE_SKILL;
const toolsDir=path.join(skillDir,'container_tools');
const {PresentationFile, FileBlob}=await import(pathToFileURL(path.join(dependencies,'node','node_modules','@oai','artifact-tool','dist','artifact_tool.mjs')).href);
const {finalizePresentation}=await import(pathToFileURL(path.join(toolsDir,'artifact_tool_utils.mjs')).href);
const qaDir=path.join(applicationRoot,'tmp','navsphere-stakeholder-update');
const sourceDeck=path.join(applicationRoot,'output','reports','NavSphere_Stakeholder_Presentation.pptx');
const sourceSha=createHash('sha256').update(await fs.readFile(sourceDeck)).digest('hex');
if(sourceSha!=='90cb3f98e5ed39881dada2d6f03b5abb333241edc7f72d3a33ad70270a4eb651')throw Error('The source presentation changed during the edit');
const presentation=await PresentationFile.importPptx(await FileBlob.load(sourceDeck));
const p=presentation;

var D = {paper:"#F5F7F6",dark:"#102C36",ink:"#183641",muted:"#526970",green:"#247A68",soft:"#DAE5E2",pale:"#E6F3ED",white:"#FFFFFF",amber:"#93491D"};
var localRoot="C:/Users/charanpreet/Documents/ChatGPT/esp32_telematics-compelete_solution";
var asset=p=>localRoot+"/"+p;
var dtext=(s,name,value,x,y,w,h,pt,opt={})=>{
  const b=s.shapes.add({name,geometry:"textbox",position:{left:x,top:y,width:w,height:h},fill:"none",line:{fill:"none",width:0}});
  b.text=value;
  b.text.style={typeface:"Arial",fontSize:pt+"pt",color:opt.color??D.ink,bold:opt.bold??false,alignment:opt.align??"left",verticalAlignment:"middle",insets:{left:0,right:0,top:0,bottom:0},wrap:opt.wrap??"none",autoFit:"none"};
  return b;
};
var ds=(p,i,section,title,footer)=>{
  const s=p.slides.add({width:1280,height:720});
  s.background.fill=D.paper;
  dtext(s,"Section","NAVSPHERE  /  "+section,64,35,1100,28,12,{color:D.green,bold:true});
  dtext(s,"Slide title",title,64,90,1152,75,30,{color:D.dark,bold:true});
  dtext(s,"Evidence footer",footer,64,660,1080,29,11,{color:D.muted});
  dtext(s,"Slide number",String(i).padStart(2,"0"),1160,660,60,30,12,{color:D.muted,align:"right"});
  return s;
};
var dt=(s,name,c,x,y,w=460)=>dtext(s,name,c,x,y,w,34,20,{bold:true,color:D.green});
var dl=(s,name,rows,x,y,w=460,pt=17,step=30,color=D.ink)=>rows.forEach((v,i)=>dtext(s,name+" "+(i+1),v,x,y+step*i,w,step,pt,{color}));
var dk=(s,name,value,label,x,y,w=442)=>{
  dtext(s,name+" number",value,x,y,w,61,38,{bold:true,color:D.green});
  dtext(s,name+" label",label,x,y+67,w,30,16,{color:D.muted});
};
var cap=(s,name,v,x,y,w)=>dtext(s,name,v,x,y,w,26,11,{color:D.muted});
var shot=(s,p,alt,x,y,w,h,crop)=>s.images.add({blob:readFileSync(asset(p)),contentType:p.endsWith(".png")?"image/png":"image/jpeg",alt,fit:"cover",position:{left:x,top:y,width:w,height:h},...(crop?{crop}:{} )});
var note=(s,v)=>{s.speakerNotes.text=v;};
var cellTable=(s,data,x,y,widths,heights,highlight=-1)=>{
  const table=s.tables.add({rows:data.length,columns:widths.length,left:x,top:y,width:widths.reduce((a,b)=>a+b,0),height:heights.reduce((a,b)=>a+b,0),columnWidths:widths,values:data});
  table.styleOptions={headerRow:false,bandedRows:false,firstColumn:false};
  table.borders.assign({width:1,fill:D.soft,style:"solid"});
  for(let i=0;i<data.length;i++){
    table.rows[i].height=heights[i];
    table.cells.block({row:i,column:0,rowCount:1,columnCount:widths.length}).assign({fill:i===0?D.dark:i===highlight?D.pale:i%2===0?"#ECF1EF":D.white,margins:{left:13,right:11,top:5,bottom:5},anchor:"middle",textStyle:{typeface:"Arial",fontSize:i===0?18:19,color:i===0?D.white:D.ink,bold:i===0}});
    if(i>0)table.cells.block({row:i,column:0,rowCount:1,columnCount:1}).textStyle.bold=true;
  }
  return table;
};

{

  const snapshot=await presentation.inspect({kind:"slide,textbox,image",maxChars:50000});
  const updates=[
    ["NAVSPHERE  /  STAKEHOLDER BRIEF","ESP32 telematics, CAN\nand Wi-Fi firmware updates","Project outcomes and readiness for the next phase","v1.1.12","Packaged software release","Updated 20 Nov 2026. Most recent hardware check: v1.1.7.\nRemote diagnostics over CAN is the next phase."],
    ["NAVSPHERE  /  TIME & EFFORT","6 h 49 m across 48 recorded work turns","Sources: 19 Nov interaction-time audit and the separate OTA work log.","02","1h 08m 06s","Initial telematics build and fixes","5h 13m 16s","Recovery, CAN/BMS, tests and reports","27m 33s for Wi-Fi OTA","4 additional completed turns for assessment, implementation and validation.","Session duration includes tool runs and waits. Human labor hours,\nbilled AI credits and time savings are unavailable."],
    ["NAVSPHERE  /  CONTRIBUTIONS","Software and bench contributions","Sources: 19 Nov project work report and the OTA work log.","03","Codex contribution","Firmware, backend, GUI and database\nCAN decoding, diagnostics and periodic TX\nOTA implementation, builds and software tests\nEvidence capture and documentation","Project owner contribution","Defined scope, priorities and CAN requirements\nConnected the ESP32, BMS and CAN analyzer\nChecked wiring and corrected the supply\nProvided network access and reviewed results","74 user inputs in the 19 Nov audit","Original master prompt: 4,338 words.\nProject-level billed tokens and AI credits are unavailable."],
    ["NAVSPHERE  /  CAPABILITY","NavSphere platform capabilities","Dashboard capture: live CAN search on v1.1.4, 19 Nov 2026.","04","Acquire and store","6 analog inputs at a nominal 10 Hz\nAuthenticated MQTT and MariaDB history","View and decode","Live charts, analytics and CSV export\n500 kbit/s CAN, DBC decoding and search","Control and maintain","Two acknowledged outputs and periodic CAN TX\nBMS workflows and Wi-Fi firmware updates"],
    ["NAVSPHERE  /  VERIFICATION","v1.1.12 passed software validation","Sources: current release status and 20 Nov OTA validation record.","05","103 / 41","Backend / frontend tests\npassed","2 builds","Firmware and GUI builds\npassed","v1.1.12","Packaged release\nHardware tests pending","Software evidence","Packaged BIN and Intel HEX validation passed\nBrowser upload and confirmation gates passed\nDesktop and mobile checks used mocked device data","Hardware evidence","Latest wire test used v1.1.7\nUSB migration and live OTA remain pending\nCAN timing and BMS response need retesting"]
  ];
  const sources=[
    "Source: docs/RELEASE_STATUS.md and output/testing/ota-comparison-validation-20261120.json. The date and package label refer to the software release. The hardware statement refers to the latest recorded bench firmware.",
    "Sources: output/reports/interaction-time.json and the Assess Wi-Fi OTA impact completed-turn record. Original audit: 22,882,384 ms across 44 turns. Separate OTA chat: 1,653,138 ms across four turns. Combined elapsed chat work: 24,535,522 ms, rounded to 6 h 49 m. This includes tools and waits and excludes gaps and unfinished turns. The original audit includes mixed work.",
    "Source: docs/reports/PROJECT_AND_AI_USAGE.md and the OTA implementation and validation records. The 74 input records and 4,338-word master attachment relate to the historical audit scope. No project billing ledger or labor-hour records were available.",
    "Sources: README.md, docs/RELEASE_STATUS.md and output/testing/bms/redeploy-20261119-gui.jpg. Screenshot is a genuine historical capture from v1.1.4. The delivered platform also includes role-based access, REST/WebSocket, service health, version display, and local/LAN release tooling.",
    "Sources: docs/RELEASE_STATUS.md and output/testing/ota-comparison-validation-20261120.json. 103 and 41 are the latest suite totals. Matching the package and GUI identity is software evidence. Earlier targeted and full suite counts overlap. No physical OTA update or rollback was performed on v1.1.12."
  ];
  for(let i=0;i<updates.length;i++){
    const records=snapshot.records.filter(x=>x.kind==="textbox"&&x.slideIndex===i);
    if(records.length!==updates[i].length)throw Error("Unexpected source textbox count on slide "+(i+1));
    for(let j=0;j<records.length;j++){
      const rec=records[j], shape=presentation.resolve(rec.id);
      shape.text=updates[i][j];
      shape.text.style={...rec.style,typeface:"Arial",fontFamily:"Arial",...(i===4&&j===8?{fontSize:52}:{})};
    }
    note(presentation.slides.items[i],sources[i]);
  }
  const img=presentation.slides.items[3].images.items[0];
  img.replace({blob:readFileSync(asset("output/testing/bms/redeploy-20261119-gui.jpg")),contentType:"image/jpeg",alt:"Live NavSphere CAN search and a decoded message on the v1.1.4 dashboard"});
  img.frame={left:650,top:200,width:566,height:399};
  img.fit="cover";
  img.crop={left:0.203,top:0,right:0.016,bottom:0.020};

}
{

  const s=ds(p,6,"TELEMATICS","299 of 299 expected records reached MariaDB","Hardware test and dashboard capture, 12 Nov 2026.");
  dk(s,"Storage","299 / 299","Expected records stored",64,181,444);
  dk(s,"Sample window","30.6 s","Measured ESP32 test window",64,316,444);
  dt(s,"Channel coverage","6 of 6 channels",64,465,455);
  dl(s,"Channel details",["All channel history endpoints responded.","No additional samples dropped during the test."],64,508,480,16);
  shot(s,"output/reports/telematics-overview.png","Live NavSphere signal chart, 12 November 2026",550,188,666,410,{left:0.025,top:0.281,right:0.025,bottom:0.510});
  cap(s,"Capture detail","Dashboard signal monitor showing live millivolt readings.",550,610,666);
  note(s,"Sources: output/testing/hardware-live-results.json and output/reports/telematics-overview.png. Physical ESP32 test: 30.571 seconds, 299 expected rows and 299 persisted rows, six successful channel history calls and zero additional dropped samples during the measured interval. 77 samples were discarded earlier during startup before MQTT connected. The archived UI capture is from the same date. The short result covers persistence in this interval. Long-duration reliability and external sensor accuracy still require testing.");
  const a=ds(p,7,"TELEMATICS","Channel analytics and acknowledged A/B controls","Dashboard captures, 12 Nov 2026.");
  dt(a,"Analytics h","6 channel analytics views",64,170,520);
  dt(a,"A/B h","2 digital outputs",592,170,620);
  shot(a,"output/reports/telematics-analytics.png","Analog 01 history chart and CSV export control",64,223,469,369,{left:0.028,top:0.414,right:0.029,bottom:0.186});
  shot(a,"output/reports/telematics-controls.png","A and B controls showing device-confirmed OFF state",592,223,624,369,{left:0.024,top:0.246,right:0.054,bottom:0.048});
  cap(a,"Analytics caption","Live and historical chart modes with plotted CSV export.",64,606,503);
  cap(a,"Controls caption","Both outputs report OFF. Commands require a device acknowledgement.",592,606,625);
  note(a,"Sources: output/reports/telematics-analytics.png, output/reports/telematics-controls.png, the project README and firmware specification. A is GPIO2 and B is GPIO0. The platform includes expiry, replay protection and safe LOW on startup, disconnect and inactivity. The screenshot records displayed output state. Full electrical output, voltage and reset characterization remains an acceptance item.");
  const c=ds(p,8,"CAN RECEIVE","Live CAN decoding and bus statistics","v1.1.4 redeploy snapshot and archived CAN statistics.");
  dk(c,"Bit rate","500 kbit/s","Classic CAN receive",64,180,490);
  dk(c,"Identifiers","33 / 71","IDs in current run / saved IDs",64,305,490);
  dt(c,"CAN analysis","Search and decode",64,448,510);
  dl(c,"CAN analysis details",["Filter by current run or saved history.","Search raw frames and DBC-decoded signals.","Review bus load, per-ID timing and loss counters."],64,491,525,16);
  dt(c,"Load h","High-load capture",602,173,610);
  shot(c,"output/testing/bms/can-statistics-overview.jpg","CAN statistics showing ESP32 capture and server delivery frame rates",602,222,614,297,{left:0.031,top:0.359,right:0.031,bottom:0.282});
  dl(c,"Capture vs delivery",["The dashboard shows 3,705.09 frames/s captured","and 169.7 frames/s delivered in this snapshot."],602,543,615,16);
  note(c,"Sources: output/testing/redeploy-20261119-can-live.json, output/testing/bms/can-statistics-overview.jpg and docs/firmware/CAN_GUIDE.md. 33 current and 71 saved IDs are a particular v1.1.4 bench snapshot. The screenshot is a separate high-load window, with an estimated 82.25–100% utilization. Its capture and delivery rates represent observed counters, not a rated capacity. Firmware supports standard, extended and RTR frames, multiple DBC definitions and conflict reporting. Lossless logging remains unverified.");

}
{

  const c=ds(p,9,"CAN TRANSMIT","Two CAN payloads matched on the wire","PCAN bench trace, 19 Nov 2026. Firmware v1.1.7. Capture length: 10 seconds.");
  cellTable(c,[
    ["CAN ID","Target period","Measured mean","Frames captured","Bench outcome"],
    ["0x014","100 ms","99.982 ms","100","Payload matched"],
    ["0x548","10 ms","12.301 ms","813","Timing missed"]
  ],64,178,[178,205,221,207,341],[45,49,49]);
  shot(c,"output/testing/can-tx-gui.jpg","Archived periodic CAN transmit controls with both configured messages and transmission OFF",64,360,661,234,{left:0.219,top:0.425,right:0.043,bottom:0.114});
  cap(c,"UI capture label","Archived CAN TX controls, v1.1.6.",64,601,661);
  dt(c,"Retest h","Wire timing retest",767,365,449);
  dl(c,"Retest",["Both ID payloads matched.","PCAN observed zero error frames.","Retest the 10 ms message with the","built retry correction on hardware."],767,410,449,16);
  note(c,"Sources: output/testing/can-tx-voltage-corrected-before-arbitration-fix.json, output/testing/can-tx-gui.jpg, docs/RELEASE_STATUS.md and docs/firmware/CAN_TX_GUIDE.md. Both fixed payloads matched after transceiver supply correction in the v1.1.7 run. The 0x548 mean interval missed the 10 ms target. v1.1.8 added bounded arbitration-only retries and that correction is included in the current code. No later wire-test acceptance is recorded. The v1.1.6 control view is an earlier UI capture and is separate from the v1.1.7 measurements.");
  const b=ds(p,10,"BMS DIAGNOSTICS","BMS workflows are ready for another bench test","Archived BMS interface and execution trace, 18 Nov 2026.");
  dk(b,"Catalog","55 / 44","CDD services / script workflows",64,173,454);
  dk(b,"Quick reads","5","Read-only Quick Reads",64,307,454);
  dt(b,"Live status","ESP32 response unverified",64,459,477);
  dl(b,"Result",["The bench job reported a transmit failure.","Reference reads via PCAN returned identifiers."],64,502,490,16);
  shot(b,"output/testing/bms/be-quick-reads.jpg","BMS catalog and five Quick Reads in the archived NavSphere dashboard",562,175,654,247,{left:0.218,top:0.482,right:0.043,bottom:0});
  cap(b,"Quick Read caption","BMS catalog and read-only controls.",562,425,654);
  shot(b,"output/testing/bms/be-read-response.jpg","Captured BMS execution trace showing CAN transmission failure",562,464,654,109,{left:0.223,top:0.012,right:0.041,bottom:0.772});
  cap(b,"Trace caption","The execution trace records a failed CAN transmission.",562,579,654);
  note(b,"Sources: docs/development/BE_CLIENT_IMPLEMENTATION.md, docs/RELEASE_STATUS.md, IMPLEMENTATION_REPORT.md and output/testing/bms/be-quick-reads.jpg plus be-read-response.jpg. Offline preparation covers the BE reference catalog, script workflows, five Quick Reads, previews, request/execution history and state-change guards. A PCAN reference workflow returned identifiers. The stored ESP32 attempt shown in the trace failed to transmit and does not establish a successful end-to-end BMS read.");
  const o=ds(p,11,"WI-FI OTA","The OTA workflow passed software validation","Mocked browser captures, 20 Nov 2026. ESP32 hardware update and rollback tests remain pending.");
  dt(o,"Desktop h","Firmware upload and reboot acknowledgement",64,163,705);
  shot(o,"output/testing/screenshots/ota-desktop-fixture.png","Desktop OTA page using mock device data, showing selected firmware and reboot acknowledgement",64,212,678,385,{left:0.187,top:0.169,right:0.017,bottom:0.208});
  cap(o,"Desktop caption","Desktop browser test with mocked device data.",64,607,678);
  dt(o,"Install h","2 firmware slots",786,163,430);
  dl(o,"OTA details",["1,984 KiB maximum per slot.","BIN or Intel HEX via authenticated upload.","Version and hash checks after reboot."],786,208,430,15);
  dt(o,"Confirmation h","Confirmation after reboot",786,325,430);
  shot(o,"output/testing/screenshots/ota-mobile-fixture.png","Mobile browser test screenshot of a mocked chip confirmation after reboot",786,374,430,214,{left:0.037,top:0.833,right:0.037,bottom:0.046});
  cap(o,"Mobile caption","Simulated confirmation in the mobile browser test.",786,600,430);
  note(o,"Sources: docs/firmware/OTA_GUIDE.md, output/testing/ota-comparison-validation-20261120.json, output/testing/screenshots/ota-desktop-fixture.png and output/testing/screenshots/ota-mobile-fixture.png. Browser checks used mocked API data. Versions in the fixture are sample values. The OTA implementation uses chunked MQTT, inactive-slot writes, bootloader rollback, and confirmation based on fresh boot, version and image hash. Administrator access, CSRF checks, broker ACLs and maintenance interlocks apply. One-time USB migration is required on existing hardware and preserves device provisioning.");

}
{

  const r=ds(p,12,"ROADMAP","Remote diagnostics over CAN","Proposed scope. Bench outcomes and rollout dates are pending.");
  dtext(r,"Roadmap lead","Read-only diagnostics over the internet, starting with one authorized bench device.",64,169,1152,40,19,{color:D.muted});
  dk(r,"Pilot BMS","1","Authorized BMS on the bench",64,244,368);
  dk(r,"Pilot reads","5","Existing Quick Reads",447,244,365);
  dk(r,"Pilot measures","3","Measures for pilot review",829,244,387);
  dt(r,"Bench h","Local acceptance first",64,389,528);
  dl(r,"Local acceptance",["Verify end-to-end ESP32 CAN responses.","Complete hardware OTA and CAN timing tests.","Run a 24-hour stability test before field use."],64,438,545,16,34);
  dt(r,"Internet h","Authorized internet pilot",641,389,570);
  dl(r,"Pilot checks",["Use authenticated, read-only access.","Record each request and outcome.","Track read success, p95 latency and audit coverage."],641,438,575,16,34);
  note(r,"Source for current readiness: docs/RELEASE_STATUS.md and docs/testing/HARDWARE_TEST_PLAN.md. Internet diagnostic access, the one-device pilot and its metrics are proposals. Reuse the five existing local read workflows only after live ESP32 responses are validated. Production transport protection and access control are acceptance items. Follow-up hardware validation includes CAN timing, initial USB OTA migration, successful update, loss-of-power handling, rollback and continued telemetry.");
  const s=ds(p,13,"PHASE SUMMARY","Phase summary and recorded effort","Sources: project work-session audit, recovery chat records and OTA work log.");
  cellTable(s,[
    ["Phase","Engineering effort and status","Recorded session time","Billed AI credits"],
    ["1  Telematics","6 inputs, live and historical views, and\n2 acknowledged device controls.","1 h 08 m 06 s\n4 initial build turns","Unavailable"],
    ["2  CAN stack","Live logging, DBC decoding and BMS workflows.\nBoth TX payloads matched. Timing retest pending.","4 h 04 m 05 s\n15 CAN-focused turns","Unavailable"],
    ["3  Wi-Fi OTA","Dual-slot updates and rollback passed software checks.\nPhysical migration and update tests remain pending.","27 m 33 s\n4 OTA turns","Unavailable"],
    ["4  Remote CAN\n    diagnostics","Proposed read-only internet pilot for 1 BMS\nusing 5 existing Quick Reads.","Pending estimate","Pending estimate"]
  ],64,177,[225,495,245,187],[45,77,77,77,77],4);
  dl(s,"Audit limitations",["Phase times include tools and waits. The 6 h 49 m overall audit includes mixed project work.","Human labor hours and project-level billing records are unavailable."],64,568,1152,14,27,D.muted);
  note(s,"Sources: output/reports/interaction-time.json, docs/reports/PROJECT_AND_AI_USAGE.md, completed-turn records from Recover missing project files and Assess Wi-Fi OTA impact, and docs/RELEASE_STATUS.md. Initial telematics: 4,086,278 ms. CAN: 14,644,985 ms across 15 completed turns whose primary focus was CAN/BMS work. Some include associated LAN, deployment or release tasks. OTA: 1,653,138 ms across four completed turns in the separate OTA chat. The overall audit covers 24,535,522 ms across 48 turns including mixed work. Remote diagnostics is upcoming. No billed credit ledger or separately recorded labor hours are available.");


}
{
  const verification=p.slides.getItem(4);
  const body=verification.shapes.items.find(b=>b.text.toString().startsWith("Packaged BIN and Intel HEX"));
  body.text.replace("Desktop and mobile checks used mocked device data","Desktop and mobile checks used mocked data");
  const t=p.slides.getItem(5);
  t.shapes.items.find(b=>b.name==="Slide title").text.replace("299 of 299 expected records reached MariaDB","ESP32 telemetry storage on the bench");
  const a=p.slides.getItem(6);
  const [history,outputs]=a.images.items;
  history.frame={left:64,top:214,width:477,height:405};
  history.crop={left:0.028,top:0.414,right:0.029,bottom:0.149};
  outputs.frame={left:592,top:214,width:558,height:405};
  outputs.crop={left:0.024,top:0.218,right:0.054,bottom:0.039};
  for(const name of ["Analytics caption","Controls caption"]){
    const g=a.shapes.items.find(b=>b.name===name);
    g.position={...g.position,top:623};
  }
  p.slides.getItem(12).tables.items[0].cells.set(3,1,"Dual-slot update and rollback logic implemented.\nPhysical migration and update tests remain pending.");
}
console.log('Rendering the completed slides');
for(const [index,slide] of p.slides.items.entries()){
  const render=await slide.export({format:'png',scale:1});
  await fs.writeFile(path.join(qaDir,`final-slide-${index+1}.png`),new Uint8Array(await render.arrayBuffer()));
}
const candidatePath=path.join(qaDir,'candidate.pptx');
await (await PresentationFile.exportPptx(p)).save(candidatePath);
console.log('Validating exported PowerPoint');
const finalPath=path.join(qaDir,'staged',`NavSphere_Expanded-${Date.now()}.pptx`);
const result=await finalizePresentation({
  workspaceDir:applicationRoot,candidatePath,finalPath,
  pythonExecutable:path.join(dependencies,'python','python.exe'),
  integrityValidatorPath:path.join(toolsDir,'inspect_presentation_package_integrity.py'),
  layoutValidatorPath:path.join(toolsDir,'inspect_presentation_layout_geometry.py'),
  layoutArgs:['--expected-slide-size-emu','12192000,6858000','--validate-heading-fit','--require-native-table-slide','9','--require-native-table-slide','13'],
  explicitTotalSlideCount:13,requiredNativeTableOwnerSlides:[9,13],
  fontPolicy:{basis:'reference',families:['Arial'],referencePath:sourceDeck,referenceSha256:sourceSha},
  verifyArtifactToolImport:true,receiptPath:path.join(qaDir,'validation.json')
});
console.log(JSON.stringify({finalPath,result}));

