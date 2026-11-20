"""
Figures for the AWOC 2026 talk (``papers/bbp/prompts/talk_awoc2026.md``).

Each figure is one function. The PB24 Hydrolight figures read the consolidated
PB24 cache (``$OS_COLOR/SD/derived/pb24_v1/``) through
``robust.rt.data.pb24_cache``, so they need the ``retrieve-or-bust`` package
(installed in ocean14).

Usage:
    python papers/bbp/talks/figs_awoc2026.py                 # every figure
    python papers/bbp/talks/figs_awoc2026.py --which rrs_vs_x --wave 650
    python papers/bbp/talks/figs_awoc2026.py --out-dir ~/Desktop/awoc/
"""
from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import LinearSegmentedColormap

#: Default output directory: next to this module.
DEFAULT_OUT_DIR = Path(__file__).resolve().parent

#: Categorical slots (reference palette, slots 1-2): molecular- vs particle-rich.
C_MOLECULAR = "#eb6834"   # orange: the lowest 10 % of b_bp/b_b in a bin
C_PARTICLE = "#2a78d6"    # blue:   the highest 10 % of b_bp/b_b in a bin
INK = "#0b0b0b"
INK_2 = "#52514e"
GRID = "#e4e3df"

#: Single-hue sequential map for b_bp/b_b (light -> dark blue); the lightest
#: step is kept visible on a white surface.
CMAP_BBP_FRAC = LinearSegmentedColormap.from_list(
    "bbp_frac", ["#c6dbf3", "#6fa4e4", "#2a78d6", "#1c4f8f", "#0d2a4f"])

RC = {
    "font.size": 11, "axes.labelsize": 12, "axes.titlesize": 12,
    "xtick.labelsize": 10, "ytick.labelsize": 10, "legend.fontsize": 10,
    "axes.edgecolor": INK_2, "axes.labelcolor": INK, "xtick.color": INK_2,
    "ytick.color": INK_2, "axes.linewidth": 0.8, "figure.dpi": 150,
    "savefig.dpi": 200, "axes.spines.top": False, "axes.spines.right": False,
}


# ── data ──────────────────────────────────────────────────────────────────────

def load_pb24_band(wave: float = 650.0, theta_s: float = 0.0, theta_v: float = 0.0,
                   phi: float = 0.0, cache_dir=None) -> dict:
    """IOPs and above-water Rrs of all 5,000 PB24 realisations at one band.

    Args:
        wave: Wavelength (nm); must be a node of PB24's 1 nm grid (350-800).
        theta_s, theta_v, phi: Geometry (deg); grid nodes. The default
            (0, 0, 0) -- sun at zenith, nadir view -- is the geometry the PACE
            L2 ``Rrs`` is normalized to.
        cache_dir: Override of the PB24 cache directory.

    Returns:
        dict of float64 arrays, one value per realisation: ``a``, ``bbw``,
        ``bbp``, ``bb``, ``x`` = b_b/(a+b_b), ``bbp_frac`` = b_bp/b_b, ``Rrs``
        (sr⁻¹, elastic only -- PB24 "no_R" has no Raman), ``C`` (mg m⁻³).
    """
    from robust.rt.data import pb24_cache

    cache = pb24_cache.open_cache(cache_dir)
    ib = cache.band_index(wave)

    def iop(name):
        return np.asarray(cache.table(name)[:, ib], dtype=float)

    a = iop("aw") + iop("aph") + iop("ag") + iop("aNAP")
    bbw = iop("bbw")
    bbp = iop("bbph") + iop("bbNAP")
    bb = bbw + bbp
    rrs = cache.four_d_at("Rrs", theta_s=theta_s, theta=theta_v, phi=phi,
                          wavelengths=wave)
    return {
        "a": a, "bbw": bbw, "bbp": bbp, "bb": bb,
        "x": bb / (a + bb), "bbp_frac": bbp / bb,
        "Rrs": np.asarray(rrs, dtype=float).reshape(-1),
        "C": np.asarray(cache.table("C"), dtype=float),
    }


def gordon_Rrs(x):
    """Above-water Rrs from x = b_b/(a+b_b): Gordon et al. (1988) for the
    sub-surface rrs, then Lee et al. (2002) to cross the surface."""
    x = np.asarray(x, dtype=float)
    rrs = 0.0949 * x + 0.0794 * x**2
    return 0.52 * rrs / (1.0 - 1.7 * rrs)


def binned_extremes(x, frac, n_bins: int = 10, pct: float = 10.0, min_n: int = 20):
    """Per log-x bin, masks of the lowest and highest ``pct`` % of ``frac``.

    Returns ``(edges, lo_mask, hi_mask, bin_ok)``; ``lo_mask``/``hi_mask`` are
    boolean over the samples, ``bin_ok`` flags bins with at least ``min_n``
    samples (the others contribute nothing).
    """
    edges = np.logspace(np.log10(x.min()), np.log10(x.max()), n_bins + 1)
    idx = np.clip(np.digitize(x, edges) - 1, 0, n_bins - 1)
    lo = np.zeros(x.size, bool)
    hi = np.zeros(x.size, bool)
    ok = np.zeros(n_bins, bool)
    for k in range(n_bins):
        m = idx == k
        if m.sum() < min_n:
            continue
        ok[k] = True
        q_lo, q_hi = np.percentile(frac[m], [pct, 100.0 - pct])
        lo |= m & (frac <= q_lo)
        hi |= m & (frac >= q_hi)
    return edges, lo, hi, ok


# ── figures ───────────────────────────────────────────────────────────────────

def load_pb24_bands(waves, x_max: float | None = None, **kw) -> dict:
    """:func:`load_pb24_band` at several bands, concatenated, with a ``wave``
    column; rows with x > ``x_max`` dropped when it is given."""
    parts = []
    for w in waves:
        d = load_pb24_band(float(w), **kw)
        d["wave"] = np.full(d["x"].size, float(w))
        if x_max is not None:
            k = d["x"] <= x_max
            d = {key: val[k] for key, val in d.items()}
        parts.append(d)
    return {key: np.concatenate([p[key] for p in parts]) for key in parts[0]}


def _logit(p):
    p = np.clip(p, 1e-9, 1.0 - 1e-9)   # the colour bar probes its ends at 0 and 1
    return np.log(p / (1.0 - p))


def _expit(z):
    return 1.0 / (1.0 + np.exp(-z))


#: Pooled bands for panel (b): 400-700 nm every 20 nm.
POOL_WAVES = tuple(range(400, 701, 20))


def fig_rrs_vs_x(out=None, wave: float = 650.0, x_max: float = 0.05,
                 pool_waves=POOL_WAVES, frac_lim=(0.02, 0.995),
                 data: dict | None = None, pooled: dict | None = None):
    """Rrs vs b_b/(a+b_b) from PB24 Hydrolight, and what sets G = Rrs/x.

    (a) Every realisation at ``wave`` with x ≤ ``x_max``: Rrs vs x (log–log),
        coloured by b_bp/b_b on a **logit** colour scale (Q7), with the
        Gordon (1988) + Lee (2002) curve.
    (b) Rrs/x vs b_bp/b_b, pooled over ``pool_waves`` (x ≤ ``x_max``),
        coloured by λ, the median in b_bp/b_b bins over all bands and over
        ``wave`` alone, and the (x-only) Gordon G as a shaded band (Q6 = b).

    At one band x and b_bp/b_b are the same variable (a ≈ a_w, b_bw fixed);
    pooling bands decouples them and G collapses onto b_bp/b_b.
    """
    d = data if data is not None else load_pb24_band(wave)
    keep = d["x"] <= x_max
    x, frac, rrs = d["x"][keep], d["bbp_frac"][keep], d["Rrs"][keep]
    xx = np.logspace(np.log10(x.min()), np.log10(x_max), 200)

    pool_waves = sorted({float(w) for w in pool_waves} | {float(wave)})  # panel (a)'s band too
    P = pooled if pooled is not None else load_pb24_bands(pool_waves, x_max=x_max)
    pg = P["Rrs"] / P["x"]
    pf = P["bbp_frac"]

    with mpl.rc_context(RC):
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4.8),
                                       constrained_layout=True)

        # (a) whole population at one band, coloured by logit(b_bp/b_b)
        lo, hi = frac_lim
        norm = mpl.colors.FuncNorm((_logit, _expit), vmin=lo, vmax=hi)
        order = np.argsort(frac)          # particle-rich points drawn on top
        sc = ax1.scatter(x[order], rrs[order], c=np.clip(frac[order], lo, hi),
                         cmap=CMAP_BBP_FRAC, norm=norm, s=9, linewidths=0,
                         alpha=0.85, rasterized=True)
        ax1.plot(xx, gordon_Rrs(xx), color=INK_2, lw=1.5, ls="--",
                 label="Gordon (1988)")
        cb = fig.colorbar(sc, ax=ax1, pad=0.02)
        cb.set_ticks([t for t in (0.05, 0.1, 0.25, 0.5, 0.75, 0.9, 0.95, 0.99)
                      if lo <= t <= hi])
        cb.ax.yaxis.set_major_formatter(mpl.ticker.FormatStrFormatter("%g"))
        cb.ax.yaxis.set_minor_locator(mpl.ticker.NullLocator())
        cb.set_label(r"$b_{bp}/b_b$ (logit scale)")
        cb.outline.set_visible(False)
        ax1.set_xscale("log")
        ax1.set_yscale("log")
        ax1.set_xlabel(r"$b_b/(a+b_b)$")
        ax1.set_ylabel(r"$R_{rs}$ (sr$^{-1}$)")
        ax1.legend(loc="upper left", frameon=False)
        ax1.set_title(f"(a) PB24 Hydrolight, {wave:.0f} nm  (N = {keep.sum():,})",
                      loc="left", color=INK)

        # (b) G = Rrs/x vs b_bp/b_b, pooled over bands
        g_lo, g_hi = gordon_Rrs(x.min()) / x.min(), gordon_Rrs(x_max) / x_max
        ax2.axhspan(min(g_lo, g_hi), max(g_lo, g_hi), color=GRID, alpha=0.9,
                    lw=0, zorder=0,
                    label=f"Gordon (1988), $x \\leq {x_max:g}$")
        rng = np.random.default_rng(0)    # random draw order: no band on top
        o = rng.permutation(pf.size)
        sc2 = ax2.scatter(pf[o], pg[o], c=P["wave"][o], cmap="viridis", s=5,
                          linewidths=0, alpha=0.5, rasterized=True)
        here = P["wave"] == wave
        edges = np.linspace(0.0, 1.0, 21)
        centres = 0.5 * (edges[:-1] + edges[1:])

        def binned_median(mask):
            idx = np.clip(np.digitize(pf[mask], edges) - 1, 0, edges.size - 2)
            gm = pg[mask]
            return np.array([np.median(gm[idx == k]) if (idx == k).sum() >= 30
                             else np.nan for k in range(edges.size - 1)])

        ax2.plot(centres, binned_median(np.ones(pf.size, bool)), color=INK, lw=2,
                 marker="o", ms=7, markeredgecolor="white", markeredgewidth=1.5,
                 label="median, all bands", zorder=4)
        if here.any():
            ax2.plot(centres, binned_median(here), color=C_MOLECULAR, lw=2,
                     label=f"median, {wave:.0f} nm only", zorder=5)
        cb2 = fig.colorbar(sc2, ax=ax2, pad=0.02)
        cb2.set_label(r"$\lambda$ (nm)")
        cb2.outline.set_visible(False)
        cb2.solids.set_alpha(1)
        ax2.set_xlim(0, 1)
        ax2.set_xlabel(r"$b_{bp}/b_b$")
        ax2.set_ylabel(r"$R_{rs}\,/\,[b_b/(a+b_b)]$ (sr$^{-1}$)")
        ax2.legend(loc="upper right", frameon=False)
        ax2.set_title(f"(b) {min(pool_waves):.0f}–{max(pool_waves):.0f} nm pooled "
                      f"(N = {pf.size:,})", loc="left", color=INK)

        for ax in (ax1, ax2):
            ax.grid(True, which="major", color=GRID, lw=0.6)
            ax.set_axisbelow(True)

    if out is not None:
        fig.savefig(out, bbox_inches="tight")
    return fig


FIGURES = {
    "rrs_vs_x": (fig_rrs_vs_x, "pb24_rrs_vs_x_{wave:.0f}.png"),
}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--which", nargs="+", choices=list(FIGURES), default=list(FIGURES))
    p.add_argument("--wave", type=float, default=650.0, help="Wavelength (nm).")
    p.add_argument("--x-max", type=float, default=0.05, help="Clip x = b_b/(a+b_b).")
    p.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    args = p.parse_args(argv)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    for key in args.which:
        fn, fname = FIGURES[key]
        out = args.out_dir / fname.format(wave=args.wave)
        fn(out=out, wave=args.wave, x_max=args.x_max)
        print(f"✓ {out}")


if __name__ == "__main__":
    main()
