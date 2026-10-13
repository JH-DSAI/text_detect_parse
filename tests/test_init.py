import importlib
import re
import tomllib
from importlib.metadata import PackageNotFoundError
from pathlib import Path
from unittest import mock

import text_detect_parse


def test_version_is_valid_string():
    assert re.match(r"^\d+(\.\d+)*", text_detect_parse.__version__)


def test_version_falls_back_when_not_installed():
    with mock.patch("importlib.metadata.version", side_effect=PackageNotFoundError):
        reloaded = importlib.reload(text_detect_parse)
        assert reloaded.__version__ == "0.0.0+unknown"
    importlib.reload(text_detect_parse)
    assert text_detect_parse.__version__ != "0.0.0+unknown"


def test_version_lookup_name_matches_pyproject():
    """The hard-coded distribution name in __init__ must track pyproject's project name."""
    pyproject = Path(__file__).parent.parent / "pyproject.toml"
    name = tomllib.loads(pyproject.read_text())["project"]["name"]
    with mock.patch("importlib.metadata.version", return_value="9.9.9") as version:
        importlib.reload(text_detect_parse)
    version.assert_called_once_with(name)
    importlib.reload(text_detect_parse)
