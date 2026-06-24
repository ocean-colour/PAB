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
HOVER_FIELDS = ("matchup_id", "wmo", "cycle", "bbp_bing", "bbp_argo", "chl_bing")


def comparison_scatter(
    df,
    *,
    sat_col: str = "bbp_bing",
    insitu_col: str = "bbp_argo",
    label: str = "b_bp",
    artifact_url_col: str | None = None,
    title: str | None = None,
):
    """A log-log satellite-vs-in-situ Bokeh scatter with a 1:1 line and hover.

    Args:
        df: Per-matchup frame (``gather_matchups`` output).
        sat_col, insitu_col: Columns to plot (satellite vs in-situ).
        label, title: Axis label and figure title.
        artifact_url_col: If given (and present), tapping a point opens that URL
            (the matchup's figure/artifact).

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
    fig.scatter(insitu_col, sat_col, source=src, size=7, alpha=0.7)
    finite = df[[sat_col, insitu_col]].to_numpy(dtype=float)
    finite = finite[np.isfinite(finite).all(axis=1) & (finite > 0).all(axis=1)]
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


def embed(fig) -> tuple[str, str]:
    """Return the standalone ``(script, div)`` for a Bokeh figure (for ``.rst``)."""
    from bokeh.embed import components

    return components(fig)


def raw_html(fig) -> str:
    """A reStructuredText ``.. raw:: html`` block embedding ``fig`` standalone."""
    script, div = embed(fig)
    body = "\n".join("   " + ln for ln in (div + "\n" + script).splitlines())
    return ".. raw:: html\n\n" + body + "\n"
