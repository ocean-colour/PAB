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


def _version_key(v: str) -> tuple:
    """Sort key for a ``pab_version`` string, numeric where it can be.

    ``"2.0"`` must sort above ``"1.1"``, which plain string comparison gets
    right here but would not once a ``"10.0"`` exists. Non-numeric parts fall
    back to comparing as text so an odd value never raises.
    """
    parts = []
    for piece in str(v).split("."):
        try:
            parts.append((0, int(piece)))
        except ValueError:
            parts.append((1, piece))
    return tuple(parts)


def newest_bing_version(store) -> str | None:
    """The newest ``pab_version`` among the store's BING fits, or ``None``.

    The v2 database holds BING **2.0** fits alongside NASA-GIOP **1.1** rows,
    and a store that has been fitted twice would hold 1.0 and 2.0 BING fits for
    the same matchup. Metrics must pick one, and the newest is the one the
    report is about -- so this is the default rather than something every
    caller has to remember to pass.
    """
    rows = store.query(
        "SELECT DISTINCT pab_version FROM fits "
        "WHERE algorithm = 'BING' AND pab_version IS NOT NULL"
    )
    versions = [r["pab_version"] for r in rows]
    return max(versions, key=_version_key) if versions else None


def gather_matchups(store, *, model_pair: str = "ExpBPow", pab_version=None):
    """Assemble the per-matchup comparison table from the DB.

    One row per matchup that has a BING fit **for ``model_pair``**: the satellite
    ``b_bp(700)`` and ``chl`` (BING-retrieved, with credible bounds), the in-situ
    Argo ``b_bp(700)`` and ``chla``, the fit's reduced ``chisq``, and the float
    position/time (for stratification). The ``fits`` join is filtered by
    ``model_pair`` so a second model pair (or other fits on the same matchup) does
    not produce duplicate rows.

    The join is also filtered to ``algorithm = 'BING'`` and a **single
    ``pab_version``**. Without the version filter a store holding both 1.0 and
    2.0 fits for one matchup yields *two* rows, silently doubling every count
    and mixing two physics configurations into one scatter.

    Args:
        store: An open :class:`pab.db.store.Store`.
        model_pair: Which BING fit to pull (default ``"ExpBPow"`` →
            ``BING_ExpBPow_bbp700`` / ``BING_ExpBPow_chl``).
        pab_version: Which BING version to report. ``None`` (the default) picks
            the store's newest via :func:`newest_bing_version`, which is the
            one the report is about.

    Returns:
        A :class:`pandas.DataFrame` (empty when no matched fits exist).
    """
    bbp_q = f"BING_{model_pair}_{DEFAULT_BBP_QUANTITY}"
    chl_q = f"BING_{model_pair}_{DEFAULT_CHL_QUANTITY}"
    if pab_version is None:
        pab_version = newest_bing_version(store)
    sql = """
        SELECT m.matchup_id, p.wmo, p.cycle, p.latitude, p.longitude, p.time,
               f.fit_id, f.chisq, f.pab_version,
               ms.bbp700 AS bbp_argo, ms.chla AS chla_argo,
               fb.value AS bbp_bing,
               fb.value_lo AS bbp_bing_lo, fb.value_hi AS bbp_bing_hi,
               fc.value AS chl_bing,
               fc.value_lo AS chl_bing_lo, fc.value_hi AS chl_bing_hi
        FROM matchups m
        JOIN profiles p ON p.profile_id = m.profile_id
        JOIN mld_summary ms ON ms.profile_id = m.profile_id
        JOIN fits f ON f.matchup_id = m.matchup_id
                   AND f.algorithm = 'BING'
                   AND f.model_pair = ?
                   AND (? IS NULL OR f.pab_version = ?)
        LEFT JOIN fit_results fb
               ON fb.fit_id = f.fit_id AND fb.quantity = ?
        LEFT JOIN fit_results fc
               ON fc.fit_id = f.fit_id AND fc.quantity = ?
        ORDER BY m.matchup_id
    """
    return store.query_df(sql, (model_pair, pab_version, pab_version, bbp_q, chl_q))


def gather_version_pair(store, v1_path, *, model_pair: str = "ExpBPow"):
    """One row per matchup fitted in **both** 1.0 and 2.0, for the comparison.

    The 1.0 BING fits do not live in the v2 database — the v2 split carried the
    NASA-GIOP rows across but not the BING ones — so the only place to read
    them is the frozen ``v1/pab.db``. That database is ``chmod a-w`` and at
    schema v4 while the code is at v5, so it is **attached read-only** via a
    ``file:…?mode=ro`` URI: a plain ``Store.open`` would try to migrate it and
    die with ``attempt to write a readonly database``. The URI form needs the
    connection opened with ``uri=True`` (:meth:`pab.db.store.Store.open` does),
    and there is deliberately **no plain-path fallback** -- a plain ``ATTACH``
    is read-write, so a fallback would quietly make the frozen release
    writable.

    Rows are matched on ``matchup_id`` **and** ``pixel_id``. `matchup_id` alone
    is not enough: it identifies the profile/granule pair, not which pixel was
    fitted, and comparing two fits of *different pixels* would silently
    attribute a spatial difference to the physics change.

    Args:
        store: An open :class:`pab.db.store.Store` on the v2 database.
        v1_path: Path to the frozen v1 database.
        model_pair: Which BING fit to pull from both sides.

    Raises:
        FileNotFoundError: If ``v1_path`` does not exist -- rather than letting
            ``ATTACH`` create an empty database there.

    Returns:
        A :class:`pandas.DataFrame` with ``bbp700``/``chl``/``aph``/``chisq``
        for each version (suffixed ``_v1``/``_v2``) plus ``Bp_v2`` — the free
        phase-function parameter, which exists only in 2.0. Empty when the two
        databases share no fitted matchup.
    """
    from pathlib import Path as _Path

    # Check existence FIRST. `ATTACH` of a plain path *creates* the database
    # when it is missing, so a typo'd --compare-db would silently leave an
    # empty `pab.b` next to the real data and then fail with the confusing
    # `no such table: v1.fits`. Fail on the path, before touching the disk.
    if not _Path(v1_path).is_file():
        raise FileNotFoundError(f"comparison database not found: {v1_path}")

    q = {k: f"BING_{model_pair}_{k}" for k in ("bbp700", "chl", "Aph", "Bp")}
    # NO fallback to a plain-path ATTACH. A plain `ATTACH` is read-WRITE, so a
    # fallback turns "the read-only attach failed" into "the frozen release is
    # now writable" -- silently. This is not hypothetical: the URI form fails
    # unless the connection was opened with `uri=True`, so an earlier version
    # of this function attached `v1/pab.db` read-write on every call and was
    # saved only by the file's `chmod a-w`. If the read-only attach fails, that
    # is an error worth seeing.
    store.conn.execute("ATTACH DATABASE ? AS v1", (f"file:{v1_path}?mode=ro",))
    attached = True
    try:
        sql = """
            SELECT m.matchup_id, f2.pixel_id,
                   p.wmo, p.cycle, p.latitude, p.longitude, p.time,
                   f1.pab_version AS version_v1, f2.pab_version AS version_v2,
                   f1.chisq AS chisq_v1,   f2.chisq AS chisq_v2,
                   f1.accept_frac AS accept_v1, f2.accept_frac AS accept_v2,
                   b1.value AS bbp700_v1,  b2.value AS bbp700_v2,
                   c1.value AS chl_v1,     c2.value AS chl_v2,
                   a1.value AS aph_v1,     a2.value AS aph_v2,
                   bp2.value AS Bp_v2
            FROM matchups m
            JOIN profiles p ON p.profile_id = m.profile_id
            JOIN fits f2 ON f2.matchup_id = m.matchup_id
                        AND f2.algorithm = 'BING' AND f2.model_pair = ?
            JOIN v1.fits f1 ON f1.matchup_id = m.matchup_id
                           AND f1.pixel_id = f2.pixel_id
                           AND f1.algorithm = 'BING' AND f1.model_pair = ?
            LEFT JOIN fit_results    b2 ON b2.fit_id = f2.fit_id AND b2.quantity = ?
            LEFT JOIN v1.fit_results b1 ON b1.fit_id = f1.fit_id AND b1.quantity = ?
            LEFT JOIN fit_results    c2 ON c2.fit_id = f2.fit_id AND c2.quantity = ?
            LEFT JOIN v1.fit_results c1 ON c1.fit_id = f1.fit_id AND c1.quantity = ?
            LEFT JOIN fit_results    a2 ON a2.fit_id = f2.fit_id AND a2.quantity = ?
            LEFT JOIN v1.fit_results a1 ON a1.fit_id = f1.fit_id AND a1.quantity = ?
            LEFT JOIN fit_results    bp2 ON bp2.fit_id = f2.fit_id AND bp2.quantity = ?
            ORDER BY m.matchup_id
        """
        params = (
            model_pair, model_pair,
            q["bbp700"], q["bbp700"],
            q["chl"], q["chl"],
            q["Aph"], q["Aph"],
            q["Bp"],
        )
        return store.query_df(sql, params)
    finally:
        if attached:
            try:
                store.conn.execute("DETACH DATABASE v1")
            except Exception:
                pass

def gather_nasa_giop(store, *, model_pair: str = "ExpBPow"):
    """Assemble the "BING vs NASA GIOP" comparison table from the DB.

    One row per matchup that has **both** a BING fit (for ``model_pair``) and
    a NASA-GIOP ingest (``pab.fit.nasa_giop.build_nasa_giop``): BING's
    ``b_bp(700)`` alongside NASA's ``bbp_442``, plus NASA's ``adg_442`` and
    ``aph_442`` for reference. NASA's ``bbp`` is reported at 442 nm only,
    while BING's headline ``bbp`` is at 700 nm — this wavelength offset is a
    known, deliberately-unadjusted mismatch (design *Comparison & metrics*;
    ``claude_prompts/pace_giop_gsm.md`` Q3), so any comparison built on this
    frame must carry that caveat rather than treating the two as directly
    equivalent.

    Args:
        store: An open :class:`pab.db.store.Store`.
        model_pair: Which BING fit to pull (default ``"ExpBPow"``).

    Returns:
        A :class:`pandas.DataFrame` (empty when no matchup has both fits).
    """
    bbp_q = f"BING_{model_pair}_{DEFAULT_BBP_QUANTITY}"
    sql = """
        SELECT m.matchup_id, p.wmo, p.cycle, p.latitude, p.longitude, p.time,
               fbing.fit_id AS bing_fit_id,
               fb.value AS bbp_bing,
               fb.value_lo AS bbp_bing_lo, fb.value_hi AS bbp_bing_hi,
               fnasa.fit_id AS nasa_fit_id,
               fn_bbp.value AS bbp_442_nasa,
               fn_bbp.value_lo AS bbp_442_nasa_lo, fn_bbp.value_hi AS bbp_442_nasa_hi,
               fn_adg.value AS adg_442_nasa,
               fn_aph.value AS aph_442_nasa
        FROM matchups m
        JOIN profiles p ON p.profile_id = m.profile_id
        JOIN fits fbing ON fbing.matchup_id = m.matchup_id AND fbing.model_pair = ?
        JOIN fit_results fb
               ON fb.fit_id = fbing.fit_id AND fb.quantity = ?
        JOIN fits fnasa ON fnasa.matchup_id = m.matchup_id AND fnasa.algorithm = 'NASA_GIOP'
        LEFT JOIN fit_results fn_bbp
               ON fn_bbp.fit_id = fnasa.fit_id AND fn_bbp.quantity = 'NASA_GIOP_bbp_442'
        LEFT JOIN fit_results fn_adg
               ON fn_adg.fit_id = fnasa.fit_id AND fn_adg.quantity = 'NASA_GIOP_adg_442'
        LEFT JOIN fit_results fn_aph
               ON fn_aph.fit_id = fnasa.fit_id AND fn_aph.quantity = 'NASA_GIOP_aph_442'
        ORDER BY m.matchup_id
    """
    return store.query_df(sql, (model_pair, bbp_q))


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
