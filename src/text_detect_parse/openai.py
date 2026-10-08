"""Convert a parsed Document into a single string for an OpenAI-compatible endpoint."""

from __future__ import annotations

import base64
import warnings

from .models import Document, ImageBlock

# Image formats accepted by OpenAI-compatible vision endpoints.
_MIME = {
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "gif": "image/gif",
    "webp": "image/webp",
}


def _image_url(img: ImageBlock) -> str | None:
    ext, data = img.ext.lower(), img.data
    if ext not in _MIME:  # e.g. bmp/tiff/jpx/emf: try re-encoding as PNG
        try:
            import pymupdf

            data, ext = pymupdf.Pixmap(data).tobytes("png"), "png"
        except Exception:
            warnings.warn(f"Skipping image with unsupported format {img.ext!r}", stacklevel=2)
            return None
    return f"data:{_MIME[ext]};base64,{base64.b64encode(data).decode('ascii')}"


def to_openai_string(doc: Document) -> str:
    """Render the document as one markdown string to place in a message.

    Text and tables are markdown; each image is inlined in place as a markdown
    image whose URL is a base64 data URL. Images in formats the endpoint is
    unlikely to accept are re-encoded to PNG, or skipped with a warning.
    """
    parts: list[str] = []
    for block in doc.blocks:
        if isinstance(block, ImageBlock):
            if (url := _image_url(block)) is None:
                continue
            parts.append(f"![image]({url})")
        elif md := block.to_markdown():
            parts.append(md)
    return "\n\n".join(parts) + "\n"
