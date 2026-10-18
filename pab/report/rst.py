"""Programmatic reStructuredText generation for the reporting site (Stage 7).

Builds a **small, fixed set of aggregate pages** from the SQLite store — a
landing/summary page, a binned-results page, and a methods page — never one page
per matchup (the design's hard constraint at ~10⁴ matchups; per-matchup detail is
reached on demand through the interactive figures). Pure string generation
(unit-testable); :func:`build_site` writes the pages to an output directory
*outside* the developer docs.
"""

from __future__ import annotations

import logging
import shutil
from datetime import UTC, datetime
from pathlib import Path

from pab.config import pab_version as _pab_version
from pab.metrics import compare

_log = logging.getLogger("pab.report")

#: Where per-matchup figures are copied inside the site source tree so Sphinx
#: serves them verbatim (``html_static_path``). The same relative URL works for
#: the inline gallery, the per-matchup download links, and the scatter's
#: tap-to-open — one mechanism, no reliance on Sphinx's ``_images`` renaming.
FIGURE_URL_COL = "figure_url"
_STATIC_FIGURES = "_static/figures"
#: Above this matchup count the inline gallery is suppressed (the design's
#: no-page-explosion constraint); detail then comes via tap-to-open + downloads.
MAX_INLINE_FIGURES = 50

#: The representative galleries shown above :data:`MAX_INLINE_FIGURES`
#: (Q&A/v2 Q4 = A): the fit figures nearest these percentiles of
#: ``log10(satellite / float b_bp)`` — plus one runaway and one matchup from
#: each of the clearest and the most productive ``chl_bing`` terciles — and one
#: scene quick-look per :func:`pab.metrics.compare.add_strata` region, at most
#: :data:`MAX_SCENE_REGIONS` of them.
REPRESENTATIVE_PERCENTILES = (5, 25, 50, 75, 95)
MAX_SCENE_REGIONS = 6
#: Longest side, in pixels, of a gallery file staged into the site. The
#: committed site must stay small, so every staged copy is downscaled to this.
GALLERY_MAX_SIDE = 1200

#: Above this matchup count the Comparisons page renders **static** Matplotlib
#: scatter/map PNGs instead of the interactive Bokeh embed. An all-points Bokeh
#: embed of ~10⁴ matchups is ~14 MB of inline JSON — too big to commit — so at
#: scale the committed site keeps small static figures and points per-matchup
#: detail at the downloadable summary table (the "keep git small" constraint).
MAX_INTERACTIVE_MATCHUPS = 2000

#: The fixed set of generated page stems (there is no per-matchup page). The
#: matchup results are split across topical pages so no single page is overloaded.
PAGE_STEMS = (
    "index",
    "summary",
    "comparisons",
    "figures",
    "aggregates",
    "methods",
    "downloads",
)


def _fmt(x, spec: str = "{:.3g}") -> str:
    import numpy as np

    if x is None or (isinstance(x, float) and np.isnan(x)):
        return "—"
    if isinstance(x, float):
        return spec.format(x)
    return str(x)


def rst_table(df, *, columns=None, float_fmt: str = "{:.3g}") -> str:
    """Render a DataFrame as a reStructuredText ``list-table``."""
    cols = list(columns) if columns is not None else list(df.columns)
    lines = [
        ".. list-table::",
        "   :header-rows: 1",
        "",
        "   * - " + "\n     - ".join(str(c) for c in cols),
    ]
    for _, row in df.iterrows():
        cells = [_fmt(row[c], float_fmt) for c in cols]
        lines.append("   * - " + "\n     - ".join(cells))
    return "\n".join(lines) + "\n"


def _heading(text: str, char: str = "=") -> str:
    return f"{text}\n{char * len(text)}\n"


def summary_page(store, *, pab_version: str | None = None, compare_db=None) -> str:
    """The landing/summary page: coverage counts + headline sat-vs-float metrics.

    ``compare_db`` (the frozen v1 database) adds the **1.0 vs 2.0** headline
    block — the result of the re-analysis, which belongs above the fold rather
    than only on the Comparisons page.
    """
    pab_version = pab_version or _pab_version
    # NOTE two different versions are in play on this page and conflating them
    # would be a quiet error: `pab_version` above is the *running code's*
    # version, for the provenance line, while `_bing_version` is the version of
    # the *fits being reported*. They differ whenever the report is regenerated
    # by newer code over an older run. Resolve the fit version once and pass it
    # to every consumer, so the counts and the table can never describe
    # different sets.
    _bing_version = compare.newest_bing_version(store)
    df = compare.gather_matchups(store, pab_version=_bing_version)
    n_matchups = store.count("matchups")
    n_floats = store.count("floats")
    # Only the BING retrievals — the parallel NASA_GIOP rows are baseline
    # ingests, not fits, and would silently double this count.
    #
    # And only ONE pab_version: a store fitted twice holds a 1.0 and a 2.0 BING
    # fit for the same matchup, so without this the headline "BING fits" would
    # exceed the matchup count and mix two physics configurations. The version
    # shown is the one resolved above and handed to `gather_matchups`, so this
    # count and the metrics table always describe the same set of fits.
    n_fits = store.query(
        "SELECT COUNT(*) AS n FROM fits WHERE algorithm = 'BING' "
        "AND (? IS NULL OR pab_version = ?)",
        (_bing_version, _bing_version),
    )[0]["n"]
    # The b_bp headline is computed on the gated frame (Q&A/Outliers 1 = B);
    # the Chl headline is not gated (Q&A/Outliers 6 = A) and `gate_bbp` only
    # touches `bbp_bing`, so one gated frame serves both.
    df, bbp_clause = _gated(df, "bbp_bing")
    bbp = (
        compare.log_comparison(df.get("bbp_bing"), df.get("bbp_argo"))
        if len(df)
        else {}
    )
    chl = (
        compare.log_comparison(df.get("chl_bing"), df.get("chla_argo"))
        if len(df)
        else {}
    )

    out = [_heading("PAB matchup results"), ""]
    out.append(
        "PACE ↔ BGC-Argo matchups: satellite vs. in-situ backscatter "
        "(``b_bp``) and chlorophyll, retrieved with BING. Built from "
        f"``pab_version`` ``{pab_version}`` on "
        f"{datetime.now(UTC).date().isoformat()}.\n"
    )
    out.append(
        "**PAB** validates ocean-colour retrievals from NASA's **PACE/OCI** "
        "satellite against in-situ profiles from autonomous **BGC-Argo** floats. "
        "For each float profile we find the closest-in-space-and-time PACE scene, "
        "extract the remote-sensing reflectance (``Rrs``) at the float, retrieve "
        "the inherent optical properties with **BING**, and compare the "
        "satellite-derived particulate backscatter ``b_bp`` and chlorophyll "
        "against the float's mixed-layer values. The headline numbers below "
        "summarise that comparison; the :doc:`comparisons <comparisons>` and "
        ":doc:`figures <figures>` give the per-matchup detail, and the "
        ":doc:`Methods <methods>` page explains how to read them.\n"
    )
    import numpy as np

    n_profiles = store.count("profiles")
    sep = store.query("SELECT distance_km, dtime_hours FROM matchups")
    dist = np.array(
        [r["distance_km"] for r in sep if r["distance_km"] is not None], dtype=float
    )
    dt = np.array(
        [r["dtime_hours"] for r in sep if r["dtime_hours"] is not None], dtype=float
    )
    out.append(_heading("Coverage", "-"))
    cov = (
        f"- **Profiles ingested:** {n_profiles}\n"
        f"- **Matchups:** {n_matchups}\n- **Floats:** {n_floats}\n"
        f"- **BING fits:** {n_fits}"
        + (f" (``pab_version`` {_bing_version})\n" if _bing_version else "\n")
    )
    if dist.size:
        cov += f"- **Median separation:** {_fmt(float(np.median(dist)))} km\n"
    if dt.size:
        cov += f"- **Median Δtime:** {_fmt(float(np.median(dt)))} h\n"
    out.append(cov)
    out.append(_heading("Headline comparison (b_bp 700 nm)", "-"))
    if bbp.get("n"):
        out.append(
            f"- n = {bbp['n']}; median sat/float ratio = "
            f"{_fmt(bbp['median_ratio'])}; Spearman ρ = {_fmt(bbp['spearman'])}; "
            f"log10 bias = {_fmt(bbp['log_bias'])}, RMS = {_fmt(bbp['log_rms'])}. "
            f"{bbp_clause} — see the :doc:`Methods <methods>` page.\n"
        )
    else:
        out.append("- (no matchups with a BING fit yet)\n")
    if chl.get("n"):
        out.append(_heading("Chlorophyll", "-"))
        out.append(
            f"- n = {chl['n']}; median sat/float ratio = "
            f"{_fmt(chl['median_ratio'])}; Spearman ρ = {_fmt(chl['spearman'])}.\n"
        )
    nasa_df, nasa_clause = _gated(compare.gather_nasa_giop(store), "bbp_bing")
    nasa = (
        compare.log_comparison(nasa_df["bbp_700_nasa"], nasa_df["bbp_bing"])
        if len(nasa_df)
        else {}
    )
    if nasa.get("n"):
        out.append(_heading("BING vs NASA GIOP (b_bp)", "-"))
        out.append(
            f"- n = {nasa['n']}; median NASA(700 nm)/BING(700 nm) ratio = "
            f"{_fmt(nasa['median_ratio'])}; Spearman ρ = {_fmt(nasa['spearman'])}; "
            f"{nasa_clause}. "
            "NASA's ``b_bp`` is shifted from 442 nm to 700 nm with its own "
            "per-pixel slope — see the :doc:`comparisons <comparisons>` and "
            ":doc:`Methods <methods>` pages for the formula and its caveat.\n"
        )
    out.append(_version_headline(store, compare_db))
    out.append(_heading("Explore the results", "-"))
    out.append(
        "- :doc:`Comparisons <comparisons>` — interactive ``b_bp`` & Chl scatters "
        "and the matchup map.\n"
        "- :doc:`Figures <figures>` — per-matchup fit, PACE scene, and Argo Q&A "
        "thumbnails.\n"
        "- :doc:`Aggregate results <aggregates>` — binned statistics + a matchup "
        "quality table.\n"
        "- :doc:`Methods <methods>` — how the analysis works and how to read these "
        "numbers.\n"
        "- :doc:`Downloads <downloads>` — the summary tables (CSV/Parquet).\n"
    )
    return "\n".join(out)


def _version_headline(store, compare_db) -> str:
    """The 1.0-vs-2.0 headline block for the summary page (``""`` without a v1).

    Only ``b_bp`` and Chl, only the median ratio and n — the full treatment is
    the Comparisons section. Kept to the numbers that answer "did the inelastic
    physics move the answer, and by how much".
    """
    if not compare_db or not Path(compare_db).is_file():
        return ""
    try:
        df = compare.gather_version_pair(store, str(compare_db))
    except Exception:  # noqa: BLE001 — a bad v1 must not break the whole build
        _log.warning(
            "1.0-vs-2.0 summary headline skipped: could not read %s", compare_db,
            exc_info=True,
        )
        return ""
    if not len(df):
        return ""
    df, bbp_clause = _gated(df, "bbp700_v2")
    lines = []
    for key, label in (("bbp700", "b_bp(700 nm)"), ("chl", "chlorophyll")):
        c1, c2 = f"{key}_v1", f"{key}_v2"
        if c1 not in df or c2 not in df:
            continue
        st = compare.log_comparison(df[c2], df[c1])
        if st.get("n"):
            tail = f"; {bbp_clause}" if key == "bbp700" else ""
            lines.append(
                f"- **{label}** — median 2.0/1.0 ratio = "
                f"{_fmt(st['median_ratio'])} (n = {st['n']:,}{tail})\n"
            )
    if not lines:
        return ""
    out = [_heading("1.0 vs 2.0 (elastic vs inelastic)", "-")]
    out.append(
        f"The same {len(df):,} matchups and the same pixels, retrieved with the "
        "elastic (1.0) and inelastic (2.0) forward model — what the re-analysis "
        "changed:\n"
    )
    out.extend(lines)
    out.append(
        "The :doc:`Comparisons <comparisons>` page has the scatters, the full "
        "statistics, and what exactly differs between the two configurations.\n"
    )
    return "\n".join(out)

def interactive_figures(df, *, artifact_url_col: str = FIGURE_URL_COL) -> str:
    """Standalone Bokeh **scatter + map** for the landing page (Bokeh-guarded).

    The design's route to per-matchup detail without per-matchup pages: a
    satellite-vs-float ``b_bp`` log-log scatter (hover for values, **tap** to open
    that matchup's fit figure when ``artifact_url_col`` is present) and a matchup
    map coloured by the per-matchup sat/float ratio. Returns ``""`` when ``bokeh``
    is unavailable or there are no matchups, so the page still builds.
    """
    if not len(df):
        return ""
    # The gate applies to the interactive page too: the b_bp scatter and the
    # map are b_bp figures; the Chl scatter reads an untouched column.
    df, bbp_clause = _gated(df, "bbp_bing")
    try:
        import numpy as np

        from pab.report import interactive

        url_col = artifact_url_col if artifact_url_col in df.columns else None
        scatter = interactive.comparison_scatter(df, artifact_url_col=url_col)
        chl = _chl_scatter(df, interactive, np, url_col)
        dfm = df.copy()
        with np.errstate(divide="ignore", invalid="ignore"):
            dfm["ratio"] = dfm["bbp_bing"].to_numpy(dtype=float) / dfm[
                "bbp_argo"
            ].to_numpy(dtype=float)
        mp = interactive.matchup_map(dfm, color_col="ratio")
    except ImportError:
        return ""

    out = [
        "Satellite-vs-float ``b_bp`` (700 nm) and chlorophyll, plus the matchup "
        "map. **Hover** a point for its values; **tap** a scatter point to open "
        "that matchup's fit figure. Per-matchup detail is reached here, not as "
        f"individual pages. ``b_bp``: {bbp_clause}.\n"
    ]
    out.append(interactive.raw_html(scatter))
    if chl is not None:
        out.append(interactive.raw_html(chl))
    out.append(interactive.raw_html(mp))
    return "\n".join(out)


def _chl_scatter(df, interactive, np, url_col):
    """The satellite-vs-in-situ **Chl** scatter (``chl_bing`` vs Argo ``chla``),
    overlaying the OC4 band-ratio Chl (``chl_oc``) when present. Returns ``None``
    when the frame has no finite Chl pair to plot."""
    if not {"chl_bing", "chla_argo"} <= set(df.columns):
        return None
    pairs = df[["chl_bing", "chla_argo"]].to_numpy(dtype=float)
    if not np.isfinite(pairs).all(axis=1).any():
        return None
    extra = (
        [("chl_oc", "OC4 band-ratio Chl")]
        if "chl_oc" in df.columns
        and np.isfinite(df["chl_oc"].to_numpy(dtype=float)).any()
        else None
    )
    return interactive.comparison_scatter(
        df,
        sat_col="chl_bing",
        insitu_col="chla_argo",
        label="Chl",
        artifact_url_col=url_col,
        extra_series=extra,
    )


#: What 2.0 changed, **stated once** and reused by the Comparisons section, the
#: Methods page, and the summary headline — three places that would otherwise
#: drift apart. Every claim here is read back off the `fits` rows of the v2
#: database (`rt_backend`, `include_raman`, `include_chl_fl`,
#: `include_cdom_fl`, `phi_c`, `fit_bp`, `wave_min`/`wave_max`), not from the
#: plan: CDOM fluorescence was *planned* and is **off** in the run, and the fit
#: window is **unchanged**, so both are stated as such rather than listed as
#: improvements.
V2_CHANGES = (
    "**What changed in 2.0.** The 1.0 fits used the *elastic* Gordon "
    "radiative-transfer model: ``Rrs`` is produced by absorption and elastic "
    "scattering alone. 2.0 re-fits the same spectra with an **inelastic** "
    "forward model:\n"
    "\n"
    "- **Radiative-transfer backend** — ``robust_hybrid`` (a neural-network "
    "emulator of a full RT solution) replaces the analytic ``gordon`` "
    "parameterisation.\n"
    "- **Raman scattering** — water molecules re-emit absorbed blue light at "
    "longer wavelengths; included.\n"
    "- **Chlorophyll fluorescence** — the ~685 nm phytoplankton emission "
    "line, at quantum yield ``phi_C = 0.02``; included.\n"
    "- **CDOM fluorescence** — available in the model but **off** in this "
    "run, so none of the results below include it.\n"
    "- **Free ``B_p``** — the backscatter phase-function parameter, held "
    "fixed in 1.0, is a sixth fitted parameter in 2.0 with a uniform prior "
    "over ``[0.004, 0.05]``.\n"
    "\n"
    "The **fit window is unchanged** at 400–700 nm. The red edge (713/719 nm, "
    "where Raman and fluorescence are strongest) was evaluated and "
    "deliberately left out: on a 97-matchup diagnostic sample Rrs(719) is "
    "negative or noise-dominated on **44 %** of matchups, so including it "
    "would feed the inelastic terms mostly noise.\n"
)

#: The free-``B_p`` prior bounds, read from the fitter rather than restated, so
#: the edges drawn on the histogram cannot drift from the ones actually used.
def _bp_prior_range():
    try:
        from bing.rt import defs

        return (float(defs.BP_PRIOR_PMIN), float(defs.BP_PRIOR_PMAX))
    except Exception:  # noqa: BLE001 — the figure is still worth drawing
        return None


#: The GIOP slope-ceiling caveat, shared by the Comparisons note and the
#: Methods page so the two cannot drift. The *fraction* is computed per frame
#: (:func:`_nasa_bbp_note`), never quoted.
_NASA_BBP_CEILING_CAVEAT = (
    "such a slope is a pinned fit rather than a measurement, so those pixels' "
    "700 nm values are the least constrained."
)


def _nasa_bbp_note(df) -> str:
    """The reader-facing note on the 700 nm shift, with its numbers computed
    from ``df`` (a :func:`~pab.metrics.compare.gather_nasa_giop` frame).

    States the formula (one source: :data:`~pab.metrics.compare.GIOP_BBP_SHIFT_FORMULA`),
    that the slope is NASA's own per-pixel ``bbp_s``, the fraction of slopes
    at GIOP's ceiling (``bbp_s >= 1.99``), and -- once, for continuity with
    the previous release, which compared the two wavelengths as stored -- the
    unadjusted 442-vs-700 median ratio from the same frame.
    """
    import numpy as np

    ceiling = compare.giop_slope_ceiling_fraction(df["bbp_s_nasa"])
    raw = compare.log_comparison(df["bbp_442_nasa"], df["bbp_bing"])
    n_slope = int(np.isfinite(np.asarray(df["bbp_s_nasa"], dtype=float)).sum())
    out = (
        "**Wavelength note:** NASA reports ``b_bp`` at **442 nm** while BING's "
        "headline ``b_bp`` is at **700 nm** (chosen to match the float "
        "``BBP700``). NASA's value is shifted to 700 nm with GIOP's own "
        f"per-pixel power-law slope ``bbp_s``: ``{compare.GIOP_BBP_SHIFT_FORMULA}`` "
        "(the credible bounds scale by the same factor), so the comparison "
        "below is at one wavelength."
    )
    if np.isfinite(ceiling):
        out += (
            f" {ceiling * 100:.1f} % of the {n_slope:,} slopes sit at GIOP's "
            f"ceiling of {compare.GIOP_BBP_S_CEILING:.1f} — "
            + _NASA_BBP_CEILING_CAVEAT
        )
    if raw.get("n") and np.isfinite(raw["median_ratio"]):
        out += (
            " For continuity with the previous release, which compared the two "
            "as stored, the unadjusted median NASA(442)/BING(700) ratio on the "
            f"same matchups is {_fmt(raw['median_ratio'])}."
        )
    return out


def _density_caption(df, sat_col: str, insitu_col: str) -> str:
    """The clause every density panel's caption carries: what is drawn, and
    how many matchups the axes leave out (counted from the same rule the
    figure used, so the caption's ``N`` is the title's ``N``)."""
    from pab.plotting import population

    n_off = population.offscale_count(df, sat_col, insitu_col)
    outside = (
        "1 matchup lies outside the axes and is counted"
        if n_off == 1
        else f"{n_off:,} matchups lie outside the axes and are counted"
    )
    return (
        f"Filled cells where ≥ {population.DENSITY_MIN_COUNT} matchups fall in a "
        f"cell, individual points elsewhere; {outside} in the statistics. The "
        "dashed line is the median ratio; the solid line is 1:1."
    )


def nasa_giop_section(
    store,
    *,
    outdir=None,
    sortable: bool = True,
    max_interactive: int = MAX_INTERACTIVE_MATCHUPS,
) -> str:
    """The **BING vs NASA GIOP** section for the Comparisons page.

    Mirrors the satellite-vs-float ``b_bp`` treatment: a log-log scatter
    (interactive Bokeh below ``max_interactive`` matchups, a static PNG above
    it) plus :func:`~pab.metrics.compare.log_comparison` summary stats, built
    on :func:`~pab.metrics.compare.gather_nasa_giop`. The comparison is at
    **700 nm on both sides** (NASA's 442 nm value shifted with its own
    per-pixel slope, see :func:`_nasa_bbp_note`); the figure and the stats
    use the derived ``bbp_700_nasa`` column. Returns ``""`` when the store
    holds no NASA-GIOP ingest (the section simply doesn't appear).
    """
    df = compare.gather_nasa_giop(store)
    if not len(df):
        return ""
    # BING's runaways are gated out of this comparison too (the NASA side has
    # no such failure mode); the note's continuity ratio, the stats line and
    # the panel all read the gated frame, so one count describes all three.
    df, bbp_clause = _gated(df, "bbp_bing")
    stats = compare.log_comparison(df["bbp_700_nasa"], df["bbp_bing"])

    out = [_heading("BING vs NASA GIOP (L2 IOP)", "-"), ""]
    out.append(
        "The same PACE overpasses, retrieved two ways: **BING** (this project) "
        "against NASA's own **GIOP** retrieval, read from the operational "
        "``PACE_OCI_L2_IOP`` product at the *same pixel* used for the BING fit. "
        "See the :doc:`Methods <methods>` page for the product details and "
        "provenance.\n"
    )
    out.append(_nasa_bbp_note(df) + "\n")
    if stats.get("n"):
        out.append(
            f"- n = {stats['n']}; median NASA(700)/BING(700) ratio = "
            f"{_fmt(stats['median_ratio'])} "
            f"(IQR {_fmt(stats['ratio_iqr_lo'])}–{_fmt(stats['ratio_iqr_hi'])}); "
            f"Spearman ρ = {_fmt(stats['spearman'])}; "
            f"log10 offset = {_fmt(stats['log_bias'])}, "
            f"RMS = {_fmt(stats['log_rms'])}; BING {bbp_clause}.\n"
        )

    if outdir is not None and len(df) > max_interactive:
        try:
            from pab.plotting import population

            dest = Path(outdir) / "_static" / "comparisons"
            dest.mkdir(parents=True, exist_ok=True)
            # Density-plus-dots (Q&A/v2 Q5), its own hue so the page reads as
            # three different comparisons. The frame is gated, so the BING
            # runaways are out of the panel and its statistics alike; the
            # caption says how many (Q&A/Outliers 1 = B).
            population.density_scatter(
                df,
                "bbp_700_nasa",
                "bbp_bing",
                outfile=dest / "nasa_giop_bbp_scatter.png",
                xlabel="BING $b_{bp}$(700 nm) [m$^{-1}$]",
                ylabel="NASA GIOP $b_{bp}$(700 nm) [m$^{-1}$]",
                cmap="Purples",
            )
            out.append(
                ".. figure:: _static/comparisons/nasa_giop_bbp_scatter.png\n"
                "   :width: 520px\n\n"
                "   NASA GIOP ``b_bp`` shifted to 700 nm vs BING ``b_bp`` "
                "(700 nm), log-log; axes span the central 99 % of the values. "
                + _density_caption(df, "bbp_700_nasa", "bbp_bing")
                + f" BING {bbp_clause}.\n"
            )
        except Exception:  # noqa: BLE001 — a bad panel must not break the build
            pass
    elif sortable:
        try:
            from pab.report import interactive

            fig = interactive.comparison_scatter(
                df,
                sat_col="bbp_700_nasa",
                insitu_col="bbp_bing",
                title="NASA GIOP b_bp(700, shifted from 442) vs BING b_bp(700)",
                xlabel="BING b_bp(700 nm)",
                ylabel="NASA GIOP b_bp(700 nm)",
            )
            out.append(interactive.raw_html(fig))
        except ImportError:
            out.append(
                "(The interactive BING-vs-NASA scatter requires ``bokeh`` at "
                "build time.)\n"
            )
    return "\n".join(out)


def version_section(
    store,
    compare_db,
    *,
    outdir=None,
    sortable: bool = True,
    max_interactive: int = MAX_INTERACTIVE_MATCHUPS,
) -> str:
    """The **1.0 vs 2.0** section for the Comparisons page.

    The same matchups, the same pixels, retrieved with the elastic (1.0) and
    the inelastic (2.0) forward model — the headline result of the v2
    re-analysis. Mirrors :func:`nasa_giop_section`: ``bbp700`` and ``chl``
    scatters (interactive Bokeh below ``max_interactive`` matchups, static PNGs
    above), :func:`~pab.metrics.compare.log_comparison` stats, plus a ``B_p``
    posterior-median histogram — ``B_p`` exists only in 2.0, so it has no
    scatter, only a distribution.

    Unlike the NASA section, both axes here are **the same quantity at the same
    wavelength from the same pixel**; the only difference is the physics. That
    is what makes a ratio readable as a result rather than a consistency check.

    Returns ``""`` when ``compare_db`` is ``None``, missing, or shares no
    fitted matchup with the store — the section simply doesn't appear.
    """
    if not compare_db or not Path(compare_db).is_file():
        return ""
    try:
        df = compare.gather_version_pair(store, str(compare_db))
    except Exception:  # noqa: BLE001 — a bad v1 must not break the whole build
        # But it must not vanish silently either: without this the section
        # simply isn't in the published site and nothing says why, which is
        # indistinguishable from "no v1 was given".
        _log.warning(
            "1.0-vs-2.0 section skipped: could not read %s", compare_db,
            exc_info=True,
        )
        return ""
    if not len(df):
        _log.warning(
            "1.0-vs-2.0 section skipped: %s shares no fitted matchup+pixel "
            "with this store", compare_db,
        )
        return ""

    out = [_heading("1.0 vs 2.0 — elastic vs inelastic retrieval", "-"), ""]
    out.append(
        f"The **same {len(df):,} matchups**, fitted twice: the 1.0 results come "
        "from the frozen v1 release, the 2.0 results from this one. Rows are "
        "paired on matchup **and pixel**, so a difference below is a difference "
        "in the retrieval, not in which patch of ocean was looked at. See the "
        ":doc:`Methods <methods>` page for the two-database provenance.\n"
    )
    out.append(V2_CHANGES)

    # `aph` is gathered (it is in the downloadable table) but deliberately NOT
    # given its own stats line: the stored `Aph` is the linear amplitude and
    # `chl = Aph / 0.05582`, a fixed rescaling, so every ratio, IQR, Spearman ρ
    # and log-RMS below would be identical to the Chl ones. Two identical rows
    # under different names read as two independent agreements.
    pairs = (
        ("bbp700", "b_bp(700 nm)", "m$^{-1}$", "m^-1"),
        ("chl", "chlorophyll", "mg m$^{-3}$", "mg m^-3"),
    )
    # `df` stays the RAW pair frame: the failure note counts the runaways from
    # it, and every b_bp helper below gates for itself (once, on the raw frame,
    # so each quotes the same count). The stats lines use this gated copy.
    gated, bbp_clause = _gated(df, "bbp700_v2")
    for key, label, _unit, _plain in pairs:
        c1, c2 = f"{key}_v1", f"{key}_v2"
        if c1 not in gated or c2 not in gated:
            continue
        st = compare.log_comparison(gated[c2], gated[c1])
        if not st.get("n"):
            continue
        tail = f"; {bbp_clause}" if key == "bbp700" else ""
        out.append(
            f"- **{label}** — n = {st['n']:,}; median 2.0/1.0 ratio = "
            f"{_fmt(st['median_ratio'])} "
            f"(IQR {_fmt(st['ratio_iqr_lo'])}–{_fmt(st['ratio_iqr_hi'])}); "
            f"Spearman ρ = {_fmt(st['spearman'])}; "
            f"log10 offset = {_fmt(st['log_bias'])}, "
            f"RMS = {_fmt(st['log_rms'])}{tail}.\n"
        )
    out.append(_version_ratio_by_level(df))
    if outdir is not None:
        out.append(_ratio_figure_block(df, outdir))
    out.append(_version_failure_note(df, store=store))
    out.append(
        "(The Chl figures are also the ``A_ph`` figures: BING's chlorophyll is "
        "a fixed rescaling of the fitted phytoplankton absorption amplitude, "
        "``Chl = A_ph / 0.05582``, so every ratio statistic is identical. Both "
        "columns are in the downloadable table.)\n"
    )

    static = outdir is not None and len(df) > max_interactive
    if static:
        out.append(_version_static_figures(df, outdir))
    elif sortable:
        try:
            from pab.report import interactive

            for key, label, _u, plain in pairs:
                c1, c2 = f"{key}_v1", f"{key}_v2"
                if c1 not in df or c2 not in df:
                    continue
                unit = f" [{plain}]" if plain else ""
                fig = interactive.comparison_scatter(
                    df,
                    sat_col=c2,
                    insitu_col=c1,
                    title=f"{label}: 2.0 (inelastic) vs 1.0 (elastic)",
                    xlabel=f"1.0 {label}{unit}",
                    ylabel=f"2.0 {label}{unit}",
                )
                out.append(interactive.raw_html(fig))
        except ImportError:
            out.append(
                "(The interactive 1.0-vs-2.0 scatters require ``bokeh`` at "
                "build time.)\n"
            )
    if outdir is not None:
        out.append(_bp_histogram_block(df, outdir))
    return "\n".join(x for x in out if x)


#: The runaway gate lives in :mod:`pab.metrics.compare` (with the gate helpers
#: that every ``b_bp`` statistic goes through); re-exported here so the old
#: ``rst.BBP_IMPLAUSIBLE`` import keeps working.
BBP_IMPLAUSIBLE = compare.BBP_IMPLAUSIBLE


def _gate_clause(n_excluded: int, n_total: int) -> str:
    """``"51 failed retrievals (0.32 %, ``b_bp`` > 1 m⁻¹) excluded"`` -- the
    clause every gated caption and stats line carries, computed from the
    counts (``n_total`` = the values the gate looked at), never quoted."""
    pct = 100.0 * n_excluded / n_total if n_total else 0.0
    noun = "failed retrieval" if n_excluded == 1 else "failed retrievals"
    return (
        f"{n_excluded:,} {noun} ({pct:.2f} %, ``b_bp`` > "
        f"{compare.BBP_IMPLAUSIBLE:g} m⁻¹) excluded"
    )


def _gated(df, col: str = "bbp_bing"):
    """:func:`~pab.metrics.compare.gate_bbp` on ``df`` plus the reader-facing
    clause: ``(df_gated, clause)``. Call it **once per frame**, on the raw
    frame -- a second pass sees nothing left to exclude and would say "0"."""
    import numpy as np

    n_total = (
        int(np.isfinite(np.asarray(df[col], dtype=float)).sum())
        if col in df.columns
        else 0
    )
    gated, n_excluded = compare.gate_bbp(df, col)
    return gated, _gate_clause(n_excluded, n_total)


def _version_ratio_by_level(df) -> str:
    """Report the 2.0/1.0 ``b_bp`` ratio in terciles of the 1.0 value.

    The single median ratio is not the whole story: the shift is strongly
    level-dependent, and quoting one number for a population whose ratio spans
    an order of magnitude would invite the reader to apply it as a uniform
    correction. Terciles of the 1.0 value are the least arbitrary split that
    shows the trend (no hand-chosen edges), and they are computed here so the
    statement cannot go stale.
    """
    import numpy as np

    if "bbp700_v1" not in df or "bbp700_v2" not in df:
        return ""
    df, _ = _gated(df, "bbp700_v2")  # the runaways would sit in a tercile
    v1 = np.asarray(df["bbp700_v1"], dtype=float)
    v2 = np.asarray(df["bbp700_v2"], dtype=float)
    ok = np.isfinite(v1) & np.isfinite(v2) & (v1 > 0) & (v2 > 0)
    if ok.sum() < 30:  # terciles of a handful of points say nothing
        return ""
    v1, v2 = v1[ok], v2[ok]
    lo_e, hi_e = np.percentile(v1, [100 / 3, 200 / 3])
    groups = (
        ("clearest third", v1 < lo_e),
        ("middle third", (v1 >= lo_e) & (v1 < hi_e)),
        ("most-scattering third", v1 >= hi_e),
    )
    parts = []
    for name, m in groups:
        if m.sum():
            parts.append(f"{name} {np.median(v2[m] / v1[m]):.2f}")
    if len(parts) < 2:
        return ""
    hi_r = float(np.median(v2[groups[2][1]] / v1[groups[2][1]]))
    return (
        _heading("Result: the inelastic correction is a clear-water effect", "~")
        + "\n"
        "The single median ratio understates and overstates by turns, because "
        "the shift is a strong, monotonic function of how much backscatter "
        "there is to begin with. Split by the 1.0 ``b_bp`` into terciles, the "
        "median 2.0/1.0 ratio runs " + "; ".join(parts) + " (tercile edges "
        f"{lo_e:.3g} and {hi_e:.3g} m⁻¹), and it keeps going at the extremes: "
        "below 2e-4 m⁻¹ the ratio is ~0.02, i.e. 2.0 retrieves some **fifty "
        "times less** backscatter than 1.0.\n"
        "\n"
        "This is the expected behaviour of the physics, not an artifact. Raman "
        "scattering and chlorophyll fluorescence contribute a roughly fixed "
        "radiance; what varies is how much *elastic* signal sits underneath "
        "them. In clear water the elastic contribution is small, so the "
        "inelastic terms are a large fraction of ``Rrs`` — and the 1.0 model, "
        "which has no inelastic terms at all, could only explain that radiance "
        "by inventing particulate backscatter. 2.0 attributes it to the "
        "processes that actually produce it, and the retrieved ``b_bp`` drops "
        "accordingly. In productive water the elastic signal dominates, the "
        "inelastic terms are a small correction, and the two versions "
        f"converge — the most-scattering tercile differs by only "
        f"{(1 - hi_r) * 100:.0f} %.\n"
        "\n"
        "The practical consequence: the headline ratio is a population median "
        "and **not** a correction factor to apply to a single retrieval. Which "
        "end of this curve a matchup sits on matters more than the median "
        "does.\n"
    )

def _ratio_figure_block(df, outdir) -> str:
    """The 2.0/1.0 ratio as a function of the 1.0 ``b_bp`` — the Q2 result."""
    try:
        import numpy as np

        from pab.plotting import population
    except ImportError:
        return ""
    if "bbp700_v1" not in df or "bbp700_v2" not in df:
        return ""
    df, bbp_clause = _gated(df, "bbp700_v2")
    v1 = np.asarray(df["bbp700_v1"], dtype=float)
    if np.isfinite(v1).sum() < 200:  # the curve needs populated bins
        return ""
    dest = Path(outdir) / "_static" / "comparisons"
    dest.mkdir(parents=True, exist_ok=True)
    try:
        population.ratio_vs_level(
            df,
            "bbp700_v2",
            "bbp700_v1",
            outfile=dest / "v2_v1_ratio_vs_level.png",
            xlabel="1.0 (elastic) $b_{bp}$(700 nm) [m$^{-1}$]",
            ylabel="2.0 / 1.0",
        )
    except Exception:  # noqa: BLE001 — a bad panel must not break the build
        return ""
    return (
        ".. figure:: _static/comparisons/v2_v1_ratio_vs_level.png\n"
        "   :width: 560px\n\n"
        "   The 2.0/1.0 ``b_bp`` ratio against the 1.0 value, with the "
        "interquartile band. The curve rises from ~0.02 in the clearest water "
        "to ~0.95 in the most scattering: the inelastic correction is large "
        "where the elastic signal is weak and vanishes where it is strong. "
        f"Bins with fewer than 20 matchups are not plotted; {bbp_clause}.\n"
    )

def _float_chl_medians(store, matchup_ids, runaway_ids):
    """``(median float Chl of the runaway matchups, median over all)`` from
    ``mld_summary``, or ``(nan, nan)`` without a store -- so the note can say
    what water the failed fits sit over with this build's numbers, not the
    investigation's."""
    import numpy as np

    if store is None:
        return float("nan"), float("nan")
    try:
        rows = store.query(
            "SELECT m.matchup_id, ms.chla FROM matchups m "
            "JOIN mld_summary ms ON ms.profile_id = m.profile_id"
        )
    except Exception:  # noqa: BLE001 — the note must build without the join
        return float("nan"), float("nan")
    chl = {r["matchup_id"]: r["chla"] for r in rows if r["chla"] is not None}
    every = np.asarray([chl[m] for m in matchup_ids if m in chl], dtype=float)
    bad = np.asarray([chl[m] for m in runaway_ids if m in chl], dtype=float)

    def med(a):
        return float(np.median(a)) if a.size else float("nan")

    return med(bad), med(every)


def _neg_blue_sentence(df) -> str:
    """``"N of M fitted spectra (x.xx %) have at least one negative band at
    400–450 nm; K of the F failed retrievals do."`` -- computed from the
    ``n_neg_blue`` column of a :func:`~pab.metrics.compare.gather_matchups`
    frame. Returns ``""`` when the column is absent or **all NaN** (a store
    whose fits predate the quantity and have not been backfilled), so a page
    never quotes a zero that means "not recorded"."""
    import numpy as np

    if df is None or "n_neg_blue" not in df.columns:
        return ""
    n = np.asarray(df["n_neg_blue"], dtype=float)
    have = np.isfinite(n)
    m = int(have.sum())
    if not m:
        return ""
    neg = have & (n >= 1)
    n_neg = int(neg.sum())
    lo, hi = _blue_qa_band()
    # a partial backfill: say what the denominator is, so "N of M" is honest
    noun = "fitted spectra" if m == len(df) else "fitted spectra with the count recorded"
    text = (
        f"{n_neg:,} of {m:,} {noun} ({100.0 * n_neg / m:.2f} %) have at "
        f"least one negative band at {lo:g}–{hi:g} nm (``n_neg_blue`` ≥ 1)"
    )
    if "bbp_bing_implausible" in df.columns:
        bad = np.asarray(df["bbp_bing_implausible"], dtype=float) == 1
        n_bad = int(bad.sum())
        if n_bad:
            k = int((bad & neg).sum())
            noun = "failed retrieval does" if n_bad == 1 else "failed retrievals do"
            text += f"; {k} of the {n_bad} {noun}"
    return text + "."


def _blue_qa_band():
    """The QA window, from where it is defined (``pab.fit.run.BLUE_QA_BAND``)."""
    from pab.fit.run import BLUE_QA_BAND

    return BLUE_QA_BAND


def _neg_blue_from_store(store) -> str:
    """:func:`_neg_blue_sentence` on the store's matchup frame; ``""`` without
    a store or when the frame cannot be built (the page must still build)."""
    if store is None:
        return ""
    try:
        return _neg_blue_sentence(compare.gather_matchups(store))
    except Exception:  # noqa: BLE001 — the page must build without the frame
        return ""


def _version_failure_note(df, store=None) -> str:
    """Count and explain the 2.0 fits that returned a non-physical ``b_bp``.

    Computed from the **raw** pair frame rather than hard-coded: the number is
    checked at every build, so a regression that multiplies these shows up in
    the report instead of hiding behind a robust median. The explanation is
    the corrected reading of ``versions/v2/high_bbp_outliers.md`` (2026-10-18;
    it replaced a retrieved-Chl rate table that read the failed fits' own Chl
    as "clear water"): marginal-sea spectra with a depressed or negative blue
    ``Rrs``, the LM warm-start delivered to the ``Bnw`` prior ceiling, a better
    physical basin in every re-fitted case. ``store`` lets the note quote the
    float Chl under the failed fits from this build. Returns ``""`` when there
    are none.
    """
    import numpy as np

    if "bbp700_v2" not in df:
        return ""
    v2 = np.asarray(df["bbp700_v2"], dtype=float)
    bad_mask = compare.implausible_bbp(v2)
    bad2 = int(bad_mask.sum())
    if not bad2:
        return ""
    n = int(np.isfinite(v2).sum())
    bits = [
        f"**Retrieval failures.** {bad2} of {n:,} 2.0 fits "
        f"({bad2 / n * 100:.2f} %) return ``b_bp(700 nm)`` above "
        f"{compare.BBP_IMPLAUSIBLE:g} m⁻¹, which is not a possible value for "
        "seawater (the open ocean spans roughly 1e-4 to 1e-1 m⁻¹); the largest "
        f"is {np.nanmax(v2):.3g} m⁻¹."
    ]
    if "bbp700_v1" in df:
        v1 = np.asarray(df["bbp700_v1"], dtype=float)
        bad1 = int(compare.implausible_bbp(v1).sum())
        bits.append(
            f" The same matchups fitted in 1.0 produce {bad1} such value"
            f"{'' if bad1 == 1 else 's'} (maximum {np.nanmax(v1):.3g} m⁻¹), so "
            "these are specific to the 2.0 configuration."
        )
    bits.append(
        f" They are **excluded** from every ``b_bp`` statistic and figure on "
        f"this site ({_gate_clause(bad2, n)}); the chlorophyll of the same fits "
        "is not gated, the gallery still shows one of them, and the "
        "downloadable table keeps the raw values with a "
        "``bbp_bing_implausible`` flag.\n"
    )
    chl_bad, chl_all = (float("nan"), float("nan"))
    if "matchup_id" in df:
        ids = list(df["matchup_id"])
        chl_bad, chl_all = _float_chl_medians(
            store, ids, [m for m, b in zip(ids, bad_mask, strict=True) if b]
        )
    water = (
        f" (the floats under them report a median Chl of {chl_bad:.2f} mg m⁻³, "
        f"against {chl_all:.2f} for the population)"
        if np.isfinite(chl_bad) and np.isfinite(chl_all)
        else ""
    )
    neg_blue = _neg_blue_from_store(store)
    neg_blue = f" In this release {neg_blue}" if neg_blue else ""
    bits.append(
        "\n**What they are.** These are not a clear-water tail — their own "
        "retrieved chlorophyll of ~0.01 mg m⁻³ is part of the failed fit. They "
        "are marginal-sea spectra (the Baltic above all, the tropical Atlantic, "
        "the Arabian Sea) with a depressed or *negative* blue ``Rrs`` at "
        f"400–450 nm{water}.{neg_blue} On such a spectrum the Levenberg–Marquardt "
        "warm-start delivers the walkers to the ``Bnw`` prior ceiling of "
        "10⁵ m⁻¹, where ``b_b ≫ a`` and the reflectance saturates, and the "
        "chains never leave it — although a physical basin with a *better* χ² "
        "and a ``b_bp`` within a factor of ~2 of the float exists in every "
        "case re-fitted so far. A re-fit of these fits under ``pab_version`` "
        "2.0.1, with physical ceilings on the priors, is pending; until then "
        "they are gated, not corrected. The full investigation is "
        f"`high_bbp_outliers.md <{compare.BBP_OUTLIERS_URL}>`__.\n"
    )
    return "".join(bits)


def _version_static_figures(df, outdir) -> str:
    """Static 2.0-vs-1.0 ``bbp700``/``chl`` scatters for the large-N page."""
    try:
        from pab.plotting import population
    except ImportError:
        return ""
    dest = Path(outdir) / "_static" / "comparisons"
    dest.mkdir(parents=True, exist_ok=True)
    figs: list[tuple[str, str]] = []
    df, bbp_clause = _gated(df, "bbp700_v2")
    # Two labels per row, deliberately: `mpl` is Matplotlib mathtext for the
    # axis, `rst` is what goes in the caption. Reusing one put a literal
    # "$b_{bp}$" into the rendered page.
    for key, mpl, unit, rst_label, cmap in (
        ("bbp700", "$b_{bp}$(700 nm)", "m$^{-1}$", "``b_bp`` (700 nm)", "Blues"),
        ("chl", "chlorophyll", "mg m$^{-3}$", "chlorophyll", "Greens"),
    ):
        c1, c2 = f"{key}_v1", f"{key}_v2"
        if c1 not in df or c2 not in df:
            continue
        try:
            # Same hues as the satellite-vs-float panels above (F4), so the
            # page reads as one set. The 2.0 fits that returned a
            # non-physical b_bp (the retrieval-failure note in the section
            # text) are gated out of the b_bp panel and its statistics; the
            # caption carries the count. The Chl panel is not gated.
            population.density_scatter(
                df,
                c2,
                c1,
                outfile=dest / f"v2_vs_v1_{key}.png",
                xlabel=f"1.0 (elastic) {mpl} [{unit}]",
                ylabel=f"2.0 (inelastic) {mpl} [{unit}]",
                cmap=cmap,
            )
            figs.append(
                (
                    f"v2_vs_v1_{key}.png",
                    f"2.0 (inelastic) vs 1.0 (elastic) {rst_label}, log-log, "
                    "same matchup and same pixel. "
                    + _density_caption(df, c2, c1)
                    + (f" {bbp_clause}." if key == "bbp700" else ""),
                )
            )
        except Exception:  # noqa: BLE001 — a bad panel must not break the build
            pass
    if not figs:
        return ""
    out = [
        f"{len(df):,} paired matchups — shown as static figures (the "
        "interactive per-point scatter is suppressed at this scale to keep the "
        "committed site small).\n"
    ]
    for name, cap in figs:
        out.append(
            f".. figure:: _static/comparisons/{name}\n   :width: 520px\n\n   {cap}\n"
        )
    return "\n".join(out)


def _bp_histogram_block(df, outdir) -> str:
    """The free-``B_p`` posterior-median histogram (2.0 only), with prior edges."""
    if "Bp_v2" not in df:
        return ""
    try:
        import numpy as np

        from pab.plotting import population
    except ImportError:
        return ""
    v = np.asarray(df["Bp_v2"], dtype=float)
    n = int(np.isfinite(v).sum())
    if not n:
        return ""
    dest = Path(outdir) / "_static" / "comparisons"
    dest.mkdir(parents=True, exist_ok=True)
    try:
        population.value_histogram(
            df,
            "Bp_v2",
            outfile=dest / "v2_bp_hist.png",
            xlabel="$B_p$ (posterior median)",
            prior_range=_bp_prior_range(),
        )
    except Exception:  # noqa: BLE001
        return ""
    bounds = _bp_prior_range()
    edge_txt = ""
    if bounds:
        lo, hi = bounds
        span = hi - lo
        parts = []
        for tol in (0.01, 0.02, 0.05):
            w = span * tol
            k = int(np.count_nonzero((v <= lo + w) | (v >= hi - w)))
            parts.append(f"{k / n * 100:.1f} % within {tol * 100:g} %")
        edge_txt = (
            "\n**The prior is doing real work at both ends.** The posterior "
            "medians are **bimodal**, with mass against *both* bounds of the "
            f"uniform ``[{lo:g}, {hi:g}]`` prior: " + ", ".join(parts) + " of a "
            "bound. The 1st percentile sits at the floor and the 99th at the "
            "ceiling. A pile-up at a bound means the data preferred a value "
            "the prior forbade, so for those fits the bound — not the "
            "spectrum — sets ``B_p``. The bounds are physically motivated and "
            "have been kept, but the headline ``B_p`` distribution should be "
            "read as *censored at both ends* rather than as a free "
            "measurement.\n"
        )
    return (
        ".. figure:: _static/comparisons/v2_bp_hist.png\n"
        "   :width: 520px\n\n"
        f"   Posterior-median ``B_p`` across the {n:,} 2.0 fits. ``B_p`` was "
        "**fixed** in 1.0, so there is no 1.0 counterpart to scatter it "
        "against. The dotted lines are the uniform prior's bounds; the "
        "fraction within 1 % of an edge is given in the panel title.\n"
        + edge_txt
    )

def _static_comparison_figures(df, outdir) -> str:
    """Static (Matplotlib) ``b_bp``/Chl scatters + matchup map for the large-N page.

    Renders small PNGs into ``outdir/_static/comparisons`` (reusing
    :mod:`pab.plotting.population`) and returns the ``.. figure::`` block. Used
    above :data:`MAX_INTERACTIVE_MATCHUPS`, where an all-points Bokeh embed would
    bloat the committed site. Best-effort: returns ``""`` if Matplotlib / the
    population helpers are unavailable or every panel fails.
    """
    try:
        from pab.plotting import population
    except ImportError:
        return ""
    dest = Path(outdir) / "_static" / "comparisons"
    dest.mkdir(parents=True, exist_ok=True)
    figs: list[tuple[str, str]] = []
    # The gate (Q&A/Outliers 1 = B): the non-physical BING `b_bp` retrievals
    # are NaN in this frame, so the b_bp panel, both maps and their statistics
    # never see them, and every caption says how many were excluded. The Chl
    # panel reads an untouched column (Q&A/Outliers 6 = A).
    df, bbp_clause = _gated(df, "bbp_bing")
    # Density-plus-dots panels (Q&A/v2 Q5): the low-end pile-up at the prior
    # floor does not set the axes (the 99 % clip), the dense core shows its
    # structure instead of one blob, and each quantity has its own hue.
    try:
        population.density_scatter(
            df,
            "bbp_bing",
            "bbp_argo",
            label="b_bp",
            unit="m$^{-1}$",
            cmap="Blues",
            outfile=dest / "bbp_scatter.png",
        )
        figs.append(
            (
                "bbp_scatter.png",
                "Satellite vs float ``b_bp`` (700 nm), log-log; axes span the "
                "central 99 % of the values. "
                + _density_caption(df, "bbp_bing", "bbp_argo")
                + f" {bbp_clause}.",
            )
        )
    except Exception:  # noqa: BLE001 — a bad panel must not break the build
        pass
    if "chl_bing" in df and "chla_argo" in df:
        try:
            population.density_scatter(
                df,
                "chl_bing",
                "chla_argo",
                label="chlorophyll",
                unit="mg m$^{-3}$",
                cmap="Greens",
                outfile=dest / "chl_scatter.png",
            )
            figs.append(
                (
                    "chl_scatter.png",
                    "Satellite vs float chlorophyll, log-log; axes span the "
                    "central 99 % of the values. "
                    + _density_caption(df, "chl_bing", "chla_argo"),
                )
            )
        except Exception:  # noqa: BLE001
            pass
    # The two maps (Q&A/v2 Q8, F5, Edits 5 = B) share one fixed symmetric
    # colour scale, ±0.5 dex; the maps compute the ratio themselves, so no
    # runaway reaches the colorbar through this caller, and the captions
    # count what the clip saturates.
    vmax = population.LOG_RATIO_VMAX
    scale = (
        "colour = log10(satellite / float ``b_bp``), symmetric about 0 and "
        f"clipped at a fixed ±{vmax:g} dex (a factor of {10 ** vmax:.1f} "
        "either way)"
    )
    try:
        population.matchup_map(
            df, sat_col="bbp_bing", insitu_col="bbp_argo", vmax=vmax,
            outfile=dest / "matchup_map.png",
        )
        sat, n_ratio = population.log_ratio_saturated(
            df, "bbp_bing", "bbp_argo", vmax=vmax
        )
        pct = f"{100.0 * sat / n_ratio:.1f} %" if n_ratio else "0 %"
        # The grey dots as the map draws them: positioned, but no finite
        # ratio (a retracted position is on neither count).
        import numpy as np

        positioned = np.isfinite(np.asarray(df["longitude"], dtype=float)) & np.isfinite(
            np.asarray(df["latitude"], dtype=float)
        )
        n_grey = int(
            (positioned & ~np.isfinite(population.log_ratio(df, "bbp_bing", "bbp_argo"))).sum()
        )
        figs.append(
            (
                "matchup_map.png",
                f"Matchup locations (one dot per matchup); {scale}. The "
                f"{sat:,} matchups ({pct} of the {n_ratio:,} with a ratio) at "
                f"or beyond ±{vmax:g} dex saturate to the end colours. The "
                f"{n_grey:,} matchups without a ratio (no float ``b_bp``, or a "
                f"failed retrieval) are grey; {bbp_clause}.",
            )
        )
    except Exception:  # noqa: BLE001
        pass
    try:
        population.healpix_map(
            df, sat_col="bbp_bing", insitu_col="bbp_argo", vmax=vmax,
            outfile=dest / "healpix_map.png",
        )
        cells = population.healpix_medians(df, "bbp_bing", "bbp_argo")
        drawn = cells[cells["n"] >= population.HEALPIX_MIN_COUNT]
        nside = int(cells["nside"].iloc[0]) if len(cells) else 0
        width = f"≈ {population.healpix_cell_deg(nside):.0f}° cells" if nside else ""
        sat_cells = population.saturated_count(drawn["median_log_ratio"], vmax)
        figs.append(
            (
                "healpix_map.png",
                "Median log10(satellite / float ``b_bp``) per HEALPix cell "
                f"(nside {nside}, {width}); only cells holding ≥ "
                f"{population.HEALPIX_MIN_COUNT} matchups are drawn "
                f"({len(drawn)} cells, {int(drawn['n'].sum()):,} matchups; "
                f"{len(cells) - len(drawn)} sparser cells left out). The same "
                f"scale as the dot map: {scale}; saturated (median at or "
                f"beyond ±{vmax:g} dex): {sat_cells} of the {len(drawn)} "
                f"drawn cells. {bbp_clause}.",
            )
        )
    except Exception:  # noqa: BLE001
        pass
    if not figs:
        return ""
    out = [
        f"{len(df):,} matchups — shown as static summary figures (the interactive "
        "per-point scatter is suppressed at this scale to keep the committed site "
        "small; per-matchup values are in the downloadable summary table on the "
        ":doc:`Downloads <downloads>` page).\n"
    ]
    for name, cap in figs:
        out.append(
            f".. figure:: _static/comparisons/{name}\n   :width: 520px\n\n   {cap}\n"
        )
    return "\n".join(out)


def comparisons_page(
    df,
    *,
    sortable: bool = True,
    outdir=None,
    max_interactive: int = MAX_INTERACTIVE_MATCHUPS,
) -> str:
    """The **Comparisons** page: satellite-vs-float scatters + map.

    Interactive Bokeh below ``max_interactive`` matchups; **static** PNGs above it
    (when ``outdir`` is given) so the committed site stays small at ~10⁴ matchups.
    """
    out = [_heading("Satellite vs float comparisons"), ""]
    body = ""
    if outdir is not None and len(df) > max_interactive:
        body = _static_comparison_figures(df, outdir)
    if not body and sortable:
        body = interactive_figures(df)
    if body:
        out.append(body)
    else:
        out.append(
            "The interactive ``b_bp`` and chlorophyll scatters and the matchup map "
            "require ``bokeh`` at build time.\n"
        )
    return "\n".join(out)


def figures_page(store, outdir, df, *, figure_roots=None) -> str:
    """The **Figures** page: the per-matchup fit, PACE scene, and Argo Q&A
    thumbnail galleries (each N-guarded; no per-matchup pages).

    Above :data:`MAX_INLINE_FIGURES` each gallery shows a representative
    subset instead of nothing: the fits from :func:`select_representative_fits`,
    one scene per region (:func:`select_representative_scenes`) and the Q&A
    plots of the profiles behind the selected fits. Logs the total bytes the
    galleries staged under ``_static``.
    """
    out = [_heading("Matchup & profile figures"), ""]
    out.append(
        "Per-matchup **BING fit** figures and **PACE scene** quick-looks, plus the "
        "**Argo profile Q&A** plots. Shown as thumbnails (click to enlarge), never "
        "as separate per-matchup pages.\n"
    )
    fits = scenes = None
    if len(df) > MAX_INLINE_FIGURES:
        fits = select_representative_fits(df)
        scenes = select_representative_scenes(df)
    out.append(figure_gallery(df, representative=fits))
    out.append(
        scene_gallery(store, outdir, representative=scenes, figure_roots=figure_roots)
    )
    out.append(
        argo_qa_gallery(store, outdir, representative=fits, figure_roots=figure_roots)
    )
    staged = [
        p
        for sub in ("figures", "scenes", "argo_qa")
        for p in sorted((Path(outdir) / "_static" / sub).glob("*"))
        if p.is_file()
    ]
    if staged:
        _log.info(
            "report: galleries staged %d files, %.2f MB under _static/ "
            "(longest side ≤ %d px)",
            len(staged),
            sum(p.stat().st_size for p in staged) / 1e6,
            GALLERY_MAX_SIDE,
        )
    return "\n".join(out)


def remap_figure_path(src: str, figure_roots=None) -> str:
    """Translate a stored (in-pod) figure path through ``--figure-root OLD=NEW``.

    The database records PVC paths (``/data/v2/pipeline/figures/…``); a build
    on the workstation reaches the files under other roots. The **longest**
    matching ``OLD`` prefix wins (so ``/data/v2/pipeline/figures`` beats
    ``/data`` when both are given); a prefix matches whole path components
    only. A ``NEW`` root that does not exist is tolerated here — the file just
    fails :func:`_stage_static`'s existence check and is counted as missing.
    """
    if not figure_roots or not src:
        return src
    best = None
    for old, new in figure_roots.items():
        old = old.rstrip("/")
        if old and (src == old or src.startswith(old + "/")):
            if best is None or len(old) > len(best[0]):
                best = (old, new)
    if best is None:
        return src
    old, new = best
    return new.rstrip("/") + src[len(old) :]


def _downscaled_copy(src: Path, dest: Path, max_side: int | None) -> Path:
    """Write ``src`` to ``dest``, shrunk so its longest side is ``max_side`` px.

    Pillow decodes and re-encodes (PNG) only when the image is actually larger
    than ``max_side``; a smaller image, a file Pillow cannot read (test stubs),
    or a build without Pillow gets a verbatim copy. Returns the written path
    (the suffix becomes ``.png`` when re-encoded).
    """
    if max_side:
        try:
            from PIL import Image
        except ImportError:
            Image = None
        if Image is not None:
            try:
                with Image.open(src) as im:
                    if max(im.size) > max_side:
                        im.thumbnail((max_side, max_side))
                        out = dest.with_suffix(".png")
                        im.save(out, format="PNG", optimize=True)
                        return out
            except (OSError, ValueError):
                pass  # not a decodable image: copy it as it is
    shutil.copyfile(src, dest)
    return dest


def _stage_static(
    src,
    outdir,
    subdir: str,
    *,
    figure_roots=None,
    max_side: int | None = GALLERY_MAX_SIDE,
) -> str | None:
    """Copy an artifact into ``outdir/_static/<subdir>`` and return its
    page-relative URL, or ``None`` if ``src`` is missing/not on disk.

    The one place that copies a figure into the site tree — shared by the fit,
    scene, and Argo-Q&A galleries so the copy/URL convention stays consistent.
    ``src`` is first translated through ``figure_roots``
    (:func:`remap_figure_path`), and the copy is downscaled to ``max_side``
    pixels on its longest side (:func:`_downscaled_copy`) so the committed
    site grows by kilobytes per thumbnail, not by the full-resolution PNG.
    Callers count the ``None`` returns and warn once per gallery.
    """
    if not src:
        return None
    path = Path(remap_figure_path(str(src), figure_roots))
    if not path.is_file():
        return None
    dest = Path(outdir) / "_static" / subdir
    dest.mkdir(parents=True, exist_ok=True)
    written = _downscaled_copy(path, dest / path.name, max_side)
    return f"_static/{subdir}/{written.name}"


def _thumbnail_gallery(
    items,
    *,
    heading: str,
    intro: str,
    over_limit: str,
    max_inline: int,
    stage=None,
    total: int | None = None,
    representative=None,
    representative_intro: str | None = None,
) -> str:
    """An N-guarded clickable-thumbnail gallery from ``(url, caption)`` items.

    For a small set (``<= max_inline``) every item is shown as a thumbnail that
    links to the full PNG; above the threshold the gallery is suppressed (the
    design's no-page-explosion constraint) and ``over_limit`` (a ``{n}`` template)
    is shown instead — unless ``representative`` gives a handful of
    ``(source, caption)`` items chosen to stand for the population, in which
    case those are rendered under ``representative_intro`` (a ``{n}``/``{k}``
    template: population size, thumbnails shown). Returns ``""`` when there are
    no items.

    ``stage`` maps an item's first element (a source path) to a published URL,
    and is called **only when the gallery will actually render**. Callers used
    to stage every file before calling this, so at 10⁴ matchups the site copied
    the entire figure set — ~32,000 files and 636 MB — in order to display none
    of them. The N-guard protected the HTML and not the payload, which is the
    expensive half; measured in-pod, that copy ran at 2.8 files/s on CephFS, or
    3.2 h to stage a gallery nobody sees. A representative item whose file
    cannot be staged (no recorded path, or not on disk after the
    ``--figure-root`` remap) is dropped, and the drops are reported in **one**
    warning per gallery, not one per file.
    """
    items = [(u, c) for (u, c) in items if isinstance(u, str) and u]
    # `total` is the population size, which is NOT len(items) once a caller
    # stops staging at scale: the urls are all None then, and judging by the
    # surviving items would make the whole section disappear instead of saying
    # the artifacts exist as downloads.
    n = len(items) if total is None else total
    if not n:
        return ""
    out = [_heading(heading, "-"), ""]
    if n > max_inline:
        chosen = list(representative or [])
        rep = [(u, c) for (u, c) in chosen if isinstance(u, str) and u]
        if stage is not None:
            rep = [(stage(src), c) for (src, c) in rep]
            rep = [(u, c) for (u, c) in rep if isinstance(u, str) and u]
        dropped = len(chosen) - len(rep)
        if dropped:
            _log.warning(
                "report: %s — %d of %d representative files dropped (no "
                "recorded path, or not on disk after the --figure-root remap)",
                heading,
                dropped,
                len(chosen),
            )
        if not rep:
            out.append(over_limit.format(n=n) + "\n")
            return "\n".join(out)
        items = rep
        intro = (representative_intro or over_limit).format(n=n, k=len(rep))
        if dropped:
            intro += (
                f" ({dropped} of the {len(chosen)} chosen have no file reachable "
                "at build time and are left out.)"
            )
    else:
        if not items:
            return ""
        if stage is not None:
            items = [(stage(src), c) for (src, c) in items]
            items = [(u, c) for (u, c) in items if isinstance(u, str) and u]
            if not items:
                return ""
    out.append(intro + "\n")
    html = ['<div class="pab-gallery">']
    for url, cap in items:
        html.append(
            '<figure style="display:inline-block;margin:8px;text-align:center;'
            'vertical-align:top">'
            f'<a href="{url}"><img src="{url}" style="max-width:360px;height:auto">'
            "</a>"
            f"<figcaption>{cap}</figcaption></figure>"
        )
    html.append("</div>")
    out.append(".. raw:: html\n")
    out.extend("   " + ln for ln in html)
    return "\n".join(out) + "\n"


def _ordinal(n: int) -> str:
    suffix = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def _sci(x: float) -> str:
    """``9.3e4`` — a compact mantissa/exponent for a runaway caption."""
    mantissa, exponent = f"{x:.1e}".split("e")
    return f"{mantissa}e{int(exponent)}"


def _sorted_with_log_ratio(df):
    """The frame sorted by ``matchup_id`` with a ``log_ratio`` column
    (``log10(bbp_bing / bbp_argo)``, NaN unless both are finite and positive).

    The sort is what makes every "nearest" pick below deterministic: an
    ``argmin``/``argmax`` over the sorted frame returns the **first** of tied
    rows, i.e. the smallest ``matchup_id``.
    """
    import numpy as np

    base = df.sort_values("matchup_id", kind="stable").reset_index(drop=True).copy()
    sat = base["bbp_bing"].to_numpy(dtype=float)
    ins = base["bbp_argo"].to_numpy(dtype=float)
    ok = np.isfinite(sat) & np.isfinite(ins) & (sat > 0) & (ins > 0)
    lr = np.full(len(base), np.nan)
    lr[ok] = np.log10(sat[ok] / ins[ok])
    base["log_ratio"] = lr
    return base


def _nearest(log_ratio, mask, target) -> int | None:
    """Position of the ``mask``-ed row whose ``log_ratio`` is nearest ``target``
    (first = smallest ``matchup_id`` on a tie); ``None`` if the mask is empty."""
    import numpy as np

    d = np.where(mask, np.abs(log_ratio - target), np.inf)
    if not np.isfinite(d).any():
        return None
    return int(np.argmin(d))


def _with_captions(base, picks):
    """De-duplicate ``(row, reason)`` picks keeping order; return the rows with
    ``reason`` and ``caption`` (``WMO/cycle — reason``) columns."""
    rows, reasons = [], []
    for i, why in picks:
        if i is None or i in rows:
            continue
        rows.append(i)
        reasons.append(why)
    out = base.iloc[rows].copy()
    out["reason"] = reasons
    out["caption"] = [
        f"{w}/{c} — {r}"
        for w, c, r in zip(out["wmo"], out["cycle"], reasons, strict=True)
    ]
    return out.reset_index(drop=True)


def select_representative_fits(df):
    """The ≤ 8 matchups whose fit figures stand for the population (Q4 = A).

    Deterministic — the same rows on every rebuild of the same database — and
    each row says why it was chosen (``reason``; ``caption`` is
    ``WMO/cycle — reason``). In order:

    1. the matchups whose ``log10(bbp_bing / bbp_argo)`` is nearest the
       :data:`REPRESENTATIVE_PERCENTILES` (5th, 25th, 50th, 75th, 95th) of that
       ratio over the finite positive pairs — what good, typical and poor
       agreement look like;
    2. the runaway with the largest ``bbp_bing`` above :data:`BBP_IMPLAUSIBLE`
       (skipped when there is none) — what a failed retrieval looks like;
    3. within the clearest and the most productive ``chl_bing`` tercile, the
       matchup nearest that tercile's median log-ratio — the two regimes.

    Ties go to the smallest ``matchup_id``; duplicates are removed keeping the
    first reason. Returns an empty frame for an empty or ratio-less input.
    """
    import numpy as np
    import pandas as pd

    if not len(df) or "bbp_bing" not in df or "bbp_argo" not in df:
        return pd.DataFrame(
            columns=[*df.columns, "log_ratio", "reason", "caption"]
        )
    base = _sorted_with_log_ratio(df)
    lr = base["log_ratio"].to_numpy()
    sat = base["bbp_bing"].to_numpy(dtype=float)
    ok = np.isfinite(lr)
    picks: list[tuple[int | None, str]] = []
    if ok.any():
        targets = np.percentile(lr[ok], REPRESENTATIVE_PERCENTILES)
        for p, target in zip(REPRESENTATIVE_PERCENTILES, targets, strict=True):
            i = _nearest(lr, ok, target)
            picks.append(
                (i, f"{_ordinal(p)} percentile of sat/float b_bp, ratio {10 ** lr[i]:.3g}")
            )
    runaway = np.isfinite(sat) & (sat > BBP_IMPLAUSIBLE)
    if runaway.any():
        i = int(np.argmax(np.where(runaway, sat, -np.inf)))
        picks.append((i, f"non-physical retrieval, b_bp = {_sci(sat[i])} m⁻¹"))
    if "chl_bing" in base:
        chl = base["chl_bing"].to_numpy(dtype=float)
        okc = ok & np.isfinite(chl) & (chl > 0)
        if okc.sum() >= 3:  # terciles of fewer rows are not terciles
            lo_e, hi_e = np.percentile(chl[okc], [100 / 3, 200 / 3])
            terciles = (
                ("clearest", okc & (chl < lo_e)),
                ("most productive", okc & (chl >= hi_e)),
            )
            for name, m in terciles:
                if not m.any():
                    continue
                i = _nearest(lr, m, float(np.median(lr[m])))
                picks.append(
                    (
                        i,
                        f"{name} tercile, Chl {chl[i]:.2g} mg m⁻³, "
                        f"ratio {10 ** lr[i]:.3g}",
                    )
                )
    return _with_captions(base, picks)


def select_representative_scenes(df, *, max_regions: int = MAX_SCENE_REGIONS):
    """One matchup per :func:`pab.metrics.compare.add_strata` ``region`` — the
    one nearest the region's median ``log10(bbp_bing / bbp_argo)`` — for the
    ``max_regions`` most populous regions (ties: alphabetical). Deterministic;
    ``reason``/``caption`` columns as in :func:`select_representative_fits`.
    """
    import numpy as np
    import pandas as pd

    if not len(df) or "bbp_bing" not in df or "bbp_argo" not in df:
        return pd.DataFrame(
            columns=[*df.columns, "log_ratio", "reason", "caption"]
        )
    if "region" not in df and "latitude" in df and "time" in df:
        df = compare.add_strata(df)
    base = _sorted_with_log_ratio(df)
    lr = base["log_ratio"].to_numpy()
    ok = np.isfinite(lr)
    region = base["region"] if "region" in base else pd.Series([None] * len(base))
    counts = {}
    for name in region[ok]:
        if name is not None:
            counts[name] = counts.get(name, 0) + 1
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], str(kv[0])))
    picks = []
    for name, count in ranked[:max_regions]:
        m = ok & (region.to_numpy() == name)
        med = float(np.median(lr[m]))
        i = _nearest(lr, m, med)
        picks.append(
            (
                i,
                f"{name} band, nearest its median sat/float b_bp ratio "
                f"{10 ** med:.3g} (n={count:,})",
            )
        )
    return _with_captions(base, picks)


def _fit_gallery_intro(selection) -> str:
    """The representative fit gallery's intro, saying what the subset spans —
    a ``{n}``/``{k}`` template for :func:`_thumbnail_gallery`."""
    reasons = list(selection["reason"]) if len(selection) else []
    text = (
        "{n} matchups — too many to show inline. The {k} below were chosen to "
        "span the sat/float agreement from the "
        f"{_ordinal(REPRESENTATIVE_PERCENTILES[0])} to the "
        f"{_ordinal(REPRESENTATIVE_PERCENTILES[-1])} percentile"
    )
    if any(r.startswith("non-physical") for r in reasons):
        text += ", plus one failed retrieval"
    if any("tercile" in r for r in reasons):
        text += " and the clearest and most productive regimes"
    return text + "; every figure is available as a download (Downloads page)."


def figure_gallery(
    df,
    *,
    url_col: str = FIGURE_URL_COL,
    max_inline: int | None = None,
    representative=None,
) -> str:
    """An N-guarded inline gallery of per-matchup fit figures (no per-matchup pages).

    For a small population every matchup's fit figure is a clickable thumbnail
    (tap opens the full PNG / download); above the threshold the gallery shows
    the ``representative`` selection (:func:`select_representative_fits`, whose
    figures :func:`_gather_with_figures` has staged) with a line saying how it
    was chosen — or, without one, only the downloads note.
    """
    if max_inline is None:
        max_inline = MAX_INLINE_FIGURES
    items = [
        (r.get(url_col), f"{r.get('wmo')}/{r.get('cycle')}") for _, r in df.iterrows()
    ]
    rep = None
    if representative is not None and len(representative):
        urls = dict(zip(df["matchup_id"], df[url_col], strict=True))
        rep = [
            (urls.get(mid), cap)
            for mid, cap in zip(
                representative["matchup_id"], representative["caption"], strict=True
            )
        ]
    return _thumbnail_gallery(
        items,
        total=len(df),
        heading="Per-matchup figures",
        intro="One thumbnail per matchup (the design exposes figures, not "
        "per-matchup pages). Click a thumbnail to open the full-resolution PNG.",
        # No "tap a point in the scatter" here: above MAX_INTERACTIVE_MATCHUPS
        # the Comparisons page falls back to static PNGs, so at exactly the
        # scale this message appears there is nothing tappable to point at.
        over_limit="{n} matchups — too many to show inline. Per-matchup fit "
        "figures are published as downloads; see the release manifest on the "
        "Downloads page.",
        max_inline=max_inline,
        representative=rep,
        representative_intro=_fit_gallery_intro(representative)
        if rep is not None
        else None,
    )


def _paths_for(store, sql: str, selection, col: str):
    """``(path, caption)`` per selected matchup, in selection order, from a
    query with one ``IN (…)`` placeholder list over ``matchup_id``."""
    ids = list(selection["matchup_id"])
    if not ids:
        return []
    marks = ",".join("?" * len(ids))
    found = {
        r["matchup_id"]: r[col] for r in store.query(sql.format(marks=marks), ids)
    }
    return [
        (found.get(mid), cap)
        for mid, cap in zip(ids, selection["caption"], strict=True)
    ]


def argo_qa_gallery(
    store,
    outdir,
    *,
    max_inline: int | None = None,
    representative=None,
    figure_roots=None,
) -> str:
    """An N-guarded gallery of the **Argo profile Q&A** figures.

    Each ``mld_summary.qa_path`` (BBP700/CHLA vs pressure with the MLD marked,
    emitted by ``ingest``) is copied into ``outdir/_static/argo_qa`` and linked.
    Above the threshold, ``representative`` (the fit selection) picks the
    profiles behind those fits, so the three galleries tell one story; a
    profile with no recorded or reachable plot is dropped with a counted
    warning rather than biasing the selection toward profiles that have one.
    Returns ``""`` when no profile has a recorded, on-disk Q&A figure.
    """
    if max_inline is None:
        max_inline = MAX_INLINE_FIGURES
    rows = store.query(
        "SELECT p.wmo, p.cycle, ms.qa_path FROM mld_summary ms "
        "JOIN profiles p ON p.profile_id = ms.profile_id "
        "WHERE ms.qa_path IS NOT NULL ORDER BY p.wmo, p.cycle"
    )
    items = [(r["qa_path"], f"{r['wmo']}/{r['cycle']}") for r in rows]
    rep = None
    if representative is not None and len(representative):
        rep = _paths_for(
            store,
            "SELECT m.matchup_id, ms.qa_path FROM matchups m "
            "JOIN mld_summary ms ON ms.profile_id = m.profile_id "
            "WHERE m.matchup_id IN ({marks})",
            representative,
            "qa_path",
        )
    return _thumbnail_gallery(
        items,
        stage=lambda src: _stage_static(src, outdir, "argo_qa", figure_roots=figure_roots),
        heading="Argo profile Q&A",
        intro="Per-profile quality-assurance plots: ``BBP700`` and ``CHLA`` vs "
        "pressure with the mixed-layer depth marked — to eyeball the MLD and the "
        "de-spiking behind each summary. Click a thumbnail to enlarge.",
        over_limit="{n} profiles — too many to show inline; the per-profile Q&A "
        "plots are available as downloads.",
        max_inline=max_inline,
        representative=rep,
        representative_intro="{n} profiles — too many to show inline. The {k} "
        "below are the profiles behind the representative fit figures above "
        "(same order, same captions): ``BBP700`` and ``CHLA`` vs pressure with "
        "the mixed-layer depth marked; every Q&A plot is available as a "
        "download (Downloads page).",
    )


def scene_gallery(
    store,
    outdir,
    *,
    max_inline: int | None = None,
    representative=None,
    figure_roots=None,
) -> str:
    """An N-guarded gallery of the **PACE scene quick-looks** per matchup.

    Each ``matchups.scene_path`` (false-colour scene around the float, emitted by
    the ``figure`` stage) is copied into ``outdir/_static/scenes`` and linked.
    Above the threshold, ``representative`` (:func:`select_representative_scenes`)
    gives one scene per latitude band. Returns ``""`` when no matchup has a
    recorded, on-disk scene figure.
    """
    if max_inline is None:
        max_inline = MAX_INLINE_FIGURES
    rows = store.query(
        "SELECT p.wmo, p.cycle, m.scene_path FROM matchups m "
        "JOIN profiles p ON p.profile_id = m.profile_id "
        "WHERE m.scene_path IS NOT NULL ORDER BY p.wmo, p.cycle"
    )
    items = [(r["scene_path"], f"{r['wmo']}/{r['cycle']}") for r in rows]
    rep = None
    if representative is not None and len(representative):
        rep = _paths_for(
            store,
            "SELECT matchup_id, scene_path FROM matchups WHERE matchup_id IN ({marks})",
            representative,
            "scene_path",
        )
    return _thumbnail_gallery(
        items,
        stage=lambda src: _stage_static(src, outdir, "scenes", figure_roots=figure_roots),
        heading="PACE scene quick-looks",
        intro="False-colour PACE/OCI scene around each float (red star = float "
        "position; white circles = the analyzed pixels) — so cloudy or glinty "
        "scenes are visible at a glance. Click a thumbnail to enlarge.",
        over_limit="{n} matchups — too many to show inline; the scene quick-looks "
        "are available as downloads.",
        max_inline=max_inline,
        representative=rep,
        representative_intro="{n} matchups — too many to show inline. The {k} "
        "below are one per latitude band — the matchup nearest the band's "
        "median sat/float ``b_bp`` ratio — so the reader sees a typical scene "
        "from each: false-colour PACE/OCI around the float (red star = float "
        "position; white circles = the analyzed pixels); every scene is "
        "available as a download (Downloads page).",
    )


def _table_block(df, *, columns=None, sortable: bool = True) -> str:
    """A **sortable** Bokeh ``DataTable`` (embedded) when available, else a static
    ``list-table`` — so pages render with or without ``bokeh``."""
    if sortable:
        try:
            from pab.report import interactive

            return interactive.raw_html(interactive.stats_table(df, columns=columns))
        except ImportError:
            pass
    return rst_table(df, columns=columns)


def aggregates_page(store, *, sortable: bool = True) -> str:
    """The binned-results page: region/season tables + a HEALPix per-cell table.

    Tables are **sortable** Bokeh ``DataTable`` embeds when ``bokeh`` is available
    (``sortable=True``), falling back to static reStructuredText ``list-table``.
    """
    from pab.report import aggregate as agg

    # Every table below is a b_bp statistic, so the frame is gated once here.
    df, bbp_clause = _gated(compare.add_strata(compare.gather_matchups(store)))
    out = [_heading("Aggregate results"), ""]
    out.append(
        "Population statistics binned by region and season, and an equal-area "
        "HEALPix spatial aggregation. Per-matchup detail is available through the "
        "interactive figures, not as individual pages.\n"
    )
    if not len(df):
        out.append("(no matchups yet)\n")
        return "\n".join(out)
    out.append(
        f"All tables compare satellite and float ``b_bp`` (700 nm); {bbp_clause} "
        "(see the :doc:`Methods <methods>` page).\n"
    )
    out.append(_heading("By region", "-"))
    out.append(_table_block(agg.aggregate_by(df, "region"), sortable=sortable))
    out.append(_heading("By season", "-"))
    out.append(_table_block(agg.aggregate_by(df, "season"), sortable=sortable))
    out.append(_heading("HEALPix cells", "-"))
    try:
        hp = agg.aggregate_healpix(df)
        out.append(
            _table_block(
                hp,
                columns=["hpix", "lon", "lat", "n", "median_ratio"],
                sortable=sortable,
            )
        )
    except ImportError:
        # HEALPix aggregation needs healpy / remote_sensing.healpix; the flat
        # region/season bins above are the default, so degrade gracefully.
        out.append("(HEALPix aggregation requires ``healpy`` / ``remote_sensing``)\n")
    return "\n".join(out)


def matchup_quality_table(store, *, sortable: bool = True) -> str:
    """A compact per-matchup quality/coverage table.

    The space/time separation and spectra count per matchup — how close (km) and
    how near in time (h) the PACE scene was to the float, and how many valid
    spectra fed the fit — so a reader can judge each matchup. Network-free
    (straight from the DB). Returns ``""`` when there are no matchups.
    """
    import pandas as pd

    rows = store.query(
        "SELECT p.wmo, p.cycle, m.distance_km, m.dtime_hours, m.n_spectra "
        "FROM matchups m JOIN profiles p ON p.profile_id = m.profile_id "
        "ORDER BY p.wmo, p.cycle"
    )
    if not rows:
        return ""
    df = pd.DataFrame(rows)
    out = [_heading("Matchup quality", "-"), ""]
    out.append(
        "Space/time separation and spectra count per matchup: how close (km) and "
        "how near in time (h) the PACE scene was to the float, and how many valid "
        "spectra fed the BING fit.\n"
    )
    out.append(_table_block(df, sortable=sortable))
    return "\n".join(out)


def _methods_ceiling_sentence(store) -> str:
    """The Methods page's slope-ceiling sentence, with the fraction computed
    from ``store`` when one is given (and holds an ingest), else deferred to
    the Comparisons page -- never a quoted number."""
    import numpy as np

    frac = float("nan")
    if store is not None:
        try:
            df = compare.gather_nasa_giop(store)
            if len(df):
                frac = compare.giop_slope_ceiling_fraction(df["bbp_s_nasa"])
        except Exception:  # noqa: BLE001 — the page must build without the frame
            pass
    lead = f"GIOP bounds the slope at {compare.GIOP_BBP_S_CEILING:.1f}, and "
    if np.isfinite(frac):
        lead += f"{frac * 100:.1f} % of the slopes sit at that ceiling in this release"
    else:
        lead += (
            "the *Comparisons* page reports the fraction of slopes at that "
            "ceiling in this release"
        )
    return f"{lead} — {_NASA_BBP_CEILING_CAVEAT}"


def _methods_matchups(store):
    """The store's matchup frame for the Methods page's computed numbers, or
    ``None`` (no store, or the frame cannot be built -- the page must build)."""
    if store is None:
        return None
    try:
        df = compare.gather_matchups(store)
    except Exception:  # noqa: BLE001 — the page must build without the frame
        return None
    return df if len(df) else None


def _methods_neg_blue(df) -> str:
    """The Methods page's definition of ``n_neg_blue`` (O4, Q&A/Outliers
    3 = A) plus, when ``df`` carries it, the computed rate in this release."""
    lo, hi = _blue_qa_band()
    rate = _neg_blue_sentence(df)
    rate = (
        f" In this release {rate}"
        if rate
        else (
            " Where the count has not been recorded the column is empty and no "
            "rate is quoted."
        )
    )
    return (
        "**Negative-blue QA count.** Every fit also records ``n_neg_blue``: the "
        f"number of bands of the fitted spectrum with ``Rrs < 0`` between {lo:g} "
        f"and {hi:g} nm (inclusive), stored as the ``BING_ExpBPow_n_neg_blue`` "
        "quantity and carried as the ``n_neg_blue`` column of the downloadable "
        "summary table. It is a flag, not a screen: a spectrum with a negative "
        "blue band is fitted exactly like any other. It is recorded because a "
        "depressed or negative blue ``Rrs`` is what the failed retrievals have "
        "in common, while a negative band *anywhere* in the window is ordinary "
        "(the red bands of clear-water spectra dip below zero). Fits made before "
        "the quantity existed were backfilled from the spectrum stored with "
        "their chains, so fit-time and backfilled counts are the same number."
        + rate
        + "\n"
    )


def _methods_failed_retrievals(df) -> str:
    """The Methods page's "Failed retrievals" paragraph: the gate, the count
    computed from the store's matchup frame ``df`` (deferred to the
    Comparisons page when it is ``None``), what is and is not gated, and the
    pointer to the investigation."""
    count = ""
    if df is not None:
        _, clause = _gated(df, "bbp_bing")
        count = f" In this release that is {clause}."
    if not count:
        count = " The *Comparisons* page reports how many fits this excludes in this release."
    return (
        "**Failed retrievals.** A BING ``b_bp`` (700 nm) above "
        f"{compare.BBP_IMPLAUSIBLE:g} m⁻¹ is not a measurement of seawater (the "
        "open ocean spans roughly 1e-4 to 1e-1 m⁻¹) but an optimiser failure: "
        "the fit ran to the prior ceiling on a spectrum with a depressed or "
        "negative blue ``Rrs``. Such fits are **excluded from every ``b_bp`` "
        "statistic and figure** on this site — the headline, the density "
        "panels, both maps, the aggregates and the NASA-GIOP and 1.0-vs-2.0 "
        "comparisons — and each caption says how many." + count + " The "
        "chlorophyll of the same fits is not gated, the figure gallery shows "
        "one such fit on purpose, and the downloadable summary table keeps the "
        "raw values with a 0/1 ``bbp_bing_implausible`` column so a reader can "
        "apply or lift the gate. What went wrong and why is in "
        f"`high_bbp_outliers.md <{compare.BBP_OUTLIERS_URL}>`__.\n"
    )


def methods_page(*, compare_db=None, store=None) -> str:
    """Reader-facing methods/context page: data, protocol, retrieval, how to read
    the figures and metrics, caveats, and references.

    ``compare_db`` (the frozen v1 database) adds the two-database provenance
    note; the 2.0 retrieval configuration is described either way, because it
    describes *this* release whether or not 1.0 is alongside it. ``store``
    (optional) lets the NASA-GIOP caveat quote the **computed** fraction of
    slopes at GIOP's ceiling; without it the sentence points at the
    Comparisons page, which always computes it.
    """
    out = [_heading("Methods"), ""]
    out.append(
        "This page explains what PAB does and how to read the results. PAB pairs "
        "satellite ocean-colour observations with in-situ float profiles, retrieves "
        "the optical properties from the satellite spectrum, and compares them "
        "against the float — a like-for-like validation of the satellite product.\n"
    )

    out.append(_heading("Data", "-"))
    out.append(
        "- **Satellite — PACE/OCI Level-2 AOP.** NASA's PACE mission (Ocean Colour "
        "Instrument) hyperspectral remote-sensing reflectance ``Rrs(λ)``, accessed "
        "by ``earthaccess``. PAB reads only the pixels near each float.\n"
        "- **In-situ — BGC-Argo.** Autonomous biogeochemical floats, fetched via "
        "``argopy``. PAB de-spikes and averages ``BBP700`` (particulate backscatter "
        "at 700 nm) and ``CHLA`` (chlorophyll-a) within the mixed layer, and records "
        "the mixed-layer depth (MLD) and mean temperature/salinity.\n"
    )

    out.append(_heading("Matchup protocol", "-"))
    out.append(
        "Following **Bisson et al. (2019)**: for each float profile PAB takes a "
        "small box of **unflagged** PACE pixels centred on the float position and a "
        "**tight time window** between the profile and the overpass. A profile with "
        "no qualifying pixels (cloud, glint, or simply no coincident scene) yields "
        "no matchup — that is expected, not an error. The space/time separation and "
        "the number of valid spectra for each matchup are listed in the *Matchup "
        "quality* table on the *Aggregate results* page.\n"
    )

    out.append(_heading("Retrieval (BING)", "-"))
    out.append(
        "The satellite ``Rrs`` spectrum is fit with **BING** (Bayesian inference "
        "with Gordon coefficients; Prochaska & Frouin 2025), which returns the "
        "inherent optical properties with full posterior uncertainties:\n"
        "\n"
        "- **``b_bp``** — non-water particulate backscatter (reported at 700 nm, to "
        "match the float ``BBP700``); the primary matchup observable.\n"
        "- **Chlorophyll** — retrieved from the fitted phytoplankton absorption "
        "amplitude ``Aph`` (``Chl = 10**Aph / 0.05582``). The float ``CHLA`` only "
        "*seeds* the absorption shape; it is **not** a fixed input, so the BING Chl "
        "is a genuine retrieval compared against the in-situ value. An independent "
        "**OC4** band-ratio Chl is shown as a cross-check when available.\n"
    )
    matchups_df = _methods_matchups(store)  # one query for both paragraphs
    out.append(_methods_failed_retrievals(matchups_df))
    out.append(_methods_neg_blue(matchups_df))

    out.append(_heading("Retrieval configuration (2.0) & the two databases", "-"))
    out.append(V2_CHANGES)
    out.append(
        "**``pab_version`` semantics.** Every row carries the version of the "
        "*analysis* that produced it, not of the code that wrote it. ``1.0`` is "
        "the elastic BING retrieval of the v1 release; ``2.0`` is the inelastic "
        "re-analysis in this one; ``1.1`` marks the NASA-GIOP ingests, which are "
        "the **same NASA product read by the same code** in both releases and so "
        "are deliberately *not* re-stamped ``2.0`` — a re-stamp would imply a "
        "re-analysis that did not happen.\n"
    )
    if compare_db:
        out.append(
            "**Two databases.** The 1.0 fits are not in this release's database. "
            "They live in the **frozen v1 database**, which is held read-only "
            "(and at an older schema) so published results cannot be edited "
            "after the fact; the 1.0-vs-2.0 comparison attaches it read-only "
            "and joins on matchup **and pixel**, so each pair is two retrievals "
            "of one spectrum. Matchups fitted in only one of the two releases "
            "are absent from that comparison rather than being half-filled.\n"
        )
    out.append(_heading("How to read the figures & metrics", "-"))
    out.append(
        "Each scatter plots the **satellite** value (y) against the **in-situ** "
        "float value (x) on log axes, with the **1:1 line** for reference; points on "
        "the line are perfect agreement. **Hover** a point to see its matchup id, "
        "float, and values; **tap** a point to open that matchup's BING fit figure. "
        "The headline and binned tables report, per group:\n"
        "\n"
        "- **median sat/float ratio** — typical multiplicative bias (1.0 = no bias);\n"
        "- **Spearman ρ** — rank correlation between satellite and float (1 = "
        "perfectly monotonic);\n"
        "- **log10 bias / RMS / MAD** — mean / scatter / robust scatter of "
        "``log10(satellite / in-situ)`` (0 = unbiased; smaller is tighter).\n"
        "\n"
        "The **PACE scene quick-looks** show the false-colour scene around each "
        "float (red star) with the analyzed pixels (white circles), so cloudy or "
        "glinty scenes are obvious. The **Argo profile Q&A** plots show ``BBP700`` "
        "and ``CHLA`` vs pressure with the MLD marked, to sanity-check each "
        "in-situ summary.\n"
    )

    out.append(_heading("Caveats & provenance", "-"))
    out.append(
        "- **Sample size.** This release may cover a small development set; treat "
        "the aggregate statistics accordingly.\n"
        "- **Granule access.** Run out-of-region (outside AWS ``us-west-2``), PACE "
        "reads are slow; PAB pre-downloads granules for reliability. This affects "
        "*how* the data were read, not the results.\n"
        "- **BING vs NASA GIOP.** The *Comparisons* page includes NASA's own "
        "retrieval as a baseline: the operational ``PACE_OCI_L2_IOP`` product "
        "(**GIOP** algorithm, default configuration; Werdell et al. 2013), read "
        "at the **same pixel** used for each BING fit. NASA reports ``b_bp`` at "
        "**442 nm**, BING at **700 nm**; for the comparison NASA's value is "
        "shifted to 700 nm with GIOP's own per-pixel power-law slope "
        f"``bbp_s``: ``{compare.GIOP_BBP_SHIFT_FORMULA}`` (bounds scaled by the "
        "same factor; nothing is written back to the database). "
        + _methods_ceiling_sentence(store)
        + " **GSM is absent by NASA product availability, not by choice:** NASA "
        "does not operationally distribute a GSM (Garver-Siegel-Maritorena) "
        "Level-2 product for PACE — GIOP is the only distributed L2 IOP suite — "
        "so no GSM comparison is possible without reprocessing from Level-1B. "
        'The NASA-GIOP records carry ``pab_version = "1.1"`` (they were added '
        "alongside the existing ``1.0`` BING fits; the BING results are "
        "unchanged).\n"
        "- **Provenance.** Every record is stamped with a ``pab_version``; the "
        "landing page shows the version and build date for this site. Per-matchup "
        "MCMC chains and figures are published as downloads (see the release "
        "manifest), keyed by matchup id.\n"
    )

    out.append(_heading("References", "-"))
    out.append(
        "- Prochaska & Frouin (2025), *BING* — Bayesian inference of IOPs from "
        "remote-sensing reflectance with the Gordon model.\n"
        "- Bisson et al. (2019) — satellite/in-situ ocean-colour matchup protocol "
        "and uncertainty assessment.\n"
    )
    return "\n".join(out)


#: The downloadable summary tables: ``export_tables`` key stem, file stem and
#: link text. The NASA-GIOP table (one row per matchup with both retrievals,
#: ``bbp_442_nasa`` as stored plus the derived ``bbp_700_nasa``) is listed only
#: when the store holds an ingest, so a dev site never links an absent file.
_DOWNLOAD_TABLES = (
    ("summary", "matchup_summary", "Matchup summary"),
    ("nasa_giop", "nasa_giop_summary", "BING vs NASA GIOP summary"),
)


def _has_nasa_giop(store) -> bool:
    return bool(
        store.query("SELECT 1 FROM fits WHERE algorithm = 'NASA_GIOP' LIMIT 1")
    )


def downloads_page(store, outdir, *, downloads_base_url: str | None = None) -> str:
    """The **Downloads** page: links the matchup and BING-vs-NASA summary tables.

    Default (``downloads_base_url=None``): stage the summary CSV/Parquet
    (``publish.export_tables``) into ``outdir/_static/downloads`` and link them
    page-relative — fine for a small dev set committed with the site. At full
    scale those tables are multi-MB, so pass ``downloads_base_url`` (e.g. the
    ``s3://pab`` public URL prefix) and the page links them **there** instead,
    staging nothing into git — the "reference by S3 URL at scale" path in
    ``HOWTO.md`` §7b. The bulky per-matchup chains/figures live in the object
    store keyed by ``matchup_id``. Best-effort: never breaks the build.
    """
    from pab.report import publish

    out = [_heading("Downloads"), ""]
    links = []
    if downloads_base_url:
        base = downloads_base_url.rstrip("/")
        for key, stem, text in _DOWNLOAD_TABLES:
            if key == "nasa_giop" and not _has_nasa_giop(store):
                continue
            links.append(f'<li><a href="{base}/{stem}.csv">{text} (CSV)</a></li>')
            links.append(
                f'<li><a href="{base}/{stem}.parquet">{text} (Parquet)</a></li>'
            )
    else:
        try:
            tables = publish.export_tables(
                store, Path(outdir) / "_static" / "downloads"
            )
        except Exception:  # noqa: BLE001 — downloads are a bonus, not load-bearing
            tables = {}
        for key, stem, text in _DOWNLOAD_TABLES:
            for ext, fmt in (("csv", "CSV"), ("parquet", "Parquet")):
                if f"{key}_{ext}" in tables:
                    links.append(
                        f'<li><a href="_static/downloads/{stem}.{ext}">'
                        f"{text} ({fmt})</a></li>"
                    )
    if links:
        out.append(".. raw:: html\n")
        out.extend("   " + ln for ln in ["<ul>", *links, "</ul>"])
        out.append("")
    out.append(
        "Per-matchup MCMC chains and BING fit figures are published as object-store "
        "artifacts (NSF/Nautilus S3), keyed by ``matchup_id`` in the release "
        "manifest — available once that backend is activated.\n"
    )
    return "\n".join(out)


def provenance_block(*, pab_version: str | None = None) -> str:
    """A provenance footer: the ``pab_version`` + build date and a table of the
    installed package versions (:func:`pab.config.package_versions`), so every
    published site is traceable to the code and environment that produced it.

    Uses a static reStructuredText table (no Bokeh) — provenance must always render.
    """
    import pandas as pd

    from pab.config import package_versions

    pab_version = pab_version or _pab_version
    out = [_heading("Provenance", "-"), ""]
    out.append(
        f"Built from ``pab_version`` ``{pab_version}`` on "
        f"{datetime.now(UTC).date().isoformat()}. Installed package versions:\n"
    )
    pv = dict(package_versions())
    # `git_sha` is a nested {repo: sha} map, not a version string — render it as
    # its own table rather than letting a dict repr into the version column.
    shas = pv.pop("git_sha", None)
    df = pd.DataFrame({"package": list(pv), "version": list(pv.values())})
    out.append(rst_table(df))
    if shas:
        out.append("")
        out.append(
            "Source revisions (the editable installs all report ``0.0.dev0``, "
            "so the commit is what identifies the code):\n"
        )
        sha_df = pd.DataFrame({"repository": list(shas), "commit": list(shas.values())})
        out.append(rst_table(sha_df))
    return "\n".join(out)


def index_page() -> str:
    """The site front page: a reader-facing description of PAB + the toctree."""
    out = [_heading("PAB — PACE ↔ BGC-Argo Matchups"), ""]
    out.append(
        "**PAB** produces **matchup analyses between PACE (satellite ocean colour) "
        "and BGC-Argo (autonomous float) data**, and shares the results with the "
        "community.\n"
    )

    out.append(_heading("Why", "-"))
    out.append(
        "Satellite ocean-colour missions like NASA's **PACE** retrieve the ocean's "
        "inherent optical properties (IOPs) and chlorophyll from space — but those "
        "retrievals need validation against independent, in-situ measurements. "
        "**BGC-Argo** floats drift through the global ocean returning vertical "
        "profiles of exactly the quantities PACE estimates: particulate backscatter "
        "(``BBP700``) and chlorophyll (``CHLA``). PAB pairs the two — for every "
        "float profile it finds the coincident PACE scene, retrieves the IOPs from "
        "the satellite spectrum with **BING**, and compares them against the float. "
        "The result is a growing, reproducible record of how well the satellite "
        "agrees with the ocean.\n"
    )

    out.append(_heading("What PAB does", "-"))
    out.append(
        "For each BGC-Argo profile, PAB:\n"
        "\n"
        "#. **Matches** it to the closest-in-space-and-time PACE/OCI Level-2 scene "
        "(following Bisson et al. 2019 — an unflagged pixel box and a tight time "
        "window);\n"
        "#. **Extracts** the ~10 nearest remote-sensing reflectance (``Rrs``) "
        "spectra;\n"
        "#. **Retrieves** the IOPs — non-water backscatter ``b_bp`` and chlorophyll "
        "— with **BING** (Bayesian inference with Gordon coefficients), with full "
        "posterior uncertainties;\n"
        "#. **Compares** the satellite retrieval against the float's mixed-layer "
        "values.\n"
    )

    out.append(_heading("What's on this site", "-"))
    out.append(
        "- :doc:`Summary <summary>` — dataset coverage and the headline "
        "satellite-vs-float ``b_bp`` and chlorophyll metrics.\n"
        "- :doc:`Comparisons <comparisons>` — the interactive ``b_bp`` and "
        "chlorophyll scatter plots and the matchup map (hover for values, tap for "
        "the fit figure).\n"
        "- :doc:`Figures <figures>` — per-matchup BING fit figures, PACE scene "
        "quick-looks, and the Argo profile Q&A plots.\n"
        "- :doc:`Aggregate results <aggregates>` — population statistics binned by "
        "region and season (plus an equal-area HEALPix view) and a per-matchup "
        "quality table.\n"
        "- :doc:`Methods <methods>` — the data, the matchup protocol, the BING "
        "retrieval, how to read the figures and metrics, caveats, provenance, and "
        "references.\n"
        "- :doc:`Downloads <downloads>` — the exported summary tables "
        "(CSV/Parquet).\n"
        "\n"
        "New here? Start with the :doc:`Summary <summary>`, then open the "
        ":doc:`Comparisons <comparisons>`. Every result is stamped with a "
        "``pab_version`` for provenance.\n"
    )

    out.append(".. toctree::\n   :maxdepth: 1\n   :hidden:\n")
    out.append(
        "   summary\n   comparisons\n   figures\n   aggregates\n   methods\n"
        "   downloads\n"
    )
    return "\n".join(out)


def reporting_conf(*, pab_version: str | None = None) -> str:
    """A minimal Sphinx ``conf.py`` for the **separate** reporting site.

    Distinct from the developer docs: a content-only static site. When ``bokeh``
    is installed, the BokehJS CDN is added to ``html_js_files`` so the embedded
    standalone figures and tables actually render.
    """
    pab_version = pab_version or _pab_version
    js_files: list[str] = []
    try:
        from bokeh.resources import CDN

        js_files = list(CDN.js_files)
    except ImportError:
        pass
    return (
        '"""Sphinx config for the PAB reporting site (generated; separate from '
        'the developer docs)."""\n'
        f'project = "PAB matchup results"\n'
        f'release = version = "{pab_version}"\n'
        "extensions = []\n"
        'exclude_patterns = ["_build"]\n'
        "try:\n"
        "    import sphinx_rtd_theme  # noqa: F401\n\n"
        '    html_theme = "sphinx_rtd_theme"\n'
        "except ImportError:\n"
        '    html_theme = "alabaster"\n'
        f"html_js_files = {js_files!r}\n"
        "# Per-matchup figures are copied under _static/figures and served verbatim.\n"
        'html_static_path = ["_static"]\n'
    )


def _gather_with_figures(store, outdir: Path, *, opener=None, figure_roots=None):
    """The per-matchup comparison frame with a ``figure_url`` column.

    Each matchup's fit figure (``fits.figure_path``, translated through
    ``figure_roots`` — see :func:`remap_figure_path`) is copied into
    ``outdir/_static/figures`` (so Sphinx serves it verbatim) and the
    page-relative URL recorded in :data:`FIGURE_URL_COL`. Rows whose figure is
    missing on disk get ``None`` there. When ``opener`` is given, the OC4
    band-ratio Chl cross-check (``chl_oc``) is added via
    :func:`pab.metrics.compare.add_oc_chl` — best-effort: it re-reads each
    matchup's pixel ``Rrs`` through the opener, so it is skipped silently if
    ``ocpy`` is missing or a granule read fails. Returns the strata-augmented frame.
    """
    df = compare.add_strata(compare.gather_matchups(store))
    if not len(df):
        return df
    if opener is not None:
        try:
            df = compare.add_oc_chl(df, store, opener=opener)
        except Exception:  # noqa: BLE001 — ocpy missing / granule read failure
            pass
    fig_paths = {
        r["fit_id"]: r["figure_path"]
        for r in store.query(
            "SELECT fit_id, figure_path FROM fits WHERE figure_path IS NOT NULL"
        )
    }
    # Both consumers of this column are N-guarded: the inline gallery
    # (`MAX_INLINE_FIGURES`) and the interactive scatter's tap-to-open
    # (`MAX_INTERACTIVE_MATCHUPS`, which also falls back to static PNGs). Above
    # both thresholds only the representative selection links to these files,
    # so only those are staged: copying the whole set into the site is 636 MB
    # and 3.2 h of CephFS traffic for an unreachable payload.
    df = df.copy()

    def stage(fit_id):
        return _stage_static(
            fig_paths.get(fit_id), outdir, "figures", figure_roots=figure_roots
        )

    if len(df) > max(MAX_INLINE_FIGURES, MAX_INTERACTIVE_MATCHUPS):
        chosen = set(select_representative_fits(df)["matchup_id"])
        _log.info(
            "report: %d matchups — staging only the %d representative fit "
            "figures into the site (nothing else links to them at this scale; "
            "they are published via the release manifest)",
            len(df),
            len(chosen),
        )
        df[FIGURE_URL_COL] = [
            stage(fit_id) if mid in chosen else None
            for mid, fit_id in zip(df["matchup_id"], df["fit_id"], strict=True)
        ]
        return df
    df[FIGURE_URL_COL] = [stage(fit_id) for fit_id in df["fit_id"]]
    return df


def build_site(
    store,
    outdir,
    *,
    pab_version: str | None = None,
    sortable: bool = True,
    opener=None,
    downloads_base_url: str | None = None,
    compare_db=None,
    figure_roots=None,
) -> dict[str, Path]:
    """Write the fixed aggregate ``.rst`` pages **and a Sphinx ``conf.py``** to
    ``outdir`` — a self-contained, buildable reporting-site source tree.

    The output is a **separate** Sphinx target from the developer docs: build it
    with ``sphinx-build <outdir> <outdir>/_build``.

    Args:
        store: An open :class:`pab.db.store.Store`.
        outdir: Output directory for the generated community-site sources.
        pab_version: Provenance stamp (defaults to :data:`pab.config.pab_version`).
        sortable: Render the stats tables as sortable Bokeh ``DataTable`` embeds
            when ``bokeh`` is available (else static ``list-table``).
        opener: Optional granule opener (test/cache seam). When given, the OC4
            band-ratio Chl cross-check (``chl_oc``) is added to the Chl figure.
        compare_db: Path to the frozen **v1** database. When given, the site
            gains the 1.0-vs-2.0 section, summary headline, and provenance
            note; when omitted (or the file is absent) those simply don't
            appear and every other page is unchanged.
        figure_roots: ``{stored_prefix: local_root}`` translating the in-pod
            figure paths recorded in the database (``fits.figure_path``,
            ``matchups.scene_path``, ``mld_summary.qa_path``) to where the
            files are on this machine — the CLI's repeatable
            ``--figure-root OLD=NEW``. Longest prefix wins; a file that is
            still missing is dropped from its gallery with a counted warning.

    Returns:
        ``{name: path}`` for each written file — the fixed :data:`PAGE_STEMS`
        pages plus ``conf`` (regardless of matchup count; no per-matchup pages).
    """
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    # Always present so the conf's html_static_path entry exists (no Sphinx warning).
    (outdir / "_static").mkdir(parents=True, exist_ok=True)

    df = _gather_with_figures(store, outdir, opener=opener, figure_roots=figure_roots)
    # The matchup results are split across topical pages so none is overloaded:
    # summary (coverage + headline metrics), comparisons (interactive scatters +
    # map), figures (the thumbnail galleries), aggregates (tables), methods,
    # downloads. All are fixed pages — still no per-matchup page.
    pages = {
        "index": index_page(),
        "summary": summary_page(
            store, pab_version=pab_version, compare_db=compare_db
        ),
        "comparisons": (
            comparisons_page(df, sortable=sortable, outdir=outdir)
            + "\n"
            + nasa_giop_section(store, outdir=outdir, sortable=sortable)
            + "\n"
            + version_section(
                store, compare_db, outdir=outdir, sortable=sortable
            )
        ),
        "figures": figures_page(store, outdir, df, figure_roots=figure_roots),
        "aggregates": (
            aggregates_page(store, sortable=sortable)
            + "\n"
            + matchup_quality_table(store, sortable=sortable)
        ),
        "methods": (
            methods_page(compare_db=compare_db, store=store)
            + "\n"
            + provenance_block(pab_version=pab_version)
        ),
        "downloads": downloads_page(
            store, outdir, downloads_base_url=downloads_base_url
        ),
    }
    written = {}
    for stem, text in pages.items():
        path = outdir / f"{stem}.rst"
        path.write_text(text)
        written[stem] = path
    conf = outdir / "conf.py"
    conf.write_text(reporting_conf(pab_version=pab_version))
    written["conf"] = conf
    return written
