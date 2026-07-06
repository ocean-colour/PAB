"""Programmatic reStructuredText generation for the reporting site (Stage 7).

Builds a **small, fixed set of aggregate pages** from the SQLite store — a
landing/summary page, a binned-results page, and a methods page — never one page
per matchup (the design's hard constraint at ~10⁴ matchups; per-matchup detail is
reached on demand through the interactive figures). Pure string generation
(unit-testable); :func:`build_site` writes the pages to an output directory
*outside* the developer docs.
"""

from __future__ import annotations

import shutil
from datetime import UTC, datetime
from pathlib import Path

from pab.config import pab_version as _pab_version
from pab.metrics import compare

#: Where per-matchup figures are copied inside the site source tree so Sphinx
#: serves them verbatim (``html_static_path``). The same relative URL works for
#: the inline gallery, the per-matchup download links, and the scatter's
#: tap-to-open — one mechanism, no reliance on Sphinx's ``_images`` renaming.
FIGURE_URL_COL = "figure_url"
_STATIC_FIGURES = "_static/figures"
#: Above this matchup count the inline gallery is suppressed (the design's
#: no-page-explosion constraint); detail then comes via tap-to-open + downloads.
MAX_INLINE_FIGURES = 50

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


def summary_page(store, *, pab_version: str | None = None) -> str:
    """The landing/summary page: coverage counts + headline sat-vs-float metrics."""
    pab_version = pab_version or _pab_version
    df = compare.gather_matchups(store)
    n_matchups = store.count("matchups")
    n_floats = store.count("floats")
    n_fits = store.count("fits")
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
        f"- **BING fits:** {n_fits}\n"
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
            dfm["ratio"] = (
                dfm["bbp_bing"].to_numpy(dtype=float)
                / dfm["bbp_argo"].to_numpy(dtype=float)
            )
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


def comparisons_page(df, *, sortable: bool = True) -> str:
    """The **Comparisons** page: interactive satellite-vs-float scatters + map."""
    out = [_heading("Satellite vs float comparisons"), ""]
    body = interactive_figures(df) if sortable else ""
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


def methods_page() -> str:
    """Reader-facing methods/context page: data, protocol, retrieval, how to read
    the figures and metrics, caveats, and references."""
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
        "- **BING vs NASA L2 IOPs.** A direct comparison against NASA's own L2 IOP "
        "product is planned but **not yet included**.\n"
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


def downloads_page(store, outdir) -> str:
    """The **Downloads** page: links the small summary tables.

    Stages the matchup summary CSV/Parquet (``publish.export_tables``) into
    ``outdir/_static/downloads`` and links them (small, committed with the site).
    The bulky per-matchup MCMC chains and figures live in the object store
    (Nautilus S3) keyed by matchup id — noted here as available once that backend
    is wired (``HOWTO.md`` §7b). Best-effort: never breaks the build.
    """
    from pab.report import publish

    try:
        tables = publish.export_tables(store, Path(outdir) / "_static" / "downloads")
    except Exception:  # noqa: BLE001 — downloads are a bonus, not load-bearing
        tables = {}
    out = [_heading("Downloads"), ""]
    links = []
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
    pv = package_versions()
    df = pd.DataFrame({"package": list(pv), "version": list(pv.values())})
    out.append(rst_table(df))
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
        '# Per-matchup figures are copied under _static/figures and served verbatim.\n'
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
    urls = [_stage_static(fig_paths.get(fit_id), outdir, "figures") for fit_id in df["fit_id"]]
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
        "summary": summary_page(store, pab_version=pab_version),
        "comparisons": comparisons_page(df, sortable=sortable),
        "figures": figures_page(store, outdir, df),
        "aggregates": (
            aggregates_page(store, sortable=sortable)
            + "\n"
            + matchup_quality_table(store, sortable=sortable)
        ),
        "methods": methods_page() + "\n" + provenance_block(pab_version=pab_version),
        "downloads": downloads_page(store, outdir),
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
