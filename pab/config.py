"""Project configuration: version stamp, paths, and provenance helpers.

This module is intentionally dependency-light so that ``import pab`` works in a
minimal environment (the Stage 0 smoke test). Heavier settings (run config,
database paths, cloud credentials) will be layered on in later stages.
"""

from __future__ import annotations

import importlib.metadata
import os
from pathlib import Path

#: Version stamp recorded with every fit for provenance (see design §Provenance
#: & versioning). Bumped as the analysis pipeline evolves; distinct from the
#: packaging version in ``setup.py``.
pab_version = "0.0.dev0"

#: Packages whose versions are captured per fit for reproducibility.
_PROVENANCE_PACKAGES = (
    "pab",
    "bing",
    "ocpy",
    "argopy",
    "remote_sensing",
    "earthaccess",
    "numpy",
    "scipy",
    "xarray",
)


def _package_root() -> Path:
    """Return the directory containing the ``pab`` package."""
    return Path(__file__).resolve().parent


def _repo_root() -> Path:
    """Return the repository root (parent of the ``pab`` package)."""
    return _package_root().parent


#: Repository root, overridable via the ``PAB_ROOT`` environment variable.
ROOT = Path(os.environ.get("PAB_ROOT", _repo_root()))

#: Default location for the SQLite store and on-disk fit artifacts. Kept out of
#: the repo by default (large data); overridable via ``PAB_DATA_DIR``.
DATA_DIR = Path(os.environ.get("PAB_DATA_DIR", ROOT / "data"))


def package_versions() -> dict[str, str]:
    """Return installed versions of the packages tracked for provenance.

    Packages that are not installed are reported as ``"not installed"`` rather
    than raising, so provenance capture never breaks a run.

    Returns:
        Mapping of package name to version string.
    """
    versions: dict[str, str] = {}
    for name in _PROVENANCE_PACKAGES:
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            versions[name] = "not installed"
    return versions
