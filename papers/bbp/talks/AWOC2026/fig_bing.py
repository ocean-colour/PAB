"""
BING-fit figures for the AWOC 2026 talk (``papers/bbp/prompts/talks/aw2026_bing_fits.md``).

Figures (one Google slide each; the slide carries the title, so the figure
is sized 10 x 4.6 in to sit under it):
    1  fig_bing_good_<wmo>_<cycle>.png -- a "good" BING fit:
       (a) PACE Rrs with the BING median and 5-95 % band, a 600-700 nm inset,
           and the residuals in units of sigma;
       (b) the non-water IOPs a_dg, a_ph (left axis) and b_bp (right axis).

"Good" / "bad" / "very bad" refer to the quality of the spectral fit (Q1).

The fit is rebuilt from its v2.1 chain NPZ with :func:`pab.viz.fits.reconstruct`
(the Bokeh viewer's code, ~3-5 s); the panels mimic the PACE and IOP panels of
``pab/viz/bokeh_argo_pace.py``.

Usage:
    python papers/bbp/talks/AWOC2026/fig_bing.py 1     # the "good" fit

Change the profile by editing ``GOOD`` in :func:`main` or by calling
``fig_bing_fit(wmo, cycle, out=...)`` from Python.
"""
from __future__ import annotations

import sys
import warnings
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
from mpl_toolkits.axes_grid1.inset_locator import inset_axes

from pab.config import DATA_DIR
from pab.viz import data as vdata
from pab.viz import fits as vfits
from pab.viz.bokeh_argo_pace import (ADG_COLOR, APH_COLOR, BBP_COLOR,
                                     PACE_COLOR, ZERO_COLOR, load_selection)

# ── defaults ──────────────────────────────────────────────────────────────────

#: The v2.1 release: its database and the folder holding ``fit_chains/``.
V2_DIR = Path(DATA_DIR) / "v2"
DEFAULT_DB = V2_DIR / "pab.db"

#: Output directory: next to this script.
DEFAULT_OUT_DIR = Path(__file__).resolve().parent


#: Fit colours (prompt 2): pale blue for the BING median and its band;
#: residuals stay orange (the viewer's PACE colour).
FIT_COLOR = "#5b9bd5"        # median line
FIT_BAND = "#bdd7ee"         # 5-95 % band
RESID_COLOR = PACE_COLOR

#: Wavelength window of the Rrs inset (Q3).
INSET_WAVE = (600.0, 700.0)

RC = {
    "font.size": 12, "axes.labelsize": 14, "axes.titlesize": 14,
    "xtick.labelsize": 12, "ytick.labelsize": 12, "legend.fontsize": 11,
    "figure.dpi": 150, "savefig.dpi": 300,
    "axes.spines.top": False, "axes.spines.right": False,
}


# ── data ──────────────────────────────────────────────────────────────────────

def load_fit(wmo: int, cycle: int, db=None):
    """The v2.1 BING fit of profile ``(wmo, cycle)``, reconstructed.

    Returns:
        ``(sel, curves)``: the :class:`pab.viz.bokeh_argo_pace.Selection`
        (``sel.fit`` holds fit_id, χ²_red, success; ``sel.matchup`` the time,
        dx, dt) and the :class:`pab.viz.fits.FitCurves` (observed Rrs, σ,
        model median and 5-95 %, residuals, IOP spectra with bands).
    """
    db = Path(db or DEFAULT_DB)
    vdata.set_data_dir(db.parent)            # v2.1 chains live in v2/fit_chains
    store = vdata.open_store(db)
    try:
        sel = load_selection(store, wmo, cycle)
    finally:
        store.close()
    if sel.fit is None:
        raise ValueError(f"No BING fit for wmo {wmo}, cycle {cycle} in {db}")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")      # robust's DomainWarning on most fits
        curves = vfits.reconstruct(db, sel.fit["fit_id"])
    return sel, curves


# ── panels ────────────────────────────────────────────────────────────────────

def _rrs_glyphs(ax, c, mask=None, ms: float = 4.0):
    """Observed Rrs ± σ (black) and the BING median + 5-95 % band (pale blue)
    on ``ax``, restricted to ``mask`` if given. The model is drawn over the
    data so the pale line stays visible."""
    k = np.ones(c.wave.size, bool) if mask is None else mask
    w = c.wave[k]
    ax.fill_between(w, c.rrs_lo[k], c.rrs_hi[k], color=FIT_BAND, lw=0, zorder=1,
                    label="BING 5–95 %")
    ax.errorbar(w, c.rrs_obs[k], yerr=c.sigma[k], fmt="o", ms=ms, color="black",
                ecolor="#00000066", elinewidth=0.8, capsize=0, zorder=2,
                label="PACE $R_{rs}$ ± σ")
    ax.plot(w, c.rrs_med[k], color=FIT_COLOR, lw=2.2, zorder=3,
            label="BING median")


def _rrs_panel(ax, axr, c, info: str):
    """(a) PACE Rrs and the BING fit (linear), a 600-700 nm inset, the
    info box, and (obs - model)/σ in the strip ``axr`` below."""
    _rrs_glyphs(ax, c)
    ax.axhline(0, color=ZERO_COLOR, ls="--", lw=1.0, zorder=0)
    ax.set_ylabel(r"$R_{rs}$ (sr$^{-1}$)")
    ax.set_xlim(c.wave.min() - 5, c.wave.max() + 5)
    fmt = mpl.ticker.ScalarFormatter(useMathText=True)
    fmt.set_powerlimits((-2, 2))
    ax.yaxis.set_major_formatter(fmt)
    ax.tick_params(labelbottom=False)
    # lower left is empty (Rrs is high in the blue); upper right is the info box
    # raised off the dashed zero line (prompt 3)
    ax.legend(loc="lower left", frameon=False, fontsize=10, handlelength=1.4,
              borderaxespad=0.3, bbox_to_anchor=(0.0, 0.06))
    ax.set_title("(a) PACE $R_{rs}$ and the BING fit", loc="left")

    # info box (Q5): wmo/cycle, date, dx, dt, χ²_red
    ax.text(0.98, 0.99, info, transform=ax.transAxes, ha="right", va="top",
            fontsize=10, linespacing=1.2,
            bbox=dict(boxstyle="round,pad=0.35", fc="white", ec="#bbbbbb"))

    # inset: the red end, where Rrs is small and b_bp dominates (Q3)
    ins = inset_axes(ax, width="40%", height="38%", loc="center right",
                     bbox_to_anchor=(0.0, -0.01, 1.0, 1.0),   # raised (prompt 3)
                     bbox_transform=ax.transAxes, borderpad=0.6)
    k = (c.wave >= INSET_WAVE[0]) & (c.wave <= INSET_WAVE[1])
    _rrs_glyphs(ins, c, mask=k, ms=2.5)
    ins.axhline(0, color=ZERO_COLOR, ls="--", lw=0.8, zorder=0)
    ins.set_xlim(*INSET_WAVE)
    ins.tick_params(labelsize=9)
    ifmt = mpl.ticker.ScalarFormatter(useMathText=True)
    ifmt.set_powerlimits((-2, 2))
    ins.yaxis.set_major_formatter(ifmt)
    ins.yaxis.get_offset_text().set_fontsize(9)
    ins.text(0.97, 0.93, f"{INSET_WAVE[0]:.0f}–{INSET_WAVE[1]:.0f} nm",
             transform=ins.transAxes, ha="right", va="top", fontsize=9)
    for sp in ("top", "right"):
        ins.spines[sp].set_visible(True)

    # residual strip
    for loc, ls in ((0, "-"), (1, "--"), (-1, "--")):
        axr.axhline(loc, color="gray", ls=ls, lw=0.8)
    axr.scatter(c.wave, c.resid_sigma, s=10, color=RESID_COLOR, linewidths=0)
    lim = max(2.0, 1.1 * np.nanmax(np.abs(c.resid_sigma)))
    axr.set_ylim(-lim, lim)
    axr.set_ylabel("resid / σ", fontsize=12)
    axr.set_xlabel("wavelength (nm)")

    for a in (ax, axr):
        a.grid(True, color="#e4e3df", lw=0.6)
        a.set_axisbelow(True)


def _iop_panel(ax, c):
    """(b) The non-water IOPs, 5-95 %: a_dg and a_ph on the left axis
    (a_nw dropped, Q4), b_bp dashed on a purple right-hand axis."""
    handles = []
    for key, label, color in (("adg", r"$a_{dg}$", ADG_COLOR),
                              ("aph", r"$a_{ph}$", APH_COLOR)):
        if key not in c.iops:
            continue
        med, lo, hi = c.iops[key]
        ax.fill_between(c.wave, lo, hi, color=color, alpha=0.15, lw=0)
        handles += ax.plot(c.wave, med, color=color, lw=2.2, label=label)
    amax = max(np.nanmax(c.iops[k][2]) for k in ("adg", "aph") if k in c.iops)
    ax.set_ylim(0, 1.08 * amax)
    ax.set_xlim(c.wave.min() - 5, c.wave.max() + 5)
    ax.set_xlabel("wavelength (nm)")
    ax.set_ylabel(r"$a$ (m$^{-1}$)")
    fmt = mpl.ticker.ScalarFormatter(useMathText=True)
    fmt.set_powerlimits((-2, 2))
    ax.yaxis.set_major_formatter(fmt)

    # b_bp on the right axis, coloured so it is not misread (Q4)
    axb = ax.twinx()
    med, lo, hi = c.iops["bbp"]
    axb.fill_between(c.wave, lo, hi, color=BBP_COLOR, alpha=0.15, lw=0)
    handles += axb.plot(c.wave, med, color=BBP_COLOR, lw=2.2, ls="--",
                        label=r"$b_{bp}$ (right axis)")
    axb.set_ylim(0, 1.3 * np.nanmax(hi))     # 0-based, as the viewer
    axb.set_ylabel(r"$b_{bp}$ (m$^{-1}$)", color=BBP_COLOR)
    axb.tick_params(axis="y", colors=BBP_COLOR)
    axb.spines["right"].set_visible(True)
    axb.spines["right"].set_color(BBP_COLOR)
    bfmt = mpl.ticker.ScalarFormatter(useMathText=True)
    bfmt.set_powerlimits((-2, 2))
    axb.yaxis.set_major_formatter(bfmt)
    axb.yaxis.get_offset_text().set_color(BBP_COLOR)

    ax.legend(handles=handles, loc="upper right", frameon=False)
    ax.grid(True, color="#e4e3df", lw=0.6)
    ax.set_axisbelow(True)
    ax.set_title("(b) BING IOPs (non-water), 5–95 %", loc="left")


# ── figure ────────────────────────────────────────────────────────────────────

def fig_bing_fit(wmo: int, cycle: int, out=None, db=None,
                 sel=None, curves=None):
    """Two-panel BING-fit figure for one matchup, sized for a slide.

    Args:
        wmo, cycle: The float profile.
        out: Path to save the PNG; nothing is saved if ``None``.
        db: Path to ``pab.db``; default :data:`DEFAULT_DB` (its folder must
            hold ``fit_chains/``).
        sel, curves: Pre-loaded data (skip the DB read and reconstruction).

    Returns:
        The matplotlib Figure.
    """
    if sel is None or curves is None:
        sel, curves = load_fit(wmo, cycle, db)
    m, f = sel.matchup, sel.fit
    info = (f"{sel.wmo} / {sel.cycle}   {str(m['time'])[:10]}\n"
            f"Δx = {m['distance_km']:.1f} km,  Δt = {m['dtime_hours']:.1f} h\n"
            f"$\\chi^2_\\nu$ = {f['chisq']:.2f}")

    with mpl.rc_context(RC):
        fig = plt.figure(figsize=(10, 4.6), constrained_layout=True)
        gs = fig.add_gridspec(2, 2, width_ratios=[1.15, 1], height_ratios=[3.2, 1])
        ax = fig.add_subplot(gs[0, 0])
        axr = fig.add_subplot(gs[1, 0], sharex=ax)
        axi = fig.add_subplot(gs[:, 1])
        _rrs_panel(ax, axr, curves, info)
        _iop_panel(axi, curves)
        if out is not None:
            fig.savefig(out)                 # inside the rc context: 300 dpi
    return fig


# ── main ──────────────────────────────────────────────────────────────────────

#: Figures by number: ``python fig_bing.py <n>``.
FIGURES = {
    1: "a good BING fit (fig_bing_good_<wmo>_<cycle>.png)",
}


def main(flg: int):
    """Make figure ``flg`` with the module defaults (see :data:`FIGURES`).

    1: :func:`fig_bing_fit` for :data:`GOOD`, written to :data:`DEFAULT_OUT_DIR`.
    """
    if flg == 1:
        #: The "good" fit (prompt 2): wmo, cycle.
        GOOD = (7902116, 30)

        wmo, cycle = GOOD
        out = DEFAULT_OUT_DIR / f"fig_bing_good_{wmo}_{cycle}.png"
        fig = fig_bing_fit(wmo, cycle, out=out)
        plt.close(fig)
        print(f"✓ {out}")
    else:
        raise ValueError(f"Unknown figure {flg}; choose from {FIGURES}")


if __name__ == "__main__":
    # python fig_bing.py <n>; no argument means figure 1
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 1)
