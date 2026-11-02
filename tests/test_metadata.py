"""Packaged metadata is discoverable at runtime."""

from __future__ import annotations

from importlib.metadata import version
from pathlib import Path

import sc1p
import scbm
import synteny_tree


def test_versions_match_installed_metadata():
    assert sc1p.__version__ == version("sc1p")
    assert scbm.__version__ == version("scbm")
    assert synteny_tree.__version__ == version("synteny-tree")


def test_typing_markers_are_installed():
    assert (Path(sc1p.__file__).with_name("py.typed")).is_file()
    assert (Path(scbm.__file__).with_name("py.typed")).is_file()
    assert (Path(synteny_tree.__file__).with_name("py.typed")).is_file()
