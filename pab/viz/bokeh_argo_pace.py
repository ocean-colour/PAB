"""The Argo + PACE view: a float's ``b_bp`` profile beside the PACE ``Rrs`` fit.

Design: ``claude_prompts/viz_tools.md``, Q&A / Argo+PACE (AP-Q1 to AP-Q15).

* **Argo panel** (left): pressure down, 0 → 2×MLD (0 → 200 m without an
  MLD). The raw ``BBP700`` samples, the de-spiked profile, the in-ML samples
  the IQR filter rejected (de-spike and filter over the BBP700 samples only,
  AP-Q16), the MLD (dashed), the stored ML mean ± std over
  0 → MLD, and the PACE ``b_bp(700)`` (median, 5–95 %) over the same span.
  NASA-GIOP ``b_bp(700)`` is a toggle (dashed).
* **PACE panel** (right): observed ``Rrs`` ± σ, the BING model median and
  5–95 % band (y from 0 or below, dashed zero line), a residual strip in σ units with a linked x-axis, and the
  table of retrieved values with the Argo counterparts.

:class:`ArgoPaceView` owns the figures and data sources and has one
``show_*`` method per piece, so the server app can fill it piece by piece as
slow work finishes. :func:`make_argo_pace` fills it synchronously and needs
no server (tests, and a later static export).
"""

from __future__ import annotations

import html
from dataclasses import dataclass
from typing import Any

import numpy as np
from bokeh.layouts import column, row
from bokeh.models import (
    BasicTickFormatter,
    ColumnDataSource,
    Div,
    HoverTool,
    Range1d,
    Span,
)
from bokeh.plotting import figure

from pab.viz import argo as vargo
from pab.viz import data
from pab.viz import fits as vfits

ARGO_COLOR = "#1f77b4"
PACE_COLOR = "#d95f02"
GIOP_COLOR = "#1b9e77"
RAW_COLOR = "#9e9e9e"
ZERO_COLOR = "#444444"
DROP_COLOR = "#c62828"

#: y-extent of the Argo panel when the profile has no MLD (m).
NO_MLD_DEPTH = 200.0

_EMPTY_BAND = {"x1": [], "x2": [], "y": []}
_EMPTY_LINE = {"x": [], "y": []}


def fmt(v, digits: int = 3) -> str:
    """``v`` to ``digits`` significant figures; ``—`` for missing."""
    if v is None:
        return "—"
    try:
        v = float(v)
    except (TypeError, ValueError):
        return html.escape(str(v))
    return "—" if not np.isfinite(v) else f"{v:.{digits}g}"


def fmt_ci(triple) -> str:
    """``median [lo–hi]`` from a ``(value, lo, hi)`` triple."""
    if triple is None:
        return "—"
    v, lo, hi = triple
    if not np.isfinite(v):
        return "—"
    if np.isfinite(lo) and np.isfinite(hi):
        return f"{fmt(v)} [{fmt(lo)}–{fmt(hi)}]"
    return fmt(v)


def _finite(x) -> bool:
    return x is not None and np.isfinite(float(x))


@dataclass
class Selection:
    """The fast (DB-only) part of one view: matchup, fit and GIOP rows."""

    wmo: int
    cycle: int
    family: str | None
    family_label: str
    matchup: dict[str, Any] | None
    fit: dict[str, Any] | None
    giop: dict[str, Any] | None

    @property
    def mld(self) -> float:
        m = self.matchup or {}
        return float(m["mld"]) if _finite(m.get("mld")) else float("nan")

    @property
    def ml_span(self) -> float:
        """Depth to which the ML values are drawn (the MLD, else half-window)."""
        return self.mld if np.isfinite(self.mld) else NO_MLD_DEPTH / 2.0

    @property
    def y_max(self) -> float:
        return 2.0 * self.mld if np.isfinite(self.mld) else NO_MLD_DEPTH


def load_selection(store, wmo: int, cycle: int, family: str | None = None, *,
                   model_pair: str = data.DEFAULT_MODEL_PAIR) -> Selection:
    """Everything the view needs from the DB for profile ``(wmo, cycle)``."""
    families = data.version_families(store)
    if family is None and families:
        family = families[0]
    m = data.matchup_for(store, wmo, cycle)
    fit = giop = None
    if m is not None and family is not None:
        fit = data.bing_fit(store, m["matchup_id"], family, model_pair=model_pair)
        giop = data.giop_fit(store, m["matchup_id"], fit["pixel_id"] if fit else None)
    label = data.family_label(store, family) if family else "—"
    return Selection(int(wmo), int(cycle), family, label, m, fit, giop)


class ArgoPaceView:
    """Figures, sources and text of the Argo + PACE view."""

    def __init__(self, *, width: int = 1150):
        argo_w = 380
        pace_w = width - argo_w - 20
        self.header = Div(text="", sizing_mode="stretch_width")
        self.notes = Div(text="", sizing_mode="stretch_width")
        self.table = Div(text="", width=pace_w)
        self.show_giop_flag = False
        self._sel: Selection | None = None
        self._layers: vargo.BbpLayers | None = None
        self._adg440 = None

        # -- Argo panel ----------------------------------------------------
        self.raw_src = ColumnDataSource({"x": [], "y": [], "qc": []})
        self.desp_src = ColumnDataSource(dict(_EMPTY_LINE))
        self.drop_src = ColumnDataSource({"x": [], "y": [], "raw": []})
        self.argo_band = ColumnDataSource(dict(_EMPTY_BAND))
        self.argo_line = ColumnDataSource(dict(_EMPTY_LINE))
        self.fixed_line = ColumnDataSource(dict(_EMPTY_LINE))
        self.pace_band = ColumnDataSource(dict(_EMPTY_BAND))
        self.pace_line = ColumnDataSource(dict(_EMPTY_LINE))
        self.giop_band = ColumnDataSource(dict(_EMPTY_BAND))
        self.giop_line = ColumnDataSource(dict(_EMPTY_LINE))

        p = figure(
            width=argo_w, height=640, title="BGC-Argo b_bp(700)",
            x_axis_label="b_bp(700) (m⁻¹)", y_axis_label="pressure (dbar)",
            y_range=Range1d(NO_MLD_DEPTH, 0), x_range=Range1d(0, 1e-3),
            tools="pan,wheel_zoom,box_zoom,reset,save",
        )
        p.harea(x1="x1", x2="x2", y="y", source=self.argo_band, fill_color=ARGO_COLOR,
                fill_alpha=0.18, legend_label="Argo ML mean ± std")
        p.line("x", "y", source=self.argo_line, color=ARGO_COLOR, line_width=3,
               legend_label="Argo ML mean ± std")
        self.fixed_renderer = p.line(
            "x", "y", source=self.fixed_line, color=ARGO_COLOR, line_width=2,
            line_dash="dotted", legend_label="ML mean, sample de-spike")
        p.harea(x1="x1", x2="x2", y="y", source=self.pace_band, fill_color=PACE_COLOR,
                fill_alpha=0.18, legend_label="PACE (BING) 5–95 %")
        p.line("x", "y", source=self.pace_line, color=PACE_COLOR, line_width=3,
               legend_label="PACE (BING) 5–95 %")
        self.giop_renderers = [
            p.harea(x1="x1", x2="x2", y="y", source=self.giop_band, fill_color=GIOP_COLOR,
                    fill_alpha=0.12, legend_label="NASA-GIOP ± unc"),
            p.line("x", "y", source=self.giop_line, color=GIOP_COLOR, line_width=2,
                   line_dash="dashed", legend_label="NASA-GIOP ± unc"),
        ]
        raw = p.scatter("x", "y", source=self.raw_src, size=4, color=RAW_COLOR,
                        alpha=0.7, legend_label="raw samples")
        p.line("x", "y", source=self.desp_src, color="black", line_width=1.2,
               legend_label="de-spiked (3-pt median)")
        drop = p.scatter("x", "y", source=self.drop_src, marker="x", size=9,
                         color=DROP_COLOR, line_width=2, legend_label="IQR-rejected (in ML)")
        self.mld_span = Span(location=0, dimension="width", line_dash="dashed",
                             line_color="black", line_width=1.5, visible=False)
        p.add_layout(self.mld_span)
        p.add_tools(HoverTool(renderers=[raw], tooltips=[
            ("P", "@y{0.0} dbar"), ("b_bp", "@x{0.00000}"), ("QC", "@qc")]))
        p.add_tools(HoverTool(renderers=[drop], tooltips=[
            ("P", "@y{0.0} dbar"), ("de-spiked", "@x{0.000000}"), ("raw", "@raw{0.000000}")]))
        p.xaxis.formatter = BasicTickFormatter(precision=1, power_limit_low=-2)
        p.xaxis.ticker.desired_num_ticks = 4
        p.legend.location = "bottom_right"
        p.legend.click_policy = "hide"
        p.legend.label_text_font_size = "8pt"
        self.argo_fig = p
        for r in self.giop_renderers:
            r.visible = False

        # -- PACE panel ----------------------------------------------------
        self.obs_src = ColumnDataSource(
            {"wave": [], "rrs": [], "lo": [], "hi": [], "sigma": [], "model": []})
        self.model_src = ColumnDataSource({"wave": [], "med": [], "lo": [], "hi": []})
        self.resid_src = ColumnDataSource(
            {"wave": [], "rs": [], "r": [], "pct": []})

        q = figure(
            width=pace_w, height=420, title="PACE Rrs and the BING fit",
            x_axis_label=None, y_axis_label="Rrs (sr⁻¹)", y_range=Range1d(0, 0.01),
            tools="pan,wheel_zoom,box_zoom,reset,save",
        )
        q.add_layout(Span(location=0, dimension="width", line_dash="dashed",
                          line_color=ZERO_COLOR, line_width=1.5))
        q.varea(x="wave", y1="lo", y2="hi", source=self.model_src, fill_color=PACE_COLOR,
                fill_alpha=0.25, legend_label="BING 5–95 %")
        q.line("wave", "med", source=self.model_src, color=PACE_COLOR, line_width=2,
               legend_label="BING median")
        q.segment(x0="wave", y0="lo", x1="wave", y1="hi", source=self.obs_src,
                  color="black", alpha=0.5)
        obs = q.scatter("wave", "rrs", source=self.obs_src, size=4, color="black",
                        legend_label="PACE Rrs ± σ")
        q.add_tools(HoverTool(renderers=[obs], tooltips=[
            ("λ", "@wave{0} nm"), ("Rrs", "@rrs{0.000000}"), ("σ", "@sigma{0.000000}"),
            ("model", "@model{0.000000}")]))
        q.yaxis.formatter = BasicTickFormatter(precision=1, power_limit_low=-2)
        q.legend.location = "top_right"
        q.legend.click_policy = "hide"
        self.rrs_fig = q

        r = figure(
            width=pace_w, height=170, x_range=q.x_range,
            x_axis_label="wavelength (nm)", y_axis_label="(obs − model)/σ",
            tools="pan,wheel_zoom,box_zoom,reset,save",
        )
        for loc, dash in ((0, "solid"), (1, "dashed"), (-1, "dashed")):
            r.add_layout(Span(location=loc, dimension="width", line_color="gray",
                              line_dash=dash))
        res = r.scatter("wave", "rs", source=self.resid_src, size=4, color=PACE_COLOR)
        r.add_tools(HoverTool(renderers=[res], tooltips=[
            ("λ", "@wave{0} nm"), ("resid/σ", "@rs{0.00}"), ("resid", "@r{0.0000000} sr⁻¹"),
            ("resid", "@pct{0.0} %")]))
        self.resid_fig = r

        self.layout = column(
            self.header,
            self.notes,
            row(self.argo_fig, column(self.rrs_fig, self.resid_fig, self.table)),
        )

    # -- text ----------------------------------------------------------------
    def set_notes(self, messages) -> None:
        """Show ``messages`` (strings) as a note list; empty clears it."""
        msgs = [m for m in messages if m]
        self.notes.text = (
            "<div style='color:#8a5a00;font-size:90%'>"
            + "<br>".join(msgs) + "</div>" if msgs else ""
        )

    def show_header(self, sel: Selection) -> None:
        m, f = sel.matchup, sel.fit
        if m is None:
            self.header.text = (f"<b>WMO {sel.wmo} · cycle {sel.cycle}</b> — "
                                "no matchup for this profile")
            return
        lat, lon = m.get("latitude"), m.get("longitude")
        pos = (f"{abs(lat):.3f}°{'N' if lat >= 0 else 'S'}, "
               f"{abs(lon):.3f}°{'E' if lon >= 0 else 'W'}") if _finite(lat) and _finite(lon) else "—"
        parts = [
            f"<b>WMO {sel.wmo} · cycle {sel.cycle}</b>",
            html.escape(str(m.get("time") or "—")).replace("T", " ")[:16],
            pos,
            f"Δx {fmt(m.get('distance_km'))} km",
            f"Δt {fmt(m.get('dtime_hours'))} h",
        ]
        if f is None:
            parts.append(f"BING {html.escape(sel.family_label)}: <i>no fit</i>")
        else:
            ver = html.escape(str(f["pab_version"]))
            parts.append(f"BING {ver}" + (" (patch)" if f.get("patched") else ""))
            if f.get("success") == 0:
                parts.append("<span style='background:#c62828;color:white;padding:0 4px;"
                             "border-radius:3px'>LM success = 0</span>")
            else:
                parts.append("LM success ✓")
            parts.append(f"χ²<sub>red</sub> {fmt(f.get('chisq'))}")
        self.header.text = "<div style='font-size:110%'>" + " · ".join(parts) + "</div>"

    def show_table(self) -> None:
        sel = self._sel
        if sel is None:
            self.table.text = ""
            return
        m = sel.matchup or {}
        res = (sel.fit or {}).get("results", {})
        ver = html.escape(str(sel.fit["pab_version"])) if sel.fit else "—"
        adg = self._adg440
        if adg is None:
            adg_txt = "<i>loading…</i>" if sel.fit else "—"
        elif not np.isfinite(adg[0]):
            adg_txt = "— (needs the chains)"
        else:
            adg_txt = fmt_ci(adg)
        argo_bbp = fmt(m.get("bbp700"))
        if _finite(m.get("bbp700")) and _finite(m.get("bbp700_std")):
            argo_bbp += f" ± {fmt(m.get('bbp700_std'))}"
        if m.get("n_points"):
            argo_bbp += f" (n={int(m['n_points'])})"
        ly = self._layers
        if ly is not None and ly.n and ly.ingest_differs:
            argo_bbp += (f"<br><span style='color:#555'>sample de-spike: {fmt(ly.mean)} "
                         f"± {fmt(ly.std)} (n={ly.n})</span>")
        argo_chl = fmt(m.get("chla"))
        if _finite(m.get("chla_adjusted")):
            argo_chl += f" (adjusted {fmt(m.get('chla_adjusted'))})"
        rows = [
            ("b<sub>bp</sub>(700) (m⁻¹)", fmt_ci(res.get("bbp700")), argo_bbp),
            ("β (b<sub>bp</sub> slope)", fmt_ci(res.get("beta")), "—"),
            ("B<sub>nw</sub> = b<sub>bp</sub>(600) (m⁻¹)", fmt_ci(res.get("Bnw")), "—"),
            ("Chl (mg m⁻³)", fmt_ci(res.get("chl")), argo_chl),
            ("a<sub>dg</sub>(440) (m⁻¹), CDOM + detritus", adg_txt, "—"),
            ("S<sub>dg</sub> (nm⁻¹)", fmt_ci(res.get("Sdg")), "—"),
        ]
        if self.show_giop_flag and sel.giop is not None:
            g = sel.giop
            txt = fmt(g["bbp700"])
            if _finite(g["bbp700_unc"]):
                txt += f" ± {fmt(g['bbp700_unc'])}"
            rows.append(("NASA-GIOP b<sub>bp</sub>(700) (m⁻¹)", txt, "—"))
        th = "style='text-align:left;padding:2px 10px;border-bottom:1px solid #999'"
        td = "style='padding:2px 10px'"
        body = "".join(
            f"<tr><td {td}>{a}</td><td {td}>{b}</td><td {td}>{c}</td></tr>" for a, b, c in rows
        )
        self.table.text = (
            "<table style='border-collapse:collapse;font-size:90%'>"
            f"<tr><th {th}>quantity</th><th {th}>PACE (BING {ver}) median [5–95 %]</th>"
            f"<th {th}>Argo (ML mean)</th></tr>{body}</table>"
        )

    # -- Argo panel -----------------------------------------------------------
    def _vband(self, src_band, src_line, value, lo, hi, top) -> None:
        if not _finite(value):
            src_band.data, src_line.data = dict(_EMPTY_BAND), dict(_EMPTY_LINE)
            return
        src_line.data = {"x": [value, value], "y": [0.0, top]}
        if _finite(lo) and _finite(hi):
            src_band.data = {"x1": [lo, lo], "x2": [hi, hi], "y": [0.0, top]}
        else:
            src_band.data = dict(_EMPTY_BAND)

    def show_selection(self, sel: Selection) -> None:
        """Header, table and the stored values (no fetch, no reconstruction)."""
        self._sel = sel
        self._adg440 = None
        self._layers = None
        self.show_header(sel)
        m = sel.matchup or {}
        top = sel.ml_span
        self.argo_fig.y_range.start = sel.y_max
        self.argo_fig.y_range.end = 0.0
        self.mld_span.visible = np.isfinite(sel.mld)
        if np.isfinite(sel.mld):
            self.mld_span.location = sel.mld
        mean, std = m.get("bbp700"), m.get("bbp700_std")
        if _finite(mean) and _finite(std):
            self._vband(self.argo_band, self.argo_line, mean, mean - std, mean + std, top)
        else:
            self._vband(self.argo_band, self.argo_line, mean, None, None, top)
        bbp = (sel.fit or {}).get("results", {}).get("bbp700")
        if bbp is None:
            self._vband(self.pace_band, self.pace_line, None, None, None, top)
        else:
            self._vband(self.pace_band, self.pace_line, *bbp, top)
        g = sel.giop
        if g is None or not _finite(g["bbp700"]):
            self._vband(self.giop_band, self.giop_line, None, None, None, top)
        else:
            u = g["bbp700_unc"]
            lo, hi = (g["bbp700"] - u, g["bbp700"] + u) if _finite(u) else (None, None)
            self._vband(self.giop_band, self.giop_line, g["bbp700"], lo, hi, top)
        for src in (self.raw_src, self.drop_src):
            src.data = {k: [] for k in src.data}
        self.desp_src.data = dict(_EMPTY_LINE)
        self.fixed_line.data = dict(_EMPTY_LINE)
        for src in (self.obs_src, self.model_src, self.resid_src):
            src.data = {k: [] for k in src.data}
        self._autorange_x()
        self.show_table()

    def show_profile(self, layers: vargo.BbpLayers | None) -> None:
        """Draw the re-fetched samples (``None`` clears them)."""
        self._layers = layers
        if layers is None:
            self.raw_src.data = {"x": [], "y": [], "qc": []}
            self.desp_src.data = dict(_EMPTY_LINE)
            self.drop_src.data = {"x": [], "y": [], "raw": []}
            self.fixed_line.data = dict(_EMPTY_LINE)
        else:
            ok = np.isfinite(layers.raw) & np.isfinite(layers.pres)
            self.raw_src.data = {"x": layers.raw[ok], "y": layers.pres[ok],
                                 "qc": [fmt(q, 1) for q in layers.qc[ok]]}
            okd = np.isfinite(layers.despiked) & np.isfinite(layers.pres)
            self.desp_src.data = {"x": layers.despiked[okd], "y": layers.pres[okd]}
            d = layers.dropped
            self.drop_src.data = {"x": layers.despiked[d], "y": layers.pres[d],
                                  "raw": layers.raw[d]}
            if layers.n and layers.ingest_differs and self._sel is not None:
                self.fixed_line.data = {"x": [layers.mean, layers.mean],
                                        "y": [0.0, self._sel.ml_span]}
            else:
                self.fixed_line.data = dict(_EMPTY_LINE)
        self._autorange_x()
        self.show_table()

    def set_giop_visible(self, flag: bool) -> None:
        self.show_giop_flag = bool(flag)
        for r in self.giop_renderers:
            r.visible = self.show_giop_flag
        self._autorange_x()
        self.show_table()

    def _autorange_x(self) -> None:
        """Fit x to the samples inside the y window plus every drawn band."""
        vals = []
        if self._layers is not None and self._sel is not None:
            ly = self._layers
            ok = np.isfinite(ly.raw) & (ly.pres <= self._sel.y_max)
            vals.extend(ly.raw[ok].tolist())
        sources = [(self.argo_band, self.argo_line), (self.pace_band, self.pace_line)]
        if self.show_giop_flag:
            sources.append((self.giop_band, self.giop_line))
        for band, line in sources:
            vals.extend(band.data["x1"])
            vals.extend(band.data["x2"])
            vals.extend(line.data["x"])
        vals.extend(self.fixed_line.data["x"])
        vals = np.asarray([v for v in vals if _finite(v)], dtype=float)
        if not vals.size:
            return
        lo, hi = float(vals.min()), float(vals.max())
        pad = 0.08 * (hi - lo) if hi > lo else 0.1 * abs(hi) or 1e-4
        self.argo_fig.x_range.start = max(lo - pad, 0.0) if lo >= 0 else lo - pad
        self.argo_fig.x_range.end = hi + pad

    # -- PACE panel ------------------------------------------------------------
    def _autorange_rrs(self) -> None:
        """y from min(0, data) to the top of the data: 0 is always in view."""
        vals = []
        for src, keys in ((self.obs_src, ("lo", "hi")), (self.model_src, ("lo", "hi", "med"))):
            for k in keys:
                vals.extend(np.asarray(src.data[k], dtype=float).ravel().tolist())
        vals = np.asarray([v for v in vals if np.isfinite(v)], dtype=float)
        if not vals.size:
            return
        lo, hi = min(0.0, float(vals.min())), max(0.0, float(vals.max()))
        pad = 0.05 * (hi - lo) if hi > lo else 1e-4
        self.rrs_fig.y_range.start = lo - pad if lo < 0 else 0.0
        self.rrs_fig.y_range.end = hi + pad

    def show_observed(self, wave, rrs, sigma) -> None:
        """Observed ``Rrs`` ± σ before the model is ready."""
        self.obs_src.data = {"wave": wave, "rrs": rrs, "lo": rrs - sigma, "hi": rrs + sigma,
                             "sigma": sigma, "model": np.full_like(rrs, np.nan)}
        self._autorange_rrs()

    def show_curves(self, c: vfits.FitCurves) -> None:
        """The reconstructed model, the residuals and ``a_dg(440)``."""
        self.obs_src.data = {"wave": c.wave, "rrs": c.rrs_obs, "lo": c.rrs_obs - c.sigma,
                             "hi": c.rrs_obs + c.sigma, "sigma": c.sigma, "model": c.rrs_med}
        self.model_src.data = {"wave": c.wave, "med": c.rrs_med, "lo": c.rrs_lo,
                               "hi": c.rrs_hi}
        self.resid_src.data = {"wave": c.wave, "rs": c.resid_sigma, "r": c.resid,
                               "pct": c.resid_pct}
        self._autorange_rrs()
        self._adg440 = c.adg440
        self.show_table()

    def show_no_curves(self) -> None:
        """Mark ``a_dg(440)`` unavailable (no chains)."""
        self._adg440 = (np.nan, np.nan, np.nan)
        self.show_table()


def profile_notes(sel: Selection, layers: vargo.BbpLayers | None, recomputed: dict | None):
    """The AP-Q13 / AP-Q15 messages about the Argo side."""
    notes = []
    m = sel.matchup or {}
    if layers is not None and not np.isfinite(layers.raw).any():
        notes.append("This profile has no BBP700 samples.")
    if not np.isfinite(sel.mld):
        notes.append(f"No MLD for this profile: no ML mean; depth shown to {NO_MLD_DEPTH:.0f} m.")
    elif _finite(m.get("bbp700")) and not _finite(m.get("bbp700_std")):
        notes.append("The stored ML std is missing, so the Argo mean is drawn without a band.")
    if layers is not None and layers.n and layers.ingest_differs:
        notes.append(
            f"The stored ML mean ({fmt(layers.ingest_mean)} m⁻¹, n={layers.ingest_n}) comes "
            "from the ingest de-spike, which runs over every pressure level: with BBP700 on "
            "only some levels it de-spikes nothing and copies samples into the empty levels. "
            f"Over the {layers.n_samples_ml} BBP700 samples in the ML, de-spiked sample to "
            f"sample, the mean is {fmt(layers.mean)} m⁻¹ (n={layers.n}, dotted line; AP-Q16).")
    if recomputed is not None:
        stored, new = m.get("bbp700"), recomputed.get("bbp700", np.nan)
        if not vargo.reproduces(stored, new):
            notes.append(
                f"The re-fetched profile gives an ML mean of {fmt(new)} m⁻¹ "
                f"(MLD {fmt(recomputed.get('mld'))} m) against the stored {fmt(stored)} m⁻¹ "
                f"(MLD {fmt(m.get('mld'))} m): the GDAC file changed since ingest. "
                "The stored values are drawn.")
    return notes


def make_argo_pace(store, wmo: int, cycle: int, *, family: str | None = None,
                   db_path=None, model_pair: str = data.DEFAULT_MODEL_PAIR,
                   show_giop: bool = False, fetch: bool = True,
                   argo_profile: vargo.ArgoProfile | None = None,
                   curves: vfits.FitCurves | None = None) -> ArgoPaceView:
    """Build and fill the view synchronously (no server).

    ``argo_profile`` / ``curves`` inject pre-loaded data (tests). Otherwise the
    profile is fetched when ``fetch`` is true, and the fit is reconstructed
    when ``db_path`` is given and the chains are present.
    """
    view = ArgoPaceView()
    sel = load_selection(store, wmo, cycle, family, model_pair=model_pair)
    view.show_selection(sel)
    view.set_giop_visible(show_giop)
    notes = []
    if argo_profile is None and fetch and sel.matchup is not None:
        try:
            argo_profile = vargo.fetch_argo_profile(sel.wmo, sel.cycle)
        except Exception as exc:  # noqa: BLE001 - shown, never raised (AP-Q15)
            notes.append(f"Argo fetch failed ({type(exc).__name__}: {exc}); "
                         "showing the stored ML mean and MLD only.")
    layers = recomputed = None
    if argo_profile is not None:
        layers = vargo.bbp_layers(argo_profile.pres, argo_profile.bbp, sel.mld,
                                  argo_profile.bbp_qc)
        recomputed = vargo.recompute_summary(argo_profile)
    view.show_profile(layers)
    notes.extend(profile_notes(sel, layers, recomputed))
    if sel.fit is not None:
        fid = sel.fit["fit_id"]
        if curves is None and db_path is not None and data.has_chains(fid):
            curves = vfits.reconstruct(db_path, fid)
        if curves is not None:
            view.show_curves(curves)
        else:
            notes.append(f"No chain file for {fid}: the model curve cannot be drawn.")
            view.show_no_curves()
    view.set_notes(notes)
    return view
