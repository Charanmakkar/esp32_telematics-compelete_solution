"""Build four polished PDF editions from the requested Markdown deliverables."""
from __future__ import annotations

from html import escape
from pathlib import Path
import re
import textwrap

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    HRFlowable, KeepTogether, Paragraph, Preformatted, SimpleDocTemplate,
    Spacer, Table, TableStyle,
)

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "output" / "pdf"
SOURCES = [
    ("IMPLEMENTATION_REPORT.md", "NavSphere_Implementation_Report.pdf", "01 / IMPLEMENTATION"),
    ("docs/api/API_REFERENCE.md", "NavSphere_API_Reference.pdf", "02 / INTERFACES"),
    ("docs/firmware/FIRMWARE_TECHNICAL_SPECIFICATION.md", "NavSphere_Firmware_Technical_Specification.pdf", "03 / FIRMWARE"),
    ("docs/deployment/DEPLOYMENT_AND_USER_GUIDE.md", "NavSphere_Deployment_and_User_Guide.pdf", "04 / OPERATIONS"),
]
NAVY = colors.HexColor("#0B1220")
CYAN = colors.HexColor("#0891B2")
SLATE = colors.HexColor("#334155")


def normalize(text: str) -> str:
    return text.replace("\u2011", "-").replace("\u2013", "-").replace("\u2014", "-").replace("\u2192", " -> ")


def inline(text: str) -> str:
    text = escape(normalize(text))
    text = re.sub(r"\[([^]]+)\]\(([^)]+)\)", lambda m: f'<link href="{m[2]}" color="#087C9C">{m[1]}</link>', text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"`([^`]+)`", r'<font name="Code" size="8.4">\1</font>', text)
    return text


def fonts() -> None:
    directory = Path("C:/Windows/Fonts")
    pdfmetrics.registerFont(TTFont("Body", str(directory / "segoeui.ttf")))
    pdfmetrics.registerFont(TTFont("BodyBold", str(directory / "segoeuib.ttf")))
    pdfmetrics.registerFont(TTFont("Code", str(directory / "consola.ttf")))
    pdfmetrics.registerFontFamily("Body", normal="Body", bold="BodyBold", italic="Body", boldItalic="BodyBold")


def styles():
    base = getSampleStyleSheet()
    return {
        "body": ParagraphStyle("NSBody", fontName="Body", fontSize=9.5, leading=14.5,
            textColor=SLATE, spaceAfter=7, splitLongWords=True, alignment=TA_LEFT),
        "title": ParagraphStyle("NSTitle", fontName="BodyBold", fontSize=27, leading=33,
            textColor=NAVY, spaceAfter=16),
        "h2": ParagraphStyle("NSH2", fontName="BodyBold", fontSize=15, leading=20,
            textColor=NAVY, spaceBefore=14, spaceAfter=9, keepWithNext=True),
        "h3": ParagraphStyle("NSH3", fontName="BodyBold", fontSize=11.5, leading=16,
            textColor=NAVY, spaceBefore=10, spaceAfter=7, keepWithNext=True),
        "label": ParagraphStyle("NSLabel", fontName="BodyBold", fontSize=9, leading=12,
            textColor=CYAN, spaceAfter=9),
        "cell": ParagraphStyle("NSCell", fontName="Body", fontSize=8.5, leading=12,
            textColor=SLATE, spaceAfter=0),
        "code": ParagraphStyle("NSCode", fontName="Code", fontSize=7.4, leading=10.5,
            backColor=colors.HexColor("#F1F5F9"), borderPadding=9, spaceBefore=4, spaceAfter=9),
    }


def parse(source: str, label: str, style: dict) -> list:
    lines = source.splitlines()
    story = [Paragraph("NAVSPHERE / ENGINEERING DOCUMENTATION", style["label"]),
             Paragraph(label, style["label"])]
    index = 0
    while index < len(lines):
        line = lines[index].strip()
        if not line:
            index += 1
            continue
        if line.startswith("```"):
            index += 1
            block = []
            while index < len(lines) and not lines[index].startswith("```"):
                normalized = normalize(lines[index])
                block.extend(textwrap.wrap(normalized, width=100, replace_whitespace=False,
                                           drop_whitespace=False, subsequent_indent="  ") or [""])
                index += 1
            code = Preformatted("\n".join(block), style["code"])
            story.append(KeepTogether([code]) if len(block) < 45 else code)
            index += 1
            continue
        if line.startswith("|"):
            rows = []
            while index < len(lines) and lines[index].strip().startswith("|"):
                cells = [cell.strip() for cell in lines[index].strip().strip("|").split("|")]
                if not all(re.fullmatch(r"[: -]+", cell) for cell in cells):
                    rows.append([Paragraph(inline(cell), style["cell"]) for cell in cells])
                index += 1
            columns = max(len(row) for row in rows)
            widths = [174*mm/columns]*columns
            if columns == 2:
                widths = [52*mm,122*mm]
            table = Table(rows, colWidths=widths, repeatRows=1, hAlign="LEFT")
            table.setStyle(TableStyle([
                ("BACKGROUND",(0,0),(-1,0),colors.HexColor("#DFF5FA")),
                ("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white,colors.HexColor("#F8FAFC")]),
                ("VALIGN",(0,0),(-1,-1),"TOP"),
                ("LEFTPADDING",(0,0),(-1,-1),8), ("RIGHTPADDING",(0,0),(-1,-1),8),
                ("TOPPADDING",(0,0),(-1,-1),7),("BOTTOMPADDING",(0,0),(-1,-1),7),
                ("LINEBELOW",(0,0),(-1,0),0.8,CYAN),
                ("LINEBELOW",(0,1),(-1,-1),0.3,colors.HexColor("#E2E8F0")),
            ]))
            story.extend([table,Spacer(1,8)])
            continue
        if line.startswith("#"):
            level = len(line) - len(line.lstrip("#"))
            story.append(Paragraph(inline(line.lstrip("# ")), style["title" if level == 1 else "h2" if level == 2 else "h3"]))
            if level == 1:
                story.extend([HRFlowable(width="100%", thickness=1.5, color=CYAN),Spacer(1,12)])
            index += 1
            continue
        if line.startswith("- "):
            story.append(Paragraph("&#8226; " + inline(line[2:]), style["body"]))
            index += 1
            continue
        paragraph = [line]
        index += 1
        while index < len(lines) and lines[index].strip() and not lines[index].startswith(("#", "|", "```", "- ")):
            paragraph.append(lines[index].strip())
            index += 1
        story.append(Paragraph(inline(" ".join(paragraph)), style["body"]))
    return story


def footer(canvas, document) -> None:
    canvas.saveState()
    width, height = A4
    canvas.setStrokeColor(colors.HexColor("#CBD5E1"))
    canvas.line(18*mm,15*mm,width-18*mm,15*mm)
    canvas.setFont("Body",8)
    canvas.setFillColor(SLATE)
    canvas.drawString(18*mm,10*mm,"NavSphere | Six-channel ESP32S-WROOM | 11 November 2026")
    canvas.drawRightString(width-18*mm,10*mm,f"{document.page}")
    canvas.restoreState()


def main() -> None:
    fonts()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    style = styles()
    for relative, filename, label in SOURCES:
        destination = OUTPUT / filename
        doc = SimpleDocTemplate(str(destination), pagesize=A4, rightMargin=18*mm,
            leftMargin=18*mm, topMargin=18*mm, bottomMargin=22*mm,
            title=filename.removesuffix(".pdf").replace("_", " "), author="NavSphere Engineering")
        doc.build(parse((ROOT / relative).read_text(encoding="utf-8"), label, style),
                  onFirstPage=footer, onLaterPages=footer)
        print(destination.relative_to(ROOT))


if __name__ == "__main__":
    main()
