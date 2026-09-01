"""Exports, the download manifest, and (stubbed) publish backends (Stage 7).

Reporting exposes three downloadable product types — summary tables (CSV/Parquet),
per-matchup MCMC chains (NPZ), and per-matchup figures — but **not** the raw
SQLite file. The bulky chains/figures live in an object store (NSF/Nautilus S3);
a **download manifest** (matchup id → URL + checksum, stamped with
``pab_version``) ties them back to the DB rows.

The reporting build runs end-to-end offline against a filesystem stub
(:class:`LocalStubBackend`). :class:`NautilusS3Backend` is the **live** NSF/Nautilus
S3 (Ceph RGW) backend — used to publish to the public ``s3://pab`` bucket; it
imports ``boto3`` lazily so the offline test path never needs it.
:class:`ZenodoBackend` (citable DOI snapshots) remains an explicit
``NotImplementedError`` stub until activated.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pab.config import pab_version as _pab_version
from pab.config import package_versions
from pab.metrics import compare


def file_checksum(path) -> str | None:
    """SHA-256 of a file (first 16 hex chars), or ``None`` if it doesn't exist."""
    path = Path(path)
    if not path.is_file():
        return None
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


def export_tables(store, outdir, *, model_pair: str = "ExpBPow") -> dict[str, Path]:
    """Write the summary tables (matchup comparison + wide fit results) to disk.

    Returns ``{name: path}`` for the CSV and Parquet exports. The raw SQLite file
    is never written here.
    """
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    df = compare.gather_matchups(store, model_pair=model_pair)
    out: dict[str, Path] = {}
    csv = outdir / "matchup_summary.csv"
    df.to_csv(csv, index=False)
    out["summary_csv"] = csv
    try:
        pq = outdir / "matchup_summary.parquet"
        df.to_parquet(pq, index=False)
        out["summary_parquet"] = pq
    except Exception:  # noqa: BLE001 — parquet engine optional; CSV is the floor
        pass
    return out


def build_manifest(store, *, base_url: str = "", pab_version: str | None = None):
    """Build the download manifest: one row per per-matchup artifact.

    Reads ``fits.chains_path`` / ``figure_path`` and emits ``(matchup_id, fit_id,
    kind, local_path, url, checksum, pab_version)`` rows for the chains and
    figures (skipping rows with no path). The ``url`` is ``base_url`` + the file
    name; ``checksum`` is the file's SHA-256 (when the file exists locally).

    Returns:
        A list of manifest dicts.
    """
    pab_version = pab_version or _pab_version
    rows: list[dict[str, Any]] = []
    fits = store.query(
        "SELECT fit_id, matchup_id, chains_path, figure_path FROM fits ORDER BY fit_id"
    )
    base = base_url.rstrip("/")
    for f in fits:
        for kind, col in (("chains", "chains_path"), ("figure", "figure_path")):
            local = f[col]
            if not local:
                continue
            name = Path(local).name
            rows.append(
                {
                    "matchup_id": f["matchup_id"],
                    "fit_id": f["fit_id"],
                    "kind": kind,
                    "local_path": local,
                    "url": f"{base}/{name}" if base else name,
                    "checksum": file_checksum(local),
                    "pab_version": pab_version,
                }
            )
    return rows


class LocalStubBackend:
    """Filesystem stand-in for the object store: 'uploads' by copying locally.

    Records every upload so tests can assert no network was used.
    """

    def __init__(self, root, *, base_url: str = "file://local"):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.base_url = base_url.rstrip("/")
        self.uploaded: list[tuple[str, str]] = []

    def upload(self, local_path, key: str | None = None) -> str:
        """Copy ``local_path`` into the stub store; return its (stub) URL."""
        local_path = Path(local_path)
        key = key or local_path.name
        shutil.copy2(local_path, self.root / Path(key).name)
        url = f"{self.base_url}/{key}"
        self.uploaded.append((str(local_path), url))
        return url


class NautilusS3Backend:
    """NSF/Nautilus S3 (Ceph RGW) upload backend for the public ``s3://pab`` bucket.

    ``upload`` puts a file to ``s3://<bucket>/<prefix>/<key>`` and returns its
    **public** URL — the ``pab`` bucket is public-read, so the returned URLs need
    no credentials to fetch. Nautilus runs Ceph RGW, which requires **path-style**
    addressing (``<endpoint>/<bucket>/<key>``, not virtual-host).

    Write credentials come from the standard boto3 chain (env
    ``AWS_ACCESS_KEY_ID``/``AWS_SECRET_ACCESS_KEY``, a shared-credentials
    ``profile_name``, or a mounted secret) unless ``aws_access_key_id`` /
    ``aws_secret_access_key`` are passed explicitly. Pass ``client`` (a boto3 S3
    client) to unit-test without a network. ``boto3`` is imported lazily so
    ``import pab.report.publish`` works without it.

    Mirrors :class:`LocalStubBackend` (``.upload``, ``.uploaded``, ``.base_url``)
    so it drops into :func:`publish_release` interchangeably.
    """

    DEFAULT_ENDPOINT = "https://s3-west.nrp-nautilus.io"

    def __init__(
        self,
        bucket: str = "pab",
        *,
        prefix: str = "",
        endpoint_url: str | None = None,
        base_url: str | None = None,
        profile_name: str | None = None,
        aws_access_key_id: str | None = None,
        aws_secret_access_key: str | None = None,
        client=None,
    ):
        self.bucket = bucket
        self.prefix = prefix.strip("/")
        self.endpoint_url = (endpoint_url or self.DEFAULT_ENDPOINT).rstrip("/")
        # Ceph RGW is path-style; the public URL is <endpoint>/<bucket>[/<key>].
        self.base_url = (base_url or f"{self.endpoint_url}/{bucket}").rstrip("/")
        self.uploaded: list[tuple[str, str]] = []
        if client is not None:
            self._client = client
        else:
            import boto3
            from botocore.config import Config

            session = boto3.Session(profile_name=profile_name)
            self._client = session.client(
                "s3",
                endpoint_url=self.endpoint_url,
                aws_access_key_id=aws_access_key_id,
                aws_secret_access_key=aws_secret_access_key,
                config=Config(s3={"addressing_style": "path"}),
            )

    def _full_key(self, key: str) -> str:
        key = key.lstrip("/")
        return f"{self.prefix}/{key}" if self.prefix else key

    def upload(self, local_path, key: str | None = None) -> str:
        """Upload ``local_path`` to ``s3://bucket/prefix/key``; return its public URL."""
        local_path = Path(local_path)
        full_key = self._full_key(key or local_path.name)
        self._client.upload_file(str(local_path), self.bucket, full_key)
        url = f"{self.base_url}/{full_key}"
        self.uploaded.append((str(local_path), url))
        return url


class ZenodoBackend:
    """Zenodo snapshot/DOI backend — deferred (config-gated activation)."""

    def __init__(self, *args, **kwargs):
        raise NotImplementedError(
            "Zenodo packaging is deferred; snapshots are produced locally for now."
        )


def publish_release(
    store,
    outdir,
    *,
    backend=None,
    base_url: str = "",
    pab_version: str | None = None,
) -> dict[str, Any]:
    """Produce a release **locally**: exports + manifest + (stubbed) uploads.

    Writes the summary tables, builds the download manifest, "uploads" each
    artifact through ``backend`` (default :class:`LocalStubBackend`, no network),
    and writes ``manifest.json``. Real S3/Zenodo uploads are deferred — pass an
    activated backend later to wire them.

    Returns:
        ``{"exports", "manifest", "manifest_path", "n_uploaded", "pkg_versions"}``.
    """
    pab_version = pab_version or _pab_version
    outdir = Path(outdir)
    backend = backend or LocalStubBackend(outdir / "store")

    exports = export_tables(store, outdir)
    manifest = build_manifest(store, base_url=base_url, pab_version=pab_version)
    n_uploaded = 0
    for row in manifest:
        if Path(row["local_path"]).is_file():
            row["url"] = backend.upload(row["local_path"])
            n_uploaded += 1
    manifest_path = outdir / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "pab_version": pab_version,
                "created": datetime.now(UTC).isoformat(),
                "pkg_versions": package_versions(),
                "artifacts": manifest,
            },
            indent=2,
        )
    )
    return {
        "exports": exports,
        "manifest": manifest,
        "manifest_path": manifest_path,
        "n_uploaded": n_uploaded,
        "pkg_versions": package_versions(),
    }
