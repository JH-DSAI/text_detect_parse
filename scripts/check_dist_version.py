"""Fail unless every built distribution in dist/ carries the version of the release tag."""

import email
import sys
import tarfile
import zipfile
from pathlib import Path

from packaging.version import InvalidVersion, Version


def main(tag: str, dist: Path) -> int:
    try:
        expected = Version(tag.removeprefix("v"))
    except InvalidVersion:
        print(f"error: tag {tag!r} is not a valid PEP 440 version", file=sys.stderr)
        return 1

    found: dict[Path, str] = {}
    for wheel in dist.glob("*.whl"):
        with zipfile.ZipFile(wheel) as zf:
            name = next(n for n in zf.namelist() if n.endswith(".dist-info/METADATA"))
            found[wheel] = email.message_from_bytes(zf.read(name))["Version"]
    for sdist in dist.glob("*.tar.gz"):
        with tarfile.open(sdist) as tf:
            name = next(n for n in tf.getnames() if n.count("/") == 1 and n.endswith("/PKG-INFO"))
            member = tf.extractfile(name)
            assert member is not None
            found[sdist] = email.message_from_bytes(member.read())["Version"]

    if not found:
        print(f"error: no distributions found in {dist}", file=sys.stderr)
        return 1
    bad = {path: v for path, v in found.items() if Version(v) != expected}
    for path, v in bad.items():
        print(f"error: {path} has version {v}, tag expects {expected}", file=sys.stderr)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], Path(sys.argv[2])))
