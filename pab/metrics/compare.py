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
#: The negative-blue QA count (``pab.fit.run.rrs_qa_quantities``), stored per
#: fit as ``BING_<model_pair>_n_neg_blue`` since O4.
NEG_BLUE_QUANTITY = "n_neg_blue"

#: The two ``b_bp`` reference wavelengths (nm) the BING-vs-NASA comparison has
#: to reconcile: NASA's GIOP reports ``bbp_442`` (``pab.pace.iop.IOP_REF_WAVE``
#: — the product variable is 442, not 443) and BING's headline ``bbp700`` is
#: at the float's ``BBP700`` wavelength.
GIOP_BBP_WAVE = 442.0
BING_BBP_WAVE = 700.0
#: GIOP's upper bound on the fitted power-law slope ``bbp_s``; a slope at the
#: ceiling is a pinned fit, not a measurement, so its 700 nm extrapolation is
#: the least constrained. :func:`giop_slope_ceiling_fraction` counts slopes
#: within ``GIOP_BBP_S_CEILING_TOL`` of it (``bbp_s >= 1.99``).
GIOP_BBP_S_CEILING = 2.0
GIOP_BBP_S_CEILING_TOL = 0.01
#: The shift formula as reader-facing text, built from the same constants the
#: code uses so the Methods/Comparisons wording cannot drift from
#: :func:`giop_bbp_to_700`.
GIOP_BBP_SHIFT_FORMULA = (
    f"b_bp({BING_BBP_WAVE:g}) = b_bp({GIOP_BBP_WAVE:g}) × "
    f"({GIOP_BBP_WAVE:g}/{BING_BBP_WAVE:g})^bbp_s"
)

#: Above this ``b_bp(700 nm)`` (m⁻¹) a retrieval is not a measurement of
#: seawater: open-ocean particulate backscatter at 700 nm spans roughly 1e-4 to
#: 1e-1 m⁻¹, so a value above 1 is a failed fit, not a bright scene. The 2.0
#: runaways (``versions/v2/high_bbp_outliers.md``) all sit at 5–9 × 10⁴ m⁻¹,
#: pressed against the ``Bnw`` prior ceiling; the 52nd-largest 2.0 value is
#: 0.03 m⁻¹, so the gate is not near anything real. :func:`gate_bbp` keeps
#: them out of every ``b_bp`` statistic (Q&A/Outliers 1 = B).
BBP_IMPLAUSIBLE = 1.0
#: Where the failed retrievals are documented; the report text points here.
BBP_OUTLIERS_URL = (
    "https://github.com/ocean-colour/PAB/blob/main/versions/v2/high_bbp_outliers.md"
)


def implausible_bbp(values):
    """Boolean mask: finite ``values`` above :data:`BBP_IMPLAUSIBLE`.

    ``NaN``/``None`` are *not* implausible (they are simply missing), so a
    column that is partly unretrieved is masked only where a number exists.
    """
    values = np.asarray(values, dtype=float)
    with np.errstate(invalid="ignore"):
        return np.isfinite(values) & (values > BBP_IMPLAUSIBLE)


def gate_bbp(df, col: str = "bbp_bing"):
    """Set ``col`` to ``NaN`` where it is implausible; touch nothing else.

    The one gate every ``b_bp`` statistic and figure in the report passes
    through: the summary headline, the density panel, both maps, the
    aggregates, the NASA-GIOP and 1.0-vs-2.0 comparisons. Only the named
    column changes -- the row stays (so the matchup count and the map's grey
    "without a ratio" dots are honest), the Chl of the same fit stays
    (Q&A/Outliers 6 = A) and the bounds columns stay, because nothing
    downstream reads a bound without the value. The exported tables and the
    gallery selection are built from the **ungated** frame on purpose: a
    reader filters on the ``bbp_bing_implausible`` column instead.

    Args:
        df: A gathered frame. A frame without ``col`` is returned as is.
        col: The satellite ``b_bp`` column (``"bbp_bing"`` in the matchup and
            NASA-GIOP frames, ``"bbp700_v2"`` in the version-pair frame).

    Returns:
        ``(df_gated, n_excluded)`` -- a copy with the masked values ``NaN``,
        and how many were masked.
    """
    if col not in df.columns:
        return df, 0
    mask = implausible_bbp(df[col])
    n = int(mask.sum())
    if not n:
        return df, 0
    out = df.copy()
    out[col] = out[col].astype(float)
    out.loc[mask, col] = np.nan
    return out, n


def giop_bbp_to_700(bbp_442, slope):
    """Shift NASA GIOP ``b_bp`` from 442 nm to 700 nm with its own slope.

    GIOP models particulate backscatter as a power law,
    ``b_bp(λ) = b_bp(442) × (442/λ)^bbp_s``, and reports both the 442 nm
    amplitude and the fitted per-pixel slope ``bbp_s``. Evaluating that model
    at BING's 700 nm puts the two retrievals at one wavelength without any
    assumption GIOP did not already make. The **single source** of the
    ``(442/700)^bbp_s`` factor: the value, its bounds and the report text all
    come through here.

    Args:
        bbp_442: NASA ``bbp_442`` (scalar or array; a ``None``/``NaN`` passes
            through as ``NaN``).
        slope: NASA ``bbp_s`` for the same pixel(s). ``None``/``NaN`` (the
            slope was not ingested) gives ``NaN`` -- there is no default
            slope, by design (Q&A/v2 Q1 = per-pixel).

    Returns:
        ``b_bp(700)`` as a float ``ndarray`` (0-d for scalar input).
    """
    bbp_442 = np.asarray(bbp_442, dtype=float)
    slope = np.asarray(slope, dtype=float)
    return bbp_442 * (GIOP_BBP_WAVE / BING_BBP_WAVE) ** slope


def giop_slope_ceiling_fraction(slope) -> float:
    """Fraction of finite GIOP slopes pinned at the ceiling (``bbp_s >= 1.99``).

    Computed, never quoted: the report states this number next to the 700 nm
    comparison because those pixels' extrapolation is the least constrained.
    ``NaN`` when no finite slope is present.
    """
    slope = np.asarray(slope, dtype=float)
    slope = slope[np.isfinite(slope)]
    if not slope.size:
        return float("nan")
    at_ceiling = slope >= GIOP_BBP_S_CEILING - GIOP_BBP_S_CEILING_TOL
    return float(np.count_nonzero(at_ceiling) / slope.size)


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


def _bing_versions(store) -> list[str]:
    """The distinct BING ``pab_version`` strings in ``store``, oldest first."""
    rows = store.query(
        "SELECT DISTINCT pab_version FROM fits "
        "WHERE algorithm = 'BING' AND pab_version IS NOT NULL"
    )
    return sorted({str(r["pab_version"]) for r in rows}, key=_version_key)


def newest_bing_version(store) -> str | None:
    """The newest ``pab_version`` among the store's BING fits, or ``None``.

    The v2 database holds BING **2.0** fits alongside NASA-GIOP **1.1** rows,
    and a store that has been fitted twice would hold 1.0 and 2.0 BING fits for
    the same matchup. Metrics must pick one, and the newest is the one the
    report is about. Since 2.0.1 the newest may be a **patch** version, so the
    report's gatherers resolve the whole :func:`version_family` instead and
    overlay the patch rows on their base (:func:`overlay_patch`).
    """
    versions = _bing_versions(store)
    return versions[-1] if versions else None


def is_patch_version(version) -> bool:
    """``"2.0.1"`` is a patch version (three components); ``"2.0"`` is not."""
    return len(str(version).split(".")) > 2


def base_version(version) -> str:
    """The base ``X.Y`` of a patch ``X.Y.Z``; a two-part version is its own base."""
    parts = str(version).split(".")
    return ".".join(parts[:2]) if len(parts) > 2 else str(version)


def version_family(store, version=None) -> tuple[str | None, list[str]]:
    """``(base, patches)`` -- the BING version the report is about and the
    patch versions that supersede parts of it.

    A **patch** version ``X.Y.Z`` (:data:`pab.config.pab_version` 2.0.1 is the
    first) is the same data, physics and matchup set as its base ``X.Y``, with
    some fits re-done under a changed configuration and stored as **new rows**
    next to the base rows. The report must show one value per matchup and
    pixel, so a patch row supersedes the base row of the same ``(matchup_id,
    pixel_id)`` -- that is :func:`overlay_patch` -- and the base rows stay in
    the database untouched (the design's provenance rule).

    Args:
        store: An open :class:`pab.db.store.Store`.
        version: The version to report. ``None`` → the store's newest BING
            version. A patch version reports its base plus every patch of
            that base up to and including itself; a base version given
            **explicitly** reports exactly itself (``("2.0", [])`` on the v2
            database), which is what ``--figure-version 2.0`` means.

    Returns:
        ``(base, patches)`` with ``patches`` ascending; ``("2.0", [])`` on a
        2.0-only store, ``("2.0", ["2.0.1"])`` on the v2 database after the
        re-fit, ``(None, [])`` on a store with no BING fit.
    """
    versions = _bing_versions(store)
    if version is None:
        if not versions:
            return None, []
        version = versions[-1]
    version = str(version)
    base = base_version(version)
    patches = [
        v
        for v in versions
        if is_patch_version(v)
        and base_version(v) == base
        and _version_key(v) <= _version_key(version)
    ]
    return base, patches


def resolve_versions(store, pab_version=None) -> list[str]:
    """The ``pab_version`` values a gatherer filters on.

    ``None`` → the newest :func:`version_family` (base + patches, to be
    overlaid); a string → exactly that version, no overlay; a list/tuple →
    those versions, overlaid. An empty list means "no version filter" (a
    store with no BING fit -- nothing to filter).
    """
    if pab_version is None:
        base, patches = version_family(store)
        return [base, *patches] if base is not None else []
    if isinstance(pab_version, (list, tuple, set)):
        return [str(v) for v in pab_version]
    return [str(pab_version)]


def _version_clause(column: str, versions: list[str]) -> tuple[str, tuple]:
    """``("AND col IN (?, ?)", params)``; no clause for an empty list."""
    if not versions:
        return "", ()
    marks = ", ".join("?" for _ in versions)
    return f"AND {column} IN ({marks})", tuple(versions)


OVERLAY_KEYS = ("matchup_id", "pixel_id")


def overlay_patch(df, *, version_col: str = "pab_version", carry=()):
    """Drop a base row where a patch row exists for the same matchup **and
    pixel**; keep the newest version per key.

    The one rule that makes a patch version visible in the report: among the
    rows of one ``(matchup_id, pixel_id)`` -- plus ``model_pair`` when the
    frame carries it -- only the rows at the newest :func:`_version_key` are
    kept. A patch fit of a *different* pixel of the same matchup supersedes
    nothing. Rows keep their own ``version_col`` value, so a frame says which
    rows are patched. A key that is ``NULL`` (an old fit with no
    ``pixel_id``) matches only other ``NULL`` keys of the same matchup.

    Args:
        df: A frame with :data:`OVERLAY_KEYS` and ``version_col`` (a frame
            without the version column, or empty, is returned unchanged).
        version_col: The column holding each row's ``pab_version``.
        carry: Column names whose value **on the superseded row** is kept on
            the superseding row as ``<name>_superseded`` (NaN where the row
            superseded nothing) -- how the exported table and the gallery
            still know the 2.0 value a 2.0.1 fit replaced.

    Returns:
        A new frame in the input order with the superseded rows removed and
        the ``carry`` columns added.
    """
    import numpy as np
    import pandas as pd

    carry = [c for c in carry if c in df.columns]
    if not len(df) or version_col not in df.columns:
        out = df.copy()
        for c in carry:
            out[f"{c}_superseded"] = np.nan
        return out
    keys = [k for k in OVERLAY_KEYS if k in df.columns]
    if "model_pair" in df.columns:
        keys.append("model_pair")
    if not keys:
        raise ValueError(f"overlay_patch needs {OVERLAY_KEYS} in the frame")
    work = df.copy()
    versions = sorted({str(v) for v in work[version_col]}, key=_version_key)
    rank = {v: i for i, v in enumerate(versions)}
    work["_vrank"] = work[version_col].astype(str).map(rank)
    groups = work.groupby(keys, dropna=False, sort=False)
    work["_gid"] = groups.ngroup()
    best = groups["_vrank"].transform("max")
    superseded = work["_vrank"] < best
    kept = work[~superseded].copy()
    if carry:
        sup = work[superseded].sort_values("_vrank", kind="stable")
        last = sup.groupby("_gid")[carry].last() if len(sup) else None
        for c in carry:
            if last is None:
                kept[f"{c}_superseded"] = np.nan
            else:
                # missing (nothing superseded) is NaN whatever the dtype --
                # pandas' string dtype has no other sentinel; test with isna()
                mapped = kept["_gid"].map(last[c])
                kept[f"{c}_superseded"] = (
                    mapped.astype(float) if pd.api.types.is_numeric_dtype(df[c]) else mapped
                )
    return kept.drop(columns=["_vrank", "_gid"]).reset_index(drop=True)


def fit_version_counts(store, pab_version=None) -> dict[str, int]:
    """``{pab_version: n}`` BING fits per version **after the overlay** --
    the summary page's "15,971 (15,920 at 2.0, 51 re-fitted at 2.0.1)",
    computed. Keys are in version order; a version with every row superseded
    is still listed with 0. All model pairs count (the overlay keys include
    ``model_pair`` when present).
    """
    versions = resolve_versions(store, pab_version)
    clause, params = _version_clause("pab_version", versions)
    df = store.query_df(
        "SELECT fit_id, matchup_id, pixel_id, model_pair, pab_version FROM fits "
        f"WHERE algorithm = 'BING' {clause}",
        params,
    )
    kept = overlay_patch(df)
    counts = kept["pab_version"].astype(str).value_counts() if len(kept) else {}
    order = versions or sorted({str(v) for v in df["pab_version"]}, key=_version_key)
    return {v: int(counts.get(v, 0)) for v in order}


#: Below this retrieved Chl (mg m⁻³) a BING fit has its ``A_ph`` at or near
#: the 10⁻⁶ prior floor: the absorption landed on ``A_dg`` instead (the
#: ``A_ph``-mirror mode of ``versions/v2/high_bbp_outliers.md`` §4). The
#: report *states* how many re-fitted runaways do this (Q&A/Outliers 11 = A);
#: it does not gate them (6 = A).
REFIT_CHL_FLOOR = 0.01


def patch_refit_summary(store, *, model_pair: str = "ExpBPow"):
    """The numbers behind the report's retrieval-failure note once a patch
    version exists -- every one computed from the store, none quoted.

    Returns ``None`` when the newest :func:`version_family` has no patch (the
    note then describes the base fits alone). Otherwise a dict:

    ``base``, ``patches``, ``prior_sets`` (the distinct ``fits.prior_set``
    of the patch rows), ``n_base`` / ``n_base_runaway`` / ``max_base_bbp`` /
    ``runaway_matchup_ids`` (the base fits and those above
    :data:`BBP_IMPLAUSIBLE`), ``n_patch`` (patch fits), ``n_patch_of_runaway``
    (patch fits whose superseded base fit was a runaway),
    ``n_patch_below_gate`` / ``n_patch_above_gate`` / ``n_patch_no_bbp``,
    ``n_runaway_unpatched`` (base runaways no patch row supersedes -- still
    gated), ``n_still_above_gate`` (what the gate excludes after the overlay:
    patched-and-still-above plus unpatched), ``n_patch_chl_low`` (patch fits
    with Chl below :data:`REFIT_CHL_FLOOR`), ``patch_success0`` (``[(wmo,
    cycle), …]`` of patch fits with ``success = 0``), ``n_base_success0``.
    """
    import numpy as np

    base, patches = version_family(store)
    if base is None or not patches:
        return None
    versions = [base, *patches]
    clause, params = _version_clause("f.pab_version", versions)
    bbp_q = f"BING_{model_pair}_{DEFAULT_BBP_QUANTITY}"
    chl_q = f"BING_{model_pair}_{DEFAULT_CHL_QUANTITY}"
    df = store.query_df(
        f"""
        SELECT f.fit_id, f.matchup_id, f.pixel_id, f.pab_version, f.success,
               f.prior_set, p.wmo, p.cycle,
               fb.value AS bbp, fc.value AS chl
        FROM fits f
        JOIN matchups m ON m.matchup_id = f.matchup_id
        JOIN profiles p ON p.profile_id = m.profile_id
        LEFT JOIN fit_results fb ON fb.fit_id = f.fit_id AND fb.quantity = ?
        LEFT JOIN fit_results fc ON fc.fit_id = f.fit_id AND fc.quantity = ?
        WHERE f.algorithm = 'BING' AND f.model_pair = ? {clause}
        ORDER BY f.matchup_id
        """,
        (bbp_q, chl_q, model_pair, *params),
    )
    for col in ("bbp", "chl", "success"):
        df[col] = df[col].astype(float)
    is_base = df["pab_version"].astype(str) == base
    base_df = df[is_base]
    patch_df = df[~is_base]
    base_bad = implausible_bbp(base_df["bbp"])
    runaway_ids = set(base_df.loc[base_bad, "fit_id"])
    kept = overlay_patch(df, carry=("fit_id", "bbp"))
    kept_patch = kept[kept["pab_version"].astype(str) != base]
    patched_runaways = kept_patch["fit_id_superseded"].isin(runaway_ids)
    superseded_ids = set(kept_patch["fit_id_superseded"].dropna())
    unpatched = int(len(runaway_ids - superseded_ids))
    pbbp = kept_patch["bbp"].to_numpy(dtype=float)
    above = int(implausible_bbp(pbbp).sum())
    below = int((np.isfinite(pbbp) & ~implausible_bbp(pbbp)).sum())
    pchl = patch_df["chl"].to_numpy(dtype=float)
    s0 = patch_df[patch_df["success"] == 0].sort_values(["wmo", "cycle"])
    return {
        "base": base,
        "patches": patches,
        "prior_sets": sorted({str(s) for s in patch_df["prior_set"] if s}),
        "n_base": int(len(base_df)),
        "n_base_runaway": int(base_bad.sum()),
        "max_base_bbp": float(np.nanmax(base_df["bbp"])) if len(base_df) else float("nan"),
        "runaway_matchup_ids": list(base_df.loc[base_bad, "matchup_id"]),
        "n_patch": int(len(patch_df)),
        "n_patch_of_runaway": int(patched_runaways.sum()),
        "n_patch_below_gate": below,
        "n_patch_above_gate": above,
        "n_patch_no_bbp": int((~np.isfinite(pbbp)).sum()),
        "n_runaway_unpatched": unpatched,
        "n_still_above_gate": above + unpatched,
        "n_patch_chl_low": int((np.isfinite(pchl) & (pchl < REFIT_CHL_FLOOR)).sum()),
        "patch_success0": [(int(w), int(c)) for w, c in zip(s0["wmo"], s0["cycle"], strict=True)],
        "n_base_success0": int((base_df["success"] == 0).sum()),
    }


#: The free-``B_p`` quantity of a 2.0-style fit (bare name; the
#: ``BING_<model_pair>_`` prefix is added per call).
BP_QUANTITY = "Bp"
#: The ``B_p`` range the packaged ``robust_hybrid`` emulator was trained over
#: (``robust.rt.emulator.load_default().domain``, feature ``B_p``, as read on
#: 2026-10-19). :func:`emulator_bp_domain` reads the live value and falls back
#: to this when ``robust`` is not importable. BING's free-``B_p`` prior is
#: [0.004, 0.05] and the seed 0.01, so the learned correction extrapolates in
#: ``B_p`` for most fits (``versions/v2/ztt_slice.md``; Q&A/Outliers 13 = A:
#: stated on the Methods page, not changed in this release).
EMULATOR_BP_TRAINED = (0.01026, 0.018)
#: Where the out-of-domain slice test is written up; the Methods page points here.
ZTT_SLICE_URL = "https://github.com/ocean-colour/PAB/blob/main/versions/v2/ztt_slice.md"


def emulator_bp_domain() -> tuple[float, float]:
    """``(lo, hi)`` of the default emulator's trained ``B_p`` range, read from
    ``robust`` (never retyped) -- :data:`EMULATOR_BP_TRAINED` when ``robust``
    is absent or its emulator carries no usable domain."""
    try:
        from robust.rt import emulator as _em

        i = list(_em.FEATURES).index("B_p")
        domain = np.asarray(_em.load_default().domain, dtype=float)
        lo, hi = float(domain[0, i]), float(domain[1, i])
        if np.isfinite(lo) and np.isfinite(hi) and lo < hi:
            return (lo, hi)
    except Exception:  # noqa: BLE001 — the page must build without robust
        pass
    return EMULATOR_BP_TRAINED


def forward_model_domain_summary(store, *, model_pair: str = "ExpBPow", domain=None):
    """How far the fits sit from the hybrid emulator's trained domain -- the
    numbers behind the Methods page's forward-model paragraph (Q&A/Outliers
    12–13 = A), computed from the store, none quoted.

    Over the overlaid :func:`version_family` (the fits the site shows):
    ``n`` fits with a ``B_p`` posterior median, ``n_inside`` / ``n_below`` /
    ``n_above`` / ``n_outside`` against ``domain`` (default
    :func:`emulator_bp_domain`), ``frac_outside``, the ``lo``/``hi`` used, and
    the view-zenith range of the fitted pixels (``theta_v_min`` /
    ``theta_v_max``, degrees; NaN when no geometry is stored) with
    ``n_off_nadir`` (``theta_v > 0``) of ``n_theta_v``. ``None`` when the
    store holds no BING fit with a ``B_p`` value (a 1.0-only store)."""
    lo, hi = domain if domain is not None else emulator_bp_domain()
    versions = resolve_versions(store)
    clause, params = _version_clause("f.pab_version", versions)
    bp_q = f"BING_{model_pair}_{BP_QUANTITY}"
    df = store.query_df(
        f"""
        SELECT f.fit_id, f.matchup_id, f.pixel_id, f.pab_version,
               r.value AS bp, mp.theta_v
        FROM fits f
        LEFT JOIN fit_results r ON r.fit_id = f.fit_id AND r.quantity = ?
        LEFT JOIN matchup_pixels mp ON mp.pixel_id = f.pixel_id
        WHERE f.algorithm = 'BING' AND f.model_pair = ? {clause}
        """,
        (bp_q, model_pair, *params),
    )
    if not len(df):
        return None
    kept = overlay_patch(df)
    bp = kept["bp"].to_numpy(dtype=float)
    ok = np.isfinite(bp)
    if not ok.any():
        return None
    bp = bp[ok]
    below = int((bp < lo).sum())
    above = int((bp > hi).sum())
    theta = kept["theta_v"].to_numpy(dtype=float)
    theta = theta[np.isfinite(theta)]
    return {
        "lo": float(lo),
        "hi": float(hi),
        "n": int(len(bp)),
        "n_inside": int(len(bp) - below - above),
        "n_below": below,
        "n_above": above,
        "n_outside": below + above,
        "frac_outside": float((below + above) / len(bp)),
        "theta_v_min": float(theta.min()) if len(theta) else float("nan"),
        "theta_v_max": float(theta.max()) if len(theta) else float("nan"),
        "n_theta_v": int(len(theta)),
        "n_off_nadir": int((theta > 0).sum()),
    }


def gather_matchups(store, *, model_pair: str = "ExpBPow", pab_version=None):
    """Assemble the per-matchup comparison table from the DB.

    One row per matchup that has a BING fit **for ``model_pair``**: the satellite
    ``b_bp(700)`` and ``chl`` (BING-retrieved, with credible bounds), the in-situ
    Argo ``b_bp(700)`` and ``chla``, the fit's reduced ``chisq``, and the float
    position/time (for stratification). The ``fits`` join is filtered by
    ``model_pair`` so a second model pair (or other fits on the same matchup) does
    not produce duplicate rows.

    The join is also filtered to ``algorithm = 'BING'`` and to **one version
    family** (:func:`version_family`): the base version plus its patch
    versions, with a patch row superseding the base row of the same matchup
    **and pixel** (:func:`overlay_patch`). Without the version filter a store
    holding both 1.0 and 2.0 fits for one matchup yields *two* rows, silently
    doubling every count and mixing two physics configurations into one
    scatter; without the overlay the v2 database after the 2.0.1 re-fit would
    show its 51 re-fitted matchups twice.

    Args:
        store: An open :class:`pab.db.store.Store`.
        model_pair: Which BING fit to pull (default ``"ExpBPow"`` →
            ``BING_ExpBPow_bbp700`` / ``BING_ExpBPow_chl``).
        pab_version: Which BING version to report. ``None`` (the default) is
            the store's newest :func:`version_family`, overlaid -- the one the
            report is about. A single version string selects exactly that
            version (no overlay); a list of versions is overlaid
            (:func:`resolve_versions`).

    Returns:
        A :class:`pandas.DataFrame` (empty when no matched fits exist), one
        row per matchup, each carrying its own ``pab_version``, ``fit_id`` and
        ``pixel_id``. The satellite values are **as stored** -- nothing is
        gated here -- plus a derived 0/1 column ``bbp_bing_implausible``
        (:func:`implausible_bbp`) so the exported table can be filtered by a
        reader; the report applies :func:`gate_bbp` itself where it computes
        statistics. A patched row also carries ``fit_id_superseded`` and
        ``bbp_bing_superseded`` -- the base fit it replaced and that fit's
        ``b_bp`` (``None``/NaN on every other row). ``n_neg_blue`` is the
        fit's negative-blue QA count (:data:`NEG_BLUE_QUANTITY`: the number
        of fitted bands with ``Rrs < 0`` at 400–450 nm), **NaN** for a fit
        that predates the quantity and has not been backfilled.
    """
    bbp_q = f"BING_{model_pair}_{DEFAULT_BBP_QUANTITY}"
    chl_q = f"BING_{model_pair}_{DEFAULT_CHL_QUANTITY}"
    neg_q = f"BING_{model_pair}_{NEG_BLUE_QUANTITY}"
    versions = resolve_versions(store, pab_version)
    clause, vparams = _version_clause("f.pab_version", versions)
    sql = f"""
        SELECT m.matchup_id, p.wmo, p.cycle, p.latitude, p.longitude, p.time,
               f.fit_id, f.pixel_id, f.chisq, f.pab_version,
               ms.bbp700 AS bbp_argo, ms.chla AS chla_argo,
               fb.value AS bbp_bing,
               fb.value_lo AS bbp_bing_lo, fb.value_hi AS bbp_bing_hi,
               fc.value AS chl_bing,
               fc.value_lo AS chl_bing_lo, fc.value_hi AS chl_bing_hi,
               fn.value AS n_neg_blue
        FROM matchups m
        JOIN profiles p ON p.profile_id = m.profile_id
        JOIN mld_summary ms ON ms.profile_id = m.profile_id
        JOIN fits f ON f.matchup_id = m.matchup_id
                   AND f.algorithm = 'BING'
                   AND f.model_pair = ?
                   {clause}
        LEFT JOIN fit_results fb
               ON fb.fit_id = f.fit_id AND fb.quantity = ?
        LEFT JOIN fit_results fc
               ON fc.fit_id = f.fit_id AND fc.quantity = ?
        LEFT JOIN fit_results fn
               ON fn.fit_id = f.fit_id AND fn.quantity = ?
        ORDER BY m.matchup_id
    """
    df = store.query_df(sql, (model_pair, *vparams, bbp_q, chl_q, neg_q))
    # A missing quantity row arrives as ``None`` (object dtype) from the LEFT
    # JOIN; the flag and the gate both want a float column, and so does the
    # QA count (NaN = not recorded for this fit).
    for col in ("bbp_bing", "n_neg_blue"):
        if col in df.columns:
            df[col] = df[col].astype(float)
    # The patch overlay (Q&A/Outliers 1 = C): one row per matchup+pixel, the
    # newest version's. Applied even to a single-version frame so the two
    # ``_superseded`` columns always exist in the exported table.
    df = overlay_patch(df, carry=("fit_id", "bbp_bing"))
    df["bbp_bing_implausible"] = implausible_bbp(df.get("bbp_bing", [])).astype(int)
    return df


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

    The 2.0 side is the store's newest :func:`version_family`, overlaid: where
    a 2.0.1 re-fit supersedes a 2.0 fit, the pair is 1.0 vs **2.0.1** and
    ``version_v2`` says so (without the overlay such a matchup would appear
    twice, once per version).

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
    versions = resolve_versions(store)
    clause, vparams = _version_clause("f2.pab_version", versions)
    store.conn.execute("ATTACH DATABASE ? AS v1", (f"file:{v1_path}?mode=ro",))
    attached = True
    try:
        sql = f"""
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
                        {clause}
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
            model_pair, *vparams, model_pair,
            q["bbp700"], q["bbp700"],
            q["chl"], q["chl"],
            q["Aph"], q["Aph"],
            q["Bp"],
        )
        df = store.query_df(sql, params)
        # The patch overlay on the 2.0 side; the 1.0 side is one row per
        # pixel already (the frozen release holds one version).
        return overlay_patch(df, version_col="version_v2")
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
    ``b_bp(700)`` alongside NASA's ``bbp_442`` (kept as stored) **and** the
    same value shifted to 700 nm (``bbp_700_nasa`` + ``_lo``/``_hi``) with
    NASA's own per-pixel power-law slope ``bbp_s`` via
    :func:`giop_bbp_to_700`, plus NASA's ``adg_442`` and ``aph_442`` for
    reference. The 700 nm columns are **derived here, never persisted**
    (Q&A/v2 Q2): they are reproducible from the stored rows and carry no new
    ``pab_version``. Where the slope row is missing (the ``LEFT JOIN`` finds
    none) they are ``NaN`` rather than a fixed-slope guess.

    The BING side is the store's newest :func:`version_family`, overlaid
    (:func:`overlay_patch`), and each row carries the BING fit's
    ``pab_version`` and ``pixel_id`` -- so a re-fitted matchup appears once,
    with its 2.0.1 value, not once per version.

    Args:
        store: An open :class:`pab.db.store.Store`.
        model_pair: Which BING fit to pull (default ``"ExpBPow"``).

    Returns:
        A :class:`pandas.DataFrame` (empty when no matchup has both fits).
    """
    bbp_q = f"BING_{model_pair}_{DEFAULT_BBP_QUANTITY}"
    versions = resolve_versions(store)
    clause, vparams = _version_clause("fbing.pab_version", versions)
    sql = f"""
        SELECT m.matchup_id, p.wmo, p.cycle, p.latitude, p.longitude, p.time,
               fbing.fit_id AS bing_fit_id, fbing.pixel_id, fbing.pab_version,
               fb.value AS bbp_bing,
               fb.value_lo AS bbp_bing_lo, fb.value_hi AS bbp_bing_hi,
               fnasa.fit_id AS nasa_fit_id,
               fn_bbp.value AS bbp_442_nasa,
               fn_bbp.value_lo AS bbp_442_nasa_lo, fn_bbp.value_hi AS bbp_442_nasa_hi,
               fn_s.value AS bbp_s_nasa,
               fn_adg.value AS adg_442_nasa,
               fn_aph.value AS aph_442_nasa
        FROM matchups m
        JOIN profiles p ON p.profile_id = m.profile_id
        JOIN fits fbing ON fbing.matchup_id = m.matchup_id
                       AND fbing.algorithm = 'BING' AND fbing.model_pair = ?
                       {clause}
        JOIN fit_results fb
               ON fb.fit_id = fbing.fit_id AND fb.quantity = ?
        JOIN fits fnasa ON fnasa.matchup_id = m.matchup_id AND fnasa.algorithm = 'NASA_GIOP'
        LEFT JOIN fit_results fn_bbp
               ON fn_bbp.fit_id = fnasa.fit_id AND fn_bbp.quantity = 'NASA_GIOP_bbp_442'
        LEFT JOIN fit_results fn_s
               ON fn_s.fit_id = fnasa.fit_id AND fn_s.quantity = 'NASA_GIOP_bbp_s'
        LEFT JOIN fit_results fn_adg
               ON fn_adg.fit_id = fnasa.fit_id AND fn_adg.quantity = 'NASA_GIOP_adg_442'
        LEFT JOIN fit_results fn_aph
               ON fn_aph.fit_id = fnasa.fit_id AND fn_aph.quantity = 'NASA_GIOP_aph_442'
        ORDER BY m.matchup_id
    """
    df = store.query_df(sql, (model_pair, *vparams, bbp_q))
    df = overlay_patch(df)
    # The 700 nm columns, derived with the per-pixel slope. The bounds scale by
    # the same factor (the slope's own uncertainty is not propagated: NASA
    # reports none), so a NaN slope leaves all three NaN together. A missing
    # slope row arrives as ``None`` (object dtype); make the column numeric so
    # the ceiling fraction and the exported table see NaN, not ``None``.
    df["bbp_s_nasa"] = df["bbp_s_nasa"].astype(float)
    for src, dst in (
        ("bbp_442_nasa", "bbp_700_nasa"),
        ("bbp_442_nasa_lo", "bbp_700_nasa_lo"),
        ("bbp_442_nasa_hi", "bbp_700_nasa_hi"),
    ):
        df[dst] = giop_bbp_to_700(df[src], df["bbp_s_nasa"])
    return df


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
