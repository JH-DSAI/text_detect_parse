"""Document parsing for txt, pdf and docx files."""

from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

from .models import Block, Document, ImageBlock, TableBlock, TextBlock

if TYPE_CHECKING:
    import pymupdf
    from docx.table import _Row

SUPPORTED_EXTENSIONS = (".txt", ".pdf", ".docx")


def parse(
    path: str | Path,
    *,
    parse_images: bool = True,
    parse_tables: bool = True,
) -> Document:
    """Parse a document into an ordered list of text, table and image blocks.

    When `parse_tables` / `parse_images` is False that content is skipped
    entirely (table text is not leaked into the text blocks either).
    Plain-text files contain neither, so the flags have no effect on them.
    """
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(path)
    try:
        parser = _PARSERS[path.suffix.lower()]
    except KeyError:
        raise ValueError(
            f"Unsupported file type {path.suffix!r}; supported: {', '.join(SUPPORTED_EXTENSIONS)}"
        ) from None
    return Document(source=path, blocks=parser(path, parse_images, parse_tables))


def _parse_txt(path: Path, parse_images: bool, parse_tables: bool) -> list[Block]:
    try:
        content = path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError:
        content = path.read_text(encoding="latin-1")
    paragraphs = re.split(r"\n\s*\n", content.replace("\r\n", "\n"))
    return [TextBlock(p.strip()) for p in paragraphs if p.strip()]


def _parse_docx(path: Path, parse_images: bool, parse_tables: bool) -> list[Block]:
    import docx
    from docx.table import Table
    from docx.text.hyperlink import Hyperlink
    from docx.text.paragraph import Paragraph

    doc = docx.Document(str(path))
    blocks: list[Block] = []
    blip_embed = "{http://schemas.openxmlformats.org/drawingml/2006/main}blip"
    embed_attr = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed"

    for child in doc.element.body.iterchildren():
        tag = child.tag.rsplit("}", 1)[-1]
        if tag == "p":
            para = Paragraph(child, doc)
            style = para.style.name if para.style is not None else ""
            m = re.fullmatch(r"Heading (\d)", style or "")
            level = min(int(m.group(1)), 6) if m else (1 if style == "Title" else 0)
            pending: list[str] = []

            def flush_text(level: int = level, pending: list[str] = pending) -> None:
                text = "".join(pending).strip()
                pending.clear()
                if text:
                    blocks.append(TextBlock(text, level=level))

            # Walk runs in order so text after an inline image stays after it.
            for item in para.iter_inner_content():
                for run in item.runs if isinstance(item, Hyperlink) else [item]:
                    pending.append(run.text)
                    if not parse_images:
                        continue
                    for blip in run._r.iter(blip_embed):
                        part = doc.part.related_parts.get(blip.get(embed_attr))
                        if part is not None:
                            flush_text()
                            ext = Path(part.partname).suffix.lstrip(".") or "png"
                            blocks.append(ImageBlock(part.blob, ext=ext))
            flush_text()
        elif tag == "tbl" and parse_tables:
            table = Table(child, doc)
            rows = [_docx_row(row) for row in table.rows]
            blocks.append(TableBlock(rows))
    return blocks


def _docx_row(row: _Row) -> list[str]:
    # Merged cells repeat the same underlying cell; keep each once.
    seen: set[int] = set()
    cells = []
    for cell in row.cells:
        if id(cell._tc) not in seen:
            seen.add(id(cell._tc))
            cells.append(cell.text.strip())
    return cells


def _parse_pdf(path: Path, parse_images: bool, parse_tables: bool) -> list[Block]:
    import pymupdf

    blocks: list[Block] = []
    with pymupdf.open(path) as pdf:
        for page_no, page in enumerate(pdf, 1):
            # (y, x, block) so page content comes out in reading order.
            found: list[tuple[float, float, Block]] = []

            # Always locate tables so their text is excluded from the text
            # blocks, even when table parsing is disabled.
            tables = page.find_tables().tables
            table_boxes = [pymupdf.Rect(t.bbox) for t in tables]
            if parse_tables:
                for t, box in zip(tables, table_boxes, strict=True):
                    rows = [[c or "" for c in r] for r in t.extract()]
                    found.append((box.y0, box.x0, TableBlock(rows, page=page_no)))

            for b in page.get_text("dict")["blocks"]:
                box = pymupdf.Rect(b["bbox"])
                if b["type"] == 1:
                    if parse_images:
                        found.append(
                            (
                                box.y0,
                                box.x0,
                                ImageBlock(b["image"], ext=b.get("ext", "png"), page=page_no),
                            )
                        )
                elif not any(_mostly_inside(box, t) for t in table_boxes):
                    lines = ("".join(s["text"] for s in ln["spans"]) for ln in b["lines"])
                    text = "\n".join(ln for ln in lines if ln.strip()).strip()
                    if text:
                        found.append((box.y0, box.x0, TextBlock(text, page=page_no)))

            blocks += [blk for _, _, blk in sorted(found, key=lambda f: (f[0], f[1]))]
    return blocks


def _mostly_inside(box: pymupdf.Rect, container: pymupdf.Rect) -> bool:
    area = box.get_area()
    return bool(area > 0 and (box & container).get_area() / area > 0.5)


_PARSERS: dict[str, Callable[[Path, bool, bool], list[Block]]] = {
    ".txt": _parse_txt,
    ".docx": _parse_docx,
    ".pdf": _parse_pdf,
}
