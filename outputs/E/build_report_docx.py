#!/usr/bin/env python3
"""Build report/report.docx from report/report.md and local figure assets."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

from docx import Document
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor


ROOT = Path(__file__).resolve().parent
DEFAULT_MARKDOWN = ROOT / "report" / "report.md"
DEFAULT_OUTPUT = ROOT / "report" / "report.docx"

BLACK = RGBColor(0, 0, 0)
WHITE = RGBColor(255, 255, 255)
NAVY = "1F4E79"
PALE_BLUE = "EDF3F8"
LIGHT_GRAY = "D9D9D9"


def set_run_font(run, size: float = 11, bold=None, italic=None, name="Times New Roman"):
    run.font.name = name
    run._element.get_or_add_rPr().rFonts.set(qn("w:eastAsia"), name)
    run.font.size = Pt(size)
    run.font.color.rgb = BLACK
    if bold is not None:
        run.bold = bold
    if italic is not None:
        run.italic = italic


def set_cell_fill(cell, fill: str) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    shade = tc_pr.find(qn("w:shd"))
    if shade is None:
        shade = OxmlElement("w:shd")
        tc_pr.append(shade)
    shade.set(qn("w:fill"), fill)
    shade.set(qn("w:val"), "clear")


def set_table_borders(table) -> None:
    tbl_pr = table._tbl.tblPr
    borders = tbl_pr.find(qn("w:tblBorders"))
    if borders is None:
        borders = OxmlElement("w:tblBorders")
        tbl_pr.append(borders)
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        element = borders.find(qn(f"w:{edge}"))
        if element is None:
            element = OxmlElement(f"w:{edge}")
            borders.append(element)
        element.set(qn("w:val"), "single")
        element.set(qn("w:sz"), "4")
        element.set(qn("w:space"), "0")
        element.set(qn("w:color"), LIGHT_GRAY)


def set_cell_margins(table, top=70, start=85, bottom=70, end=85) -> None:
    tbl_pr = table._tbl.tblPr
    margins = tbl_pr.find(qn("w:tblCellMar"))
    if margins is None:
        margins = OxmlElement("w:tblCellMar")
        tbl_pr.append(margins)
    for key, value in (("top", top), ("start", start), ("bottom", bottom), ("end", end)):
        node = margins.find(qn(f"w:{key}"))
        if node is None:
            node = OxmlElement(f"w:{key}")
            margins.append(node)
        node.set(qn("w:w"), str(value))
        node.set(qn("w:type"), "dxa")


def set_col_widths(table, widths: list[float]) -> None:
    for row in table.rows:
        for index, width in enumerate(widths):
            row.cells[index].width = Inches(width)


def prevent_row_split(row) -> None:
    tr_pr = row._tr.get_or_add_trPr()
    tr_pr.append(OxmlElement("w:cantSplit"))


def repeat_header(row) -> None:
    tr_pr = row._tr.get_or_add_trPr()
    marker = OxmlElement("w:tblHeader")
    marker.set(qn("w:val"), "true")
    tr_pr.append(marker)


def clear_markdown(text: str) -> str:
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = text.replace(r"\<", "<").replace(r"\>", ">")
    return text


INLINE_PATTERN = re.compile(r"(\*\*.+?\*\*|`.+?`|\*[^*]+\*)")


def add_inline_runs(paragraph, text: str, size: float = 11) -> None:
    text = clear_markdown(text)
    position = 0
    for match in INLINE_PATTERN.finditer(text):
        if match.start() > position:
            run = paragraph.add_run(text[position : match.start()])
            set_run_font(run, size=size)
        token = match.group(0)
        if token.startswith("**") and token.endswith("**"):
            run = paragraph.add_run(token[2:-2])
            set_run_font(run, size=size, bold=True)
        elif token.startswith("`") and token.endswith("`"):
            run = paragraph.add_run(token[1:-1])
            set_run_font(run, size=size, italic=True)
        else:
            run = paragraph.add_run(token[1:-1])
            set_run_font(run, size=size, italic=True)
        position = match.end()
    if position < len(text):
        run = paragraph.add_run(text[position:])
        set_run_font(run, size=size)


def add_body(document: Document, text: str) -> None:
    paragraph = document.add_paragraph(style="Normal")
    add_inline_runs(paragraph, text, size=11)
    paragraph.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    paragraph.paragraph_format.line_spacing = 1.4
    paragraph.paragraph_format.space_after = Pt(6)


def add_heading(document: Document, text: str, level: int) -> None:
    style = "Heading 1" if level == 1 else "Heading 2"
    paragraph = document.add_paragraph(style=style)
    add_inline_runs(paragraph, text, size=14 if level == 1 else 12)
    for run in paragraph.runs:
        run.bold = True
        run.font.color.rgb = BLACK
    paragraph.paragraph_format.keep_with_next = True


def add_title(document: Document, text: str) -> None:
    paragraph = document.add_paragraph(style="Title")
    add_inline_runs(paragraph, text, size=20)
    for run in paragraph.runs:
        run.bold = True
        run.font.color.rgb = BLACK


def add_note(document: Document, text: str) -> None:
    paragraph = document.add_paragraph(style="Normal")
    add_inline_runs(paragraph, text, size=9)
    paragraph.paragraph_format.line_spacing = 1.0
    paragraph.paragraph_format.space_before = Pt(4)
    paragraph.paragraph_format.space_after = Pt(8)


def add_caption(document: Document, text: str) -> None:
    paragraph = document.add_paragraph(style="Normal")
    add_inline_runs(paragraph, text, size=9.5)
    for run in paragraph.runs:
        run.italic = True
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    paragraph.paragraph_format.keep_with_next = True
    paragraph.paragraph_format.space_after = Pt(4)


def add_equation(document: Document, text: str) -> None:
    paragraph = document.add_paragraph(style="Normal")
    run = paragraph.add_run(text)
    set_run_font(run, size=11, italic=True)
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    paragraph.paragraph_format.space_before = Pt(4)
    paragraph.paragraph_format.space_after = Pt(8)


def add_picture(document: Document, path: Path) -> None:
    paragraph = document.add_paragraph(style="Normal")
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = paragraph.add_run()
    run.add_picture(str(path), width=Inches(6.15))
    paragraph.paragraph_format.space_before = Pt(4)
    paragraph.paragraph_format.space_after = Pt(3)


def parse_table(lines: list[str], start: int) -> tuple[list[list[str]], int]:
    rows: list[list[str]] = []
    index = start
    while index < len(lines) and lines[index].strip().startswith("|"):
        cells = [cell.strip() for cell in lines[index].strip().strip("|").split("|")]
        rows.append(cells)
        index += 1
    if len(rows) < 2:
        raise ValueError("Markdown table must include a header and separator")
    rows.pop(1)
    return rows, index


def add_table(document: Document, rows: list[list[str]]) -> None:
    header, body = rows[0], rows[1:]
    table = document.add_table(rows=1 + len(body), cols=len(header))
    table.style = "Light Shading Accent 1"
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    set_table_borders(table)
    set_cell_margins(table)

    widths = (
        [0.62, 1.42, 1.38, 1.32, 1.26]
        if len(header) == 5
        else [6.0 / len(header)] * len(header)
    )
    set_col_widths(table, widths)

    for column, label in enumerate(header):
        cell = table.cell(0, column)
        cell.text = ""
        paragraph = cell.paragraphs[0]
        paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
        paragraph.paragraph_format.space_after = Pt(0)
        run = paragraph.add_run(label)
        set_run_font(run, size=8.5, bold=True)
        run.font.color.rgb = WHITE
        cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
        set_cell_fill(cell, NAVY)
    repeat_header(table.rows[0])

    for row_index, values in enumerate(body, start=1):
        for column in range(len(header)):
            cell = table.cell(row_index, column)
            cell.text = ""
            paragraph = cell.paragraphs[0]
            paragraph.alignment = (
                WD_ALIGN_PARAGRAPH.LEFT
                if column == 0
                else WD_ALIGN_PARAGRAPH.CENTER
            )
            paragraph.paragraph_format.space_after = Pt(0)
            paragraph.paragraph_format.line_spacing = 1.0
            value = values[column] if column < len(values) else ""
            run = paragraph.add_run(value)
            set_run_font(run, size=8.5)
            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
            if row_index % 2 == 0:
                set_cell_fill(cell, PALE_BLUE)
        prevent_row_split(table.rows[row_index])
    document.add_paragraph().paragraph_format.space_after = Pt(0)


def configure_styles(document: Document) -> None:
    section = document.sections[0]
    section.page_width = Inches(8.5)
    section.page_height = Inches(11)
    section.top_margin = Inches(1.0)
    section.bottom_margin = Inches(1.0)
    section.left_margin = Inches(1.0)
    section.right_margin = Inches(1.0)

    normal = document.styles["Normal"]
    normal.font.name = "Times New Roman"
    normal.font.size = Pt(11)
    normal.font.color.rgb = BLACK
    normal.paragraph_format.line_spacing = 1.4
    normal.paragraph_format.space_after = Pt(6)

    title = document.styles["Title"]
    title.font.name = "Times New Roman"
    title.font.size = Pt(20)
    title.font.bold = True
    title.font.color.rgb = BLACK
    title.paragraph_format.space_after = Pt(12)
    title.paragraph_format.line_spacing = 1.0

    heading1 = document.styles["Heading 1"]
    heading1.font.name = "Times New Roman"
    heading1.font.size = Pt(14)
    heading1.font.bold = True
    heading1.font.color.rgb = BLACK
    heading1.paragraph_format.space_before = Pt(14)
    heading1.paragraph_format.space_after = Pt(6)

    heading2 = document.styles["Heading 2"]
    heading2.font.name = "Times New Roman"
    heading2.font.size = Pt(12)
    heading2.font.bold = True
    heading2.font.color.rgb = BLACK
    heading2.paragraph_format.space_before = Pt(10)
    heading2.paragraph_format.space_after = Pt(4)


def build(markdown_path: Path, output_path: Path) -> None:
    lines = markdown_path.read_text(encoding="utf-8").splitlines()
    document = Document()
    configure_styles(document)

    index = 0
    while index < len(lines):
        raw = lines[index].strip()
        if not raw or raw.startswith("<!--"):
            index += 1
            continue
        if raw.startswith("# "):
            add_title(document, raw[2:])
        elif raw.startswith("## "):
            add_heading(document, raw[3:], level=1)
        elif raw.startswith("### "):
            add_heading(document, raw[4:], level=2)
        elif raw.startswith("|"):
            rows, index = parse_table(lines, index)
            add_table(document, rows)
            continue
        elif match := re.fullmatch(r"!\[[^\]]*\]\(([^)]+)\)", raw):
            image_path = (markdown_path.parent / match.group(1)).resolve()
            if not image_path.exists():
                raise FileNotFoundError(image_path)
            add_picture(document, image_path)
        elif raw.startswith("$$") and raw.endswith("$$"):
            add_equation(document, raw[2:-2].strip())
        elif raw.startswith("*Figure "):
            add_caption(document, raw.strip("*"))
        elif raw.startswith("Notes:"):
            add_note(document, raw)
        elif raw.startswith("- "):
            paragraph = document.add_paragraph(style="List Bullet")
            add_inline_runs(paragraph, raw[2:], size=11)
        else:
            add_body(document, raw)
        index += 1

    document.core_properties.title = "E. How strict should expulsion be?"
    document.core_properties.subject = (
        "Threshold response surface for expulsion in a fraudulent trading market"
    )
    document.core_properties.author = ""
    document.core_properties.last_modified_by = ""
    document.core_properties.comments = ""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    document.save(output_path)
    print(output_path)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--markdown", type=Path, default=DEFAULT_MARKDOWN)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    build(args.markdown.resolve(), args.output.resolve())


if __name__ == "__main__":
    main()
