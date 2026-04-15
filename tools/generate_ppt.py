#!/usr/bin/env python3
from __future__ import annotations

import argparse
import glob
import re
from dataclasses import dataclass, field
from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt


FONT_NAME = "Microsoft YaHei"
MONO_FONT = "Consolas"

COLOR_BG = RGBColor(0xF5, 0xF7, 0xFA)
COLOR_WHITE = RGBColor(0xFF, 0xFF, 0xFF)
COLOR_PRIMARY = RGBColor(0x2F, 0x6F, 0xED)
COLOR_TEXT = RGBColor(0x11, 0x18, 0x27)
COLOR_SUBTEXT = RGBColor(0x4B, 0x55, 0x63)
COLOR_LINE = RGBColor(0xAA, 0xB4, 0xC3)
COLOR_CODE_BG = RGBColor(0x1F, 0x29, 0x37)

TEAM_NAME = "我们叫什么名字"
SCHOOL_NAME = "浙江师范大学"
TRACK_NAME = "A类"

MAX_BULLETS_PER_SLIDE = 8
GO_KEYWORDS = ("go", "golang", "gin", "grpc", "编译", "go语言")
PROCESS_KEYWORDS = ("流程", "步骤", "阶段", "演进", "架构")
CHAPTER_KEYWORDS = ("总结", "感谢", "目录", "展望", "第", "功能")


@dataclass
class TableData:
    header_left: str
    header_right: str
    rows: list[tuple[str, str]] = field(default_factory=list)


@dataclass
class Section:
    title: str
    bullets: list[str] = field(default_factory=list)
    tables: list[TableData] = field(default_factory=list)
    code_blocks: list[list[str]] = field(default_factory=list)


@dataclass
class SlideUnit:
    title: str
    bullets: list[str] = field(default_factory=list)
    table: TableData | None = None
    code_block: list[str] | None = None
    is_transition: bool = False


def set_para_style(paragraph, size: int, color: RGBColor, bold: bool = False, align: PP_ALIGN | None = None) -> None:
    if not paragraph.runs:
        paragraph.add_run()
    run = paragraph.runs[0]
    run.font.name = FONT_NAME
    run.font.size = Pt(size)
    run.font.color.rgb = color
    run.font.bold = bold
    if align is not None:
        paragraph.alignment = align


def parse_markdown_sections(path: Path) -> list[Section]:
    text = path.read_text(encoding="utf-8")
    parts = re.split(r"^##\s+", text, flags=re.MULTILINE)
    sections: list[Section] = []

    for part in parts:
        part = part.strip()
        if not part:
            continue
        lines = part.splitlines()
        section = Section(title=lines[0].strip())

        i = 1
        while i < len(lines):
            line = lines[i].rstrip()
            stripped = line.strip()

            if not stripped or stripped == "---" or stripped.lower() in {"text", "yaml", "json", "sql", "go", "bash"}:
                i += 1
                continue

            if stripped.startswith("```"):
                code: list[str] = []
                i += 1
                while i < len(lines) and not lines[i].strip().startswith("```"):
                    code.append(lines[i].rstrip())
                    i += 1
                if code:
                    section.code_blocks.append(code)
                i += 1
                continue

            if stripped.startswith("|") and stripped.endswith("|"):
                table_lines: list[str] = []
                while i < len(lines):
                    row = lines[i].strip()
                    if row.startswith("|") and row.endswith("|"):
                        table_lines.append(row)
                        i += 1
                    else:
                        break
                table = parse_markdown_table(table_lines)
                if table:
                    section.tables.append(table)
                continue

            clean = cleanup_text(stripped)
            if clean:
                section.bullets.append(clean)
            i += 1

        deduped: list[str] = []
        seen = set()
        for bullet in section.bullets:
            if bullet in seen:
                continue
            seen.add(bullet)
            deduped.append(bullet)
        section.bullets = deduped
        sections.append(section)

    return sections


def parse_markdown_table(lines: list[str]) -> TableData | None:
    rows: list[list[str]] = []
    for line in lines:
        cols = [c.strip() for c in line.strip("|").split("|")]
        if cols and all(set(c) <= {"-", ":"} for c in cols):
            continue
        rows.append(cols)

    if len(rows) < 2:
        return None

    head = rows[0]
    body = rows[1:]
    left = head[0] if len(head) > 0 else "项目"
    right = head[1] if len(head) > 1 else "说明"

    data = TableData(header_left=left, header_right=right)
    for row in body:
        l = row[0] if len(row) > 0 else ""
        r = row[1] if len(row) > 1 else ""
        if l or r:
            data.rows.append((cleanup_text(l), cleanup_text(r)))
    return data


def cleanup_text(text: str) -> str:
    text = re.sub(r"^[-*]\s+", "", text)
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"`(.+?)`", r"\1", text)
    text = re.sub(r"<[^>]+>", "", text)
    return text.strip()


def split_section(section: Section) -> list[SlideUnit]:
    units: list[SlideUnit] = []

    if section.bullets:
        chunks = [section.bullets[i : i + MAX_BULLETS_PER_SLIDE] for i in range(0, len(section.bullets), MAX_BULLETS_PER_SLIDE)]
        total = len(chunks)
        for idx, chunk in enumerate(chunks, start=1):
            title = section.title
            if len(section.bullets) > MAX_BULLETS_PER_SLIDE and total > 1:
                title = f"{section.title}（{idx}/{total}）"
            units.append(SlideUnit(title=title, bullets=chunk))

    if not section.bullets and not section.tables and not section.code_blocks:
        units.append(SlideUnit(title=section.title, bullets=["待补充内容"]))

    for table in section.tables[:1]:
        units.append(SlideUnit(title=section.title, table=table))

    for code in section.code_blocks[:1]:
        units.append(SlideUnit(title=section.title, code_block=code[:10]))

    if should_use_transition(section.title, section.bullets) and units:
        units[0].is_transition = True

    return units


def should_use_transition(title: str, bullets: list[str]) -> bool:
    txt = f"{title} {' '.join(bullets[:2])}"
    return any(k in txt for k in CHAPTER_KEYWORDS) and len(bullets) <= 2


def select_layout(unit: SlideUnit) -> str:
    title_text = unit.title.lower()
    all_text = f"{unit.title} {' '.join(unit.bullets)}".lower()
    if unit.is_transition:
        return "C"
    if any(k in all_text for k in PROCESS_KEYWORDS) and unit.bullets:
        return "D"
    if unit.table or len(unit.bullets) >= 5:
        return "B"
    if "架构" in title_text or "技术" in title_text or "部署" in title_text or "实现" in title_text:
        return "A"
    return "A"


def need_go_logo(unit: SlideUnit) -> bool:
    txt = f"{unit.title} {' '.join(unit.bullets)}".lower()
    return any(k in txt for k in GO_KEYWORDS)


def apply_theme(slide, prs: Presentation) -> None:
    bg = slide.background.fill
    bg.solid()
    bg.fore_color.rgb = COLOR_BG

    top_strip = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0), Inches(0), prs.slide_width, Inches(0.06))
    top_strip.fill.solid()
    top_strip.fill.fore_color.rgb = COLOR_PRIMARY
    top_strip.line.fill.background()

    add_hud_decor(slide)


def add_hud_decor(slide) -> None:
    left = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.28), Inches(0.35), Inches(0.02), Inches(0.36))
    left.fill.solid()
    left.fill.fore_color.rgb = COLOR_PRIMARY
    left.line.fill.background()

    top = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.28), Inches(0.35), Inches(0.46), Inches(0.02))
    top.fill.solid()
    top.fill.fore_color.rgb = COLOR_PRIMARY
    top.line.fill.background()

    right_top = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(12.55), Inches(0.35), Inches(0.46), Inches(0.02))
    right_top.fill.solid()
    right_top.fill.fore_color.rgb = COLOR_LINE
    right_top.line.fill.background()

    right_side = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(12.99), Inches(0.35), Inches(0.02), Inches(0.36))
    right_side.fill.solid()
    right_side.fill.fore_color.rgb = COLOR_LINE
    right_side.line.fill.background()


def add_title_block(slide, title: str) -> None:
    tbox = slide.shapes.add_textbox(Inches(0.8), Inches(0.42), Inches(8.8), Inches(0.7))
    tf = tbox.text_frame
    tf.clear()
    p = tf.paragraphs[0]
    p.text = title
    set_para_style(p, 28, COLOR_TEXT, bold=True)

    line = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.8), Inches(1.17), Inches(3.2), Inches(0.03))
    line.fill.solid()
    line.fill.fore_color.rgb = COLOR_PRIMARY
    line.line.fill.background()


def add_footer(slide, prs: Presentation, page_no: int) -> None:
    line = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.7), prs.slide_height - Inches(0.56), prs.slide_width - Inches(1.4), Inches(0.01))
    line.fill.solid()
    line.fill.fore_color.rgb = COLOR_LINE
    line.line.fill.background()

    left = slide.shapes.add_textbox(Inches(0.75), prs.slide_height - Inches(0.42), Inches(8.5), Inches(0.24))
    tf = left.text_frame
    tf.clear()
    p = tf.paragraphs[0]
    p.text = f"队伍：{TEAM_NAME}  ·  学校：{SCHOOL_NAME}  ·  赛道：{TRACK_NAME}"
    set_para_style(p, 10, COLOR_SUBTEXT)

    right = slide.shapes.add_textbox(prs.slide_width - Inches(1.0), prs.slide_height - Inches(0.42), Inches(0.4), Inches(0.24))
    rtf = right.text_frame
    rtf.clear()
    p2 = rtf.paragraphs[0]
    p2.text = str(page_no)
    set_para_style(p2, 10, COLOR_SUBTEXT, align=PP_ALIGN.RIGHT)


def add_card(slide, x, y, w, h, fill_color: RGBColor = COLOR_WHITE, border_color: RGBColor = COLOR_LINE):
    shadow = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, x + Pt(1), y + Pt(1), w, h)
    shadow.fill.solid()
    shadow.fill.fore_color.rgb = RGBColor(0xE9, 0xEE, 0xF4)
    shadow.line.fill.background()

    card = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, x, y, w, h)
    card.fill.solid()
    card.fill.fore_color.rgb = fill_color
    card.line.color.rgb = border_color
    card.line.width = Pt(1)
    return card


def add_bullets(slide, bullets: list[str], x, y, w, h, size=16) -> None:
    box = slide.shapes.add_textbox(x, y, w, h)
    tf = box.text_frame
    tf.clear()
    tf.word_wrap = True

    for idx, bullet in enumerate(bullets):
        p = tf.paragraphs[0] if idx == 0 else tf.add_paragraph()
        p.text = f"• {bullet}"
        set_para_style(p, size, COLOR_TEXT if idx < 2 else COLOR_SUBTEXT)
        p.space_after = Pt(8)
        p.line_spacing = 1.25


def render_table_card(slide, table: TableData, x, y, w, h) -> None:
    add_card(slide, x, y, w, h)

    header = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, x + Inches(0.12), y + Inches(0.10), w - Inches(0.24), Inches(0.42))
    header.fill.solid()
    header.fill.fore_color.rgb = RGBColor(0xEC, 0xF2, 0xFF)
    header.line.fill.background()

    left_w = (w - Inches(0.24)) * 0.32
    h1 = slide.shapes.add_textbox(x + Inches(0.16), y + Inches(0.14), left_w, Inches(0.3))
    h1tf = h1.text_frame
    h1tf.clear()
    p = h1tf.paragraphs[0]
    p.text = table.header_left
    set_para_style(p, 13, COLOR_PRIMARY, bold=True)

    h2 = slide.shapes.add_textbox(x + Inches(0.16) + left_w + Inches(0.12), y + Inches(0.14), w - Inches(0.5) - left_w, Inches(0.3))
    h2tf = h2.text_frame
    h2tf.clear()
    p2 = h2tf.paragraphs[0]
    p2.text = table.header_right
    set_para_style(p2, 13, COLOR_PRIMARY, bold=True)

    row_start = y + Inches(0.58)
    row_h = min(Inches(0.62), (h - Inches(0.75)) / max(1, len(table.rows[:6])))
    for idx, (left_text, right_text) in enumerate(table.rows[:6]):
        ry = row_start + idx * row_h
        if idx > 0:
            sep = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, x + Inches(0.16), ry - Inches(0.04), w - Inches(0.32), Inches(0.01))
            sep.fill.solid()
            sep.fill.fore_color.rgb = RGBColor(0xE3, 0xE8, 0xEF)
            sep.line.fill.background()

        lbox = slide.shapes.add_textbox(x + Inches(0.16), ry, left_w, row_h)
        ltf = lbox.text_frame
        ltf.clear()
        lp = ltf.paragraphs[0]
        lp.text = left_text
        set_para_style(lp, 12, COLOR_TEXT, bold=True)

        rbox = slide.shapes.add_textbox(x + Inches(0.16) + left_w + Inches(0.12), ry, w - Inches(0.5) - left_w, row_h)
        rtf = rbox.text_frame
        rtf.clear()
        rp = rtf.paragraphs[0]
        rp.text = right_text
        set_para_style(rp, 12, COLOR_SUBTEXT)


def render_code_card(slide, code_lines: list[str], x, y, w, h) -> None:
    card = add_card(slide, x, y, w, h, fill_color=COLOR_CODE_BG, border_color=RGBColor(0x2F, 0x3C, 0x52))
    # 调整圆角半径比例，让代码卡片更接近数码风面板观感。
    card.adjustments[0] = 0.12

    tag = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, x + Inches(0.14), y + Inches(0.10), Inches(1.0), Inches(0.28))
    tag.fill.solid()
    tag.fill.fore_color.rgb = RGBColor(0x34, 0x42, 0x59)
    tag.line.fill.background()
    ttf = tag.text_frame
    ttf.clear()
    tp = ttf.paragraphs[0]
    tp.text = "CODE"
    set_para_style(tp, 10, RGBColor(0xD4, 0xDE, 0xEF), bold=True, align=PP_ALIGN.CENTER)

    box = slide.shapes.add_textbox(x + Inches(0.18), y + Inches(0.46), w - Inches(0.36), h - Inches(0.56))
    tf = box.text_frame
    tf.clear()
    tf.word_wrap = True
    tf.vertical_anchor = MSO_ANCHOR.TOP

    for idx, line in enumerate(code_lines[:10]):
        p = tf.paragraphs[0] if idx == 0 else tf.add_paragraph()
        p.text = line
        if not p.runs:
            p.add_run()
        run = p.runs[0]
        run.font.name = MONO_FONT
        run.font.size = Pt(11)
        run.font.color.rgb = RGBColor(0xE7, 0xEF, 0xFF)
        p.space_after = Pt(2)


def add_go_logo_if_needed(slide, unit: SlideUnit, logo_path: Path) -> None:
    if need_go_logo(unit) and logo_path.exists():
        slide.shapes.add_picture(str(logo_path), Inches(10.7), Inches(1.45), width=Inches(2.1))


def render_layout_a(slide, unit: SlideUnit, logo_path: Path) -> None:
    add_card(slide, Inches(0.8), Inches(1.45), Inches(8.6), Inches(5.35))
    add_bullets(slide, unit.bullets, Inches(1.05), Inches(1.72), Inches(8.1), Inches(4.8), size=16)

    side = add_card(slide, Inches(9.65), Inches(1.45), Inches(2.85), Inches(5.35), fill_color=RGBColor(0xF9, 0xFB, 0xFF))
    side_tf = side.text_frame
    side_tf.clear()
    p = side_tf.paragraphs[0]
    p.text = "技术插图区"
    set_para_style(p, 12, COLOR_SUBTEXT, align=PP_ALIGN.CENTER)

    add_go_logo_if_needed(slide, unit, logo_path)


def render_layout_b(slide, unit: SlideUnit) -> None:
    add_card(slide, Inches(0.8), Inches(1.45), Inches(5.85), Inches(5.35))
    add_card(slide, Inches(6.65), Inches(1.45), Inches(5.85), Inches(5.35))

    mid = (len(unit.bullets) + 1) // 2
    left = unit.bullets[:mid]
    right = unit.bullets[mid:]

    add_bullets(slide, left, Inches(1.05), Inches(1.72), Inches(5.3), Inches(4.9), size=15)
    add_bullets(slide, right, Inches(6.9), Inches(1.72), Inches(5.3), Inches(4.9), size=15)


def render_layout_c(slide, unit: SlideUnit) -> None:
    badge = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.95), Inches(1.85), Inches(1.5), Inches(0.6))
    badge.fill.solid()
    badge.fill.fore_color.rgb = RGBColor(0xE9, 0xF0, 0xFF)
    badge.line.fill.background()
    tf = badge.text_frame
    tf.clear()
    p = tf.paragraphs[0]
    p.text = "SECTION"
    set_para_style(p, 14, COLOR_PRIMARY, bold=True, align=PP_ALIGN.CENTER)

    tbox = slide.shapes.add_textbox(Inches(0.95), Inches(2.65), Inches(10.2), Inches(2.2))
    ttf = tbox.text_frame
    ttf.clear()
    p2 = ttf.paragraphs[0]
    p2.text = unit.title
    set_para_style(p2, 38, COLOR_TEXT, bold=True)

    if unit.bullets:
        sbox = slide.shapes.add_textbox(Inches(0.95), Inches(5.05), Inches(9.0), Inches(1.0))
        stf = sbox.text_frame
        stf.clear()
        p3 = stf.paragraphs[0]
        p3.text = unit.bullets[0]
        set_para_style(p3, 18, COLOR_SUBTEXT)


def render_layout_d(slide, unit: SlideUnit) -> None:
    add_card(slide, Inches(0.8), Inches(1.55), Inches(11.7), Inches(5.15))

    steps = unit.bullets[:5]
    if not steps:
        steps = ["阶段一", "阶段二", "阶段三"]

    total = len(steps)
    for idx, step in enumerate(steps):
        if total == 1:
            cx = Inches(6.35)
        else:
            cx = Inches(1.25 + idx * (10.2 / (total - 1)))
        cy = Inches(3.15)

        node = slide.shapes.add_shape(MSO_SHAPE.OVAL, cx, cy, Inches(0.52), Inches(0.52))
        node.fill.solid()
        node.fill.fore_color.rgb = COLOR_PRIMARY
        node.line.fill.background()
        ntf = node.text_frame
        ntf.clear()
        np = ntf.paragraphs[0]
        np.text = str(idx + 1)
        set_para_style(np, 12, COLOR_WHITE, bold=True, align=PP_ALIGN.CENTER)

        tbox = slide.shapes.add_textbox(cx - Inches(0.38), cy + Inches(0.65), Inches(1.35), Inches(1.2))
        ttf = tbox.text_frame
        ttf.clear()
        tp = ttf.paragraphs[0]
        tp.text = step
        set_para_style(tp, 12, COLOR_SUBTEXT, align=PP_ALIGN.CENTER)

        if idx < total - 1:
            arrow = slide.shapes.add_shape(MSO_SHAPE.CHEVRON, cx + Inches(0.62), cy + Inches(0.18), Inches(1.0), Inches(0.17))
            arrow.fill.solid()
            arrow.fill.fore_color.rgb = RGBColor(0xB8, 0xC5, 0xDD)
            arrow.line.fill.background()


def add_cover(prs: Presentation, title: str, subtitle: str, logo_path: Path) -> None:
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    apply_theme(slide, prs)

    hero = add_card(slide, Inches(0.95), Inches(1.2), Inches(11.4), Inches(5.25), fill_color=COLOR_WHITE)
    hero.line.color.rgb = RGBColor(0xD7, 0xE0, 0xEF)

    tag = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(1.25), Inches(1.55), Inches(2.0), Inches(0.52))
    tag.fill.solid()
    tag.fill.fore_color.rgb = RGBColor(0xE8, 0xF1, 0xFF)
    tag.line.fill.background()
    tf = tag.text_frame
    tf.clear()
    p = tf.paragraphs[0]
    p.text = "A类赛道路演"
    set_para_style(p, 13, COLOR_PRIMARY, bold=True, align=PP_ALIGN.CENTER)

    title_box = slide.shapes.add_textbox(Inches(1.25), Inches(2.2), Inches(8.2), Inches(1.9))
    ttf = title_box.text_frame
    ttf.clear()
    tp = ttf.paragraphs[0]
    tp.text = title
    set_para_style(tp, 38, COLOR_TEXT, bold=True)

    sub = slide.shapes.add_textbox(Inches(1.25), Inches(4.2), Inches(8.6), Inches(1.2))
    stf = sub.text_frame
    stf.clear()
    sp = stf.paragraphs[0]
    sp.text = subtitle
    set_para_style(sp, 18, COLOR_SUBTEXT)

    info = add_card(slide, Inches(9.0), Inches(2.0), Inches(2.95), Inches(2.8), fill_color=RGBColor(0xFB, 0xFC, 0xFF))
    itf = info.text_frame
    itf.clear()
    p1 = itf.paragraphs[0]
    p1.text = f"队伍\n{TEAM_NAME}"
    set_para_style(p1, 12, COLOR_TEXT, bold=True)
    p2 = itf.add_paragraph()
    p2.text = f"学校\n{SCHOOL_NAME}"
    set_para_style(p2, 12, COLOR_SUBTEXT)
    p3 = itf.add_paragraph()
    p3.text = f"赛道\n{TRACK_NAME}"
    set_para_style(p3, 12, COLOR_SUBTEXT)

    if logo_path.exists():
        slide.shapes.add_picture(str(logo_path), Inches(9.35), Inches(4.25), width=Inches(2.2))


def extract_cover(sections: list[Section]) -> tuple[str, str]:
    if not sections:
        return "比赛项目汇报", "简约科技数码风演示文稿"
    title = "比赛项目汇报"
    subtitle = "简约科技数码风演示文稿"
    for line in sections[0].bullets:
        if "项目名称" in line and "：" in line:
            title = line.split("：", 1)[1].strip() or title
        if "一句话" in line and "：" in line:
            subtitle = line.split("：", 1)[1].strip() or subtitle
    return title, subtitle


def build_ppt(md_paths: list[Path], output_path: Path, logo_path: Path) -> None:
    sections: list[Section] = []
    for md in md_paths:
        sections.extend(parse_markdown_sections(md))

    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)

    title, subtitle = extract_cover(sections)
    add_cover(prs, title, subtitle, logo_path)

    page_no = 1
    for sec in sections:
        for unit in split_section(sec):
            slide = prs.slides.add_slide(prs.slide_layouts[6])
            apply_theme(slide, prs)
            add_title_block(slide, unit.title)

            layout = select_layout(unit)
            if unit.table:
                render_table_card(slide, unit.table, Inches(0.95), Inches(1.55), Inches(11.4), Inches(5.1))
            elif unit.code_block:
                render_code_card(slide, unit.code_block, Inches(0.95), Inches(1.55), Inches(11.4), Inches(5.1))
            elif layout == "B":
                render_layout_b(slide, unit)
            elif layout == "C":
                render_layout_c(slide, unit)
            elif layout == "D":
                render_layout_d(slide, unit)
            else:
                render_layout_a(slide, unit, logo_path)

            if layout in {"B", "D"}:
                add_go_logo_if_needed(slide, unit, logo_path)

            add_footer(slide, prs, page_no)
            page_no += 1

    output_path.parent.mkdir(parents=True, exist_ok=True)
    prs.save(output_path)


def resolve_markdowns(patterns: list[str]) -> list[Path]:
    files: list[Path] = []
    for pattern in patterns:
        for matched in glob.glob(pattern):
            p = Path(matched)
            if p.is_file() and p.suffix.lower() == ".md":
                files.append(p)
    files = sorted(set(files))
    if not files:
        raise FileNotFoundError(f"No markdown files found matching: {patterns}")
    return files


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate competition PPTX with gray-tech style")
    parser.add_argument("--inputs", nargs="+", default=["CareerPlanner*.md", "docs/**/*.md"])
    parser.add_argument("--output", default="slides/competition.pptx")
    parser.add_argument("--go-logo", default="assets/icons/go.png")
    args = parser.parse_args()

    md_paths = resolve_markdowns(args.inputs)
    output = Path(args.output)
    go_logo = Path(args.go_logo)

    build_ppt(md_paths, output, go_logo)

    print("Markdown sources:")
    for md in md_paths:
        print(f"- {md}")
    print(f"Reference PDF: 比赛用的最终ppt.pdf")
    print(f"Go logo: {go_logo}")
    print(f"Output PPTX: {output}")


if __name__ == "__main__":
    main()
