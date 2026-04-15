#!/usr/bin/env python3
from __future__ import annotations

import argparse
import glob
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN
from pptx.util import Inches, Pt


FONT_NAME = "Microsoft YaHei"

BG_COLOR = RGBColor(0xF5, 0xF7, 0xFA)
PRIMARY_COLOR = RGBColor(0x2F, 0x6F, 0xED)
TEXT_COLOR = RGBColor(0x11, 0x18, 0x27)
SUBTEXT_COLOR = RGBColor(0x4B, 0x55, 0x63)
LINE_COLOR = RGBColor(0xAA, 0xB4, 0xC3)

# 队伍名称按题目要求写入，可按需替换为实际队名。
DEFAULT_TEAM_NAME = "我们叫什么名字"
SCHOOL_NAME = "浙江师范大学"
TRACK_NAME = "A类"
# Markdown 中用于标注代码块语言类型的行，不作为正文要点渲染。
SKIP_LANGUAGE_MARKERS = {"text", "yaml", "json", "sql", "go", "bash"}
GO_ICON_KEYWORDS = ("技术栈", "实现", "部署", "架构", "go", "系统架构", "运维")
MAX_BULLETS_PER_SLIDE = 8


@dataclass
class Section:
    title: str
    lines: list[str]


def parse_markdown_sections(path: Path) -> list[Section]:
    content = path.read_text(encoding="utf-8")
    chunks = re.split(r"^##\s+", content, flags=re.MULTILINE)
    sections: list[Section] = []
    for chunk in chunks:
        chunk = chunk.strip()
        if not chunk:
            continue
        lines = chunk.splitlines()
        title = lines[0].strip()
        body = lines[1:]
        bullets = normalize_lines_to_bullets(body)
        sections.append(Section(title=title, lines=bullets))
    return sections


def normalize_lines_to_bullets(lines: Iterable[str]) -> list[str]:
    bullets: list[str] = []
    in_code = False
    for raw in lines:
        line = raw.strip()
        if line.startswith("```"):
            in_code = not in_code
            continue
        if not line or line == "---":
            continue
        if line.lower() in SKIP_LANGUAGE_MARKERS:
            continue
        if in_code:
            cleaned = line.strip("` ")
            if cleaned:
                bullets.append(cleaned)
            continue

        line = re.sub(r"^[-*]\s+", "", line)
        line = re.sub(r"^\*\*(.+?)\*\*$", r"\1", line)
        line = re.sub(r"\*\*(.+?)\*\*", r"\1", line)
        line = re.sub(r"<[^>]+>", "", line)

        if line.startswith("|") and line.endswith("|"):
            cols = [c.strip() for c in line.strip("|").split("|")]
            if cols and all(set(c) <= {"-", ":"} for c in cols):
                continue
            if len(cols) >= 2:
                line = f"{cols[0]}：{' / '.join(cols[1:])}"
            else:
                line = cols[0]

        line = line.strip()
        if line:
            bullets.append(line)

    compact: list[str] = []
    seen = set()
    for bullet in bullets:
        if bullet in seen:
            continue
        seen.add(bullet)
        compact.append(bullet)

    return compact[:MAX_BULLETS_PER_SLIDE]


def apply_background(slide, prs: Presentation) -> None:
    fill = slide.background.fill
    fill.solid()
    fill.fore_color.rgb = BG_COLOR

    width = prs.slide_width
    height = prs.slide_height

    grid_gap = Inches(0.8)
    x = 0
    while x < width:
        line = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, x, 0, Pt(0.4), height)
        line.fill.solid()
        line.fill.fore_color.rgb = LINE_COLOR
        line.fill.fore_color.brightness = 0.28
        line.line.fill.background()
        x += grid_gap

    y = 0
    while y < height:
        line = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, y, width, Pt(0.4))
        line.fill.solid()
        line.fill.fore_color.rgb = LINE_COLOR
        line.fill.fore_color.brightness = 0.28
        line.line.fill.background()
        y += grid_gap


def set_text_style(paragraph, size: int, color: RGBColor, bold: bool = False, level: int = 0):
    paragraph.level = level
    if not paragraph.runs:
        paragraph.add_run()
    run = paragraph.runs[0]
    run.font.name = FONT_NAME
    run.font.size = Pt(size)
    run.font.color.rgb = color
    run.font.bold = bold


def add_footer(slide, prs: Presentation, page_no: int) -> None:
    box = slide.shapes.add_textbox(Inches(0.4), prs.slide_height - Inches(0.45), prs.slide_width - Inches(0.8), Inches(0.25))
    tf = box.text_frame
    tf.clear()
    p = tf.paragraphs[0]
    p.text = f"队伍：{DEFAULT_TEAM_NAME}    学校：{SCHOOL_NAME}    赛道：{TRACK_NAME}"
    set_text_style(p, 10, SUBTEXT_COLOR)
    p.alignment = PP_ALIGN.LEFT

    page_box = slide.shapes.add_textbox(prs.slide_width - Inches(0.9), prs.slide_height - Inches(0.45), Inches(0.5), Inches(0.25))
    p_tf = page_box.text_frame
    p_tf.clear()
    p2 = p_tf.paragraphs[0]
    p2.text = str(page_no)
    set_text_style(p2, 10, SUBTEXT_COLOR)
    p2.alignment = PP_ALIGN.RIGHT


def add_go_icon(slide) -> None:
    x, y, w, h = Inches(11.0), Inches(0.35), Inches(1.9), Inches(0.7)
    badge = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, x, y, w, h)
    badge.fill.solid()
    badge.fill.fore_color.rgb = RGBColor(0xE8, 0xF1, 0xFF)
    badge.line.color.rgb = PRIMARY_COLOR
    badge.line.width = Pt(1.5)

    tf = badge.text_frame
    tf.clear()
    p = tf.paragraphs[0]
    p.text = "GO"
    set_text_style(p, 16, PRIMARY_COLOR, bold=True)
    p.alignment = PP_ALIGN.CENTER


def add_cover_slide(prs: Presentation, title: str, subtitle: str) -> None:
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    apply_background(slide, prs)

    banner = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0), Inches(0), prs.slide_width, Inches(0.12))
    banner.fill.solid()
    banner.fill.fore_color.rgb = PRIMARY_COLOR
    banner.line.fill.background()

    title_box = slide.shapes.add_textbox(Inches(0.9), Inches(1.5), Inches(11.7), Inches(1.4))
    tf = title_box.text_frame
    tf.clear()
    p = tf.paragraphs[0]
    p.text = title
    set_text_style(p, 38, TEXT_COLOR, bold=True)

    sub_box = slide.shapes.add_textbox(Inches(0.9), Inches(3.0), Inches(11.0), Inches(1.4))
    stf = sub_box.text_frame
    stf.clear()
    p2 = stf.paragraphs[0]
    p2.text = subtitle
    set_text_style(p2, 20, SUBTEXT_COLOR)

    info = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.9), Inches(4.7), Inches(6.0), Inches(1.5))
    info.fill.solid()
    info.fill.fore_color.rgb = RGBColor(0xEE, 0xF3, 0xFF)
    info.line.color.rgb = PRIMARY_COLOR
    info.line.width = Pt(1)
    itf = info.text_frame
    itf.clear()

    p3 = itf.paragraphs[0]
    p3.text = f"队伍名称：{DEFAULT_TEAM_NAME}"
    set_text_style(p3, 16, TEXT_COLOR, bold=True)

    for text in [f"所属学校：{SCHOOL_NAME}", f"参赛赛道：{TRACK_NAME}"]:
        para = itf.add_paragraph()
        para.text = text
        set_text_style(para, 14, SUBTEXT_COLOR)

    add_go_icon(slide)


def should_add_go_icon(title: str, lines: list[str]) -> bool:
    text = f"{title} {' '.join(lines)}".lower()
    return any(k in text for k in GO_ICON_KEYWORDS)


def add_content_slide(prs: Presentation, section: Section, page_no: int) -> None:
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    apply_background(slide, prs)

    title_box = slide.shapes.add_textbox(Inches(0.7), Inches(0.45), Inches(10.8), Inches(0.9))
    tf = title_box.text_frame
    tf.clear()
    p = tf.paragraphs[0]
    p.text = section.title
    set_text_style(p, 28, TEXT_COLOR, bold=True)

    accent = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.7), Inches(1.35), Inches(2.2), Inches(0.06))
    accent.fill.solid()
    accent.fill.fore_color.rgb = PRIMARY_COLOR
    accent.line.fill.background()

    body = slide.shapes.add_textbox(Inches(0.85), Inches(1.65), Inches(11.0), Inches(5.2))
    btf = body.text_frame
    btf.word_wrap = True
    btf.clear()

    for i, line in enumerate(section.lines[:MAX_BULLETS_PER_SLIDE]):
        para = btf.paragraphs[0] if i == 0 else btf.add_paragraph()
        para.text = line
        set_text_style(para, 16 if i == 0 else 15, TEXT_COLOR if i < 2 else SUBTEXT_COLOR, level=0)
        para.space_after = Pt(8)

    if should_add_go_icon(section.title, section.lines):
        add_go_icon(slide)

    add_footer(slide, prs, page_no)


def extract_cover_text(sections: list[Section]) -> tuple[str, str]:
    if not sections:
        return "比赛项目汇报", "基于仓库 Markdown 自动生成"
    first = sections[0]
    title = "比赛项目汇报"
    subtitle = "灰白科技数码风演示文稿"

    for line in first.lines:
        if "项目名称" in line and "：" in line:
            title = line.split("：", 1)[1].strip() or title
        if "一句话" in line and "：" in line:
            subtitle = line.split("：", 1)[1].strip() or subtitle
    return title, subtitle


def build_ppt(markdown_paths: list[Path], output_path: Path) -> None:
    all_sections: list[Section] = []
    for md in markdown_paths:
        all_sections.extend(parse_markdown_sections(md))

    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)

    cover_title, cover_subtitle = extract_cover_text(all_sections)
    add_cover_slide(prs, cover_title, cover_subtitle)

    page_no = 1
    for section in all_sections:
        add_content_slide(prs, section, page_no)
        page_no += 1

    output_path.parent.mkdir(parents=True, exist_ok=True)
    prs.save(output_path)


def resolve_markdowns(patterns: list[str]) -> list[Path]:
    result: list[Path] = []
    for pat in patterns:
        for path in glob.glob(pat):
            p = Path(path)
            if p.suffix.lower() == ".md" and p.is_file():
                if p.name.lower() == "readme.md":
                    continue
                result.append(p)
    result = sorted(set(result))
    if not result:
        raise FileNotFoundError(
            f"No markdown files found matching patterns: {patterns}. Please provide valid --inputs patterns."
        )
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate competition PPTX from Markdown content.")
    parser.add_argument(
        "--inputs",
        nargs="+",
        default=["*.md", "docs/**/*.md"],
        help="Markdown glob patterns (default: *.md docs/**/*.md)",
    )
    parser.add_argument("--output", default="slides/competition.pptx", help="Output PPTX path")
    args = parser.parse_args()

    md_files = resolve_markdowns(args.inputs)
    output = Path(args.output)
    build_ppt(md_files, output)

    print("Markdown sources:")
    for f in md_files:
        print(f"- {f}")
    print(f"Output PPTX: {output}")


if __name__ == "__main__":
    main()
