"""Matchup comparison metrics (Stage 6).

The analysis payoff: compare the satellite backscatter ``b_bp`` (and, with a
satellite Chl source, chlorophyll) against the in-situ BGC-Argo values, in **log
space**, following Bisson et al. (2019) and the BING ``papers/biomass`` analysis.

Both ``b_bp`` **and chlorophyll** are retrieved by BING and compared the same
way: ``b_bp(700)`` from the backscatter model, and ``Chl`` from the fitted
``Aph`` parameter (``Chl = 10**Aph / 0.05582`` for the Bricaud family — the input
``Chl`` only *seeds* the a*_ph shape, it is not fixed). Both are stored as
namespaced quantities, so :func:`gather_matchups` pulls ``bbp_bing`` and
``chl_bing`` and compares each against the Argo ``bbp700`` / ``chla``.

The metric math is **quantity-agnostic and pure** (:func:`log_comparison` on two
arrays), so it unit-tests offline with known values. The store gatherers
assemble the aligned per-matchup arrays from the DB; :func:`add_oc_chl` adds an
**optional independent** OC4 satellite Chl (re-reading the pixel ``Rrs`` through
the mockable :func:`pab.pace.cloud.open_granule` seam) as a cross-check on the
BING Chl.

PAB computes these metrics **on demand** from ``fit_results`` / ``mld_summary``
rather than persisting a separate ``metrics`` table — they are cheap to
recompute, keep the schema stable (no migration), and the reporting layer
(Stage 7) owns aggregate presentation.
"""

from __future__ import annotations

from typing import Any

import numpy as np

#: The BING quantities gathered for the matchup comparison (bare names; the
#: ``BING_<model_pair>_`` prefix is added per call).
DEFAULT_BBP_QUANTITY = "bbp700"
DEFAULT_CHL_QUANTITY = "chl"


def log_comparison(sat, insitu) -> dict[str, Any]:
    """Log-space comparison statistics between paired satellite & in-situ values.

    Only finite, strictly-positive pairs are used (log space). Returns the
    median satellite/in-situ ratio + IQR, the Spearman rank correlation, and the
    log-space bias and scatter (RMS and MAD of ``log10(sat/insitu)``).

    Args:
        sat: Satellite values (e.g. BING ``b_bp(700)``).
        insitu: In-situ values (e.g. Argo mixed-layer ``b_bp(700)``).

    Returns:
        ``{n, median_ratio, ratio_iqr_lo, ratio_iqr_hi, spearman, log_bias,
        log_rms, log_mad}``; the stats are ``nan`` (and ``n=0``) when no valid
        pair survives.
    """
    sat = np.asarray(sat, dtype=float)
    insitu = np.asarray(insitu, dtype=float)
    ok = np.isfinite(sat) & np.isfinite(insitu) & (sat > 0) & (insitu > 0)
    n = int(ok.sum())
    out: dict[str, Any] = {
        "n": n,
        "median_ratio": float("nan"),
        "ratio_iqr_lo": float("nan"),
        "ratio_iqr_hi": float("nan"),
        "spearman": float("nan"),
        "log_bias": float("nan"),
        "log_rms": float("nan"),
        "log_mad": float("nan"),
    }
    if n == 0:
        return out
    s, f = sat[ok], insitu[ok]
    ratio = s / f
    log_resid = np.log10(ratio)
    q1, med, q3 = np.percentile(ratio, [25, 50, 75])
    out["median_ratio"] = float(med)
    out["ratio_iqr_lo"] = float(q1)
    out["ratio_iqr_hi"] = float(q3)
    out["log_bias"] = float(np.mean(log_resid))
    out["log_rms"] = float(np.sqrt(np.mean(log_resid**2)))
    out["log_mad"] = float(np.median(np.abs(log_resid - np.median(log_resid))))
    if n >= 3:
        from scipy.stats import spearmanr

        out["spearman"] = float(spearmanr(s, f)[0])
    return out


def gather_matchups(store, *, model_pair: str = "ExpBPow"):
    """Assemble the per-matchup comparison table from the DB.

    One row per matchup that has a BING fit **for ``model_pair``**: the satellite
    ``b_bp(700)`` and ``chl`` (BING-retrieved, with credible bounds), the in-situ
    Argo ``b_bp(700)`` and ``chla``, the fit's reduced ``chisq``, and the float
    position/time (for stratification). The ``fits`` join is filtered by
    ``model_pair`` so a second model pair (or other fits on the same matchup) does
    not produce duplicate rows.

    Args:
        store: An open :class:`pab.db.store.Store`.
        model_pair: Which BING fit to pull (default ``"ExpBPow"`` →
            ``BING_ExpBPow_bbp700`` / ``BING_ExpBPow_chl``).

    Returns:
        A :class:`pandas.DataFrame` (empty when no matched fits exist).
    """
    bbp_q = f"BING_{model_pair}_{DEFAULT_BBP_QUANTITY}"
    chl_q = f"BING_{model_pair}_{DEFAULT_CHL_QUANTITY}"
    sql = """
        SELECT m.matchup_id, p.wmo, p.cycle, p.latitude, p.longitude, p.time,
               f.fit_id, f.chisq,
               ms.bbp700 AS bbp_argo, ms.chla AS chla_argo,
               fb.value AS bbp_bing,
               fb.value_lo AS bbp_bing_lo, fb.value_hi AS bbp_bing_hi,
               fc.value AS chl_bing,
               fc.value_lo AS chl_bing_lo, fc.value_hi AS chl_bing_hi
        FROM matchups m
        JOIN profiles p ON p.profile_id = m.profile_id
        JOIN mld_summary ms ON ms.profile_id = m.profile_id
        JOIN fits f ON f.matchup_id = m.matchup_id AND f.model_pair = ?
        LEFT JOIN fit_results fb
               ON fb.fit_id = f.fit_id AND fb.quantity = ?
        LEFT JOIN fit_results fc
               ON fc.fit_id = f.fit_id AND fc.quantity = ?
        ORDER BY m.matchup_id
    """
    return store.query_df(sql, (model_pair, bbp_q, chl_q))


def add_oc_chl(df, store, *, opener=None, rank: int = 1):
    """Add an ``chl_oc`` column: an OC4 band-ratio Chl from each matchup's pixel.

    Re-reads the rank-``rank`` pixel ``Rrs`` from the granule (via the mockable
    :func:`pab.pace.cloud.open_granule` seam) and computes the OC4 band-ratio
    chlorophyll (``ocpy.chl.band_ratios.oc4``). This is an **optional, independent
    cross-check** on the BING-retrieved Chl (``chl_bing``) — a different satellite
    Chl algorithm on the same ``Rrs``. ``ocpy`` is imported lazily.

    Args:
        df: A frame from :func:`gather_matchups` (uses ``matchup_id``).
        store: An open store (for the pixel + granule lookups).
        opener: Optional granule opener (test seam).
        rank: Which pixel to read (1 = nearest valid).

    Returns:
        ``df`` with a new ``chl_oc`` column (``nan`` where unavailable).
    """
    from ocpy.chl import band_ratios

    from pab.pace import cloud
    from pab.pace import extract as _extract

    chl = []
    for matchup_id in df["matchup_id"]:
        try:
            row = store.query(
                "SELECT mp.ix, mp.iy, g.data_url, mch.granule_id "
                "FROM matchup_pixels mp "
                "JOIN matchups mch ON mch.matchup_id = mp.matchup_id "
                "JOIN granules g ON g.granule_id = mch.granule_id "
                "WHERE mp.matchup_id = ? AND mp.rank = ?",
                (matchup_id, rank),
            )
            if not row:
                chl.append(float("nan"))
                continue
            r = row[0]
            source = r["data_url"] or r["granule_id"]
            ds = cloud.open_granule(source, opener=opener)
            wave, rrs, _ = _extract.extract_spectrum(ds, int(r["ix"]), int(r["iy"]))
            chl.append(float(np.atleast_1d(band_ratios.oc4(wave, rrs))[0]))
        except Exception:  # noqa: BLE001 — a bad granule must not abort the column
            chl.append(float("nan"))
    df = df.copy()
    df["chl_oc"] = chl
    return df


def compare(df, sat_col: str, insitu_col: str) -> dict[str, Any]:
    """Run :func:`log_comparison` on two columns of a gathered frame."""
    return log_comparison(df[sat_col].to_numpy(), df[insitu_col].to_numpy())


def season_of(month: int) -> str:
    """Meteorological season for a month (1–12): DJF / MAM / JJA / SON."""
    return ("DJF", "MAM", "JJA", "SON")[(int(month) % 12) // 3]


def region_of(latitude: float) -> str:
    """Coarse latitude band: tropics / subtropics / temperate / polar."""
    lat = abs(float(latitude))
    if lat < 23.5:
        return "tropics"
    if lat < 35.0:
        return "subtropics"
    if lat < 55.0:
        return "temperate"
    return "polar"


def add_strata(df):
    """Add ``season`` and ``region`` columns derived from ``time``/``latitude``.

    (``Rrs`` spatial-variability stratification — Bisson's third axis — needs the
    box ``Rrs`` spread, which PAB does not yet persist; it is left for a later
    pass.)
    """
    import pandas as pd

    df = df.copy()
    months = pd.to_datetime(df["time"], errors="coerce", utc=True).dt.month
    df["season"] = [season_of(m) if pd.notna(m) else None for m in months]
    df["region"] = [region_of(la) if pd.notna(la) else None for la in df["latitude"]]
    return df
