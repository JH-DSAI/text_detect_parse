import json
from pathlib import Path

import pytest

from text_detect_parse.cli import main


def run(capsys: pytest.CaptureFixture[str], *args: str) -> tuple[int, str, str]:
    code = main(list(args))
    out = capsys.readouterr()
    return code, out.out, out.err


def test_markdown_default(docx_file: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code, out, _ = run(capsys, str(docx_file))
    assert code == 0
    assert "# Title here" in out and "| h1 | h2 |" in out and "[image]" in out


def test_no_flags_json(docx_file: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code, out, _ = run(capsys, str(docx_file), "--no-tables", "--no-images", "-f", "json")
    assert code == 0
    assert {b["type"] for b in json.loads(out)["blocks"]} == {"text"}


def test_json_embed_images(docx_file: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _, plain, _ = run(capsys, str(docx_file), "-f", "json")
    _, embedded, _ = run(capsys, str(docx_file), "-f", "json", "--embed-images")
    assert "data_base64" not in plain and "data_base64" in embedded


def test_text_format(docx_file: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _, out, _ = run(capsys, str(docx_file), "-f", "text")
    assert out.strip() == "Title here\n\nBody text\n\nAfter"


def test_openai_format(docx_file: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _, out, _ = run(capsys, str(docx_file), "-f", "openai")
    assert "data:image/png;base64," in out


def test_image_dir(docx_file: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    img_dir = tmp_path / "imgs"
    _, out, _ = run(capsys, str(docx_file), "--image-dir", str(img_dir))
    assert len(list(img_dir.iterdir())) == 1
    assert str(img_dir) in out


def test_image_dir_ignored_when_images_disabled(
    docx_file: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    img_dir = tmp_path / "imgs"
    run(capsys, str(docx_file), "--no-images", "--image-dir", str(img_dir))
    assert not img_dir.exists()


def test_output_file(docx_file: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    dest = tmp_path / "out.md"
    code, out, _ = run(capsys, str(docx_file), "-o", str(dest))
    assert code == 0 and out == ""
    assert "Body text" in dest.read_text() and dest.read_text().endswith("\n")


def test_output_file_json_gets_trailing_newline(
    txt_file: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    dest = tmp_path / "o.json"
    run(capsys, str(txt_file), "-f", "json", "-o", str(dest))
    assert dest.read_text().endswith("\n")
    json.loads(dest.read_text())


def test_txt_stdout(txt_file: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code, out, _ = run(capsys, str(txt_file))
    assert code == 0 and "Second para" in out


def test_missing_file_errors(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code, out, err = run(capsys, str(tmp_path / "missing.pdf"))
    assert code == 1 and out == "" and err.startswith("error:")


def test_unsupported_type_errors(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    p = tmp_path / "x.csv"
    p.write_text("a")
    code, _, err = run(capsys, str(p))
    assert code == 1 and "Unsupported" in err


def test_corrupt_file_errors(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    p = tmp_path / "bad.pdf"
    p.write_bytes(b"nope")
    code, _, err = run(capsys, str(p))
    assert code == 1 and "failed to parse" in err


def test_invalid_format_exits(docx_file: Path) -> None:
    with pytest.raises(SystemExit) as exc:
        main([str(docx_file), "-f", "xml"])
    assert exc.value.code == 2


def test_unwritable_output_errors(
    docx_file: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code, _, err = run(capsys, str(docx_file), "-o", str(tmp_path / "missing" / "out.md"))
    assert code == 1 and err.startswith("error:")


def test_unwritable_image_dir_errors(
    docx_file: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    blocker = tmp_path / "file"
    blocker.write_text("x")
    code, _, err = run(capsys, str(docx_file), "--image-dir", str(blocker / "sub"))
    assert code == 1 and err.startswith("error:")
