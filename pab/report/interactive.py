"""Standalone Bokeh figures for the reporting site (Stage 7).

The interactive layer is how the static site exposes **per-matchup detail**
without per-matchup pages: a satellite-vs-float ``b_bp`` scatter and a matchup
map, embedded as standalone HTML/JSON (``bokeh.embed`` — no Bokeh server), with
**hover** showing each matchup's values and an optional **tap** that opens the
matchup's artifact by URL. ``bokeh`` is imported lazily so ``import pab.report``
works without it.
"""

from __future__ import annotations

#: Columns shown in the hover tooltip when present in the frame.
HOVER_FIELDS = (
    "matchup_id",
    "wmo",
    "cycle",
    "bbp_bing",
    "bbp_argo",
    "chl_bing",
    "chla_argo",
    "chl_oc",
)

#: Palette for ``extra_series`` overlays (distinct from the default primary glyph).
_EXTRA_COLORS = ("#e66101", "#5e3c99", "#1b7837")


def comparison_scatter(
    df,
    *,
    sat_col: str = "bbp_bing",
    insitu_col: str = "bbp_argo",
    label: str = "b_bp",
    artifact_url_col: str | None = None,
    title: str | None = None,
    extra_series: list[tuple[str, str]] | None = None,
):
    """A log-log satellite-vs-in-situ Bokeh scatter with a 1:1 line and hover.

    Args:
        df: Per-matchup frame (``gather_matchups`` output).
        sat_col, insitu_col: Columns to plot (satellite vs in-situ).
        label, title: Axis label and figure title.
        artifact_url_col: If given (and present), tapping a point opens that URL
            (the matchup's figure/artifact).
        extra_series: Optional ``[(col, legend_label), …]`` overlaid against the
            same ``insitu_col`` x-axis (e.g. an OC4 band-ratio Chl alongside the
            BING Chl). When given, the primary glyph also gets a legend entry so
            the two satellite sources are distinguishable.

    Returns:
        A ``bokeh.plotting.figure``.
    """
    import numpy as np
    from bokeh.models import ColumnDataSource, HoverTool, OpenURL, TapTool
    from bokeh.plotting import figure

    data = {c: df[c].to_numpy() for c in df.columns}
    src = ColumnDataSource(data)
    fig = figure(
        title=title or f"satellite vs in-situ {label}",
        x_axis_type="log",
        y_axis_type="log",
        x_axis_label=f"in-situ {label}",
        y_axis_label=f"satellite {label}",
        width=560,
        height=520,
        output_backend="webgl",  # stays responsive at 10^4–10^5 points
        tools="pan,box_zoom,wheel_zoom,reset,save,tap",
    )
    extra = [(c, lab) for c, lab in (extra_series or []) if c in df.columns]
    primary_kw = {"legend_label": f"satellite {label}"} if extra else {}
    fig.scatter(insitu_col, sat_col, source=src, size=7, alpha=0.7, **primary_kw)
    for (col, leg), color in zip(extra, _EXTRA_COLORS):
        fig.scatter(
            insitu_col,
            col,
            source=src,
            size=7,
            alpha=0.7,
            color=color,
            marker="triangle",
            legend_label=leg,
        )
    # 1:1 line spanning every plotted series (primary + overlays).
    span_cols = [sat_col, insitu_col, *(c for c, _ in extra)]
    finite = df[span_cols].to_numpy(dtype=float)
    finite = finite[np.isfinite(finite) & (finite > 0)]
    if finite.size:
        lo, hi = float(finite.min()) * 0.7, float(finite.max()) * 1.4
        fig.line([lo, hi], [lo, hi], color="black", legend_label="1:1")
    tips = [(c, f"@{c}") for c in HOVER_FIELDS if c in df.columns]
    fig.add_tools(HoverTool(tooltips=tips))
    if artifact_url_col and artifact_url_col in df.columns:
        fig.select(TapTool).callback = OpenURL(url=f"@{artifact_url_col}")
    return fig


def matchup_map(df, *, color_col: str = "median_ratio", title: str = "matchups"):
    """A lon/lat Bokeh scatter of matchup locations, coloured by ``color_col``."""
    import numpy as np
    from bokeh.models import ColumnDataSource, HoverTool
    from bokeh.plotting import figure
    from bokeh.transform import linear_cmap

    src = ColumnDataSource({c: df[c].to_numpy() for c in df.columns})
    fig = figure(
        title=title,
        x_axis_label="longitude",
        y_axis_label="latitude",
        width=720,
        height=380,
        output_backend="webgl",
    )
    if (
        color_col in df.columns
        and np.isfinite(df[color_col].to_numpy(dtype=float)).any()
    ):
        vals = df[color_col].to_numpy(dtype=float)
        cmap = linear_cmap(
            color_col, "Viridis256", float(np.nanmin(vals)), float(np.nanmax(vals))
        )
        fig.scatter("longitude", "latitude", source=src, size=9, color=cmap)
    else:
        fig.scatter("longitude", "latitude", source=src, size=9)
    tips = [(c, f"@{c}") for c in HOVER_FIELDS if c in df.columns]
    fig.add_tools(HoverTool(tooltips=tips))
    return fig


def stats_table(df, *, columns=None, width: int = 760, height: int = 280):
    """A **sortable** Bokeh ``DataTable`` for a statistics frame.

    Columns sort on header click (Bokeh ``DataTable`` is sortable by default), so
    the static site gets sortable tables without a server. Embed it with
    :func:`embed` / :func:`raw_html`.
    """
    from bokeh.models import ColumnDataSource, DataTable, TableColumn

    cols = list(columns) if columns is not None else list(df.columns)
    src = ColumnDataSource({c: df[c].tolist() for c in cols})
    table_cols = [TableColumn(field=c, title=str(c), sortable=True) for c in cols]
    return DataTable(
        source=src, columns=table_cols, sortable=True, width=width, height=height
    )


def embed(fig) -> tuple[str, str]:
    """Return the standalone ``(script, div)`` for a Bokeh model (for ``.rst``)."""
    from bokeh.embed import components

    return components(fig)


def raw_html(fig) -> str:
    """A reStructuredText ``.. raw:: html`` block embedding ``fig`` standalone."""
    script, div = embed(fig)
    body = "\n".join("   " + ln for ln in (div + "\n" + script).splitlines())
    return ".. raw:: html\n\n" + body + "\n"
