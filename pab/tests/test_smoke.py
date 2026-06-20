"""Stage 0 smoke tests: package imports and the version stamp is present."""

import importlib

import pytest

SUBPACKAGES = [
    "pab",
    "pab.config",
    "pab.db",
    "pab.argo",
    "pab.pace",
    "pab.matchup",
    "pab.fit",
    "pab.metrics",
    "pab.plotting",
    "pab.report",
    "pab.pipeline",
]


@pytest.mark.parametrize("name", SUBPACKAGES)
def test_subpackage_imports(name):
    """Every PAB subpackage imports cleanly."""
    assert importlib.import_module(name) is not None


def test_pab_version_present():
    """``pab_version`` is exposed and is a non-empty string."""
    import pab

    assert isinstance(pab.pab_version, str)
    assert pab.pab_version
    assert pab.__version__ == pab.pab_version


def test_package_versions_includes_pab():
    """Provenance capture always reports a version for pab itself."""
    from pab.config import package_versions

    versions = package_versions()
    assert "pab" in versions
    # Uninstalled optional packages are reported, not raised.
    assert "bing" in versions
