"""
Explore CDOM fluorescence in a stored BING fit (``papers/bbp/prompts/scrutinize.md``,
Prompts/CDOM 2).

**No refit.** The stored v2.1 posterior of one matchup is pushed through the
forward model twice:

    as is     the configuration the fit ran under (``include_CDOM_fl = False``);
    CDOM on   the same posterior samples, the same geometry, the same everything,
              with only ``include_CDOM_fl = True`` (retrieve-or-bust's Hawes 1992
              kernel, ``a_cdom = cdom_fraction * a_dg``, ``cdom_fraction`` = 0.8
              and kernel ``scale`` = 1 -- BING's defaults).

The "CDOM on" curve is therefore *not* a fit: it shows what the term adds to the
model at parameters that were tuned without it.

Figure (``fig_explore_cdom_<wmo>_<cycle>.png``, next to this script):
    top     PACE Rrs +/- sigma, the BING median (+ 5-95 % band) as is, and the
            median with CDOM fluorescence on; inset at 610-700 nm;
    bottom  (obs - model) / sigma for both models.

Usage:
    python papers/bbp/py/explore_cdom.py                 # wmo 5906209, cycle 224
    python papers/bbp/py/explore_cdom.py <wmo> <cycle>
"""
from __future__ import annotations

import dataclasses
import sys
import warnings
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
from mpl_toolkits.axes_grid1.inset_locator import inset_axes

import bing.evaluate as ev
from bing.models import utils as model_utils

from pab.config import DATA_DIR
from pab.fit import artifacts, run
from pab.fit.models import build_models
from pab.plotting import fit_fig
from pab.viz import data as vdata

# ── defaults ──────────────────────────────────────────────────────────────────

#: The v2.1 release: its database and the folder holding ``fit_chains/``.
V2_DIR = Path(DATA_DIR) / "v2"
DEFAULT_DB = V2_DIR / "pab.db"
PAB_VERSION = "2.1"

#: Output directory: next to this script.
DEFAULT_OUT_DIR = Path(__file__).resolve().parent

#: The matchup of Prompts/CDOM 1.
DEFAULT_PROFILE = (5906209, 224)

#: Wavelength window of the Rrs inset (prompt 2).
INSET_WAVE = (610.0, 700.0)

FIT_COLOR = "#5b9bd5"        # as-is median (the talk figure's pale blue)
FIT_BAND = "#bdd7ee"         # as-is 5-95 % band
CDOM_COLOR = "#d95f02"       # CDOM-fluorescence-on median
ZERO_COLOR = "#444444"

RC = {
    "font.size": 12, "axes.labelsize": 14, "axes.titlesize": 13,
    "xtick.labelsize": 12, "ytick.labelsize": 12, "legend.fontsize": 10,
    "figure.dpi": 150, "savefig.dpi": 300,
    "axes.spines.top": False, "axes.spines.right": False,
}


# ── data ──────────────────────────────────────────────────────────────────────

def find_fit(store, wmo: int, cycle: int, version: str = PAB_VERSION):
    """The ``fits`` row of the BING fit of ``(wmo, cycle)`` at ``version``."""
    rows = store.query(
        "SELECT * FROM fits WHERE algorithm = 'BING' AND pab_version = ? "
        "AND matchup_id LIKE ? ORDER BY created DESC",
        (version, f"{wmo}%"),
    )
    # '_' is a LIKE wildcard, so pin the "<wmo>_<cycle>_" prefix in Python
    rows = [r for r in rows if r["matchup_id"].startswith(f"{wmo}_{cycle}_")]
    if not rows:
        raise ValueError(f"No v{version} BING fit for wmo {wmo}, cycle {cycle}")
    return rows[0]


def _forward(config, geom, wave, obs, chl, flat):
    """Model ``Rrs`` samples of the posterior ``flat`` under ``config``.

    The models are built exactly as :func:`pab.plotting.fit_fig.reconstruct_posterior`
    does (the NPZ ``Chl`` as the a_ph shape seed, the inelastic ``Ed``).

    Returns:
        ``(rrs_samples, rt_dict)``.
    """
    _, rt_dict, models = build_models(config, wave, geom=geom)
    model_utils.init_other_bits(
        models, Chl=None if chl is None else np.array([chl]), Y=None, Rrs=obs)
    run.set_inelastic_Ed(models, geom, rt_dict)
    a_flat, bb_flat, bp_flat = run._split_flat(flat, models[0].nparam, rt_dict)
    rrs = run.reconstruct_rrs(models, a_flat, bb_flat, rt_dict, geom=geom, Bp=bp_flat)
    return np.asarray(rrs, dtype=float), rt_dict


def load_models(wmo: int, cycle: int, db=None) -> dict:
    """The stored posterior of ``(wmo, cycle)``, forward-modelled with and
    without CDOM fluorescence.

    Returns a dict with ``fit_id``, ``row``, ``wave``, ``obs``, ``sigma``,
    ``nparam``, the ``(median, 5 %, 95 %)`` triples ``asis`` and ``cdom``, the
    per-sample median difference ``delta`` (CDOM on - as is, sr^-1) and
    ``cdom_fraction``.
    """
    db = Path(db or DEFAULT_DB)
    vdata.set_data_dir(db.parent)            # v2.1 chains live in v2/fit_chains
    store = vdata.open_store(db)
    try:
        row = find_fit(store, wmo, cycle)
        config = fit_fig._config_from_row(row)
        geom = fit_fig._geometry_from_row(store, row, config)
    finally:
        store.close()
    if config.include_CDOM_fl:
        raise ValueError(f"{row['fit_id']} was already fitted with CDOM fluorescence")

    npz = artifacts.load_chains(row["fit_id"])
    wave = np.asarray(npz["wave"], dtype=float)
    obs = np.asarray(npz["Rrs"], dtype=float)
    sigma = np.sqrt(np.asarray(npz["varRrs"], dtype=float))
    chains = np.asarray(npz["chains"], dtype=float)
    chl = float(npz["Chl"]) if np.isfinite(npz["Chl"]) else None
    burn = config.analysis_burn
    if chains.shape[0] <= burn:
        burn = chains.shape[0] // 2
    flat = ev.thin_burn_chains(chains, burn=burn)

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")      # robust's DomainWarning on most fits
        rrs_asis, _ = _forward(config, geom, wave, obs, chl, flat)
        rrs_cdom, rt_cdom = _forward(
            dataclasses.replace(config, include_CDOM_fl=True),
            geom, wave, obs, chl, flat)

    return {
        "fit_id": row["fit_id"], "row": dict(row), "wave": wave, "obs": obs,
        "sigma": sigma, "nparam": flat.shape[1],
        "asis": fit_fig._band(rrs_asis), "cdom": fit_fig._band(rrs_cdom),
        "delta": np.median(rrs_cdom - rrs_asis, axis=0),
        "cdom_fraction": float(rt_cdom.get("cdom_fraction", np.nan)),
    }


def chisq_red(d: dict, rrs) -> float:
    """Reduced chi^2 of ``rrs`` against the data (k = all fitted parameters)."""
    n = d["obs"].size
    return float(np.sum(((rrs - d["obs"]) / d["sigma"]) ** 2) / max(n - d["nparam"], 1))


# ── figure ────────────────────────────────────────────────────────────────────

def _glyphs(ax, d, mask=None, ms: float = 4.0):
    """Data, the as-is median + band, and the CDOM-on median on ``ax``."""
    k = np.ones(d["wave"].size, bool) if mask is None else mask
    w = d["wave"][k]
    med, lo, hi = d["asis"]
    ax.fill_between(w, lo[k], hi[k], color=FIT_BAND, lw=0, zorder=1,
                    label="BING 5–95 % (as is)")
    ax.errorbar(w, d["obs"][k], yerr=d["sigma"][k], fmt="o", ms=ms, color="black",
                ecolor="#00000066", elinewidth=0.8, capsize=0, zorder=2,
                label="PACE $R_{rs}$ ± σ")
    ax.plot(w, med[k], color=FIT_COLOR, lw=2.2, zorder=3, label="BING median (as is)")
    ax.plot(w, d["cdom"][0][k], color=CDOM_COLOR, lw=1.8, ls="--", zorder=4,
            label="same posterior, CDOM fl. on")


def fig_explore_cdom(wmo: int, cycle: int, out=None, db=None, d=None):
    """PACE Rrs, the stored BING model, and that model with CDOM fluorescence.

    Args:
        wmo, cycle: The float profile.
        out: Path to save the PNG; nothing is saved if ``None``.
        db: Path to ``pab.db``; default :data:`DEFAULT_DB`.
        d: Pre-computed :func:`load_models` output (skips the forward models).

    Returns:
        ``(fig, d)``.
    """
    d = load_models(wmo, cycle, db) if d is None else d
    wave = d["wave"]
    info = (f"{wmo} / {cycle}   v{d['row']['pab_version']}\n"
            f"$\\chi^2_\\nu$ as is = {chisq_red(d, d['asis'][0]):.2f}\n"
            f"$\\chi^2_\\nu$ CDOM on = {chisq_red(d, d['cdom'][0]):.2f}\n"
            f"$f_{{cdom}}$ = {d['cdom_fraction']:.1f}, no refit")

    with mpl.rc_context(RC):
        fig = plt.figure(figsize=(8.5, 6.2), constrained_layout=True)
        gs = fig.add_gridspec(2, 1, height_ratios=[3.2, 1])
        ax = fig.add_subplot(gs[0])
        axr = fig.add_subplot(gs[1], sharex=ax)

        _glyphs(ax, d)
        ax.axhline(0, color=ZERO_COLOR, ls="--", lw=1.0, zorder=0)
        ax.set_ylabel(r"$R_{rs}$ (sr$^{-1}$)")
        ax.set_xlim(wave.min() - 5, wave.max() + 5)
        fmt = mpl.ticker.ScalarFormatter(useMathText=True)
        fmt.set_powerlimits((-2, 2))
        ax.yaxis.set_major_formatter(fmt)
        ax.tick_params(labelbottom=False)
        ax.legend(loc="lower left", frameon=False, handlelength=1.8,
                  borderaxespad=0.3, bbox_to_anchor=(0.0, 0.05))
        ax.set_title("PACE $R_{rs}$ and the BING model, with and without "
                     "CDOM fluorescence", loc="left")
        ax.text(0.98, 0.98, info, transform=ax.transAxes, ha="right", va="top",
                fontsize=10, linespacing=1.25,
                bbox=dict(boxstyle="round,pad=0.35", fc="white", ec="#bbbbbb"))

        # inset: the red end, where Rrs is small and b_bp dominates
        ins = inset_axes(ax, width="38%", height="40%", loc="center right",
                         bbox_to_anchor=(0.0, -0.04, 1.0, 1.0),
                         bbox_transform=ax.transAxes, borderpad=0.6)
        k = (wave >= INSET_WAVE[0]) & (wave <= INSET_WAVE[1])
        _glyphs(ins, d, mask=k, ms=2.5)
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

        # residual strip: both models
        for loc, ls in ((0, "-"), (1, "--"), (-1, "--")):
            axr.axhline(loc, color="gray", ls=ls, lw=0.8)
        r_asis = (d["obs"] - d["asis"][0]) / d["sigma"]
        r_cdom = (d["obs"] - d["cdom"][0]) / d["sigma"]
        axr.scatter(wave, r_asis, s=12, color=FIT_COLOR, linewidths=0, label="as is")
        axr.scatter(wave, r_cdom, s=12, color=CDOM_COLOR, linewidths=0,
                    marker="s", label="CDOM fl. on")
        lim = max(2.0, 1.1 * np.nanmax(np.abs(np.r_[r_asis, r_cdom])))
        axr.set_ylim(-lim, lim)
        axr.set_ylabel("resid / σ", fontsize=12)
        axr.set_xlabel("wavelength (nm)")
        axr.legend(loc="upper right", frameon=False, ncol=2, fontsize=9,
                   handletextpad=0.2, columnspacing=1.0)

        for a in (ax, axr):
            a.grid(True, color="#e4e3df", lw=0.6)
            a.set_axisbelow(True)
        if out is not None:
            fig.savefig(out)                 # inside the rc context: 300 dpi
    return fig, d


def summarize(d: dict) -> None:
    """Print the size of the CDOM-fluorescence term at a few wavelengths."""
    wave, delta = d["wave"], d["delta"]
    print(f"fit: {d['fit_id']}")
    print(f"chi2_red  as is = {chisq_red(d, d['asis'][0]):.3f}   "
          f"CDOM on = {chisq_red(d, d['cdom'][0]):.3f}")
    print(f"{'wave':>6} {'Rrs_obs':>10} {'as is':>10} {'CDOM on':>10} "
          f"{'delta':>10} {'delta/mod':>9} {'delta/sig':>9}")
    for w0 in (400, 440, 490, 550, 610, 650, 680, 700):
        i = int(np.argmin(np.abs(wave - w0)))
        m = d["asis"][0][i]
        print(f"{wave[i]:6.1f} {d['obs'][i]:10.3e} {m:10.3e} {d['cdom'][0][i]:10.3e} "
              f"{delta[i]:10.3e} {100 * delta[i] / m:8.1f}% {delta[i] / d['sigma'][i]:9.2f}")


# ── main ──────────────────────────────────────────────────────────────────────

def main(wmo: int, cycle: int):
    """Make the figure for ``(wmo, cycle)`` and print the term's size."""
    out = DEFAULT_OUT_DIR / f"fig_explore_cdom_{wmo}_{cycle}.png"
    fig, d = fig_explore_cdom(wmo, cycle, out=out)
    plt.close(fig)
    summarize(d)
    print(f"✓ {out}")


if __name__ == "__main__":
    if len(sys.argv) == 3:
        main(int(sys.argv[1]), int(sys.argv[2]))
    else:
        main(*DEFAULT_PROFILE)
