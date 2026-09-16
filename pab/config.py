"""Project configuration: version stamp, paths, and provenance helpers.

This module is intentionally dependency-light so that ``import pab`` works in a
minimal environment (the Stage 0 smoke test). Heavier settings (run config,
database paths, cloud credentials) will be layered on in later stages.
"""

from __future__ import annotations

import functools
import importlib.metadata
import os
from pathlib import Path
from typing import Any

#: Version stamp recorded with every fit for provenance (see design §Provenance
#: & versioning). Bumped as the analysis pipeline evolves; distinct from the
#: packaging version in ``setup.py``. ``1.0`` = the first full-pipeline release
#: (all BGC-Argo × PACE), provenance-distinct from the ``0.0.dev0`` dev runs.
#: ``1.1`` = the NASA-GIOP comparison baseline added (new science content, not
#: a provenance backfill — see ``claude_prompts/pace_giop_gsm.md`` Q4).
pab_version = "2.0"

#: Packages whose versions are captured per fit for reproducibility.
_PROVENANCE_PACKAGES = (
    "pab",
    "bing",
    "ocpy",
    "argopy",
    "remote_sensing",
    "earthaccess",
    "robust",
    "numpy",
    "scipy",
    "xarray",
)

#: Import name -> distribution name, where they differ. ``robust`` (the
#: radiative-transfer backend behind ``rt_backend='robust_*'``) is distributed
#: as ``retrieve-or-bust``; ``importlib.metadata.version("robust")`` raises.
#: Recorded under the **import** name, which is what appears in tracebacks and
#: in ``rt_backend``.
_DISTRIBUTION_NAMES = {"robust": "retrieve-or-bust"}

#: Repositories whose git SHA is captured per fit, mapped to the import name
#: used to locate them. A version string is not enough for these: four of the
#: five are editable installs pinned at ``0.0.dev0``, so the *only* thing that
#: identifies which code produced a fit is the commit.
_GIT_REPOS = {
    "PAB": "pab",
    "bing": "bing",
    "ocpy": "ocpy",
    "remote_sensing": "remote_sensing",
    "retrieve-or-bust": "robust",
}

#: Environment variable carrying pre-resolved git SHAs as a JSON object,
#: e.g. ``PAB_GIT_SHAS='{"PAB": "03aca64", "bing": "bf56f6d"}'``.
#:
#: **This is the container seam.** The Docker image has no ``.git``, so
#: ``git rev-parse`` there yields ``"unknown"`` for every repo and a run's
#: provenance would not say which code produced it. The image build knows the
#: SHAs it checked out, so it passes them in through this variable (or a label
#: the entrypoint exports into it). Values here **override** anything git
#: reports, so a deliberately-stamped image is never second-guessed by a stray
#: ``.git`` that happened to be copied in.
GIT_SHA_ENV = "PAB_GIT_SHAS"

#: Recorded for a repo whose commit cannot be determined.
UNKNOWN_SHA = "unknown"


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


def _repo_root_for(module: str) -> Path | None:
    """Directory that should contain a repo's ``.git``, or ``None``.

    Uses ``find_spec`` rather than importing: this runs for five packages and
    must not drag ``jax`` or ``argopy`` into a provenance lookup. For an
    editable install the spec points at the source tree, whose parent is the
    checkout.
    """
    import importlib.util

    try:
        spec = importlib.util.find_spec(module)
    except (ImportError, ValueError):
        return None
    if spec is None or not spec.submodule_search_locations:
        return None
    return Path(spec.submodule_search_locations[0]).resolve().parent


def _git_sha(path: Path | None) -> str:
    """``git rev-parse --short HEAD`` in ``path``, or :data:`UNKNOWN_SHA`.

    Never raises and never blocks for long: any failure — no ``.git``, no
    ``git`` binary, a detached or corrupt repo, a slow filesystem — is just an
    unknown SHA. Provenance capture must not be able to fail a fit.
    """
    import subprocess

    if path is None or not path.is_dir():
        return UNKNOWN_SHA
    try:
        out = subprocess.run(
            ["git", "-C", str(path), "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return UNKNOWN_SHA
    sha = out.stdout.strip()
    return sha if out.returncode == 0 and sha else UNKNOWN_SHA


@functools.cache
def git_shas() -> dict[str, str]:
    """Git SHA per tracked repo, ``"unknown"`` where it cannot be determined.

    Resolution order per repo: :data:`GIT_SHA_ENV` (the container seam) first,
    then ``git rev-parse`` in the installed source tree.

    Cached for the life of the process — the SHAs cannot change under a running
    fit, and this would otherwise shell out five times per persisted row. That
    makes it "once per process" rather than literally at import, which also
    keeps ``import pab`` free of five subprocesses.

    Returns:
        ``{repo: sha}`` for every key of :data:`_GIT_REPOS`.
    """
    import json

    override: dict[str, str] = {}
    raw = os.environ.get(GIT_SHA_ENV)
    if raw:
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                override = {str(k): str(v) for k, v in parsed.items()}
        except (TypeError, ValueError):
            override = {}  # a malformed label must not break provenance

    return {
        repo: override.get(repo) or _git_sha(_repo_root_for(module))
        for repo, module in _GIT_REPOS.items()
    }


def package_versions() -> dict[str, Any]:
    """Return installed versions of the packages tracked for provenance.

    Packages that are not installed are reported as ``"not installed"`` rather
    than raising, so provenance capture never breaks a run.

    Includes a nested ``"git_sha"`` map (:func:`git_shas`). Versions alone do
    not identify the code for this project: ``bing``, ``ocpy``,
    ``remote_sensing`` and ``robust`` are editable installs permanently
    reporting ``0.0.dev0``, so the commit is the only real identifier.

    Returns:
        Mapping of package name to version string, plus ``"git_sha"`` →
        ``{repo: sha}``.
    """
    versions: dict[str, Any] = {}
    for name in _PROVENANCE_PACKAGES:
        dist = _DISTRIBUTION_NAMES.get(name, name)
        try:
            versions[name] = importlib.metadata.version(dist)
        except importlib.metadata.PackageNotFoundError:
            versions[name] = "not installed"
    versions["git_sha"] = git_shas()
    return versions
