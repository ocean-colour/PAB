"""Per-profile mixed-layer summary: de-spike, average, and persist.

Implements the Bisson et al. (2019) recipe (``docs/context.md`` §3) for turning
a BGC-Argo profile into one summary record: compute the MLD, **de-spike**
``BBP700`` with a 3-point moving median (removes bubble spikes), optionally drop
log-space IQR outliers, then **average** ``BBP700`` and ``CHLA`` and record mean
``PSAL``/``TEMP`` within the mixed layer.

The science functions operate on plain arrays so they unit-test offline;
:func:`summarize_profile` assembles a summary dict matching the ``mld_summary``
table, and :func:`persist_summary` writes the float / profile / summary rows
through :class:`pab.db.store.Store`.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import numpy as np
from numpy.typing import ArrayLike

from pab.argo import mld as _mld
from pab.config import pab_version


def moving_median(values: ArrayLike, window: int = 3) -> np.ndarray:
    """Centered moving-median filter (NaN-aware), edges use a shrinking window.

    A 3-point moving median is the de-spiking filter Bisson et al. apply to
    ``BBP700`` to remove single-sample bubble spikes.

    Args:
        values: 1-D array of values (NaNs allowed).
        window: Odd window length (default 3).

    Returns:
        Filtered array, same shape as ``values``.
    """
    if window < 1 or window % 2 == 0:
        raise ValueError("window must be a positive odd integer")
    x = np.asarray(values, dtype=float)
    n = x.size
    half = window // 2
    out = np.full(n, np.nan)
    for i in range(n):
        lo = max(0, i - half)
        hi = min(n, i + half + 1)
        seg = x[lo:hi]
        if np.any(np.isfinite(seg)):
            out[i] = np.nanmedian(seg)
    return out


#: Alias: de-spiking is a 3-point moving median by default.
def despike(values: ArrayLike, window: int = 3) -> np.ndarray:
    """De-spike a profile with a moving median (see :func:`moving_median`)."""
    return moving_median(values, window=window)


def iqr_inlier_mask(
    values: ArrayLike, *, k: float = 1.5, log: bool = True
) -> np.ndarray:
    """Boolean mask of values within ``k`` × IQR of the (log-)distribution.

    Bisson et al. remove outliers beyond 1.5×IQR of log-transformed ``bbp``
    before averaging. NaNs (and, in log mode, non-positive values) are marked
    ``False``.

    Args:
        values: 1-D array.
        k: IQR multiplier (default 1.5).
        log: Operate on ``log10(values)`` (default True; appropriate for the
            log-normal spread of ``bbp``).

    Returns:
        Boolean inlier mask aligned with ``values``.
    """
    x = np.asarray(values, dtype=float)
    work = x.copy()
    valid = np.isfinite(work)
    if log:
        valid &= work > 0
        work = np.where(valid, np.log10(np.where(valid, work, 1.0)), np.nan)
    if valid.sum() < 4:
        # Too few points to estimate quartiles robustly; keep all finite.
        return valid
    q1, q3 = np.nanpercentile(work[valid], [25, 75])
    iqr = q3 - q1
    lo, hi = q1 - k * iqr, q3 + k * iqr
    mask = valid & (work >= lo) & (work <= hi)
    return mask


def mixed_layer_mean(
    pres: ArrayLike,
    values: ArrayLike,
    mld: float,
    *,
    despike_values: bool = False,
    iqr_filter: bool = False,
) -> tuple[float, float, int]:
    """Mean / std / count of ``values`` within the mixed layer (``pres <= mld``).

    Args:
        pres: Pressure (dbar ≈ m).
        values: Values aligned with ``pres``.
        mld: Mixed-layer depth; if ``nan`` the result is ``(nan, nan, 0)``.
        despike_values: Apply a 3-point moving median before averaging.
        iqr_filter: Drop log-space IQR outliers before averaging.

    Returns:
        ``(mean, std, n_points)`` over the retained mixed-layer samples.
    """
    pres = np.asarray(pres, dtype=float)
    vals = np.asarray(values, dtype=float)
    if not np.isfinite(mld):
        return float("nan"), float("nan"), 0
    if despike_values:
        vals = moving_median(vals)
    in_ml = np.isfinite(pres) & (pres <= mld) & np.isfinite(vals)
    if iqr_filter and in_ml.any():
        in_ml &= iqr_inlier_mask(np.where(in_ml, vals, np.nan))
    sel = vals[in_ml]
    if sel.size == 0:
        return float("nan"), float("nan"), 0
    return float(np.mean(sel)), float(np.std(sel)), int(sel.size)


def summarize_profile(
    pres: ArrayLike,
    *,
    bbp700: ArrayLike | None = None,
    chla: ArrayLike | None = None,
    psal: ArrayLike | None = None,
    temp: ArrayLike | None = None,
    lon: float | None = None,
    lat: float | None = None,
    sig0: ArrayLike | None = None,
    despike_bbp: bool = True,
    iqr_filter: bool = True,
    ref_depth: float = _mld.REF_DEPTH,
    threshold: float = _mld.THRESHOLD,
) -> dict[str, Any]:
    """Compute the mixed-layer summary for one profile.

    Computes the MLD (from supplied ``sig0`` or from ``psal``/``temp`` via
    TEOS-10), de-spikes ``BBP700``, optionally removes log-IQR outliers, and
    averages within the mixed layer.

    Args:
        pres: Pressure (dbar ≈ m).
        bbp700, chla, psal, temp: Profile variables aligned with ``pres``
            (any may be omitted).
        lon, lat: Profile location (needed for TEOS-10 if ``sig0`` is absent).
        sig0: Potential density; if omitted it is derived from ``psal``/``temp``.
        despike_bbp: 3-point moving-median de-spike of ``BBP700``.
        iqr_filter: Drop log-space IQR outliers from ``BBP700`` before averaging.
        ref_depth, threshold: MLD criterion parameters.

    Returns:
        Dict with the ``mld_summary`` fields (no ``profile_id``): ``mld``,
        ``mld_method``, ``bbp700``, ``bbp700_std``, ``chla``, ``chla_std``,
        ``psal``, ``temp``, ``n_points``.
    """
    pres = np.asarray(pres, dtype=float)

    if sig0 is None and psal is not None and temp is not None:
        if lon is None or lat is None:
            raise ValueError("lon and lat are required to derive SIG0 from T/S")
        sig0 = _mld.density_sigma0(pres, psal, temp, lon, lat)

    mld_val = (
        _mld.mixed_layer_depth(pres, sig0, ref_depth=ref_depth, threshold=threshold)
        if sig0 is not None
        else float("nan")
    )

    summary: dict[str, Any] = {
        "mld": mld_val,
        "mld_method": _mld.MLD_METHOD,
        "bbp700": float("nan"),
        "bbp700_std": float("nan"),
        "chla": float("nan"),
        "chla_std": float("nan"),
        "psal": float("nan"),
        "temp": float("nan"),
        "n_points": 0,
    }

    if bbp700 is not None:
        mean, std, n = mixed_layer_mean(
            pres, bbp700, mld_val, despike_values=despike_bbp, iqr_filter=iqr_filter
        )
        summary.update(bbp700=mean, bbp700_std=std, n_points=n)
    if chla is not None:
        mean, std, _ = mixed_layer_mean(pres, chla, mld_val)
        summary.update(chla=mean, chla_std=std)
    if psal is not None:
        summary["psal"] = mixed_layer_mean(pres, psal, mld_val)[0]
    if temp is not None:
        summary["temp"] = mixed_layer_mean(pres, temp, mld_val)[0]

    return summary


def persist_summary(
    store,
    *,
    wmo: int,
    cycle: int,
    summary: dict[str, Any],
    latitude: float | None = None,
    longitude: float | None = None,
    time: str | None = None,
    data_mode: str | None = None,
    project_name: str | None = None,
    data_center: str | None = None,
    created: str | None = None,
) -> int:
    """Upsert the float, profile, and mixed-layer summary rows; return profile_id.

    Idempotent (keyed by ``wmo``/``(wmo, cycle)``/``profile_id``), so re-running
    the ingestion updates in place rather than duplicating.

    Args:
        store: An open :class:`pab.db.store.Store`.
        wmo: Float WMO id.
        cycle: Profile cycle number.
        summary: Output of :func:`summarize_profile`.
        latitude, longitude, time, data_mode: Profile metadata.
        project_name, data_center: Float metadata.
        created: Timestamp to stamp (defaults to now, UTC ISO-8601).

    Returns:
        The ``profile_id`` of the persisted profile.
    """
    created = created or datetime.now(UTC).isoformat()

    store.upsert(
        "floats",
        {"wmo": wmo, "project_name": project_name, "data_center": data_center},
    )
    store.upsert(
        "profiles",
        {
            "wmo": wmo,
            "cycle": cycle,
            "latitude": latitude,
            "longitude": longitude,
            "time": time,
            "data_mode": data_mode,
        },
    )
    profile_id = store.query(
        "SELECT profile_id FROM profiles WHERE wmo = ? AND cycle = ?",
        (wmo, cycle),
    )[0]["profile_id"]

    row = {"profile_id": profile_id, "created": created, "pab_version": pab_version}
    row.update(
        {
            k: summary.get(k)
            for k in (
                "mld",
                "mld_method",
                "bbp700",
                "bbp700_std",
                "chla",
                "chla_std",
                "psal",
                "temp",
                "n_points",
            )
        }
    )
    store.upsert("mld_summary", row)
    return profile_id
