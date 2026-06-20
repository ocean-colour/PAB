"""PACE granule discovery via ``earthaccess`` (CMR) + a granule table.

Granule *discovery* is uniform across products: a CMR query by short name,
bounding box, time window, and cloud-cover range. PAB wraps
``earthaccess.search_data`` and turns the results into a tidy ``DataFrame``
(id / footprint / time / cloud-cover / URL) — directly useful for spatially
matching granules to a float position (Stage 4) — reusing
``remote_sensing.download.earthaccess`` where available. The heavy imports are
lazy; these functions are network-bound and exercised live in the Stage 3
notebook rather than the offline suite.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pab.config import pab_version

#: Default PACE L2 AOP product short name (holds ``Rrs``; design *Datasets*).
DEFAULT_SHORT_NAME = "PACE_OCI_L2_AOP"


def search_granules(
    *,
    short_name: str = DEFAULT_SHORT_NAME,
    temporal: tuple[str, str],
    bounding_box: tuple[float, float, float, float],
    cloud_cover: tuple[int, int] = (0, 100),
):
    """Search the Earthdata Cloud (CMR) for granules.

    Args:
        short_name: Collection short name (default PACE L2 AOP).
        temporal: ``(start, end)`` ISO dates.
        bounding_box: ``(west, south, east, north)`` around the float.
        cloud_cover: ``(min, max)`` percent cloud cover.

    Returns:
        The ``earthaccess`` search results (a list of granule objects).
    """
    import earthaccess

    return earthaccess.search_data(
        short_name=short_name,
        temporal=temporal,
        bounding_box=bounding_box,
        cloud_cover=cloud_cover,
    )


def granule_table(results, *, fix_antimeridian: bool = False):
    """Turn ``earthaccess`` results into a granule ``DataFrame``.

    Uses ``remote_sensing.download.earthaccess.build_granule_table`` (id /
    footprint polygon / time / cloud-cover / data URL).

    Args:
        results: Output of :func:`search_granules`.
        fix_antimeridian: Passed through to ``build_granule_table``.

    Returns:
        A ``pandas.DataFrame`` of granule metadata.
    """
    from remote_sensing.download import earthaccess as rs_ea

    granules = rs_ea.granules_to_dict(results)
    return rs_ea.build_granule_table(granules, fix_antimeridian=fix_antimeridian)


def persist_granules(store, table, *, short_name: str = DEFAULT_SHORT_NAME) -> int:
    """Upsert a granule table into the ``granules`` DB table (idempotent).

    Maps the discovery table's columns onto the schema. The column names follow
    ``remote_sensing.download.earthaccess.build_granule_table``: ``id``,
    ``polygon`` (a shapely geometry → stored as WKT), ``time`` (granule mid-time
    → ``time_start``), ``CC`` (cloud cover), and ``url``. Each key also accepts
    the schema-native name as a fallback so a frame that already uses
    ``granule_id``/``cloud_cover``/… works too; absent columns store ``None``.

    Args:
        store: An open :class:`pab.db.store.Store`.
        table: A granule ``DataFrame`` (e.g. from :func:`granule_table`).
        short_name: Collection short name to stamp on each row.

    Returns:
        The number of rows upserted.
    """
    rows: list[dict[str, Any]] = []
    for rec in table.to_dict(orient="records"):
        gid = _first(rec, "granule_id", "id", "concept_id")
        rows.append(
            {
                "granule_id": str(gid),
                "short_name": short_name,
                "time_start": _maybe_str(_first(rec, "time_start", "time")),
                "time_end": _maybe_str(_first(rec, "time_end")),
                "footprint": _maybe_str(_first(rec, "footprint", "polygon")),
                "cloud_cover": _first(rec, "cloud_cover", "CC"),
                "data_url": _first(rec, "data_url", "url"),
            }
        )
    return store.upsert_many("granules", rows)


def _first(rec: dict, *keys: str):
    """Return the first non-``None`` value among ``keys`` in ``rec`` (else None)."""
    for key in keys:
        val = rec.get(key)
        if val is not None:
            return val
    return None


def _maybe_str(value):
    """Stringify non-None values (footprints/timestamps) for SQLite storage."""
    return None if value is None else str(value)


def discovery_provenance() -> dict[str, str]:
    """Small provenance stamp for a discovery run (version + UTC timestamp)."""
    return {"pab_version": pab_version, "created": datetime.now(UTC).isoformat()}
