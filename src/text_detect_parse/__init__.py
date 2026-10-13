from importlib.metadata import PackageNotFoundError, version

from .cli import main
from .models import Block, Document, ImageBlock, TableBlock, TextBlock
from .openai import to_openai_string
from .parser import SUPPORTED_EXTENSIONS, parse

try:
    __version__ = version("text-detect-parse")
except PackageNotFoundError:  # not installed (e.g. running from a bare checkout)
    __version__ = "0.0.0+unknown"

__all__ = [
    "SUPPORTED_EXTENSIONS",
    "Block",
    "Document",
    "ImageBlock",
    "TableBlock",
    "TextBlock",
    "__version__",
    "main",
    "parse",
    "to_openai_string",
]
