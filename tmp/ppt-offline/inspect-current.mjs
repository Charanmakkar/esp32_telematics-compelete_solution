import fs from 'node:fs/promises';
import {PresentationFile,FileBlob} from '@oai/artifact-tool';
const p=await PresentationFile.importPptx(await FileBlob.load('output/reports/NavSphere_Stakeholder_Presentation.pptx'));
await fs.mkdir('tmp/docs-review',{recursive:true});
await fs.writeFile('tmp/docs-review/presentation-inspect.json',JSON.stringify(await p.inspect({kind:'slide,textbox,image',maxChars:40000}),null,2));
for(let i=0;i<p.slides.items.length;i++){
 const s=p.slides.items[i];
 const png=await s.export({format:'png',scale:1});
 await fs.writeFile(`tmp/docs-review/before-${i+1}.png`,new Uint8Array(await png.arrayBuffer()));
}
console.log('Rendered original five-slide deck.');
