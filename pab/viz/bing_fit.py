"""The BING-fit editor: one stored BING fit, with every parameter editable.

Design: ``claude_prompts/viz/viz_bing_fit.md``, Q&A / Design (BF-Q1 to BF-Q17).

* **Left panel**: the PACE ``Rrs`` fit as in :mod:`pab.viz.bokeh_argo_pace`
  (observed ``Rrs`` ± σ, the BING posterior median in orange with its 5–95 %
  band, the linear/log10 toggle and the residual strip in σ), plus the
  **modified** model in blue and its residuals.
* **Right panel**: the non-water IOPs of the fit (``a_nw``, ``a_dg``,
  ``a_ph`` on the left axis, ``b_bp`` dashed on the right axis, each with its
  5–95 % band) and the modified IOPs in the same colours, dotted (``b_bp``
  dot-dash). The Argo ML ``b_bp(700)`` ± std is marked at 700 nm, and
  NASA-GIOP's ``b_bp(700)`` is available from the legend (hidden at start).
* **Controls** (BF-Q2 to BF-Q4 as answered): one row per free parameter in
  fit space (log10 where the prior is log-uniform). Each row has a number box
  (the model updates on Enter), "−10 %" / "+10 %" buttons that scale the
  **physical** value of the parameter by 0.9 / 1.1 (for a log parameter,
  −0.046 / +0.041 dex in fit space), a "↺" button and the physical value.
  Any finite value is accepted, inside the prior or not (BF-I9); a value
  outside the prior gets a note, not a refusal. "Reset to fit" restores
  every parameter.
  There are no sliders: they were too coarse for this.
* The modified model starts at the **posterior median of each parameter**
  (BF-Q1); its χ² must then equal the stored ``fits.chisq``, and a note says
  so when it does not. The fit's posterior bands stay visible throughout
  (BF-Q5 = B); only the modified model is drawn without a band.
* A derived-quantity table compares the fit (stored medians [5–95 %]), the
  modified model (computed by :func:`pab.fit.run.extract_quantities`) and
  Argo (secondary, greyed). Emulator out-of-domain warnings are shown as an
  amber note (BF-Q14).

Read-only: nothing is written. The current parameters are shown as
copyable text, and Bokeh's ``save`` tool exports a PNG (BF-Q10).

Launch (one fit per server; restart for another, BF-Q15)::

    python -m pab.viz.bing_fit --wmo 2902882 --cycle 96 [--show]

:class:`BingFitView` owns the figures, sources and widgets.
:func:`make_bing_fit` builds and fills it without a server (tests). With a
``doc``, evaluations run in a thread pool and land via
``doc.add_next_tick_callback``; a token drops a result superseded by a
newer edit.
"""

from __future__ import annotations

import argparse
import functools
import html
import logging
import sys
import time
from concurrent.futures import ThreadPoolExecutor

import numpy as np
from bokeh.layouts import column, row
from bokeh.models import (
    Button,
    Checkbox,
    ColumnDataSource,
    Div,
    HoverTool,
    TextInput,
)

from pab.viz import bokeh_argo_pace as ap
from pab.viz import data, server
from pab.viz import fits as vfits

log = logging.getLogger("pab.viz")

#: The modified model (left panel).
MOD_COLOR = "#2166ac"

#: The "−10 %" / "+10 %" buttons scale a parameter's physical value by
#: ``1 ∓ STEP_FRACTION`` (BF-Q2 as answered).
STEP_FRACTION = 0.10

#: Relative tolerance of the start-curve χ² against the stored ``fits.chisq``.
CHISQ_RTOL = 1e-4

#: Display labels of the parameters (fit space); unknown names are shown as is.
PARAM_LABELS = {
    "Adg": ("log<sub>10</sub> A<sub>dg</sub>", "a<sub>dg</sub>(400)", "m⁻¹"),
    "Sdg": ("S<sub>dg</sub>", "S<sub>dg</sub>", "nm⁻¹"),
    "Aph": ("log<sub>10</sub> A<sub>ph</sub>", "a<sub>ph</sub>(440)", "m⁻¹"),
    "Bnw": ("log<sub>10</sub> B<sub>nw</sub>", "b<sub>bp</sub>(600)", "m⁻¹"),
    "beta": ("β", "β", ""),
    "Bp": ("B<sub>p</sub>", "B<sub>p</sub>", ""),
}

#: Rows of the derived-quantity table: (quantity, label, Argo key).
TABLE_ROWS = (
    ("bbp700", "b<sub>bp</sub>(700) (m⁻¹)", "bbp700"),
    ("bbp440", "b<sub>bp</sub>(440) (m⁻¹)", None),
    ("beta", "β (b<sub>bp</sub> slope)", None),
    ("anw440", "a<sub>nw</sub>(440) (m⁻¹)", None),
    ("adg440", "a<sub>dg</sub>(440) (m⁻¹), CDOM + detritus", None),
    ("Sdg", "S<sub>dg</sub> (nm⁻¹)", None),
    ("chl", "Chl (mg m⁻³), from A<sub>ph</sub>", "chla"),
    ("Bp", "B<sub>p</sub>", None),
    ("chisq", "χ²<sub>red</sub>", None),
)

#: Shared by every session of the server.
_POOL = ThreadPoolExecutor(max_workers=2, thread_name_prefix="pab-bing-fit")

_NOTE_STYLE = "color:#8a5a00;font-size:90%"


def step_value(spec: vfits.ParamSpec, value: float, direction: int) -> float:
    """``value`` (fit space) after a "±10 %" step: the **physical** value is
    scaled by ``1 + direction · STEP_FRACTION`` (a log parameter moves by
    ``log10(1 ± 0.1)`` dex; BF-I8). Not clipped to the prior (BF-I9). A linear
    parameter at exactly 0 stays at 0 (a percentage of zero); type a value
    instead."""
    factor = 1.0 + direction * STEP_FRACTION
    return float(value + np.log10(factor) if spec.is_log else value * factor)


def domain_feature(line: str) -> str:
    """The feature name of a :func:`~pab.viz.fits.domain_messages` line."""
    return line.split(":", 1)[0]


def param_label(name: str) -> tuple[str, str, str]:
    """``(fit-space label, physical label, unit)`` of parameter ``name``."""
    return PARAM_LABELS.get(name, (html.escape(name), html.escape(name), ""))


def plain_label(name: str) -> str:
    """The fit-space label without HTML (``log10 A_dg``)."""
    lab = param_label(name)[0]
    for tag in ("<sub>", "</sub>"):
        lab = lab.replace(tag, "" if tag == "</sub>" else "_")
    return lab.replace("log_10", "log10")


class BingFitView:
    """Figures, sources, widgets and callbacks of the BING-fit editor."""

    def __init__(self, sel: ap.Selection, forward, curves: vfits.FitCurves | None, *,
                 doc=None, width: int = 1500):
        self.sel = sel
        self.fm = forward
        self.curves = curves
        self.doc = doc
        self.token = 0
        self._future = None
        self.specs = list(forward.specs)
        self.params = np.asarray(forward.start, dtype=float).copy()
        self.evaluation: vfits.Evaluation | None = None
        self._quiet = False
        self._messages: list[str] = []
        #: Out-of-domain lines of the start (posterior-median) evaluation.
        self._start_domain: tuple[str, ...] = ()
        #: The last evaluation failure; cleared by the next success.
        self._error: str | None = None
        left_w = int(width * 0.55)
        right_w = width - left_w - 20

        self.header = Div(text="", sizing_mode="stretch_width")
        self.notes = Div(text="", sizing_mode="stretch_width")
        self.settings = Div(text=self._settings_html(), sizing_mode="stretch_width")

        # -- left: Rrs ------------------------------------------------------
        self.obs_src = ColumnDataSource(
            {"wave": [], "rrs": [], "lo": [], "hi": [], "lo_log": [], "sigma": [],
             "model": []})
        self.model_src = ColumnDataSource(
            {"wave": [], "med": [], "lo": [], "hi": [], "lo_log": []})
        self.resid_src = ColumnDataSource({"wave": [], "rs": [], "r": [], "pct": []})
        self.mod_src = ColumnDataSource({"wave": [], "rrs": []})
        self.mod_resid_src = ColumnDataSource({"wave": [], "rs": [], "r": [], "pct": []})

        q, ql, self.rrs_scale, rr = ap.rrs_figures(left_w, self.model_src, self.obs_src)
        self.rrs_fig, self.rrs_log_fig = q, ql
        self.rrs_scale.on_change("active", lambda a, o, n: ap.set_rrs_scale(
            self.rrs_fig, self.rrs_log_fig, self.rrs_scale, n == 1))
        self.rrs_bands = [rr["lin"]["band"], rr["log"]["band"]]  # always shown (BF-Q5 = B)
        for fig in (q, ql):
            mod = fig.line("wave", "rrs", source=self.mod_src, color=MOD_COLOR,
                           line_width=2, legend_label="modified")
            fig.add_tools(HoverTool(renderers=[mod], mode="vline", tooltips=[
                ("λ", "@wave{0} nm"), ("modified", "@rrs{0.000000}")]))
        self.resid_fig, _ = ap.resid_figure(left_w, q.x_range, self.resid_src)
        self.resid_fig.scatter("wave", "rs", source=self.mod_resid_src, size=4,
                               color=MOD_COLOR, marker="square")

        # -- right: IOPs ----------------------------------------------------
        self.iop_src = ColumnDataSource({k: [] for k in ap._IOP_COLS})
        self.mod_iop_src = ColumnDataSource({"wave": [], "anw": [], "adg": [], "aph": [],
                                             "bbp": []})
        t, ir = ap.iop_figure(right_w, q.x_range, self.iop_src,
                              title="BING IOPs (non-water): fit and modified")
        self.iop_fig = t
        self.iop_bands = list(ir["bands"].values())  # always shown (BF-Q5 = B)
        for key, _label, color, _dash, yname in ap.IOP_STYLES:
            t.line("wave", key, source=self.mod_iop_src, color=color, line_width=2,
                   line_dash="dotdash" if key == "bbp" else "dotted",
                   y_range_name=yname, legend_label="modified (dotted)")
        self.argo_src = ColumnDataSource({"x": [], "y": [], "lo": [], "hi": []})
        self.giop_src = ColumnDataSource({"x": [], "y": [], "lo": [], "hi": []})
        self.argo_renderers = [
            t.segment(x0="x", y0="lo", x1="x", y1="hi", source=self.argo_src,
                      color=ap.ARGO_COLOR, line_width=2, y_range_name="bbp",
                      legend_label="Argo ML b_bp(700) ± std"),
            t.scatter("x", "y", source=self.argo_src, size=9, color=ap.ARGO_COLOR,
                      y_range_name="bbp", legend_label="Argo ML b_bp(700) ± std"),
        ]
        self.giop_renderers = [
            t.segment(x0="x", y0="lo", x1="x", y1="hi", source=self.giop_src,
                      color=ap.GIOP_COLOR, line_width=2, y_range_name="bbp",
                      legend_label="NASA-GIOP b_bp(700)"),
            t.scatter("x", "y", source=self.giop_src, size=9, marker="diamond",
                      color=ap.GIOP_COLOR, y_range_name="bbp",
                      legend_label="NASA-GIOP b_bp(700)"),
        ]
        for r in self.giop_renderers:  # off at start; the legend turns it on
            r.visible = False

        # -- controls -------------------------------------------------------
        self.boxes: list[TextInput] = []
        self.downs: list[Button] = []
        self.ups: list[Button] = []
        self.resets: list[Button] = []
        self.infos: list[Div] = []
        rows = []
        pct = f"{100 * STEP_FRACTION:g} %"
        for i, spec in enumerate(self.specs):
            name = Div(text=param_label(spec.name)[0], width=110, margin=(10, 5, 5, 5))
            down = Button(label=f"−{pct}", width=62)
            down.on_click(functools.partial(self.step_param, i, -1))
            b = TextInput(value=f"{spec.median:.6g}", width=120)
            b.on_change("value", functools.partial(self._on_box, i))
            up = Button(label=f"+{pct}", width=62)
            up.on_click(functools.partial(self.step_param, i, +1))
            r = Button(label="↺", width=36)
            r.on_click(functools.partial(self.reset_param, i))
            info = Div(text="", width=330)
            self.boxes.append(b)
            self.downs.append(down)
            self.ups.append(up)
            self.resets.append(r)
            self.infos.append(info)
            rows.append(row(name, down, b, up, r, info))
        self.reset_all = Button(label="Reset to fit", button_type="primary", width=140)
        self.reset_all.on_click(self.reset)
        self.auto_range = Checkbox(label="auto-range on edit", active=True)
        self.table = Div(text="")
        self.param_text = Div(text="")

        self.layout = column(
            self.header,
            self.notes,
            self.settings,
            row(column(self.rrs_scale, self.rrs_fig, self.rrs_log_fig, self.resid_fig),
                column(Div(text="", height=31), self.iop_fig)),
            row(column(Div(text="<b>Parameters</b> (fit space; type a value and press "
                           f"Enter, or step the physical value by ±{pct})"),
                       *rows, row(self.reset_all, self.auto_range)),
                column(self.table, self.param_text)),
        )

    # -- text ----------------------------------------------------------------
    def _settings_html(self) -> str:
        st = self.fm.settings()
        on = {True: "on", False: "off"}
        geom = st.get("geometry")
        geom_txt = ("—" if geom is None else
                    "(θ<sub>s</sub>, θ<sub>v</sub>, Δφ) = (" + ", ".join(f"{g:.3g}" for g in geom)
                    + f") [{html.escape(str(st.get('geom_mode')))}]")
        chl = st.get("chl_seed")
        w0, w1, nw = st.get("wave", (np.nan, np.nan, 0))
        parts = [
            f"backend {html.escape(str(st.get('rt_backend')))}",
            f"Raman {on[bool(st.get('Raman'))]}",
            f"Chl-fl {on[bool(st.get('Chl-fl'))]}",
            f"CDOM-fl {on[bool(st.get('CDOM-fl'))]}",
            f"φ<sub>c</sub> {ap.fmt(st.get('phi_c'))}",
            geom_txt,
            f"a<sub>ph</sub> shape seeded by Chl = {ap.fmt(chl)} mg m⁻³ (Argo)",
            f"{w0:.0f}–{w1:.0f} nm, {nw} bands",
        ]
        return ("<div style='color:#555;font-size:85%'><b>Forward model (fixed):</b> "
                + " · ".join(parts) + "</div>")

    def _show_header(self) -> None:
        ev = self.evaluation
        extra = [f"<span style='color:{MOD_COLOR}'>χ²<sub>red</sub> modified "
                 f"{ap.fmt(ev.chisq) if ev is not None else '…'}</span>"]
        self.header.text = ap.header_html(self.sel, extra)

    def _show_notes(self) -> None:
        """Standing messages, then the emulator domain (BF-Q14). Features the
        fit itself already breaches (most 2.1 fits sit above the emulator's
        trained ``B_p`` range) are a grey standing line; only a feature an edit
        newly pushes out of range is the amber warning."""
        msgs = list(self._messages)
        if self._error:
            msgs.append(f"<b>{html.escape(self._error)}</b> The plot shows the last "
                        "successful evaluation.")
        msgs.extend(self._prior_notes())
        ev = self.evaluation
        known = {domain_feature(d) for d in self._start_domain}
        new = [d for d in (ev.domain if ev is not None else ()) if domain_feature(d) not in known]
        if new:
            msgs.append("<b>The modified model is outside the emulator's training range</b> "
                        "(its curve may be unreliable): "
                        + "; ".join(html.escape(d) for d in new))
        if self._start_domain:
            msgs.append("<span style='color:#777'>The fit itself (posterior medians) is "
                        "outside the emulator's training range: "
                        + "; ".join(html.escape(d) for d in self._start_domain) + "</span>")
        self.notes.text = (f"<div style='{_NOTE_STYLE}'>" + "<br>".join(msgs) + "</div>"
                           if msgs else "")

    def _prior_notes(self) -> list[str]:
        """One note per parameter now outside its prior: allowed (BF-I9), but
        the fit never sampled there."""
        out = []
        for spec, v in zip(self.specs, self.params, strict=True):
            if not spec.in_prior(v):
                out.append(f"{html.escape(spec.name)} = {v:.6g} is outside its prior "
                           f"[{spec.prior_lo:g}, {spec.prior_hi:g}] (allowed; the fit "
                           "never sampled there).")
        return out

    def _fit_value(self, key: str):
        """The fit column of the table: stored ``(median, lo, hi)``."""
        if key == "chisq":
            v = self.fm.stored_chisq
            return (v, np.nan, np.nan)
        if key == "adg440":
            return self.curves.adg440 if self.curves is not None else None
        return (self.sel.fit or {}).get("results", {}).get(key)

    def _show_table(self) -> None:
        ev = self.evaluation
        m = self.sel.matchup or {}
        ver = html.escape(str(self.sel.fit["pab_version"])) if self.sel.fit else "—"
        rows = []
        for key, label, argo_key in TABLE_ROWS:
            if ev is None:
                mod = "…"
            elif key == "chisq":
                mod = ap.fmt(ev.chisq)
            else:
                mod = ap.fmt(ev.quantities.get(key))
            argo = "—"
            if argo_key is not None and ap._finite(m.get(argo_key)):
                argo = ap.fmt(m.get(argo_key))
                std = m.get(f"{argo_key}_std")
                if ap._finite(std):
                    argo += f" ± {ap.fmt(std)}"
            rows.append((label, ap.fmt_ci(self._fit_value(key)),
                         f"<span style='color:{MOD_COLOR}'><b>{mod}</b></span>",
                         f"<span style='color:#888'>{argo}</span>"))
        self.table.text = ap.table_html(
            ("quantity", f"fit (BING {ver}) median [5–95 %]",
             f"<span style='color:{MOD_COLOR}'>modified</span>",
             "<span style='color:#888'>Argo (ML)</span>"), rows)

    def _show_params(self) -> None:
        for i, spec in enumerate(self.specs):
            v = self.params[i]
            _, phys, unit = param_label(spec.name)
            unit = f" {unit}" if unit else ""
            fit = ap.fmt_ci((spec.physical(spec.median), spec.physical(spec.lo),
                             spec.physical(spec.hi)))
            edited = "" if v == spec.median else " <b>(edited)</b>"
            self.infos[i].text = (f"{phys} = <b>{ap.fmt(spec.physical(v))}</b>{unit}{edited}"
                                  f"<br><span style='color:#777;font-size:85%'>fit {fit}"
                                  "</span>")
        fit_space = ", ".join(f"{s.name}={v:.6g}" for s, v in zip(self.specs, self.params,
                                                                   strict=True))
        physical = ", ".join(f"{s.name}={s.physical(v):.6g}"
                             for s, v in zip(self.specs, self.params, strict=True))
        vec = "[" + ", ".join(f"{v:.6g}" for v in self.params) + "]"
        self.param_text.text = (
            "<div style='font-size:85%'><b>Current parameters</b> (copy as text)"
            f"<pre style='user-select:all;white-space:pre-wrap'>fit space: {fit_space}\n"
            f"physical:  {physical}\nvector:    {vec}</pre></div>")

    def add_messages(self, messages) -> None:
        """Append standing notes (e.g. the other matchups of the profile)."""
        self._messages.extend(m for m in messages if m)
        self._show_notes()

    # -- state -----------------------------------------------------------------
    @property
    def edited(self) -> bool:
        return bool(np.any(self.params != np.asarray(self.fm.start, dtype=float)))

    def show_fit(self) -> None:
        """The stored fit: observed spectrum, posterior model and IOPs, marks."""
        c = self.curves
        if c is not None:
            lo = c.rrs_obs - c.sigma
            self.obs_src.data = {"wave": c.wave, "rrs": c.rrs_obs, "lo": lo,
                                 "hi": c.rrs_obs + c.sigma,
                                 "lo_log": np.maximum(lo, ap.RRS_LOG_FLOOR),
                                 "sigma": c.sigma, "model": c.rrs_med}
            self.model_src.data = {"wave": c.wave, "med": c.rrs_med, "lo": c.rrs_lo,
                                   "hi": c.rrs_hi,
                                   "lo_log": np.maximum(c.rrs_lo, ap.RRS_LOG_FLOOR)}
            self.resid_src.data = {"wave": c.wave, "rs": c.resid_sigma, "r": c.resid,
                                   "pct": c.resid_pct}
            iop = {"wave": c.wave}
            nan = np.full_like(c.wave, np.nan, dtype=float)
            for k in ap.IOP_KEYS:
                med, lo_, hi = c.iops.get(k, (nan, nan, nan))
                iop[k], iop[f"{k}_lo"], iop[f"{k}_hi"] = med, lo_, hi
            self.iop_src.data = iop
        else:
            self._messages.append("No posterior reconstruction: the fit's median and "
                                  "bands cannot be drawn.")
        m = self.sel.matchup or {}
        mean, std = m.get("bbp700"), m.get("bbp700_std")
        if ap._finite(mean):
            s = float(std) if ap._finite(std) else 0.0
            self.argo_src.data = {"x": [700.0], "y": [float(mean)], "lo": [float(mean) - s],
                                  "hi": [float(mean) + s]}
        g = self.sel.giop
        if g is not None and ap._finite(g.get("bbp700")):
            u = float(g["bbp700_unc"]) if ap._finite(g.get("bbp700_unc")) else 0.0
            b = float(g["bbp700"])
            self.giop_src.data = {"x": [700.0], "y": [b], "lo": [b - u], "hi": [b + u]}

    def show_evaluation(self, ev: vfits.Evaluation, *, autorange: bool = False) -> None:
        """Draw the modified model ``ev``."""
        self.evaluation = ev
        wave = self.fm.wave
        sigma = np.sqrt(self.fm.var)
        resid = self.fm.rrs_obs - ev.rrs
        self.mod_src.data = {"wave": wave, "rrs": ev.rrs}
        self.mod_resid_src.data = {"wave": wave, "rs": resid / sigma, "r": resid,
                                   "pct": 100.0 * resid / ev.rrs}
        nan = np.full_like(wave, np.nan, dtype=float)
        self.mod_iop_src.data = {"wave": wave, **{k: ev.iops.get(k, nan) for k in
                                                  ("anw", "adg", "aph", "bbp")}}
        if autorange or self.auto_range.active:
            self.autorange()
        self._show_header()
        self._show_notes()
        self._show_table()
        self._show_params()

    def autorange(self) -> None:
        """Fit the axes to the data, the posterior and the modified model; the
        reset tool returns here. Runs on load, on reset and, while "auto-range
        on edit" is ticked (the default), on every edit; untick it to keep a
        zoom while editing."""
        o, m, d = self.obs_src.data, self.model_src.data, self.mod_src.data
        ap.autorange_rrs(self.rrs_fig, self.rrs_log_fig,
                         [o["lo"], o["hi"], m["lo"], m["hi"], m["med"], d["rrs"]],
                         [o["rrs"], o["hi"], m["lo"], m["hi"], m["med"], d["rrs"]])
        i, mi = self.iop_src.data, self.mod_iop_src.data
        ap.autorange_iops(
            self.iop_fig,
            [i[f"{k}{s}"] for k in ("anw", "adg", "aph") for s in ("", "_lo", "_hi")]
            + [mi[k] for k in ("anw", "adg", "aph")],
            [i["bbp"], i["bbp_lo"], i["bbp_hi"], mi["bbp"], self.argo_src.data["hi"]])

    # -- evaluation --------------------------------------------------------------
    def request_update(self, *, autorange: bool = False) -> None:
        """Evaluate the current parameters: synchronously without a ``doc``,
        else in the pool with a stale-result token (BF-Q4)."""
        self.token += 1
        params = self.params.copy()
        if self.doc is None:
            ev, error = self._evaluate(params)
            self._done(self.token, ev, error, autorange)
            return
        token = self.token
        self._show_header_pending()
        self._future = _POOL.submit(self._job, token, params, autorange)

    def _show_header_pending(self) -> None:
        self.header.text = ap.header_html(
            self.sel, [f"<span style='color:{MOD_COLOR}'><i>evaluating…</i></span>"])

    def _evaluate(self, params):
        """``(Evaluation, None)``, or ``(None, message)`` when the forward model
        fails (e.g. a non-physical value; any value may be typed, BF-I9)."""
        t0 = time.monotonic()
        try:
            return self.fm.evaluate(params), None
        except Exception as exc:  # noqa: BLE001 - shown in the page
            return None, f"Evaluation failed ({type(exc).__name__}: {exc})."
        finally:
            log.debug("evaluate in %.3f s", time.monotonic() - t0)

    def _job(self, token: int, params, autorange: bool) -> None:
        result = self._evaluate(params)
        self.doc.add_next_tick_callback(functools.partial(self._done, token, *result,
                                                          autorange))

    def _done(self, token: int, ev, error, autorange: bool) -> None:
        if token != self.token:
            return
        self._error = error
        if ev is None:
            self._show_header()
            self._show_notes()
            self._show_params()
            return
        self.show_evaluation(ev, autorange=autorange)

    # -- callbacks -----------------------------------------------------------
    def set_param(self, i: int, value: float) -> bool:
        """Set parameter ``i`` (fit space) and re-evaluate. Any finite value is
        taken (BF-I9): outside the prior it is noted, not refused. NaN / inf
        are refused."""
        spec = self.specs[i]
        value = float(value)
        self._messages = [m for m in self._messages if not m.startswith("Refused")]
        if not np.isfinite(value):
            self._messages.append(f"Refused {html.escape(spec.name)} = {value}: not finite.")
            self._sync_widgets(i)
            self._show_notes()
            return False
        if value == self.params[i]:
            self._sync_widgets(i)
            self._show_notes()  # a cleared "Refused" note must go too
            return False
        self.params[i] = value
        self._sync_widgets(i)
        self.request_update()
        return True

    def _sync_widgets(self, i: int) -> None:
        """Number box ``i`` to the current value (no callback)."""
        self._quiet = True
        try:
            self.boxes[i].value = f"{float(self.params[i]):.6g}"
        finally:
            self._quiet = False

    def step_param(self, i: int, direction: int) -> bool:
        """The "±10 %" buttons: scale the physical value of parameter ``i``
        (:func:`step_value`; no clipping, BF-I9)."""
        return self.set_param(i, step_value(self.specs[i], float(self.params[i]), direction))

    def _on_box(self, i: int, attr, old, new) -> None:
        if self._quiet:
            return
        try:
            value = float(new)
        except (TypeError, ValueError):
            self._messages.append(f"Refused {html.escape(self.specs[i].name)} = "
                                  f"{html.escape(str(new))!r}: not a number.")
            self._sync_widgets(i)
            self._show_notes()
            return
        self.set_param(i, value)

    def reset_param(self, i: int) -> None:
        """Parameter ``i`` back to its posterior median."""
        self.set_param(i, self.specs[i].median)

    def reset(self) -> None:
        """Every parameter back to the posterior median."""
        self.params = np.asarray(self.fm.start, dtype=float).copy()
        self._messages = [m for m in self._messages if not m.startswith("Refused")]
        for i in range(len(self.specs)):
            self._sync_widgets(i)
        self.request_update()

    # -- first fill -------------------------------------------------------------
    def load(self) -> None:
        """Fill everything; the start curve is evaluated synchronously (it is
        warm by now) so the page opens complete."""
        self.show_fit()
        ev = self.fm.evaluate(self.params.copy())
        self._start_domain = tuple(ev.domain)
        stored = self.fm.stored_chisq
        if np.isfinite(stored) and not np.isclose(ev.chisq, stored, rtol=CHISQ_RTOL):
            self._messages.append(
                f"Self-check failed: χ² at the posterior-median parameters is "
                f"{ev.chisq:.6g}, but the stored fits.chisq is {stored:.6g}. The forward "
                "model rebuilt here is not the one the fit used.")
        self.show_evaluation(ev, autorange=True)


def select_fit(store, wmo: int, cycle: int, *, family: str | None = None,
               matchup_id: str | None = None, check_chains: bool = False,
               model_pair: str = data.DEFAULT_MODEL_PAIR) -> ap.Selection:
    """The :class:`~pab.viz.bokeh_argo_pace.Selection` of the fit to edit
    (BF-Q11: first matchup, best-ranked pixel, newest family by default).

    Raises:
        LookupError: no matchup, no BING fit, or (``check_chains``) no chain
            file (BF-Q17).
    """
    sel = ap.load_selection(store, wmo, cycle, family, model_pair=model_pair,
                            matchup_id=matchup_id)
    if sel.matchup is None:
        raise LookupError(f"no matchup for WMO {wmo} cycle {cycle}"
                          + (f" with id {matchup_id}" if matchup_id else ""))
    if sel.fit is None:
        raise LookupError(f"no BING {sel.family_label} fit for {sel.matchup['matchup_id']}")
    fid = sel.fit["fit_id"]
    if check_chains and not data.has_chains(fid):
        raise LookupError(f"no chain file for {fid} under {data.chains_file(fid).parent}")
    return sel


def make_bing_fit(store, wmo: int, cycle: int, *, family: str | None = None,
                  matchup_id: str | None = None, db_path=None,
                  model_pair: str = data.DEFAULT_MODEL_PAIR, forward=None,
                  curves: vfits.FitCurves | None = None, doc=None) -> BingFitView:
    """Build and fill the editor for profile ``(wmo, cycle)``.

    ``forward`` / ``curves`` inject a prepared :class:`~pab.viz.fits.ForwardModel`
    (or a stand-in with its interface) and posterior curves (tests, and the
    server, which builds them once). Otherwise both are built from
    ``db_path`` and the chains.

    Raises:
        LookupError: no matchup, no BING fit, or no chain file.
    """
    sel = select_fit(store, wmo, cycle, family=family, matchup_id=matchup_id,
                     model_pair=model_pair)
    fid = sel.fit["fit_id"]
    if forward is None or curves is None:
        if db_path is None:
            raise LookupError(f"{fid}: no db_path to rebuild the fit from")
        if forward is None:
            forward = vfits.ForwardModel(store, fid)
        if curves is None:
            curves = vfits.reconstruct(db_path, fid)
    view = BingFitView(sel, forward, curves, doc=doc)
    view.load()
    return view


# -- server ---------------------------------------------------------------------
def parse_args(argv=None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="pab-bing-fit",
        description="Inspect one BING fit and edit its parameters (read-only).")
    p.add_argument("--wmo", type=int, required=True, help="float WMO")
    p.add_argument("--cycle", type=int, required=True, help="profile cycle number")
    p.add_argument("--version", default=None,
                   help="BING version family (default: the newest)")
    p.add_argument("--matchup-id", default=None,
                   help="which matchup, when the profile has several (default: the first)")
    server.add_common_args(p, port=5007)
    return p.parse_args(argv)


def prepare(db, wmo: int, cycle: int, *, family=None, matchup_id=None,
            model_pair: str = data.DEFAULT_MODEL_PAIR, prog: str = "pab-bing-fit"):
    """Select the fit, build its forward model and posterior curves, and warm
    the JIT, once per server. Returns ``(store, forward, curves, messages)``.

    Raises:
        LookupError: no matchup, no fit, or no chain file (BF-Q17).
    """
    store = data.open_store(db)
    try:
        sel = select_fit(store, wmo, cycle, family=family, matchup_id=matchup_id,
                         check_chains=True, model_pair=model_pair)
    except LookupError:
        store.close()
        raise
    fid = sel.fit["fit_id"]
    ids = data.matchup_ids_for(store, wmo, cycle)
    msgs = []
    if len(ids) > 1 and matchup_id is None:
        msgs.append(f"{len(ids)} matchups for this profile; showing the first. Others "
                    "(--matchup-id): " + ", ".join(ids[1:]))
    print(f"{prog}: fit {fid}")
    t0 = time.monotonic()
    forward = vfits.ForwardModel(store, fid)
    curves = vfits.reconstruct(str(db), fid)
    forward.evaluate(forward.start)  # JIT warm-up (~5 s once)
    print(f"{prog}: models, posterior and JIT ready in {time.monotonic() - t0:.1f} s")
    return store, forward, curves, msgs


def make_document(doc, *, db: str, wmo: int, cycle: int, family, matchup_id,
                  model_pair: str, forward, curves, messages) -> None:
    """One session: its own read-only store (thread safety), the shared
    forward model and curves."""
    store = data.open_store(db)
    view = make_bing_fit(store, wmo, cycle, family=family, matchup_id=matchup_id,
                         model_pair=model_pair, forward=forward, curves=curves, doc=doc)
    view.add_messages(messages)
    doc.add_root(view.layout)
    doc.title = f"BING fit {wmo}/{cycle}"
    doc.on_session_destroyed(lambda ctx: store.close())


def main(argv=None) -> int:
    prog = "pab-bing-fit"
    args = parse_args(argv)
    server.setup_logging(prog)
    db = server.check_args(args, prog)
    if db is None:
        return 2
    data.set_data_dir(args.data_dir or db.parent)
    try:
        store, forward, curves, msgs = prepare(
            db, args.wmo, args.cycle, family=args.version, matchup_id=args.matchup_id,
            model_pair=args.model_pair, prog=prog)
    except LookupError as exc:
        print(f"{prog}: {exc}", file=sys.stderr)
        return 2
    store.close()
    for m in msgs:
        print(f"{prog}: {m}")
    doc_fn = functools.partial(
        make_document, db=str(db), wmo=args.wmo, cycle=args.cycle, family=args.version,
        matchup_id=args.matchup_id, model_pair=args.model_pair, forward=forward,
        curves=curves, messages=msgs)
    return server.serve(doc_fn, port=args.port, host=args.host, show=args.show, prog=prog)


if __name__ == "__main__":
    sys.exit(main())
