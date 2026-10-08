import io
from pathlib import Path

import docx
import pymupdf
import pytest
from conftest import PNG, draw_table

from text_detect_parse import Document, ImageBlock, TableBlock, TextBlock, parse


def kinds(doc: Document) -> list[str]:
    return [b.type for b in doc.blocks]


def texts(doc: Document) -> list[TextBlock]:
    return [b for b in doc.blocks if isinstance(b, TextBlock)]


# ---- general ---------------------------------------------------------------


def test_unsupported_extension(tmp_path: Path) -> None:
    (tmp_path / "x.csv").write_text("a")
    with pytest.raises(ValueError, match="Unsupported"):
        parse(tmp_path / "x.csv")


def test_missing_file(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        parse(tmp_path / "nope.txt")


def test_accepts_str_path_and_uppercase_extension(tmp_path: Path) -> None:
    p = tmp_path / "A.TXT"
    p.write_text("hello")
    assert parse(str(p)).text == "hello"


# ---- txt -------------------------------------------------------------------


def test_txt_paragraphs(txt_file: Path) -> None:
    doc = parse(txt_file, parse_images=False, parse_tables=False)
    assert [b.text for b in texts(doc)] == ["First para\nstill first", "Second para"]


def test_txt_flags_are_noops(txt_file: Path) -> None:
    assert parse(txt_file).blocks == parse(txt_file, parse_images=False, parse_tables=False).blocks


def test_txt_empty(tmp_path: Path) -> None:
    p = tmp_path / "e.txt"
    p.write_text("  \n\n  \n")
    assert parse(p).blocks == []


def test_txt_crlf_and_bom(tmp_path: Path) -> None:
    p = tmp_path / "w.txt"
    p.write_bytes(b"\xef\xbb\xbfone\r\n\r\ntwo\r\n")
    assert [b.text for b in texts(parse(p))] == ["one", "two"]


def test_txt_latin1_fallback(tmp_path: Path) -> None:
    p = tmp_path / "l.txt"
    p.write_bytes("caf\xe9".encode("latin-1"))
    assert parse(p).text == "café"


# ---- docx ------------------------------------------------------------------


def test_docx_all(docx_file: Path) -> None:
    doc = parse(docx_file)
    assert kinds(doc) == ["text", "text", "table", "image", "text"]
    assert texts(doc)[0].level == 1
    assert doc.tables[0].rows == [["h1", "h2"], ["c1", "c2"]]
    assert doc.images[0].data == PNG
    assert doc.images[0].ext == "png"


def test_docx_flags(docx_file: Path) -> None:
    assert "table" not in kinds(parse(docx_file, parse_tables=False))
    assert "image" not in kinds(parse(docx_file, parse_images=False))
    assert kinds(parse(docx_file, parse_images=False, parse_tables=False)) == ["text"] * 3


def test_docx_table_text_not_leaked_when_disabled(docx_file: Path) -> None:
    assert "c1" not in parse(docx_file, parse_tables=False).text


def test_docx_heading_levels_and_title(tmp_path: Path) -> None:
    d = docx.Document()
    d.add_heading("T", level=0)
    d.add_heading("H2", level=2)
    d.add_heading("H9", level=9)
    d.add_paragraph("body")
    p = tmp_path / "h.docx"
    d.save(str(p))
    assert [(b.text, b.level) for b in texts(parse(p))] == [
        ("T", 1),
        ("H2", 2),
        ("H9", 6),
        ("body", 0),
    ]


def test_docx_blank_paragraphs_skipped(tmp_path: Path) -> None:
    d = docx.Document()
    d.add_paragraph("")
    d.add_paragraph("   ")
    d.add_paragraph("x")
    p = tmp_path / "b.docx"
    d.save(str(p))
    assert [b.text for b in texts(parse(p))] == ["x"]


def test_docx_merged_cells_not_duplicated(tmp_path: Path) -> None:
    d = docx.Document()
    t = d.add_table(rows=2, cols=2)
    t.cell(0, 0).merge(t.cell(0, 1)).text = "merged"
    t.cell(1, 0).text = "a"
    t.cell(1, 1).text = "b"
    p = tmp_path / "m.docx"
    d.save(str(p))
    assert parse(p).tables[0].rows == [["merged"], ["a", "b"]]


def test_docx_multiple_images_in_order(tmp_path: Path) -> None:
    d = docx.Document()
    d.add_paragraph("before")
    d.add_picture(io.BytesIO(PNG))
    d.add_paragraph("middle")
    d.add_picture(io.BytesIO(PNG))
    p = tmp_path / "i.docx"
    d.save(str(p))
    assert kinds(parse(p)) == ["text", "image", "text", "image"]


def test_docx_inline_image_splits_paragraph_text(tmp_path: Path) -> None:
    d = docx.Document()
    para = d.add_paragraph("before ")
    para.add_run().add_picture(io.BytesIO(PNG))
    para.add_run(" after")
    p = tmp_path / "inline.docx"
    d.save(str(p))
    doc = parse(p)
    assert kinds(doc) == ["text", "image", "text"]
    assert [b.text for b in texts(doc)] == ["before", "after"]
    assert [b.text for b in texts(parse(p, parse_images=False))] == ["before  after"]


def test_docx_corrupt(tmp_path: Path) -> None:
    p = tmp_path / "bad.docx"
    p.write_bytes(b"not a zip")
    with pytest.raises(Exception, match=r".+"):
        parse(p)


# ---- pdf -------------------------------------------------------------------


def test_pdf_all(pdf_file: Path) -> None:
    doc = parse(pdf_file)
    assert kinds(doc) == ["text", "table", "image", "text"]
    assert doc.tables[0].rows == [["r0c0", "r0c1"], ["r1c0", "r1c1"], ["r2c0", "r2c1"]]
    assert doc.tables[0].page == 1
    assert isinstance(doc.blocks[2], ImageBlock) and doc.blocks[2].data


def test_pdf_flags_skip_content(pdf_file: Path) -> None:
    doc = parse(pdf_file, parse_tables=False, parse_images=False)
    assert kinds(doc) == ["text", "text"]
    assert "r0c0" not in doc.text


def test_pdf_tables_only_and_images_only(pdf_file: Path) -> None:
    assert kinds(parse(pdf_file, parse_images=False)) == ["text", "table", "text"]
    assert kinds(parse(pdf_file, parse_tables=False)) == ["text", "image", "text"]


def test_pdf_multipage_numbers_and_order(tmp_path: Path) -> None:
    pdf = pymupdf.open()
    pdf.new_page().insert_text((72, 72), "page one")
    p2 = pdf.new_page()
    p2.insert_text((72, 72), "page two")
    draw_table(p2, 72, 120, rows=2)
    path = tmp_path / "m.pdf"
    pdf.save(path)
    doc = parse(path)
    assert [(b.type, b.page) for b in doc.blocks] == [("text", 1), ("text", 2), ("table", 2)]
    assert all(isinstance(b, TableBlock) for b in doc.tables)


def test_pdf_empty_page(tmp_path: Path) -> None:
    pdf = pymupdf.open()
    pdf.new_page()
    path = tmp_path / "e.pdf"
    pdf.save(path)
    assert parse(path).blocks == []


def test_pdf_corrupt(tmp_path: Path) -> None:
    p = tmp_path / "bad.pdf"
    p.write_bytes(b"not a pdf")
    with pytest.raises(Exception, match=r".+"):
        parse(p)
