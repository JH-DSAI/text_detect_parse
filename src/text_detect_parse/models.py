"""Format-independent document model."""

from __future__ import annotations

import base64
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal
from urllib.parse import quote


@dataclass
class TextBlock:
    text: str
    level: int = 0  # heading level (1-6); 0 means body text
    page: int | None = None

    type: Literal["text"] = "text"

    def to_markdown(self, **_: Any) -> str:
        if not self.level:
            return self.text
        return f"{'#' * self.level} {' '.join(self.text.split())}"  # headings are one line

    def to_dict(self, **_: Any) -> dict[str, Any]:
        return {"type": self.type, "text": self.text, "level": self.level, "page": self.page}


@dataclass
class TableBlock:
    rows: list[list[str]]
    page: int | None = None

    type: Literal["table"] = "table"

    def to_markdown(self, **_: Any) -> str:
        width = max((len(r) for r in self.rows), default=0)
        if not width:
            return ""
        rows = [[_cell(c) for c in r] + [""] * (width - len(r)) for r in self.rows]
        header, *body = rows
        lines = ["| " + " | ".join(header) + " |", "|" + " --- |" * width]
        lines += ["| " + " | ".join(r) + " |" for r in body]
        return "\n".join(lines)

    def to_dict(self, **_: Any) -> dict[str, Any]:
        return {"type": self.type, "rows": self.rows, "page": self.page}


@dataclass
class ImageBlock:
    data: bytes
    ext: str = "png"
    page: int | None = None
    path: Path | None = None  # set when images are saved to disk

    type: Literal["image"] = "image"

    def to_markdown(self, **_: Any) -> str:
        if self.path:
            return f"![image]({quote(self.path.as_posix())})"
        return f"[image: page {self.page}]" if self.page else "[image]"

    def to_dict(self, include_data: bool = False, **_: Any) -> dict[str, Any]:
        d: dict[str, Any] = {
            "type": self.type,
            "ext": self.ext,
            "page": self.page,
            "path": str(self.path) if self.path else None,
            "size_bytes": len(self.data),
        }
        if include_data:
            d["data_base64"] = base64.b64encode(self.data).decode("ascii")
        return d


Block = TextBlock | TableBlock | ImageBlock


@dataclass
class Document:
    source: Path
    blocks: list[Block] = field(default_factory=list)

    @property
    def tables(self) -> list[TableBlock]:
        return [b for b in self.blocks if isinstance(b, TableBlock)]

    @property
    def images(self) -> list[ImageBlock]:
        return [b for b in self.blocks if isinstance(b, ImageBlock)]

    @property
    def text(self) -> str:
        """Text blocks only, joined by blank lines; tables and images are omitted."""
        return "\n\n".join(b.text for b in self.blocks if isinstance(b, TextBlock))

    def to_markdown(self) -> str:
        return "\n\n".join(m for b in self.blocks if (m := b.to_markdown())) + "\n"

    def to_dict(self, include_image_data: bool = False) -> dict[str, Any]:
        return {
            "source": str(self.source),
            "blocks": [b.to_dict(include_data=include_image_data) for b in self.blocks],
        }

    def to_openai_string(self) -> str:
        """One markdown string (images inlined as data URLs) for an OpenAI-compatible endpoint."""
        from .openai import to_openai_string

        return to_openai_string(self)

    def save_images(self, directory: str | Path) -> None:
        """Write every image to `directory` and record the path on the block."""
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        for i, img in enumerate(self.images, 1):
            img.path = directory / f"{self.source.stem}_image_{i:03d}.{img.ext}"
            img.path.write_bytes(img.data)


def _cell(value: str) -> str:
    return " ".join(value.split()).replace("\\", "\\\\").replace("|", "\\|")
