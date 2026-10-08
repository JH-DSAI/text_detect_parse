# text-detect-parse

Parse `.docx`, `.pdf` and `.txt` documents into ordered text, table and image blocks, ready for LLM pipelines.

## CLI

```bash
uv run text-detect-parse report.pdf                       # markdown to stdout
uv run text-detect-parse report.docx --no-images          # skip images
uv run text-detect-parse report.pdf --no-tables -f json   # skip tables, JSON output
uv run text-detect-parse report.pdf --image-dir imgs/ -o report.md
```

Options: `-f {markdown,json,text}`, `-o FILE`, `--[no-]tables`, `--[no-]images`, `--image-dir DIR`, `--embed-images` (base64 in JSON).

## Library

```python
from text_detect_parse import parse

doc = parse("report.pdf", parse_images=False, parse_tables=True)
doc.blocks  # ordered TextBlock / TableBlock / ImageBlock
doc.text  # all text joined
doc.tables  # list[TableBlock] (.rows)
doc.to_markdown()  # or doc.to_dict()
```

A flag set to `False` skips that content entirely (table text is not leaked into text blocks).
`.txt` files contain neither, so the flags are no-ops there.

## OpenAI-compatible input

```python
prompt = doc.to_openai_string()  # a plain str; you build the request
client.chat.completions.create(model="...", messages=[{"role": "user", "content": prompt}])
```

Text and tables are markdown; images are inlined in place as `![image](data:image/png;base64,...)` (unsupported formats are re-encoded to PNG, or skipped with a warning). Note the endpoint sees these as text, not as vision inputs, and base64 data is token-heavy — use `parse_images=False` for text-only models. CLI: `-f openai`.

## Notes

- PDF tables use PyMuPDF's table finder (ruled tables work best); scanned PDFs need OCR, which is not included.
- DOCX images inside table cells are not extracted; cell text is.

## Development

```bash
uv sync
uv run ruff check .          # lint
uv run ruff format --check . # formatting (drop --check to apply)
uv run mypy                  # strict type check of src/
uv run pytest                # tests; fails under 90% coverage
```

CI (`.github/workflows/ci.yml`) runs all of the above on every push to `main` and every pull request, plus `uv build`.
To make it blocking, mark the `Lint, format & types`, `Tests (py3.12)`, `Tests (py3.13)` and `Build` checks as required in the branch protection rules for `main`.

## Releasing

Bump `version` in `pyproject.toml`, commit, then tag and push:

```bash
git tag v0.1.0 && git push origin v0.1.0
```

`.github/workflows/release.yml` re-runs CI, verifies the tag matches the package version, builds the sdist and wheel with `uv build`, smoke-tests the wheel, uploads them as a workflow artifact, publishes to PyPI via trusted publishing, and creates a GitHub Release with both files attached (only after PyPI succeeds).

### One-time PyPI setup

No API token is used. On PyPI, add a trusted publisher for `text-detect-parse` (for a new project use *Publishing > Add a new pending publisher*) with:

- Owner / repository: your GitHub owner and this repo's name
- Workflow filename: `release.yml`
- Environment name: `pypi`

Then create a `pypi` environment in the repo's GitHub settings (Settings > Environments); adding required reviewers there gives you a manual approval gate before each publish.
