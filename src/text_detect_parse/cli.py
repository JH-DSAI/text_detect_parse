"""Command line interface."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .models import Document
from .parser import SUPPORTED_EXTENSIONS, parse


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="text-detect-parse",
        description=(
            f"Parse {', '.join(SUPPORTED_EXTENSIONS)} documents into text, tables and images."
        ),
    )
    p.add_argument("file", type=Path, help="document to parse")
    p.add_argument(
        "-f",
        "--format",
        choices=["markdown", "json", "text", "openai"],
        default="markdown",
        help=(
            "output format; text keeps text blocks only (no tables or images); openai emits "
            "one string with images inlined as data URLs (default: markdown)"
        ),
    )
    p.add_argument("-o", "--output", type=Path, help="write output here instead of stdout")
    p.add_argument(
        "--tables",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="parse tables; --no-tables skips them (default: enabled)",
    )
    p.add_argument(
        "--images",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="parse images; --no-images skips them (default: enabled)",
    )
    p.add_argument(
        "--image-dir", type=Path, help="save extracted images here and link them in the output"
    )
    p.add_argument(
        "--embed-images", action="store_true", help="include base64 image data in json output"
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    try:
        doc = parse(args.file, parse_images=args.images, parse_tables=args.tables)
    except (FileNotFoundError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    except Exception as e:  # corrupt / unreadable documents
        print(f"error: failed to parse {args.file}: {e}", file=sys.stderr)
        return 1

    try:
        if args.image_dir and args.images:
            doc.save_images(args.image_dir)
        return _emit(doc, args)
    except (OSError, UnicodeEncodeError) as e:  # e.g. non-UTF-8 stdout
        print(f"error: {e}", file=sys.stderr)
        return 1


def _emit(doc: Document, args: argparse.Namespace) -> int:
    if args.format == "json":
        out = json.dumps(doc.to_dict(include_image_data=args.embed_images), indent=2)
    elif args.format == "openai":
        out = doc.to_openai_string()
    elif args.format == "text":
        out = doc.text
    else:
        out = doc.to_markdown()

    if args.output:
        args.output.write_text(out + "\n" if not out.endswith("\n") else out, encoding="utf-8")
    else:
        print(out, end="" if out.endswith("\n") else "\n")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
