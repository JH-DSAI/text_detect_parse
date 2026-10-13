import importlib
import re
import tomllib
from importlib.metadata import PackageNotFoundError
from pathlib import Path

import pytest

import text_detect_parse


@pytest.fixture
def restore_module():
    """Reload the package afterwards so a failing test cannot leak a patched __version__."""
    yield
    importlib.reload(text_detect_parse)


def test_version_is_derived_from_vcs():
    # 0.0.0 is what a build without git metadata used to produce; it must never pass.
    assert re.match(r"^\d+(\.\d+)*", text_detect_parse.__version__)
    assert not text_detect_parse.__version__.startswith("0.0.0")


def test_version_falls_back_when_not_installed(monkeypatch, restore_module):
    def missing(name):
        raise PackageNotFoundError(name)

    monkeypatch.setattr("importlib.metadata.version", missing)
    assert importlib.reload(text_detect_parse).__version__ == "0.0.0+unknown"


def test_version_lookup_name_matches_pyproject(monkeypatch, restore_module):
    """The hard-coded distribution name in __init__ must track pyproject's project name."""
    pyproject = Path(__file__).parent.parent / "pyproject.toml"
    name = tomllib.loads(pyproject.read_text())["project"]["name"]
    names: list[str] = []

    def record(dist_name):
        names.append(dist_name)
        return "9.9.9"

    monkeypatch.setattr("importlib.metadata.version", record)
    importlib.reload(text_detect_parse)
    assert names == [name]
