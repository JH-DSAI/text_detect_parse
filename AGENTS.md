# AGENTS.md

Guide for developers and coding agents working on `text-detect-parse`.

## What this project is

A document parser for LLM pipelines. It reads `.docx`, `.pdf` and `.txt` files into an ordered list of
text, table and image blocks, with a library API and a CLI. Tables and images can each be switched
off; `False` means that content is skipped entirely (including table text, which must not leak into
text blocks). A parsed `Document` can be rendered to markdown, JSON, plain text, or a single string
for an OpenAI-compatible endpoint (images inlined as base64 data URLs).

## Tooling: use `uv` for everything

Python and the build are managed by `uv`. Do not use `pip`, `python -m venv`, or bare `python`/`pytest`.

```bash
uv sync                       # create .venv and install deps (Python pinned in .python-version, >=3.12)
uv run pytest                 # tests + coverage (fails under 90%)
uv run ruff check .           # lint   (add --fix to autofix)
uv run ruff format .          # format (CI runs `ruff format --check .`)
uv run mypy                   # strict type check of src/
uv run text-detect-parse FILE # run the CLI
uv add <pkg>                  # runtime dependency
uv add --dev <pkg>            # dev dependency (note: --dev applies to ALL packages in the command)
uv build                      # sdist + wheel into dist/ (backend: uv_build)
```

Before finishing any change, run the full gate that CI runs:

```bash
uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run pytest
```

Commit `uv.lock`. CI uses `uv sync --locked` and fails if the lockfile is stale.

## Layout

```
src/text_detect_parse/
  __init__.py   public API re-exports (parse, Document, blocks, to_openai_string, main)
  models.py     TextBlock, TableBlock, ImageBlock, Document; markdown/dict rendering; save_images
  parser.py     parse() + one private parser per format (_parse_txt/_docx/_pdf), dispatch via _PARSERS
  openai.py     to_openai_string(): markdown with images inlined as data URLs
  cli.py        argparse CLI; main(argv) -> int
tests/
  conftest.py   fixtures that build tiny docx/pdf/txt files in code (no binary fixtures in the repo)
  test_*.py     one file per module
.github/workflows/
  ci.yml        lint+format+types, tests (py3.12/3.13), build; also callable via workflow_call
  release.yml   on tag v*: CI -> build -> PyPI (trusted publishing) -> GitHub Release
```

Console script: `text-detect-parse = text_detect_parse.cli:main` (returns an int exit code).

## Design notes and gotchas

- **Block model.** `Block = TextBlock | TableBlock | ImageBlock`; each has a `type` literal, optional
  `page`, `to_markdown()` and `to_dict()`. Order of `Document.blocks` is reading order.
- **Adding a format:** write `_parse_xxx(path, parse_images, parse_tables) -> list[Block]` in
  `parser.py`, register the extension in `_PARSERS` and `SUPPORTED_EXTENSIONS`, add a fixture in
  `conftest.py` and tests for both flags.
- **Imports of docx/pymupdf are lazy** (inside the `_parse_*` functions) so importing the package
  stays cheap. Type-only imports live under `TYPE_CHECKING`.
- **PDF tables:** `page.find_tables()` runs even when `parse_tables=False`, because the table
  regions are needed to exclude their text. Text blocks overlapping a table bbox by >50% are dropped.
  Blocks are sorted by `(y, x)` per page. Detection works best on ruled tables; there is no OCR.
- **DOCX:** body children are walked in order, so tables and images land in the right position.
  Heading levels come from style names (`Heading N`, `Title` -> 1; capped at 6). Merged cells are
  de-duplicated by underlying `_tc`. Images inside table cells are not extracted.
- **TXT:** paragraphs split on blank lines; UTF-8 (BOM tolerated) with latin-1 fallback.
- **OpenAI string:** images in formats other than png/jpeg/gif/webp are re-encoded to PNG via
  pymupdf, or skipped with a `UserWarning`. The result is plain text to the model, not a vision
  input. It is token-heavy; use `parse_images=False` for text-only models.
- **CLI errors:** missing/unsupported/corrupt input prints `error: ...` to stderr and returns 1.
  `--image-dir` is ignored when images are disabled.

## Conventions

- Python >=3.12; use modern syntax (`X | Y`, `list[str]`, `from __future__ import annotations`).
- Ruff: line length 100; rules `E, F, I, UP, B, SIM, C4, RUF`. Mypy is `strict` on `src/` (tests are
  not type-checked, but keep them annotated). `pymupdf`/`docx` are untyped, so the `parser` and
  `openai` modules relax `disallow_untyped_calls` in `pyproject.toml`.
- Match the surrounding style: short docstrings, comments only for non-obvious "why".
- Tests build their own documents in code; do not commit binary fixtures. Every new behavior needs a
  test, including both values of `parse_images`/`parse_tables` where relevant. Keep coverage >= 90%
  (currently ~99%).
- Warnings: pass `stacklevel` to `warnings.warn`; give `zip` an explicit `strict=`.

## CI and releases

- CI runs on pushes to `main` and PRs. For it to *block* merges, the checks `Lint, format & types`,
  `Tests (py3.12)`, `Tests (py3.13)` and `Build` must be marked required in branch protection.
- Release: bump `version` in `pyproject.toml`, commit, then `git tag vX.Y.Z && git push origin vX.Y.Z`.
  The workflow verifies the tag matches the version, builds, smoke-tests the wheel, publishes to PyPI
  via trusted publishing (environment `pypi`, no tokens), then creates a GitHub Release.
- One-time PyPI setup (trusted publisher: workflow `release.yml`, environment `pypi`) is described
  in `README.md`.

## Git

Work on a branch off `main`; do not commit directly to `main`. Do not commit `dist/`, `.venv/`, or
generated files (they are gitignored).
