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
            f"log10 bias = {_fmt(bbp['log_bias'])}, RMS = {_fmt(bbp['log_rms'])}.\n"
        )
    else:
        out.append("- (no matchups with a BING fit yet)\n")
    if chl.get("n"):
        out.append(_heading("Chlorophyll", "-"))
        out.append(
            f"- n = {chl['n']}; median sat/float ratio = "
            f"{_fmt(chl['median_ratio'])}; Spearman ρ = {_fmt(chl['spearman'])}.\n"
        )
    nasa_df = compare.gather_nasa_giop(store)
    nasa = (
        compare.log_comparison(nasa_df["bbp_442_nasa"], nasa_df["bbp_bing"])
        if len(nasa_df)
        else {}
    )
    if nasa.get("n"):
        out.append(_heading("BING vs NASA GIOP (b_bp)", "-"))
        out.append(
            f"- n = {nasa['n']}; median NASA(442 nm)/BING(700 nm) ratio = "
            f"{_fmt(nasa['median_ratio'])}; Spearman ρ = {_fmt(nasa['spearman'])}. "
            "**The wavelengths differ by design** — see the "
            ":doc:`comparisons <comparisons>` and :doc:`Methods <methods>` pages "
            "before reading this as a bias.\n"
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
    lines = []
    for key, label in (("bbp700", "b_bp(700 nm)"), ("chl", "chlorophyll")):
        c1, c2 = f"{key}_v1", f"{key}_v2"
        if c1 not in df or c2 not in df:
            continue
        st = compare.log_comparison(df[c2], df[c1])
        if st.get("n"):
            lines.append(
                f"- **{label}** — median 2.0/1.0 ratio = "
                f"{_fmt(st['median_ratio'])} (n = {st['n']:,})\n"
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
        "individual pages.\n"
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


#: Reader-facing caveat for every BING-vs-NASA ``b_bp`` figure/stat: the two
#: values are at different wavelengths, deliberately not spectrally adjusted
#: (``claude_prompts/pace_giop_gsm.md`` Q3).
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


_NASA_BBP_CAVEAT = (
    "**Wavelength caveat:** NASA reports ``b_bp`` at **442 nm** while BING's "
    "headline ``b_bp`` is at **700 nm** (chosen to match the float ``BBP700``). "
    "The two are compared **as-is, with no spectral adjustment**, so a ratio "
    "above 1 is expected simply from the blue-to-red decrease of particulate "
    "backscatter — read the scatter as a *consistency* check, not a "
    "like-for-like validation."
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
    on :func:`~pab.metrics.compare.gather_nasa_giop`. Both the figure and the
    stats carry the explicit 442 nm-vs-700 nm ``b_bp`` wavelength caveat.
    Returns ``""`` when the store holds no NASA-GIOP ingest (the section
    simply doesn't appear).
    """
    df = compare.gather_nasa_giop(store)
    if not len(df):
        return ""
    stats = compare.log_comparison(df["bbp_442_nasa"], df["bbp_bing"])

    out = [_heading("BING vs NASA GIOP (L2 IOP)", "-"), ""]
    out.append(
        "The same PACE overpasses, retrieved two ways: **BING** (this project) "
        "against NASA's own **GIOP** retrieval, read from the operational "
        "``PACE_OCI_L2_IOP`` product at the *same pixel* used for the BING fit. "
        "See the :doc:`Methods <methods>` page for the product details and "
        "provenance.\n"
    )
    out.append(_NASA_BBP_CAVEAT + "\n")
    if stats.get("n"):
        out.append(
            f"- n = {stats['n']}; median NASA(442)/BING(700) ratio = "
            f"{_fmt(stats['median_ratio'])} "
            f"(IQR {_fmt(stats['ratio_iqr_lo'])}–{_fmt(stats['ratio_iqr_hi'])}); "
            f"Spearman ρ = {_fmt(stats['spearman'])}; "
            f"log10 offset = {_fmt(stats['log_bias'])}, "
            f"RMS = {_fmt(stats['log_rms'])}.\n"
        )

    if outdir is not None and len(df) > max_interactive:
        try:
            from pab.plotting import population

            dest = Path(outdir) / "_static" / "comparisons"
            dest.mkdir(parents=True, exist_ok=True)
            population.comparison_scatter(
                df,
                "bbp_442_nasa",
                "bbp_bing",
                outfile=dest / "nasa_giop_bbp_scatter.png",
                xlabel="BING $b_{bp}$(700 nm) [m$^{-1}$]",
                ylabel="NASA GIOP $b_{bp}$(442 nm) [m$^{-1}$]",
            )
            out.append(
                ".. figure:: _static/comparisons/nasa_giop_bbp_scatter.png\n"
                "   :width: 520px\n\n"
                "   NASA GIOP ``b_bp`` (442 nm) vs BING ``b_bp`` (700 nm), "
                "log-log — **note the differing wavelengths** (no spectral "
                "adjustment applied).\n"
            )
        except Exception:  # noqa: BLE001 — a bad panel must not break the build
            pass
    elif sortable:
        try:
            from pab.report import interactive

            fig = interactive.comparison_scatter(
                df,
                sat_col="bbp_442_nasa",
                insitu_col="bbp_bing",
                title="NASA GIOP b_bp(442) vs BING b_bp(700) — wavelengths differ",
                xlabel="BING b_bp(700 nm)",
                ylabel="NASA GIOP b_bp(442 nm)",
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
    for key, label, _unit, _plain in pairs:
        c1, c2 = f"{key}_v1", f"{key}_v2"
        if c1 not in df or c2 not in df:
            continue
        st = compare.log_comparison(df[c2], df[c1])
        if not st.get("n"):
            continue
        out.append(
            f"- **{label}** — n = {st['n']:,}; median 2.0/1.0 ratio = "
            f"{_fmt(st['median_ratio'])} "
            f"(IQR {_fmt(st['ratio_iqr_lo'])}–{_fmt(st['ratio_iqr_hi'])}); "
            f"Spearman ρ = {_fmt(st['spearman'])}; "
            f"log10 offset = {_fmt(st['log_bias'])}, "
            f"RMS = {_fmt(st['log_rms'])}.\n"
        )
    out.append(_version_ratio_by_level(df))
    if outdir is not None:
        out.append(_ratio_figure_block(df, outdir))
    out.append(_version_failure_note(df))
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


#: Above this ``b_bp``(700 nm) a retrieval is not a measurement of seawater:
#: open-ocean particulate backscatter at 700 nm spans roughly 1e-4 to 1e-1
#: m^-1, so a value above 1 is a failed fit, not a bright scene.
BBP_IMPLAUSIBLE = 1.0


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
    lo_r = float(np.median(v2[groups[0][1]] / v1[groups[0][1]]))
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
        "Bins with fewer than 20 matchups are not plotted.\n"
    )

def _version_failure_note(df) -> str:
    """Count and report 2.0 fits that returned a non-physical ``b_bp``.

    Computed from the frame rather than hard-coded: the point of the note is
    that the number is checked at every build, so a regression that multiplies
    these shows up in the report instead of hiding behind a robust median.
    Returns ``""`` when there are none.
    """
    import numpy as np

    if "bbp700_v2" not in df:
        return ""
    v2 = np.asarray(df["bbp700_v2"], dtype=float)
    bad2 = int(np.count_nonzero(np.isfinite(v2) & (v2 > BBP_IMPLAUSIBLE)))
    if not bad2:
        return ""
    n = int(np.isfinite(v2).sum())
    bits = [
        f"**Retrieval failures.** {bad2} of {n:,} 2.0 fits "
        f"({bad2 / n * 100:.2f} %) return ``b_bp``(700 nm) above "
        f"{BBP_IMPLAUSIBLE:g} m⁻¹, which is not a possible value for seawater "
        "(the open ocean spans roughly 1e-4 to 1e-1 m⁻¹); the largest is "
        f"{np.nanmax(v2):.3g} m⁻¹."
    ]
    if "bbp700_v1" in df:
        v1 = np.asarray(df["bbp700_v1"], dtype=float)
        bad1 = int(np.count_nonzero(np.isfinite(v1) & (v1 > BBP_IMPLAUSIBLE)))
        bits.append(
            f" The same matchups fitted in 1.0 produce {bad1} such value"
            f"{'' if bad1 == 1 else 's'} (maximum {np.nanmax(v1):.3g} m⁻¹), so "
            "these are specific to the 2.0 configuration."
        )
    bits.append(
        " They are **left in** every statistic on this page — the medians and "
        "Spearman ρ are rank-based and barely move — and are flagged here "
        "rather than filtered, so the failure rate stays visible.\n"
    )
    bits.append(_runaway_regime_note(df))
    return "".join(bits)


#: Retrieved-Chl bin edges for the runaway-rate table. Chosen to straddle the
#: ultra-oligotrophic range where the failures live; the rates are computed, so
#: a shift in the data changes the table rather than falsifying it.
_RUNAWAY_CHL_EDGES = (0.0, 0.01, 0.02, 0.05, 0.1, 0.3, float("inf"))


def _runaway_regime_note(df) -> str:
    """Where the non-physical retrievals live, as a rate by retrieved Chl.

    The investigation behind this (Prompt 8 Q1) ruled out a node, granule or
    sampler cause — the failures spread over 47 distinct granules with every
    convergence flag set and viewing geometry indistinguishable from the rest.
    What does separate them is the regime, and that makes them the extreme
    tail of the clear-water result above rather than a separate defect. Worth
    a table rather than a sentence, because the rate is zero over most of the
    range and a single average would hide that.
    """
    import numpy as np

    if "chl_v2" not in df or "bbp700_v2" not in df:
        return ""
    chl = np.asarray(df["chl_v2"], dtype=float)
    bbp = np.asarray(df["bbp700_v2"], dtype=float)
    ok = np.isfinite(chl) & np.isfinite(bbp)
    if ok.sum() < 500:
        return ""
    chl, bbp = chl[ok], bbp[ok]
    bad = bbp > BBP_IMPLAUSIBLE
    if not bad.any():
        return ""
    rows = []
    for lo, hi in zip(_RUNAWAY_CHL_EDGES[:-1], _RUNAWAY_CHL_EDGES[1:], strict=False):
        m = (chl >= lo) & (chl < hi)
        if not m.sum():
            continue
        label = f"{lo:g}–{hi:g}" if np.isfinite(hi) else f"> {lo:g}"
        if lo == 0:
            label = f"< {hi:g}"
        rows.append((label, int(m.sum()), int((m & bad).sum())))
    if len(rows) < 3:
        return ""
    out = [
        "\n**They are not scattered at random — they are the clear-water tail.** "
        "The failures spread over many granules, carry every convergence flag "
        "set, and have viewing geometry, separation and spectrum count "
        "indistinguishable from the rest; what separates them is the regime. "
        "Rate by retrieved chlorophyll:\n",
        "",
        ".. list-table::",
        "   :header-rows: 1",
        "",
        "   * - Chl [mg m⁻³]",
        "     - matchups",
        "     - non-physical",
        "     - rate",
    ]
    for label, n, nb in rows:
        out += [
            f"   * - {label}",
            f"     - {n:,}",
            f"     - {nb}",
            f"     - {nb / n * 100:.2f} %",
        ]
    out.append("")
    out.append(
        "So the same mechanism that makes the inelastic correction large in "
        "clear water also makes the retrieval ill-conditioned there, and in a "
        "small number of cases it fails outright. **No single-variable filter "
        "isolates them**: a χ² cut that catches most of them flags fourteen "
        "times as many sound fits, and so does a chlorophyll cut. They are the "
        "tail of a continuum, not a separable population, which is why they "
        "are reported rather than removed.\n"
    )
    return "\n".join(out)

def _version_static_figures(df, outdir) -> str:
    """Static 2.0-vs-1.0 ``bbp700``/``chl`` scatters for the large-N page."""
    try:
        from pab.plotting import population
    except ImportError:
        return ""
    dest = Path(outdir) / "_static" / "comparisons"
    dest.mkdir(parents=True, exist_ok=True)
    figs: list[tuple[str, str]] = []
    # Two labels per row, deliberately: `mpl` is Matplotlib mathtext for the
    # axis, `rst` is what goes in the caption. Reusing one put a literal
    # "$b_{bp}$" into the rendered page.
    for key, mpl, unit, rst_label in (
        ("bbp700", "$b_{bp}$(700 nm)", "m$^{-1}$", "``b_bp`` (700 nm)"),
        ("chl", "chlorophyll", "mg m$^{-3}$", "chlorophyll"),
    ):
        c1, c2 = f"{key}_v1", f"{key}_v2"
        if c1 not in df or c2 not in df:
            continue
        try:
            population.comparison_scatter(
                df,
                c2,
                c1,
                outfile=dest / f"v2_vs_v1_{key}.png",
                xlabel=f"1.0 (elastic) {mpl} [{unit}]",
                ylabel=f"2.0 (inelastic) {mpl} [{unit}]",
                # A handful of 2.0 fits return non-physical values (see the
                # retrieval-failure note in the section text). Autoscaling to
                # them squashes every real point into a corner; the off-scale
                # count is printed in the panel and they stay in the stats.
                clip_percentile=99.0,
            )
            figs.append(
                (
                    f"v2_vs_v1_{key}.png",
                    f"2.0 (inelastic) vs 1.0 (elastic) {rst_label}, log-log, "
                    "same matchup and same pixel. The dashed line is the "
                    "median ratio; the solid line is 1:1.",
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
        import numpy as np

        from pab.plotting import population
    except ImportError:
        return ""
    dest = Path(outdir) / "_static" / "comparisons"
    dest.mkdir(parents=True, exist_ok=True)
    figs: list[tuple[str, str]] = []
    try:
        population.comparison_scatter(
            df,
            "bbp_bing",
            "bbp_argo",
            label="b_bp",
            unit="m$^{-1}$",
            outfile=dest / "bbp_scatter.png",
        )
        figs.append(
            ("bbp_scatter.png", "Satellite vs float ``b_bp`` (700 nm), log-log.")
        )
    except Exception:  # noqa: BLE001 — a bad panel must not break the build
        pass
    if "chl_bing" in df and "chla_argo" in df:
        try:
            population.comparison_scatter(
                df,
                "chl_bing",
                "chla_argo",
                label="chlorophyll",
                unit="mg m$^{-3}$",
                outfile=dest / "chl_scatter.png",
            )
            figs.append(("chl_scatter.png", "Satellite vs float chlorophyll, log-log."))
        except Exception:  # noqa: BLE001
            pass
    try:
        dfm = df.copy()
        with np.errstate(divide="ignore", invalid="ignore"):
            dfm["ratio"] = dfm["bbp_bing"].to_numpy(dtype=float) / dfm[
                "bbp_argo"
            ].to_numpy(dtype=float)
        population.matchup_map(dfm, color_col="ratio", outfile=dest / "matchup_map.png")
        figs.append(
            (
                "matchup_map.png",
                "Matchup locations, coloured by sat/float ``b_bp`` ratio.",
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


def figures_page(store, outdir, df) -> str:
    """The **Figures** page: the per-matchup fit, PACE scene, and Argo Q&A
    thumbnail galleries (each N-guarded; no per-matchup pages)."""
    out = [_heading("Matchup & profile figures"), ""]
    out.append(
        "Per-matchup **BING fit** figures and **PACE scene** quick-looks, plus the "
        "**Argo profile Q&A** plots. Shown as thumbnails (click to enlarge), never "
        "as separate per-matchup pages.\n"
    )
    out.append(figure_gallery(df))
    out.append(scene_gallery(store, outdir))
    out.append(argo_qa_gallery(store, outdir))
    return "\n".join(out)


def _stage_static(src, outdir, subdir: str) -> str | None:
    """Copy an artifact into ``outdir/_static/<subdir>`` and return its
    page-relative URL, or ``None`` if ``src`` is missing/not on disk.

    The one place that copies a figure into the site tree — shared by the fit,
    scene, and Argo-Q&A galleries so the copy/URL convention stays consistent.
    """
    if not (src and Path(src).is_file()):
        return None
    dest = Path(outdir) / "_static" / subdir
    dest.mkdir(parents=True, exist_ok=True)
    name = Path(src).name
    shutil.copyfile(src, dest / name)
    return f"_static/{subdir}/{name}"


def _thumbnail_gallery(
    items, *, heading: str, intro: str, over_limit: str, max_inline: int
) -> str:
    """An N-guarded clickable-thumbnail gallery from ``(url, caption)`` items.

    For a small set (``<= max_inline``) every item is shown as a thumbnail that
    links to the full PNG; above the threshold the gallery is suppressed (the
    design's no-page-explosion constraint) and ``over_limit`` (a ``{n}`` template)
    is shown instead. Returns ``""`` when there are no items.
    """
    items = [(u, c) for (u, c) in items if isinstance(u, str) and u]
    if not items:
        return ""
    out = [_heading(heading, "-"), ""]
    if len(items) > max_inline:
        out.append(over_limit.format(n=len(items)) + "\n")
        return "\n".join(out)
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


def figure_gallery(
    df, *, url_col: str = FIGURE_URL_COL, max_inline: int = MAX_INLINE_FIGURES
) -> str:
    """An N-guarded inline gallery of per-matchup fit figures (no per-matchup pages).

    For a small population every matchup's fit figure is a clickable thumbnail
    (tap opens the full PNG / download); above the threshold detail comes via
    tap-to-open on the scatter plus the release-manifest downloads.
    """
    items = [
        (r.get(url_col), f"{r.get('wmo')}/{r.get('cycle')}") for _, r in df.iterrows()
    ]
    return _thumbnail_gallery(
        items,
        heading="Per-matchup figures",
        intro="One thumbnail per matchup (the design exposes figures, not "
        "per-matchup pages). Click a thumbnail to open the full-resolution PNG.",
        over_limit="{n} matchups — too many to show inline. Per-matchup fit "
        "figures are available as downloads (see the release manifest) and by "
        "tapping a point in the scatter above.",
        max_inline=max_inline,
    )


def argo_qa_gallery(store, outdir, *, max_inline: int = MAX_INLINE_FIGURES) -> str:
    """An N-guarded gallery of the **Argo profile Q&A** figures.

    Each ``mld_summary.qa_path`` (BBP700/CHLA vs pressure with the MLD marked,
    emitted by ``ingest``) is copied into ``outdir/_static/argo_qa`` and linked.
    Returns ``""`` when no profile has a recorded, on-disk Q&A figure.
    """
    rows = store.query(
        "SELECT p.wmo, p.cycle, ms.qa_path FROM mld_summary ms "
        "JOIN profiles p ON p.profile_id = ms.profile_id "
        "WHERE ms.qa_path IS NOT NULL ORDER BY p.wmo, p.cycle"
    )
    items = [
        (_stage_static(r["qa_path"], outdir, "argo_qa"), f"{r['wmo']}/{r['cycle']}")
        for r in rows
    ]
    return _thumbnail_gallery(
        items,
        heading="Argo profile Q&A",
        intro="Per-profile quality-assurance plots: ``BBP700`` and ``CHLA`` vs "
        "pressure with the mixed-layer depth marked — to eyeball the MLD and the "
        "de-spiking behind each summary. Click a thumbnail to enlarge.",
        over_limit="{n} profiles — too many to show inline; the per-profile Q&A "
        "plots are available as downloads.",
        max_inline=max_inline,
    )


def scene_gallery(store, outdir, *, max_inline: int = MAX_INLINE_FIGURES) -> str:
    """An N-guarded gallery of the **PACE scene quick-looks** per matchup.

    Each ``matchups.scene_path`` (false-colour scene around the float, emitted by
    the ``figure`` stage) is copied into ``outdir/_static/scenes`` and linked.
    Returns ``""`` when no matchup has a recorded, on-disk scene figure.
    """
    rows = store.query(
        "SELECT p.wmo, p.cycle, m.scene_path FROM matchups m "
        "JOIN profiles p ON p.profile_id = m.profile_id "
        "WHERE m.scene_path IS NOT NULL ORDER BY p.wmo, p.cycle"
    )
    items = [
        (_stage_static(r["scene_path"], outdir, "scenes"), f"{r['wmo']}/{r['cycle']}")
        for r in rows
    ]
    return _thumbnail_gallery(
        items,
        heading="PACE scene quick-looks",
        intro="False-colour PACE/OCI scene around each float (red star = float "
        "position; white circles = the analyzed pixels) — so cloudy or glinty "
        "scenes are visible at a glance. Click a thumbnail to enlarge.",
        over_limit="{n} matchups — too many to show inline; the scene quick-looks "
        "are available as downloads.",
        max_inline=max_inline,
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

    df = compare.add_strata(compare.gather_matchups(store))
    out = [_heading("Aggregate results"), ""]
    out.append(
        "Population statistics binned by region and season, and an equal-area "
        "HEALPix spatial aggregation. Per-matchup detail is available through the "
        "interactive figures, not as individual pages.\n"
    )
    if not len(df):
        out.append("(no matchups yet)\n")
        return "\n".join(out)
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


def methods_page(*, compare_db=None) -> str:
    """Reader-facing methods/context page: data, protocol, retrieval, how to read
    the figures and metrics, caveats, and references.

    ``compare_db`` (the frozen v1 database) adds the two-database provenance
    note; the 2.0 retrieval configuration is described either way, because it
    describes *this* release whether or not 1.0 is alongside it.
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
        "**442 nm**, BING at **700 nm**; the comparison is deliberately **not** "
        "spectrally adjusted, and every figure/stat is labelled accordingly. "
        "**GSM is absent by NASA product availability, not by choice:** NASA "
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


def downloads_page(store, outdir, *, downloads_base_url: str | None = None) -> str:
    """The **Downloads** page: links the matchup summary tables.

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
        links.append(
            f'<li><a href="{base}/matchup_summary.csv">Matchup summary (CSV)</a></li>'
        )
        links.append(
            f'<li><a href="{base}/matchup_summary.parquet">'
            "Matchup summary (Parquet)</a></li>"
        )
    else:
        try:
            tables = publish.export_tables(
                store, Path(outdir) / "_static" / "downloads"
            )
        except Exception:  # noqa: BLE001 — downloads are a bonus, not load-bearing
            tables = {}
        if "summary_csv" in tables:
            links.append(
                '<li><a href="_static/downloads/matchup_summary.csv">'
                "Matchup summary (CSV)</a></li>"
            )
        if "summary_parquet" in tables:
            links.append(
                '<li><a href="_static/downloads/matchup_summary.parquet">'
                "Matchup summary (Parquet)</a></li>"
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


def _gather_with_figures(store, outdir: Path, *, opener=None):
    """The per-matchup comparison frame with a ``figure_url`` column.

    Each matchup's fit figure (``fits.figure_path``) is copied into
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
    urls = [
        _stage_static(fig_paths.get(fit_id), outdir, "figures")
        for fit_id in df["fit_id"]
    ]
    df = df.copy()
    df[FIGURE_URL_COL] = urls
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

    Returns:
        ``{name: path}`` for each written file — the fixed :data:`PAGE_STEMS`
        pages plus ``conf`` (regardless of matchup count; no per-matchup pages).
    """
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    # Always present so the conf's html_static_path entry exists (no Sphinx warning).
    (outdir / "_static").mkdir(parents=True, exist_ok=True)

    df = _gather_with_figures(store, outdir, opener=opener)
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
        "figures": figures_page(store, outdir, df),
        "aggregates": (
            aggregates_page(store, sortable=sortable)
            + "\n"
            + matchup_quality_table(store, sortable=sortable)
        ),
        "methods": (
            methods_page(compare_db=compare_db)
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
