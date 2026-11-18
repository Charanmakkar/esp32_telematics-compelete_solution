import fs from 'node:fs/promises';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
import {Presentation,PresentationFile} from '@oai/artifact-tool';
const workspace=process.cwd();
const skill='C:/Users/charanpreet/.codex/plugins/cache/openai-primary-runtime/presentations/26.1112.11011/skills/presentations';
const saved='C:/Users/charanpreet/AppData/Roaming/Codex/web/Codex/artifact-sessions/exports/latest/4d4bdbac399846092dde863f307f21b73309c2b06d675e0a7810a082f79caf94';
const p=Presentation.create({slideSize:{width:1280,height:720}});
for(let i=1;i<=5;i++){
 const layout=JSON.parse(await fs.readFile(`${saved}/slide-${i}.layout.json`,'utf8'));
 const s=p.slides.add();s.background.fill=layout.slide.backgroundColor;
 for(const e of layout.elements){
  if(e.kind==='textbox'){
   const a=s.shapes.add({geometry:'textbox',position:e.position,fill:'none',line:{fill:'none',width:0}});
   a.text=e.text;a.text.style={...e.style,fontFamily:e.style.typeface};
  }else if(e.kind==='image')s.images.add({blob:new Uint8Array(await fs.readFile(path.join(workspace,'output/reports/telematics-controls.png'))),contentType:'image/png',position:e.position,fit:e.fit,alt:e.alt});
 }
 const png=await p.export({slide:s,format:'png',scale:1});
 await fs.writeFile(`tmp/ppt-offline/slide-${i}.png`,new Uint8Array(await png.arrayBuffer()));
}
const candidate=path.join(workspace,'tmp/ppt-offline/candidate.pptx');
await(await PresentationFile.exportPptx(p)).save(candidate);
const {finalizePresentation}=await import(pathToFileURL(path.join(skill,'container_tools/artifact_tool_utils.mjs')).href);
const result=await finalizePresentation({workspaceDir:workspace,candidatePath:candidate,finalPath:path.join(workspace,'output/reports/NavSphere_Stakeholder_Presentation.pptx'),pythonExecutable:'C:/Users/charanpreet/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe',integrityValidatorPath:path.join(skill,'container_tools/inspect_presentation_package_integrity.py'),layoutValidatorPath:path.join(skill,'container_tools/inspect_presentation_layout_geometry.py'),layoutArgs:['--expected-slide-size-emu','12192000,6858000','--validate-heading-fit'],explicitTotalSlideCount:5,fontPolicy:{basis:'design',families:['Arial']},verifyArtifactToolImport:true,receiptPath:path.join(workspace,'tmp/ppt-offline/validation-offline.json')});
console.log(JSON.stringify(result));



