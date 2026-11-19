"""Check documentation coverage, local links, PDF geometry and release identity."""
from pathlib import Path
from urllib.parse import unquote
from datetime import datetime, timezone
import hashlib
import json
import re
import subprocess
import pdfplumber
from pypdf import PdfReader
from pptx import Presentation

ROOT=Path(__file__).resolve().parents[2]
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    tracked=subprocess.check_output(['git','ls-files','--cached','--others','--exclude-standard'],cwd=ROOT,text=True).splitlines()
    maintained=sorted({n for n in tracked if (n.endswith('.md') or n in ('bms_images/README.txt',))
        and not n.startswith('output/work_snapshot/')})
    broken=[]
    for name in maintained:
        p=ROOT/name
        for target in re.findall(r'\[[^\]]*\]\(([^)]+)\)',p.read_text(encoding='utf-8')):
            target=target.strip('<>').split('#')[0]
            if not target or re.match(r'^[a-zA-Z]+:',target):continue
            resolved=(p.parent/unquote(target)).resolve()
            if resolved==ROOT/'docs/testing/documentation-review.json':continue
            if not resolved.exists():broken.append({'document':name,'target':target})
    assert not broken,broken
    release=json.loads((ROOT/'version.json').read_text())
    manifest=json.loads((ROOT/'output/firmware/manifest.json').read_text())
    assert release['sw_version']==manifest['sw_version']=='1.1.8'
    assert release['source_sha256'][:12]==manifest['sw_build']=='8148c3afe9b8'
    assert not manifest['hardware_flashed']
    assert sha(ROOT/'output/firmware/navsphere.bin')==manifest['files']['navsphere.bin']['sha256']
    api=json.loads((ROOT/'docs/api/openapi.json').read_text())
    contract=(ROOT/'docs/api/API_REFERENCE.md').read_text()
    missing=[p for p in api['paths'] if p not in contract]
    assert not missing,missing
    tables=re.findall(r'CREATE TABLE\s+(\w+)',(ROOT/'database/schema.sql').read_text())
    assert len(tables)==11 and {'can_frames','can_latest','can_dbc','bms_jobs','bms_exchanges'}<=set(tables)
    pdfs=list((ROOT/'output/pdf').glob('*.pdf'))+[ROOT/'output/reports/NavSphere_Project_and_AI_Usage_Report.pdf']
    pdf_results=[]
    for p in pdfs:
        text='\n'.join(page.extract_text() for page in PdfReader(p).pages)
        assert 'v1.1.8' in text and '19 November 2026' in text,p
        overflow=[]
        with pdfplumber.open(p) as pdf:
            for i,page in enumerate(pdf.pages,1):
                for c in page.chars:
                    if c['x0']<0 or c['x1']>page.width+1 or c['top']<0 or c['bottom']>page.height+1:
                        overflow.append(i);break
            pdf_results.append({'path':p.relative_to(ROOT).as_posix(),'pages':len(pdf.pages),
                                'sha256':sha(p),'text_outside_page':overflow})
        assert not overflow,(p,overflow)
    deck=ROOT/'output/reports/NavSphere_Stakeholder_Presentation.pptx'
    ppt=Presentation(deck);assert len(ppt.slides)==5
    ppttext='\n'.join(s.text for slide in ppt.slides for s in slide.shapes if s.has_text_frame)
    for expected in ('6h 21m 22s','74 user inputs','v1.1.8','not yet flashed'):
        assert expected.lower() in ppttext.lower(),expected
    validation=json.loads((ROOT/'tmp/docs-review/presentation-validation.json').read_text())
    assert validation['finalSha256']==sha(deck)
    assert validation['packageIntegrity']['findingCount']==0
    assert validation['presentationLayout']['findingCount']==0
    metrics=json.loads((ROOT/'output/reports/interaction-time.json').read_text())
    done=[t for t in metrics['turns'] if t['status']=='completed' and isinstance(t['durationMs'],int)]
    assert sum(t['durationMs'] for t in done)==metrics['total_ms']==22882384
    assert len(done)==44
    report={'reviewed_utc':datetime.now(timezone.utc).isoformat(),'application_release':release,
        'source_commit':'c272b057ccbc3c86b27d0bb96a545ee407c330bb',
        'maintained_documents':maintained,'local_markdown_links':'passed',
        'openapi_paths':len(api['paths']),'api_contract_route_coverage':'passed',
        'schema_tables':tables,'pdf_editions':pdf_results,
        'presentation':{'slides':5,'sha256':sha(deck),'package_and_layout':'passed',
                        'render_review':'All five slides inspected; template and editable text retained.'},
        'visual_review':'All 36 PDF pages reviewed in rendered contact sheets; current report/screenshot pages checked. Updated implementation final page re-rendered.',
        'time_audit':{'completed_turns':44,'total_ms':22882384,'user_message_count':74,
                      'current_documentation_turn_included_in_time':False},
        'hardware_status':'v1.1.8 built, not flashed; final CAN timing/GUI acceptance pending; BMS unverified',
        'historical_records':'Dated tests, screenshots, prior releases and prior work snapshots retained without fabricated success.',
        'application_changes':False}
    destination=ROOT/'docs/testing/documentation-review.json'
    destination.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'documents':len(maintained),'pdf_pages':sum(p['pages'] for p in pdf_results),
                      'slides':5,'api_paths':len(api['paths']),'tables':len(tables),'result':'passed'}))

if __name__=='__main__':main()
