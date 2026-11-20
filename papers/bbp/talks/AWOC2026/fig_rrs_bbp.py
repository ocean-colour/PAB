"""
Figures for the AWOC 2026 talk (``papers/bbp/prompts/talks/aw2026_rrs_bbp.md``).

Each figure is one function. The PB24 Hydrolight figures read the consolidated
PB24 cache (``$OS_COLOR/SD/derived/pb24_v1/``) through
``robust.rt.data.pb24_cache``, so they need the ``retrieve-or-bust`` package
(installed in ocean14).

Usage:
    python papers/bbp/talks/AWOC2026/fig_rrs_bbp.py                 # every figure (rrs)
    python papers/bbp/talks/AWOC2026/fig_rrs_bbp.py --which rrs_vs_x --wave 650
    python papers/bbp/talks/AWOC2026/fig_rrs_bbp.py --Rrs             # above-water Rrs, not rrs
    python papers/bbp/talks/AWOC2026/fig_rrs_bbp.py --extra-bands 450 550   # 3-band panel (a)
    python papers/bbp/talks/AWOC2026/fig_rrs_bbp.py --out-dir ~/Desktop/awoc/
"""
from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib as mpl
import matplotlib.patheffects as pe
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
        (above-water, sr⁻¹), ``rrs`` (just below the surface, sr⁻¹; Hydrolight's
        own, not a Lee et al. 2002 inversion of ``Rrs``), ``C`` (mg m⁻³).
        Both reflectances are elastic only (PB24 "no_R" has no Raman).
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
    def refl(name):
        return np.asarray(cache.four_d_at(name, theta_s=theta_s, theta=theta_v,
                                          phi=phi, wavelengths=wave),
                          dtype=float).reshape(-1)

    return {
        "a": a, "bbw": bbw, "bbp": bbp, "bb": bb,
        "x": bb / (a + bb), "bbp_frac": bbp / bb,
        "Rrs": refl("Rrs"), "rrs": refl("rrs"),
        "C": np.asarray(cache.table("C"), dtype=float),
    }


#: Gordon et al. (1988) coefficients: rrs = G1 x + G2 x^2.
GORDON_G1, GORDON_G2 = 0.0949, 0.0794


def gordon_rrs(x):
    """Sub-surface rrs from x = b_b/(a+b_b): Gordon et al. (1988)."""
    x = np.asarray(x, dtype=float)
    return GORDON_G1 * x + GORDON_G2 * x**2


def gordon_Rrs(x):
    """Above-water Rrs from x = b_b/(a+b_b): Gordon et al. (1988) for the
    sub-surface rrs, then Lee et al. (2002) to cross the surface."""
    rrs = gordon_rrs(x)
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

#: Extra panel-(a) bands next to ``wave`` (Q11). ``()`` -- the default since
#: Q13 -- draws the single band coloured by b_bp/b_b; e.g. ``(450.0, 550.0)``
#: gives the 3-band version.
EXTRA_BANDS = ()

#: Colour map for λ (Q9: spectral).
CMAP_WAVE = "jet"

#: Gordon et al. (1988) + Lee et al. (2002) G = Rrs/x in the limit x -> 0
#: (0.52 * 0.0949 = 0.0493 sr^-1); the reference line in panel (b) (Q10).
GORDON_G0 = 0.52 * GORDON_G1

#: Per reflectance (prompt 5): the Gordon curve for panel (a), the x -> 0 G
#: for panel (b), and the axis symbol.
REFLECTANCE = {
    "Rrs": (gordon_Rrs, GORDON_G0, r"R_{rs}", "Gordon (1988) + Lee (2002)"),
    "rrs": (gordon_rrs, GORDON_G1, r"r_{rs}", "Gordon (1988)"),
}


def fig_rrs_vs_x(out=None, wave: float = 650.0, x_max: float = 0.05,
                 extra_bands=EXTRA_BANDS, pool_waves=POOL_WAVES,
                 frac_lim=(0.02, 0.995), data: dict | None = None,
                 use_log: bool = True, refl: str = "rrs",
                 pooled: dict | None = None):
    """Rrs vs b_b/(a+b_b) from PB24 Hydrolight, and what sets G = Rrs/x.

    ``refl="rrs"`` (the default since Q14) uses Hydrolight's sub-surface rrs,
    with the plain Gordon (1988) polynomial as the reference (G -> 0.0949 sr⁻¹
    as x -> 0). ``refl="Rrs"`` uses the above-water Rrs with the Gordon (1988)
    + Lee (2002) reference (G -> 0.0493 sr⁻¹). The description below is
    written for Rrs; for rrs read rrs throughout. The file name is the same.

    (a) Rrs vs x (log–log) for every realisation with x ≤ ``x_max``, with the
        Gordon (1988) + Lee (2002) curve. With ``extra_bands`` (default
        450, 550 nm; Q11) the bands ``wave`` + ``extra_bands`` are drawn in
        their λ colours (the panel-(b) colour map) and labelled directly;
        with ``extra_bands=()`` only ``wave`` is drawn, coloured by b_bp/b_b
        on a **logit** colour scale (Q7).
    (b) Rrs/x vs b_bp/b_b, pooled over ``pool_waves`` (x ≤ ``x_max``),
        coloured by λ (``CMAP_WAVE``, Q9), the median in b_bp/b_b bins over
        all bands and over ``wave`` alone, and the x → 0 Gordon G as a
        dark-grey line (``GORDON_G0``, Q10).

    At one band x and b_bp/b_b are the same variable (a ≈ a_w, b_bw fixed);
    pooling bands decouples them and G collapses onto b_bp/b_b.
    """
    if refl not in REFLECTANCE:
        raise ValueError(f"refl must be one of {list(REFLECTANCE)}, not {refl!r}")
    gordon_curve, g0, sym, gordon_label = REFLECTANCE[refl]
    bands_a = sorted({float(w) for w in extra_bands} | {float(wave)})
    multi = len(bands_a) > 1
    d = data if data is not None else load_pb24_bands(bands_a, x_max=x_max)
    if "wave" not in d:                       # a single-band dict from load_pb24_band
        k = d["x"] <= x_max
        d = {key: val[k] for key, val in d.items()}
        d["wave"] = np.full(d["x"].size, float(wave))
    xx = np.logspace(np.log10(d["x"].min()), np.log10(x_max), 200)

    # panel (a)'s bands are always in the pool
    pool_waves = sorted({float(w) for w in pool_waves} | set(bands_a))
    P = pooled if pooled is not None else load_pb24_bands(pool_waves, x_max=x_max)
    pg = P[refl] / P["x"]
    pf = P["bbp_frac"]
    wnorm = mpl.colors.Normalize(vmin=min(pool_waves), vmax=max(pool_waves))
    wcmap = mpl.colormaps[CMAP_WAVE]

    with mpl.rc_context(RC):
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4.8),
                                       constrained_layout=True)

        if multi:
            # (a) several bands, each in its λ colour, drawn in one random
            # order so no band hides another; identity via the legend
            o = np.random.default_rng(1).permutation(d["x"].size)
            ax1.scatter(d["x"][o], d[refl][o], c=wcmap(wnorm(d["wave"][o])), s=7,
                        linewidths=0, alpha=0.6, rasterized=True)
            for w in bands_a:
                ax1.scatter([], [], color=wcmap(wnorm(w)), s=30,
                            label=f"{w:.0f} nm (N = {(d['wave'] == w).sum():,})")
            title_a = "/".join(f"{w:.0f}" for w in bands_a) + " nm"
        else:
            # (a) one band, coloured by logit(b_bp/b_b)
            x, frac, rrs = d["x"], d["bbp_frac"], d[refl]
            lo, hi = frac_lim
            norm = mpl.colors.FuncNorm((_logit, _expit), vmin=lo, vmax=hi)
            order = np.argsort(frac)          # particle-rich points drawn on top
            sc = ax1.scatter(x[order], rrs[order], c=np.clip(frac[order], lo, hi),
                             cmap=CMAP_BBP_FRAC, norm=norm, s=9, linewidths=0,
                             alpha=0.85, rasterized=True)
            cb = fig.colorbar(sc, ax=ax1, pad=0.02)
            cb.set_ticks([t for t in (0.05, 0.1, 0.25, 0.5, 0.75, 0.9, 0.95, 0.99)
                          if lo <= t <= hi])
            cb.ax.yaxis.set_major_formatter(mpl.ticker.FormatStrFormatter("%g"))
            cb.ax.yaxis.set_minor_locator(mpl.ticker.NullLocator())
            cb.set_label(r"$b_{bp}/b_b$ (logit scale)")
            cb.outline.set_visible(False)
            title_a = f"{wave:.0f} nm"
        ax1.plot(xx, gordon_curve(xx), color=INK_2, lw=1.5, ls="--",
                 label=gordon_label)
        if use_log:
            ax1.set_xscale("log")
            ax1.set_yscale("log")
        ax1.set_xlabel(r"$b_b/(a+b_b)$")
        ax1.set_ylabel(rf"${sym}$ (sr$^{{-1}}$)")
        ax1.legend(loc="upper left", frameon=False)
        ax1.set_title(f"(a) PB24 Hydrolight, {title_a}  (N = {d['x'].size:,})",
                      loc="left", color=INK)

        # (b) G = Rrs/x vs b_bp/b_b, pooled over bands
        ax2.axhline(g0, color=INK_2, lw=1.5, ls="--", zorder=3,
                    label=gordon_label)
        rng = np.random.default_rng(0)    # random draw order: no band on top
        o = rng.permutation(pf.size)
        sc2 = ax2.scatter(pf[o], pg[o], c=P["wave"][o], cmap=wcmap, norm=wnorm, s=5,
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
            # white line with a dark outline: readable over every jet colour
            ax2.plot(centres, binned_median(here), color="white", lw=2,
                     label=f"median, {wave:.0f} nm only", zorder=5,
                     path_effects=[pe.Stroke(linewidth=4, foreground=INK),
                                   pe.Normal()])
        cb2 = fig.colorbar(sc2, ax=ax2, pad=0.02)
        cb2.set_label(r"$\lambda$ (nm)")
        cb2.outline.set_visible(False)
        cb2.solids.set_alpha(1)
        ax2.set_xlim(0, 1)
        ax2.set_xlabel(r"$b_{bp}/b_b$")
        ax2.set_ylabel(rf"${sym}\,/\,[b_b/(a+b_b)]$ (sr$^{{-1}}$)")
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
    "rrs_vs_x": (fig_rrs_vs_x, "pb24_rrs_vs_x_{bands}.png"),
}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--which", nargs="+", choices=list(FIGURES), default=list(FIGURES))
    p.add_argument("--wave", type=float, default=650.0, help="Wavelength (nm).")
    p.add_argument("--x-max", type=float, default=0.05, help="Clip x = b_b/(a+b_b).")
    p.add_argument("--extra-bands", type=float, nargs="*", default=list(EXTRA_BANDS),
                   help="Extra panel-(a) bands (nm); give the flag alone for "
                        "--wave only (the default).")
    p.add_argument("--Rrs", action="store_true",
                   help="Plot above-water Rrs instead of the default sub-surface "
                        "rrs (same file name).")
    p.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    args = p.parse_args(argv)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    for key in args.which:
        fn, fname = FIGURES[key]
        bands = sorted(set(args.extra_bands) | {args.wave})
        out = args.out_dir / fname.format(bands="_".join(f"{w:.0f}" for w in bands))
        fn(out=out, wave=args.wave, x_max=args.x_max, extra_bands=args.extra_bands,
           refl="Rrs" if args.Rrs else "rrs")
        print(f"✓ {out}")


if __name__ == "__main__":
    main()
