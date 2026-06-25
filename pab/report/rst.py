"""Programmatic reStructuredText generation for the reporting site (Stage 7).

Builds a **small, fixed set of aggregate pages** from the SQLite store — a
landing/summary page, a binned-results page, and a methods page — never one page
per matchup (the design's hard constraint at ~10⁴ matchups; per-matchup detail is
reached on demand through the interactive figures). Pure string generation
(unit-testable); :func:`build_site` writes the pages to an output directory
*outside* the developer docs.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from pab.config import pab_version as _pab_version
from pab.metrics import compare

#: The fixed set of generated page stems (there is no per-matchup page).
PAGE_STEMS = ("index", "summary", "aggregates", "methods")


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
    out.append(_heading("Coverage", "-"))
    out.append(
        f"- **Matchups:** {n_matchups}\n- **Floats:** {n_floats}\n"
        f"- **BING fits:** {n_fits}\n"
    )
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
    return "\n".join(out)


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


def methods_page() -> str:
    """A static methods/algorithm page citing BING and Bisson."""
    out = [_heading("Methods"), ""]
    out.append(
        "PAB matches BGC-Argo mixed-layer summaries to PACE/OCI Level-2 ``Rrs`` "
        "and retrieves IOPs with **BING** (Bayesian inference with Gordon "
        "coefficients; Prochaska & Frouin 2025). The matchup protocol follows "
        "**Bisson et al. (2019)** — a small unflagged pixel box near the float "
        "and a tight time window. The matchup observable is non-water "
        "backscatter ``b_bp``; chlorophyll is retrieved from the fitted ``Aph``.\n"
    )
    return "\n".join(out)


def index_page() -> str:
    """The site index (toctree over the fixed aggregate pages)."""
    out = [_heading("PAB reporting"), ""]
    out.append(".. toctree::\n   :maxdepth: 1\n")
    out.append("   summary\n   aggregates\n   methods\n")
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
    )


def build_site(
    store, outdir, *, pab_version: str | None = None, sortable: bool = True
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

    Returns:
        ``{name: path}`` for each written file — the fixed :data:`PAGE_STEMS`
        pages plus ``conf`` (regardless of matchup count; no per-matchup pages).
    """
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    pages = {
        "index": index_page(),
        "summary": summary_page(store, pab_version=pab_version),
        "aggregates": aggregates_page(store, sortable=sortable),
        "methods": methods_page(),
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
