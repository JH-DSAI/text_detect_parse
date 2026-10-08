from pathlib import Path

from text_detect_parse import Document, ImageBlock, TableBlock, TextBlock


def test_text_block_markdown() -> None:
    assert TextBlock("hi").to_markdown() == "hi"
    assert TextBlock("Head", level=2).to_markdown() == "## Head"


def test_text_block_to_dict() -> None:
    assert TextBlock("hi", page=3).to_dict() == {
        "type": "text",
        "text": "hi",
        "level": 0,
        "page": 3,
    }


def test_table_markdown() -> None:
    md = TableBlock([["a", "b"], ["1", "2"]]).to_markdown()
    assert md == "| a | b |\n| --- | --- |\n| 1 | 2 |"


def test_table_markdown_pads_ragged_rows() -> None:
    md = TableBlock([["a", "b", "c"], ["1"]]).to_markdown()
    assert md.splitlines()[-1] == "| 1 |  |  |"


def test_table_markdown_escapes_pipes_and_newlines() -> None:
    md = TableBlock([["a|b", "x\ny"], ["1", "2"]]).to_markdown()
    assert md.splitlines()[0] == "| a\\|b | x y |"


def test_empty_table_markdown() -> None:
    assert TableBlock([]).to_markdown() == ""


def test_table_to_dict() -> None:
    assert TableBlock([["a"]], page=1).to_dict() == {"type": "table", "rows": [["a"]], "page": 1}


def test_image_markdown_and_dict(png_bytes: bytes) -> None:
    img = ImageBlock(png_bytes)
    assert img.to_markdown() == "![image]()"
    d = img.to_dict()
    assert d["size_bytes"] == len(png_bytes) and "data_base64" not in d
    assert img.to_dict(include_data=True)["data_base64"]
    img.path = Path("x/y.png")
    assert img.to_markdown() == "![image](x/y.png)"
    assert img.to_dict()["path"] == "x/y.png"


def test_document_accessors(png_bytes: bytes) -> None:
    doc = Document(
        Path("d.txt"),
        [TextBlock("a"), TableBlock([["x"]]), ImageBlock(png_bytes), TextBlock("b")],
    )
    assert doc.text == "a\n\nb"
    assert len(doc.tables) == 1 and len(doc.images) == 1
    assert doc.to_dict()["source"] == "d.txt"
    assert [b["type"] for b in doc.to_dict()["blocks"]] == ["text", "table", "image", "text"]


def test_document_markdown_skips_empty_blocks() -> None:
    doc = Document(Path("d"), [TextBlock("a"), TableBlock([]), TextBlock("b")])
    assert doc.to_markdown() == "a\n\nb\n"


def test_save_images(tmp_path: Path, png_bytes: bytes) -> None:
    doc = Document(Path("report.pdf"), [ImageBlock(png_bytes), ImageBlock(png_bytes, ext="jpg")])
    doc.save_images(tmp_path / "out" / "imgs")
    names = sorted(p.name for p in (tmp_path / "out" / "imgs").iterdir())
    assert names == ["report_image_001.png", "report_image_002.jpg"]
    assert doc.images[0].path is not None and doc.images[0].path.read_bytes() == png_bytes
