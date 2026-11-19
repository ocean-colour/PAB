"""The Global explorer: every matchup on a world map (Q&A / Global explorer).

Named ``global_explorer`` because ``global`` is a Python keyword
(``import pab.viz.global`` is a syntax error).

Design (GE-Q1 to GE-Q13):

* a **Web-Mercator map** on Esri World Gray Canvas tiles (:data:`TILES`), coloured by the chosen
  variable, with an **editable colour range** (low / high / auto, remembered
  per variable) and a colour bar;
* a linked **Argo vs PACE ``b_bp(700)``** log-log scatter (1:1 line) and a
  **histogram** of the colour variable. Map and scatter share one source, so a
  selection on either shows on both; selecting histogram bars selects their
  matchups;
* a **statistics box** (``compare.log_comparison`` for ``b_bp`` and Chl, Argo
  over PACE), over the selection, or over the visible map region when
  nothing is selected, always after the filters;
* **filters**: version family, implausible PACE ``b_bp`` hidden, LM success
  only, χ²_red ≤ x, date range, Δt ≤ x;
* a **card** for one tapped matchup, with "Open in Argo + PACE" (same
  session) and a link that opens it in a new browser tab.

Pure helpers (:func:`derive`, :func:`apply_filters`, :func:`default_range`,
:func:`histogram`, :func:`stats_rows`) carry the logic and are tested
without a server; :class:`GlobalTab` wires them to widgets.
"""

from __future__ import annotations

import html
import threading
from collections.abc import Callable
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from bokeh.layouts import column, row
from bokeh.models import (
    BasicTicker,
    Button,
    CheckboxGroup,
    ColorBar,
    ColumnDataSource,
    DateRangeSlider,
    Div,
    HoverTool,
    LinearColorMapper,
    LogColorMapper,
    LogTicker,
    Range1d,
    Select,
    Slider,
    Span,
    TextInput,
)
from bokeh.palettes import RdBu11, Viridis256
from bokeh.plotting import figure

from pab.metrics import compare
from pab.viz import data
from pab.viz.bokeh_argo_pace import fmt

#: Earth radius of the Web-Mercator projection (m).
_R = 6378137.0

#: Colour for a matchup without a value of the colour variable.
NAN_COLOR = "#bdbdbd"

#: Diverging palette, blue (Argo < PACE) → red (Argo > PACE); Bokeh's RdBu11
#: already runs blue → red.
DIVERGING = tuple(RdBu11)

#: Basemap. GE-Q2 chose CartoDB Positron, but CARTO's tiles now answer
#: "API KEY REQUIRED" (seen 2026-11-19); Esri's light gray canvas is the
#: key-free equivalent.
TILES = "Esri.WorldGrayCanvas"

#: χ²_red slider end; the end value means "no cut".
CHISQ_MAX = 30.0

HIST_BINS = 40


@dataclass(frozen=True)
class Variable:
    """A colour variable: frame column, label, scale and default range."""

    key: str
    label: str
    scale: str  # "log" | "lin" | "div"
    fixed: tuple[float, float] | None = None

    @property
    def is_log(self) -> bool:
        return self.scale == "log"


#: GE-Q4 as answered (Adg at 400 nm per GE-Q9).
VARIABLES: dict[str, Variable] = {v.key: v for v in (
    Variable("bbp_argo", "Argo b_bp(700) (m⁻¹)", "log"),
    Variable("bbp_pace", "PACE b_bp(700) (m⁻¹)", "log"),
    Variable("dbbp", "dbbp = (Argo − PACE)/PACE", "div", (-1.0, 1.0)),
    Variable("lr_bbp", "log10(Argo/PACE) b_bp", "div", (-1.0, 1.0)),
    Variable("adg", "PACE Adg = a_dg(400) (m⁻¹)", "log"),
    Variable("sdg", "PACE S_dg (nm⁻¹)", "lin"),
    Variable("beta", "PACE β (b_bp slope)", "lin"),
    Variable("chl_argo", "Argo Chl (mg m⁻³, uncorrected)", "log"),
    Variable("chl_pace", "PACE Chl (mg m⁻³)", "log"),
    Variable("lr_chl", "log10(Argo/PACE) Chl", "div", (-1.0, 1.0)),
)}

DEFAULT_VARIABLE = "dbbp"


# -- pure helpers -------------------------------------------------------------
def mercator(lon, lat):
    """Web-Mercator ``(x, y)`` in metres."""
    lon = np.asarray(lon, dtype=float)
    lat = np.clip(np.asarray(lat, dtype=float), -85.0, 85.0)
    x = np.radians(lon) * _R
    y = np.log(np.tan(np.pi / 4 + np.radians(lat) / 2)) * _R
    return x, y


def _ratio(a, b):
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    with np.errstate(divide="ignore", invalid="ignore"):
        out = np.log10(a / b)
    out[~((a > 0) & (b > 0))] = np.nan
    return out


def derive(df: pd.DataFrame) -> pd.DataFrame:
    """The explorer columns from :func:`data.explorer_frame` (ungated)."""
    out = pd.DataFrame({
        "matchup_id": df["matchup_id"].astype(str),
        "fit_id": df["fit_id"].astype(str),
        "wmo": df["wmo"].astype(int),
        "cycle": df["cycle"].astype(int),
        "latitude": df["latitude"].astype(float),
        "longitude": df["longitude"].astype(float),
        "time": pd.to_datetime(df["time"], format="ISO8601", utc=True).dt.tz_localize(None),
        "pab_version": df["pab_version"].astype(str),
        "bbp_argo": df["bbp_argo"].astype(float),
        "bbp_pace": df["bbp_bing"].astype(float),
        "chl_argo": df["chla_argo"].astype(float),
        "chl_pace": df["chl_bing"].astype(float),
        "adg": df.get("adg", np.nan),
        "sdg": df.get("sdg", np.nan),
        "beta": df.get("beta", np.nan),
        "chisq": df["chisq"].astype(float),
        "success": df.get("success", 1),
        "distance_km": df.get("distance_km", np.nan),
        "dtime_hours": df.get("dtime_hours", np.nan),
        "implausible": df["bbp_bing_implausible"].astype(bool),
    })
    with np.errstate(divide="ignore", invalid="ignore"):
        out["dbbp"] = (out["bbp_argo"] - out["bbp_pace"]) / out["bbp_pace"]
    out["lr_bbp"] = _ratio(out["bbp_argo"], out["bbp_pace"])
    out["lr_chl"] = _ratio(out["chl_argo"], out["chl_pace"])
    out["x"], out["y"] = mercator(out["longitude"], out["latitude"])
    return out.reset_index(drop=True)


@dataclass
class Filters:
    """GE-Q6. ``None`` bounds mean "no cut"."""

    hide_implausible: bool = True
    success_only: bool = True
    chisq_max: float | None = None
    date_lo: pd.Timestamp | None = None
    date_hi: pd.Timestamp | None = None
    dt_max: float | None = None


def apply_filters(df: pd.DataFrame, f: Filters) -> pd.DataFrame:
    """Rows kept by ``f``. Hidden implausible PACE ``b_bp`` follows
    ``compare.gate_bbp``: the PACE ``b_bp`` (and what derives from it) becomes
    NaN, the row and its Chl stay."""
    keep = np.ones(len(df), dtype=bool)
    if f.success_only:
        keep &= df["success"].fillna(0).to_numpy() == 1
    if f.chisq_max is not None:
        keep &= df["chisq"].to_numpy() <= f.chisq_max
    if f.date_lo is not None:
        keep &= (df["time"] >= f.date_lo).to_numpy()
    if f.date_hi is not None:
        keep &= (df["time"] <= f.date_hi).to_numpy()
    if f.dt_max is not None:
        keep &= df["dtime_hours"].to_numpy() <= f.dt_max
    out = df.loc[keep].copy()
    if f.hide_implausible:
        bad = out["implausible"].to_numpy()
        out.loc[bad, ["bbp_pace", "dbbp", "lr_bbp"]] = np.nan
    return out.reset_index(drop=True)


def default_range(values, var: Variable) -> tuple[float, float]:
    """GE-Q10: the fixed range, else 2–98 % of the finite (positive) values."""
    if var.fixed is not None:
        return var.fixed
    v = np.asarray(values, dtype=float)
    v = v[np.isfinite(v) & ((v > 0) if var.is_log else True)]
    if not v.size:
        return (1e-4, 1e-2) if var.is_log else (0.0, 1.0)
    lo, hi = np.percentile(v, [2, 98])
    if hi <= lo:
        hi = lo * 1.1 if var.is_log else lo + 1.0
    return float(lo), float(hi)


def histogram(values, var: Variable, lo: float, hi: float, bins: int = HIST_BINS):
    """Counts in ``bins`` over [lo, hi] (log10 space for log variables), plus
    the counts clipped below and above. Returns ``(edges, counts, n_lo, n_hi)``
    with ``edges`` in the axis units (log10 for log variables)."""
    v = np.asarray(values, dtype=float)
    v = v[np.isfinite(v)]
    if var.is_log:
        v = np.log10(v[v > 0])
        lo, hi = np.log10(lo), np.log10(hi)
    edges = np.linspace(lo, hi, bins + 1)
    counts, _ = np.histogram(np.clip(v, lo, hi), bins=edges)
    n_lo, n_hi = int((v < lo).sum()), int((v > hi).sum())
    # the clipped values sit in the end bins of ``counts``; take them out
    counts[0] -= n_lo
    counts[-1] -= n_hi
    return edges, counts, n_lo, n_hi


def stats_rows(df: pd.DataFrame) -> dict[str, dict]:
    """GE-Q13: Argo over PACE log statistics for ``b_bp`` and Chl."""
    bbp = compare.log_comparison(df["bbp_argo"], df["bbp_pace"])
    d = df["dbbp"].to_numpy(dtype=float)
    d = d[np.isfinite(d)]
    bbp["median_dbbp"] = float(np.median(d)) if d.size else float("nan")
    chl = compare.log_comparison(df["chl_argo"], df["chl_pace"])
    return {"bbp": bbp, "chl": chl}


def visible(df: pd.DataFrame, x0, x1, y0, y1) -> np.ndarray:
    """Row mask of matchups inside the map's current ranges."""
    x, y = df["x"].to_numpy(), df["y"].to_numpy()
    return (x >= min(x0, x1)) & (x <= max(x0, x1)) & (y >= min(y0, y1)) & (y <= max(y0, y1))


def _naive(t) -> pd.Timestamp | None:
    """A widget datetime as a naive UTC :class:`pandas.Timestamp`."""
    if t is None:
        return None
    t = pd.Timestamp(t)
    return t.tz_convert("UTC").tz_localize(None) if t.tzinfo else t


def parse_number(text: str) -> float | None:
    try:
        v = float(str(text).strip())
    except ValueError:
        return None
    return v if np.isfinite(v) else None


# -- frames cache -------------------------------------------------------------
_frames: dict[tuple, pd.DataFrame] = {}
_frames_lock = threading.Lock()


def load_frame(store, db_path: str, family: str | None, model_pair: str) -> pd.DataFrame:
    """:func:`derive` of :func:`data.explorer_frame`, cached per server."""
    key = (str(db_path), family, model_pair)
    with _frames_lock:
        if key not in _frames:
            _frames[key] = derive(data.explorer_frame(store, family, model_pair=model_pair))
        return _frames[key]


# -- the tab ------------------------------------------------------------------
_SRC_COLS = ("x", "y", "c", "matchup_id", "wmo", "cycle", "date", "bbp_argo",
             "bbp_pace", "dbbp", "chl_argo", "chl_pace")


@dataclass
class _State:
    ranges: dict[str, tuple[float, float]] = field(default_factory=dict)


class GlobalTab:
    """Controls, figures and callbacks of the Global tab, for one session.

    ``open_matchup(wmo, cycle, family)`` is called by "Open in Argo + PACE".
    """

    def __init__(self, store, db_path: str, *, model_pair: str = data.DEFAULT_MODEL_PAIR,
                 open_matchup: Callable[[int, int, str | None], None] | None = None,
                 width: int = 1150):
        self.store = store
        self.db_path = str(db_path)
        self.model_pair = model_pair
        self.open_matchup = open_matchup
        self.state = _State()
        self.view = pd.DataFrame()
        self._busy = False

        families = data.version_families(store)
        self.version = Select(
            title="BING version",
            options=[(f, data.family_label(store, f)) for f in families],
            value=families[0] if families else "", width=150)
        self.variable = Select(title="colour by",
                               options=[(k, v.label) for k, v in VARIABLES.items()],
                               value=DEFAULT_VARIABLE, width=250)
        self.low = TextInput(title="low", width=90)
        self.high = TextInput(title="high", width=90)
        self.auto = Button(label="auto", width=60, margin=(24, 5, 5, 5))
        self.checks = CheckboxGroup(labels=["hide implausible PACE b_bp", "LM success only"],
                                    active=[0, 1], width=220)
        self.chisq = Slider(title=f"χ²_red ≤ ({CHISQ_MAX:g} = no cut)", start=0.5,
                            end=CHISQ_MAX, step=0.5, value=CHISQ_MAX, width=200)
        self.dt = Slider(title="Δt ≤ (h)", start=1, end=24, step=1, value=24, width=160)
        self.dates = DateRangeSlider(title="date", start=0, end=1, value=(0, 1), step=1,
                                     format="%Y-%m", width=300)

        # -- map ---------------------------------------------------------------
        self.src = ColumnDataSource({k: [] for k in _SRC_COLS}, name="global_src")
        self.lin_mapper = LinearColorMapper(palette=DIVERGING, low=-1, high=1,
                                            nan_color=NAN_COLOR)
        self.log_mapper = LogColorMapper(palette=Viridis256, low=1e-4, high=1e-2,
                                         nan_color=NAN_COLOR)
        x0, y0 = mercator(-180, -72)
        x1, y1 = mercator(180, 80)
        m = figure(width=width - 420, height=580, x_axis_type="mercator",
                   y_axis_type="mercator", x_range=Range1d(float(x0), float(x1)),
                   y_range=Range1d(float(y0), float(y1)), output_backend="webgl",
                   tools="pan,wheel_zoom,box_zoom,box_select,lasso_select,tap,reset,save",
                   active_scroll="wheel_zoom", title="Matchups")
        m.add_tile(TILES)
        self.points = m.scatter("x", "y", source=self.src, size=5, line_color=None,
                                fill_color={"field": "c", "transform": self.lin_mapper},
                                fill_alpha=0.85, nonselection_fill_alpha=0.12,
                                selection_line_color="black")
        m.add_tools(HoverTool(renderers=[self.points], tooltips=[
            ("WMO / cycle", "@wmo / @cycle"), ("date", "@date"), ("value", "@c{%0.3g}"),
            ("Argo b_bp", "@bbp_argo{%0.3g}"), ("PACE b_bp", "@bbp_pace{%0.3g}"),
            ("dbbp", "@dbbp{0.00}")],
            formatters={"@c": "printf", "@bbp_argo": "printf", "@bbp_pace": "printf"}))
        # below the map: a side bar's width follows its label and would move the
        # map's visible extent (and the "visible" statistics) per variable
        self.color_bar = ColorBar(color_mapper=self.lin_mapper, ticker=BasicTicker(),
                                  title="", orientation="horizontal", height=10,
                                  location=(0, 0), padding=5)
        m.add_layout(self.color_bar, "below")
        self.map = m

        # -- scatter -----------------------------------------------------------
        s = figure(width=400, height=400, x_axis_type="log", y_axis_type="log",
                   x_axis_label="PACE b_bp(700) (m⁻¹)", y_axis_label="Argo b_bp(700) (m⁻¹)",
                   tools="pan,wheel_zoom,box_select,lasso_select,tap,reset,save",
                   output_backend="webgl", title="Argo vs PACE b_bp(700)",
                   x_range=Range1d(1e-4, 1e-1), y_range=Range1d(1e-4, 1e-1))
        s.line([1e-6, 1.0], [1e-6, 1.0], color="black", line_dash="dashed")
        s.scatter("bbp_pace", "bbp_argo", source=self.src, size=4, line_color=None,
                  fill_color={"field": "c", "transform": self.lin_mapper}, fill_alpha=0.7,
                  nonselection_fill_alpha=0.08)
        self.scatter = s

        # -- histogram ---------------------------------------------------------
        self.hist_src = ColumnDataSource({"left": [], "right": [], "top": []})
        self.hist_sel = ColumnDataSource({"left": [], "right": [], "top": []})
        h = figure(width=400, height=220, tools="tap,box_select,reset",
                   title="", y_axis_label="matchups")
        h.quad(left="left", right="right", top="top", bottom=0, source=self.hist_src,
               fill_color="#9ecae1", line_color="white",
               selection_fill_color="#3182bd", nonselection_fill_alpha=0.6)
        h.quad(left="left", right="right", top="top", bottom=0, source=self.hist_sel,
               fill_color="#e6550d", fill_alpha=0.7, line_color=None)
        self.zero = Span(location=0, dimension="height", line_dash="dashed",
                         line_color="#444444", visible=False)
        h.add_layout(self.zero)
        self.hist = h

        # -- text --------------------------------------------------------------
        self.stats = Div(text="", width=width - 420)
        self.card = Div(text="<i>Tap a matchup on the map or the scatter.</i>", width=400)
        self.open_btn = Button(label="Open in Argo + PACE", button_type="primary",
                               disabled=True, width=200, name="global_open")
        self.status = Div(text="", width=400)

        # -- wiring ------------------------------------------------------------
        self.version.on_change("value", lambda a, o, n: self.reload())
        self.variable.on_change("value", lambda a, o, n: self.recolor())
        for w in (self.low, self.high):
            w.on_change("value", lambda a, o, n: self._on_range_typed())
        self.auto.on_click(self._on_auto)
        self.checks.on_change("active", lambda a, o, n: self.refresh())
        for w in (self.chisq, self.dt):
            w.on_change("value_throttled", lambda a, o, n: self.refresh())
        self.dates.on_change("value_throttled", lambda a, o, n: self.refresh())
        self.src.selected.on_change("indices", lambda a, o, n: self._on_select())
        self.hist_src.selected.on_change("indices", lambda a, o, n: self._on_hist_select())
        for r in (m.x_range, m.y_range):
            r.on_change("end", lambda a, o, n: self._update_stats())
        self.open_btn.on_click(self._on_open)

        self.layout = column(
            row(self.version, self.variable, self.low, self.high, self.auto),
            row(self.checks, self.chisq, self.dt, self.dates),
            row(column(self.map, self.stats),
                column(self.scatter, self.hist, self.card, self.open_btn, self.status)),
        )
        self.reload()

    # -- data ------------------------------------------------------------------
    @property
    def var(self) -> Variable:
        return VARIABLES[self.variable.value]

    def filters(self) -> Filters:
        lo, hi = self.dates.value_as_datetime if self.frame is not None and len(self.frame) else (None, None)
        return Filters(
            hide_implausible=0 in self.checks.active,
            success_only=1 in self.checks.active,
            chisq_max=None if self.chisq.value >= CHISQ_MAX else float(self.chisq.value),
            date_lo=_naive(lo),
            date_hi=_naive(hi) + pd.Timedelta(days=1) if hi else None,
            dt_max=None if self.dt.value >= self.dt.end else float(self.dt.value),
        )

    def reload(self) -> None:
        """New version family: reload the frame and reset the date/Δt widgets."""
        self.frame = load_frame(self.store, self.db_path, self.version.value or None,
                                self.model_pair)
        self.state.ranges.clear()
        if len(self.frame):
            t0, t1 = self.frame["time"].min(), self.frame["time"].max()
            self.dates.start, self.dates.end = t0, t1
            self.dates.value = (t0, t1)
            dmax = float(np.ceil(np.nanmax(self.frame["dtime_hours"])))
            self.dt.end = max(dmax, 1.0)
            self.dt.value = self.dt.end
        self.refresh()

    def refresh(self) -> None:
        """Re-apply the filters and redraw everything."""
        self.view = apply_filters(self.frame, self.filters()) if len(self.frame) else self.frame
        self.src.selected.indices = []
        self.recolor(push=False)
        self._push()

    def _push(self) -> None:
        v = self.view
        if not len(v):
            self.src.data = {k: [] for k in _SRC_COLS}
        else:
            self.src.data = {
                "x": v["x"].to_numpy(), "y": v["y"].to_numpy(),
                "c": v[self.var.key].to_numpy(dtype=float),
                "matchup_id": v["matchup_id"].to_numpy(),
                "wmo": v["wmo"].to_numpy(), "cycle": v["cycle"].to_numpy(),
                "date": v["time"].dt.strftime("%Y-%m-%d %H:%M").to_numpy(),
                **{k: v[k].to_numpy(dtype=float) for k in
                   ("bbp_argo", "bbp_pace", "dbbp", "chl_argo", "chl_pace")},
            }
        self._update_hist()
        self._update_stats()
        self._update_card()

    # -- colour ------------------------------------------------------------------
    def current_range(self) -> tuple[float, float]:
        var = self.var
        if var.key not in self.state.ranges:
            self.state.ranges[var.key] = default_range(self.view.get(var.key, []), var)
        return self.state.ranges[var.key]

    def recolor(self, push: bool = True) -> None:
        """Apply the colour variable and its (remembered) range."""
        var = self.var
        lo, hi = self.current_range()
        mapper = self.log_mapper if var.is_log else self.lin_mapper
        mapper.palette = Viridis256 if var.scale != "div" else DIVERGING
        mapper.low, mapper.high = lo, hi
        for r in (self.points, *self.scatter.renderers[1:]):
            r.glyph.fill_color = {"field": "c", "transform": mapper}
        self.color_bar.color_mapper = mapper
        self.color_bar.ticker = LogTicker() if var.is_log else BasicTicker()
        self.color_bar.title = var.label
        self._busy = True
        self.low.value, self.high.value = fmt(lo, 3), fmt(hi, 3)
        self._busy = False
        self.zero.visible = var.scale == "div"
        if push:
            if len(self.view):
                self.src.data.update(c=self.view[var.key].to_numpy(dtype=float))
            self._update_hist()

    def _on_range_typed(self) -> None:
        if self._busy:
            return
        lo, hi = parse_number(self.low.value), parse_number(self.high.value)
        bad = (lo is None or hi is None or hi <= lo
               or (self.var.is_log and lo <= 0))
        if bad:
            self.status.text = ("<span style='color:#c62828'>The range needs low &lt; high"
                                + (" and low &gt; 0 (log scale)" if self.var.is_log else "")
                                + ".</span>")
            return
        self.status.text = ""
        self.state.ranges[self.var.key] = (lo, hi)
        self.recolor()

    def _on_auto(self) -> None:
        self.state.ranges.pop(self.var.key, None)
        self.status.text = ""
        self.recolor()

    # -- histogram ---------------------------------------------------------------
    def _hist_edges(self):
        lo, hi = self.current_range()
        vals = self.view[self.var.key] if len(self.view) else []
        return histogram(vals, self.var, lo, hi)

    def _update_hist(self) -> None:
        var = self.var
        edges, counts, n_lo, n_hi = self._hist_edges()
        self.hist_src.selected.indices = []
        self.hist_src.data = {"left": edges[:-1], "right": edges[1:], "top": counts}
        self.hist.xaxis.axis_label = f"log10 {var.label}" if var.is_log else var.label
        self.hist.title.text = f"{n_lo} below the range · {n_hi} above (not in the bars)"
        self._update_hist_sel()

    def _update_hist_sel(self) -> None:
        idx = self.src.selected.indices
        if not idx or not len(self.view):
            self.hist_sel.data = {"left": [], "right": [], "top": []}
            return
        lo, hi = self.current_range()
        edges, counts, _, _ = histogram(self.view[self.var.key].to_numpy()[idx],
                                        self.var, lo, hi)
        self.hist_sel.data = {"left": edges[:-1], "right": edges[1:], "top": counts}

    def _on_hist_select(self) -> None:
        bars = self.hist_src.selected.indices
        if not bars or not len(self.view):
            return
        v = self.view[self.var.key].to_numpy(dtype=float)
        if self.var.is_log:
            with np.errstate(divide="ignore", invalid="ignore"):
                v = np.log10(v)
        left = np.asarray(self.hist_src.data["left"])
        right = np.asarray(self.hist_src.data["right"])
        mask = np.zeros(len(v), dtype=bool)
        for b in bars:
            mask |= (v >= left[b]) & (v <= right[b])
        self.src.selected.indices = np.flatnonzero(mask).tolist()

    # -- selection, stats, card --------------------------------------------------
    def _subset(self) -> tuple[pd.DataFrame, str]:
        idx = self.src.selected.indices
        if idx:
            return self.view.iloc[idx], f"{len(idx)} selected"
        if not len(self.view):
            return self.view, "nothing"
        r = self.map
        mask = visible(self.view, r.x_range.start, r.x_range.end,
                       r.y_range.start, r.y_range.end)
        return self.view.loc[mask], "visible on the map"

    def _update_stats(self) -> None:
        sub, what = self._subset()
        s = stats_rows(sub) if len(sub) else None
        th = "style='text-align:left;padding:2px 8px;border-bottom:1px solid #999'"
        td = "style='padding:2px 8px'"

        def cells(d, extra=""):
            if d is None or not d["n"]:
                return f"<td {td}>0</td>" + f"<td {td}>—</td>" * 6
            return (f"<td {td}>{d['n']}</td><td {td}>{fmt(d['median_ratio'])} "
                    f"[{fmt(d['ratio_iqr_lo'])}–{fmt(d['ratio_iqr_hi'])}]</td>"
                    f"<td {td}>{extra}</td><td {td}>{fmt(d['spearman'], 2)}</td>"
                    f"<td {td}>{fmt(d['log_bias'], 2)}</td><td {td}>{fmt(d['log_rms'], 2)}</td>"
                    f"<td {td}>{fmt(d['log_mad'], 2)}</td>")

        bbp = s["bbp"] if s else None
        chl = s["chl"] if s else None
        n_all = len(self.view)
        self.stats.text = (
            f"<div style='font-size:90%'><b>Statistics</b>: {len(sub)} matchups {what} "
            f"(of {n_all} after the filters); Argo over PACE.</div>"
            "<table style='border-collapse:collapse;font-size:90%'><tr>"
            + "".join(f"<th {th}>{h}</th>" for h in (
                "", "N", "median ratio [IQR]", "median dbbp", "Spearman r",
                "log bias", "log RMS", "log MAD"))
            + f"</tr><tr><td {td}>b<sub>bp</sub>(700)</td>"
            + cells(bbp, fmt(bbp["median_dbbp"], 2) if bbp else "—")
            + f"</tr><tr><td {td}>Chl</td>" + cells(chl, "") + "</tr></table>"
        )

    def _on_select(self) -> None:
        self._update_hist_sel()
        self._update_stats()
        self._update_card()

    def selected_row(self):
        idx = self.src.selected.indices
        return self.view.iloc[idx[0]] if len(idx) == 1 else None

    def _update_card(self) -> None:
        r = self.selected_row()
        self.open_btn.disabled = r is None or self.open_matchup is None
        n = len(self.src.selected.indices)
        if r is None:
            self.card.text = (f"<i>{n} matchups selected; tap one for its card.</i>" if n
                              else "<i>Tap a matchup on the map or the scatter.</i>")
            return
        ver = html.escape(self.version.value)
        url = f"/?wmo={int(r.wmo)}&cycle={int(r.cycle)}&version={ver}"
        lat, lon = r.latitude, r.longitude
        rows = [
            ("date", r.time.strftime("%Y-%m-%d %H:%M")),
            ("position", f"{abs(lat):.3f}°{'N' if lat >= 0 else 'S'}, "
                         f"{abs(lon):.3f}°{'E' if lon >= 0 else 'W'}"),
            ("Δx / Δt", f"{fmt(r.distance_km)} km / {fmt(r.dtime_hours)} h"),
            ("b_bp(700) Argo / PACE", f"{fmt(r.bbp_argo)} / {fmt(r.bbp_pace)}"),
            ("dbbp · log10 ratio", f"{fmt(r.dbbp, 2)} · {fmt(r.lr_bbp, 2)}"),
            ("Chl Argo / PACE", f"{fmt(r.chl_argo)} / {fmt(r.chl_pace)}"),
            ("Adg(400) · S_dg · β", f"{fmt(r.adg)} · {fmt(r.sdg)} · {fmt(r.beta)}"),
            ("χ²_red · LM", f"{fmt(r.chisq)} · {'✓' if r.success == 1 else 'failed'}"),
            ("BING", html.escape(r.pab_version)),
        ]
        body = "".join(f"<tr><td style='padding:1px 8px;color:#555'>{a}</td>"
                       f"<td style='padding:1px 8px'>{b}</td></tr>" for a, b in rows)
        self.card.text = (
            f"<b>WMO {int(r.wmo)} · cycle {int(r.cycle)}</b> "
            f"(<a href='{url}' target='_blank'>new browser tab</a>)"
            f"<table style='font-size:90%'>{body}</table>")

    def _on_open(self) -> None:
        r = self.selected_row()
        if r is not None and self.open_matchup is not None:
            self.open_matchup(int(r.wmo), int(r.cycle), self.version.value or None)
