"""Export current offline documentation without changing application version."""
from pathlib import Path
import importlib.util
import json
from datetime import datetime, timezone
from reportlab.platypus import SimpleDocTemplate, PageBreak, Image, Paragraph, Spacer
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('legacy_export',ROOT/'scripts/export_documents.py')
base=importlib.util.module_from_spec(spec);spec.loader.exec_module(base)
version=json.loads((ROOT/'version.json').read_text())
stamp=datetime.now(timezone.utc).strftime('%d %B %Y')

def footer(canvas,doc):
    canvas.saveState();canvas.setFont('Body',8);canvas.setFillColor(base.SLATE)
    canvas.drawString(18*mm,10*mm,f"NavSphere | v{version['sw_version']} | Documentation {stamp}")
    canvas.drawRightString(A4[0]-18*mm,10*mm,str(doc.page));canvas.restoreState()

def export(relative,destination,label,images=()):
    styles=base.styles();story=base.parse((ROOT/relative).read_text(encoding='utf-8'),label,styles)
    for path,title,caption in images:
        story.extend([PageBreak(),Paragraph(title,styles['h2']),Paragraph(caption,styles['body']),Spacer(1,8)])
        picture=Image(str(ROOT/path));width,height=picture.imageWidth,picture.imageHeight
        scale=min(174*mm/width,222*mm/height)
        picture.drawWidth=width*scale;picture.drawHeight=height*scale;story.append(picture)
    out=ROOT/destination;out.parent.mkdir(parents=True,exist_ok=True)
    doc=SimpleDocTemplate(str(out),pagesize=A4,leftMargin=18*mm,rightMargin=18*mm,
        topMargin=18*mm,bottomMargin=22*mm,title=out.stem.replace('_',' '),author='NavSphere Engineering')
    doc.build(story,onFirstPage=footer,onLaterPages=footer)
    print(destination)

def main():
    base.fonts()
    for relative,filename,label in base.SOURCES:export(relative,'output/pdf/'+filename,label)
    export('docs/reports/PROJECT_AND_AI_USAGE.md','output/reports/NavSphere_Project_and_AI_Usage_Report.pdf',
        'PROJECT / AI WORK / MEASURED TIME',[
        ('output/testing/can-tx-awaiting-flash.jpg','CAN transmission controls - 19 November',
         'Genuine GUI v1.1.8 capture; device last seen v1.1.7 and offline. Flash/timing verification remains pending.'),
        ('output/testing/bms/redeploy-20261119-gui.jpg','Earlier live CAN dashboard - 19 November',
         'Historical v1.1.4 deployment capture. This is not evidence that the v1.1.8 timing correction is deployed.'),
        ('output/reports/telematics-overview.png','Telematics overview - 12 November',
         'Historical capture of six-channel telemetry and service/persistence status.'),
        ('output/reports/telematics-analytics.png','Channel analytics - 12 November',
         'Historical capture of live/history charts and channel analysis.'),
        ('output/reports/telematics-controls.png','GPIO controls - 12 November',
         'Historical capture of Control A on GPIO2 and Control B on GPIO0.')])

if __name__=='__main__':main()
