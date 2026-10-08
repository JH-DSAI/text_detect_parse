from pathlib import Path

import pytest
from conftest import make_pixmap

from text_detect_parse import Document, ImageBlock, TableBlock, TextBlock, parse, to_openai_string


def test_openai_string(docx_file: Path) -> None:
    s = parse(docx_file).to_openai_string()
    assert isinstance(s, str) and s.endswith("\n")
    assert "| h1 | h2 |" in s
    assert "![image](data:image/png;base64," in s
    assert s.index("Body text") < s.index("| h1 |") < s.index("data:image") < s.index("After")


def test_openai_string_no_images(docx_file: Path) -> None:
    assert "data:image" not in parse(docx_file, parse_images=False).to_openai_string()


def test_openai_string_no_tables(docx_file: Path) -> None:
    assert "| h1 |" not in parse(docx_file, parse_tables=False).to_openai_string()


def test_function_matches_method(docx_file: Path) -> None:
    doc = parse(docx_file)
    assert to_openai_string(doc) == doc.to_openai_string()


def test_jpg_mime(png_bytes: bytes) -> None:
    doc = Document(Path("d"), [ImageBlock(png_bytes, ext="JPG")])
    assert "data:image/jpeg;base64," in doc.to_openai_string()


def test_unsupported_format_reencoded_to_png() -> None:
    doc = Document(Path("d"), [ImageBlock(make_pixmap("pnm"), ext="pnm")])
    assert "data:image/png;base64," in doc.to_openai_string()


def test_undecodable_image_skipped_with_warning() -> None:
    doc = Document(Path("d"), [TextBlock("a"), ImageBlock(b"garbage", ext="emf"), TextBlock("b")])
    with pytest.warns(UserWarning, match="unsupported format"):
        out = doc.to_openai_string()
    assert out == "a\n\nb\n"


def test_empty_blocks_skipped() -> None:
    doc = Document(Path("d"), [TextBlock("a"), TableBlock([]), TextBlock("b")])
    assert doc.to_openai_string() == "a\n\nb\n"
