// Run from the repository root with the bundled runtime paths in environment.
import fs from 'node:fs/promises';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {pathToFileURL} from 'node:url';
const root=process.cwd();
for(const key of ['RUNTIME_NODE_MODULES','RUNTIME_PYTHON','PRESENTATIONS_SKILL_DIR'])
  if(!process.env[key]) throw new Error(`Set ${key} to the bundled runtime location.`);
const {PresentationFile,FileBlob}=await import(pathToFileURL(path.join(process.env.RUNTIME_NODE_MODULES,'@oai/artifact-tool/dist/artifact_tool.mjs')).href);
const dir=path.join(root,'tmp/docs-review');await fs.mkdir(dir,{recursive:true});
const source=path.join(root,'output/reports/NavSphere_Stakeholder_Presentation.pptx');
const backup=path.join(dir,'source.pptx');
try{await fs.access(backup);}catch{await fs.copyFile(source,backup);}
const p=await PresentationFile.importPptx(await FileBlob.load(backup));
const snapshot=await p.inspect({kind:'slide,textbox,image',maxChars:50000});
const audit=JSON.parse(await fs.readFile('output/reports/interaction-time.json','utf8'));
function duration(ms){const n=Math.floor(ms/1000);return `${Math.floor(n/3600)}h ${String(Math.floor(n/60)%60).padStart(2,'0')}m ${String(n%60).padStart(2,'0')}s`;}
const time=duration(audit.total_ms);
const initial=duration(audit.by_chat.find(x=>x.title==='Build NavSphere telemetry platform').total_ms);
const followup=duration(audit.by_chat.find(x=>x.title==='Recover missing project files').total_ms);
const content=[
 ['NAVSPHERE  /  STAKEHOLDER BRIEF','Telemetry and CAN:\nwork delivered, tests remaining',
  'Time, effort and demonstrated capability',time,
  `Recorded session time across ${audit.completed_turns} completed turns`,
  'Updated 19 Nov 2026 | Source/package v1.1.8; device last verified v1.1.7\nIncludes tools and waits; current documentation turn excluded.'],
 ['NAVSPHERE  /  TIME & EFFORT',`Recorded work-session time: ${time}`,
  'Source: interaction-time.json | Completed turns only; unfinished turns excluded.','02',
  initial,'Initial implementation and build fixes',followup,'Recovery, CAN/BMS, tests and reports',
  '8 days 4h 59m elapsed, including gaps',
  'Two project chats, 11-19 November. Calendar time is not labor time.',
  'Session duration includes tool runs and waits. Human hands-on hours,\npure AI compute time and time saved were not separately measured.'],
 ['NAVSPHERE  /  CONTRIBUTIONS','AI implemented software; the user directed and wired it',
  'Source: current project/AI work report | Prompt audit includes this documentation request.','03',
  'AI contribution','Firmware, backend, GUI and database\nDBC, CAN search, statistics and TX\nReference analysis, tests and fixes\nDeployment, evidence and documentation',
  'User contribution','Scope, priorities and exact CAN bytes\nESP32, BMS and PCAN connections\nWiring checks and supply correction\nNetwork access, reviews and decisions',
  `${audit.user_message_count} user inputs | Original master prompt: 4,338 words`,
  'Project credits and billed tokens are unavailable, not zero.\nNo cost or time-saving percentage is inferred.'],
 ['NAVSPHERE  /  CAPABILITY','Telemetry, CAN analysis and confirmed TX controls',
  'Genuine CAN GUI, 19 Nov: v1.1.8 UI; last-seen device v1.1.7/offline.','04',
  'Sense and store','Six ADC1 inputs; MQTT to MariaDB\n500 kbit/s CAN receive and raw history',
  'View and decode','Local DBC files, live search and statistics\nAnalytics, CSV and saved CAN values',
  'Control and diagnose','GPIO2/GPIO0; fixed 0x014 and 0x548 TX\nBMS page implemented; live UDS unverified'],
 ['NAVSPHERE  /  VERIFICATION','Correct payloads received; v1.1.8 timing test pending',
  'Evidence: RELEASE_STATUS.md and can-tx-voltage-corrected-before-arbitration-fix.json.','05',
  '89 / 38','Backend / GUI suite tests passed',
  '2 IDs','Exact payloads observed on PCAN',
  'v1.1.8','Built; not yet flashed',
  'What is established','v1.1.7 sends both payloads after power fix\n0x548 timing failed: mean 12.301 ms\nArbitration retry correction built',
  'Next work','Reconnect, flash and measure timing\nVerify GUI ON/OFF and DB continuity\nBMS response and soak remain separate']
];
for(let i=0;i<5;i++){
 const records=snapshot.records.filter(x=>x.kind==='textbox'&&x.slideIndex===i);
 if(records.length!==content[i].length)throw new Error(`Slide ${i+1}: template shape count changed`);
 for(let j=0;j<records.length;j++){
   const r=records[j],shape=p.resolve(r.id);
   shape.text=content[i][j];shape.text.style={...r.style,fontFamily:r.style.typeface,
     ...(i===2&&j===1?{fontSize:36}:{})};
 }
 const slide=p.slides.items[i];
 slide.speakerNotes.text='Sources: docs/reports/PROJECT_AND_AI_USAGE.md; output/reports/interaction-time.json; docs/RELEASE_STATUS.md. Timing sums completed app turn durations and excludes the current documentation turn. Suite and later targeted tests overlap. Firmware v1.1.8 has not been flashed. Exact project credits and billed tokens are unavailable.';
}
const imageRecord=snapshot.records.find(x=>x.kind==='image'&&x.slideIndex===3);
const picture=p.resolve(imageRecord.id);
const oldFrame=picture.frame;
picture.replace({blob:new Uint8Array(await fs.readFile('output/testing/can-tx-awaiting-flash.jpg')),contentType:'image/jpeg',fit:'contain',alt:'Genuine CAN transmission GUI, 19 November 2026; device offline, latest flash pending'});
picture.frame=oldFrame;picture.fit='contain';
for(let i=0;i<5;i++){
 const s=p.slides.items[i];
 const png=await s.export({format:'png',scale:1});
 await fs.writeFile(path.join(dir,`after-${i+1}.png`),new Uint8Array(await png.arrayBuffer()));
 const layout=await s.export({format:'layout'});
 await fs.writeFile(path.join(dir,`after-${i+1}.layout.json`),typeof layout==='string'?layout:JSON.stringify(layout));
}
const candidate=path.join(dir,'candidate-current.pptx');
await(await PresentationFile.exportPptx(p)).save(candidate);
const skill=process.env.PRESENTATIONS_SKILL_DIR;
const {finalizePresentation}=await import(pathToFileURL(path.join(skill,'container_tools/artifact_tool_utils.mjs')).href);
await fs.mkdir(path.join(dir,'final'),{recursive:true});
const validated=path.join(dir,'final',`validated-${Date.now()}.pptx`);
const result=await finalizePresentation({workspaceDir:root,candidatePath:candidate,finalPath:validated,
 pythonExecutable:process.env.RUNTIME_PYTHON,
 integrityValidatorPath:path.join(skill,'container_tools/inspect_presentation_package_integrity.py'),
 layoutValidatorPath:path.join(skill,'container_tools/inspect_presentation_layout_geometry.py'),
 layoutArgs:['--expected-slide-size-emu','12192000,6858000','--validate-heading-fit'],
 explicitTotalSlideCount:5,fontPolicy:{basis:'reference',families:['Arial'],referencePath:backup,
 referenceSha256:createHash('sha256').update(await fs.readFile(backup)).digest('hex')},
 verifyArtifactToolImport:true,receiptPath:path.join(dir,'presentation-validation.json')});
await fs.copyFile(validated,source);
console.log(JSON.stringify(result));
