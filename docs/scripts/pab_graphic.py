"""Project-summary "hero" graphic for PAB (README + talks/presentations).

A "light's journey" cross-section built for oceanographers who already know
PACE and BGC-Argo. The story reads in one glance:

    sunlight enters the sea  ->  PACE (above) measures water-leaving radiance,
    Rrs(lambda), over a pixel footprint  ->  a BGC-Argo float (below) profiles
    the same water column  ->  the two are MATCHED in the same column  ->  BING
    turns the PACE spectrum into IOPs (a_nw, b_b,nw) with uncertainties.

Design choices (from the Q&A in claude_prompts/website.md):
  * concept   : "light's journey" cross-section, satellite above / float below;
  * data      : illustrative (synthetic-but-realistic) Rrs / IOP / profile
                curves, so the figure is fully reproducible with no data files;
  * imagery   : one real, public-domain PACE/OCI ocean-color image is embedded
                as the "what PACE sees" inset (docs/figures/assets/, see
                CREDITS.md). If the asset is missing the inset degrades to a
                drawn placeholder so the script never hard-fails;
  * variants  : a dark "hero" theme and a clean light theme from one flag.

Usage:
    python docs/scripts/pab_graphic.py            # writes both dark + light
    python docs/scripts/pab_graphic.py dark out.png
    python docs/scripts/pab_graphic.py light out.png

Default outputs (docs/figures/):
    pab_summary_dark.png, pab_summary_light.png   (README uses the light one)
"""
import os
import sys

import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import (
    FancyBboxPatch, FancyArrowPatch, Circle, Ellipse, Polygon, Rectangle,
    PathPatch,
)
from matplotlib.path import Path
import matplotlib.image as mpimg

HERE = os.path.dirname(__file__)
FIG_DIR = os.path.join(HERE, "..", "figures")
ASSET = os.path.join(FIG_DIR, "assets", "pace_ocean_color.jpg")


# --------------------------------------------------------------------------
# Themes
# --------------------------------------------------------------------------
THEMES = {
    "dark": dict(
        sky_top="#04060f", sky_bot="#0c2036",
        sea_top="#0e3a5c", sea_bot="#01060d",
        surface="#5fd7e6", ink="#eef4fb", ink2="#9fb6cc",
        sun="#ffd45e", sunbeam="#ffe9a8", panel="#0d2137",
        panel_edge="#33546f", rrs="#4fe0c4", iop_a="#ffcf5c",
        iop_b="#5fd7e6", column="#7fe8ff", float_body="#eef2f6",
        float_stripe="#ff8f4d", star="#dfe9f5", foot="#9fb6cc",
    ),
    "light": dict(
        sky_top="#eaf5ff", sky_bot="#c3e2fb",
        sea_top="#a7d8ee", sea_bot="#123b57",
        surface="#0b6c8c", ink="#0e2233", ink2="#4a footer",
        sun="#f5a623", sunbeam="#ffd98a", panel="#ffffff",
        panel_edge="#b8ccdb", rrs="#0e8f79", iop_a="#d98a00",
        iop_b="#0e7fa0", column="#1b7fb0", float_body="#ffffff",
        float_stripe="#e8722e", star="#ffffff", foot="#cfe1ef",
    ),
}
# fix a typo-proof secondary ink for light
THEMES["light"]["ink2"] = "#4a6070"


def hx(c):
    c = c.lstrip("#")
    return tuple(int(c[i:i + 2], 16) / 255 for i in (0, 2, 4))


# --------------------------------------------------------------------------
# Illustrative (synthetic but realistic) curves
# --------------------------------------------------------------------------
def rrs_spectrum():
    """A clear-to-mesotrophic ocean-color Rrs(lambda): blue-green peaked."""
    wl = np.linspace(400, 700, 120)
    # blue peak that shifts toward green as pigment rises
    rrs = (0.9 * np.exp(-((wl - 490) ** 2) / (2 * 42 ** 2))
           + 0.55 * np.exp(-((wl - 555) ** 2) / (2 * 40 ** 2))
           + 0.06)  # blue-green peak; gentle taper into the red (no strong dip)
    return wl, rrs / rrs.max()


def iop_spectra():
    """Non-water absorption a_nw and backscatter b_b,nw vs wavelength."""
    wl = np.linspace(400, 700, 120)
    a = 0.9 * np.exp(-0.014 * (wl - 400)) + 0.28 * np.exp(
        -((wl - 675) ** 2) / (2 * 11 ** 2))  # CDOM/detritus slope + aph peak
    bb = 0.7 * (443.0 / wl) ** 1.2  # power-law backscatter
    return wl, a / a.max(), bb / bb.max()


def depth_profile():
    """bbp(z) with a subsurface maximum, normalized; z in 0..1 (surface->deep)."""
    z = np.linspace(0, 1, 120)
    prof = 0.45 + 0.55 * np.exp(-((z - 0.28) ** 2) / (2 * 0.14 ** 2))
    prof *= np.exp(-0.6 * z)  # overall decay with depth
    return z, prof / prof.max()


# --------------------------------------------------------------------------
# Drawing helpers (all in 0..100 x, 0..100 y data coords)
# --------------------------------------------------------------------------
def vgrad(ax, x0, x1, y0, y1, top, bot, z=0):
    """Vertical gradient rectangle from `top` color (at y1) to `bot` (at y0)."""
    n = 256
    t = np.linspace(0, 1, n).reshape(n, 1)
    top, bot = np.array(hx(top)), np.array(hx(bot))
    grad = bot + (top - bot) * t  # row 0 = bottom
    img = np.repeat(grad[:, None, :], 2, axis=1)
    ax.imshow(img, extent=[x0, x1, y0, y1], origin="lower",
              aspect="auto", zorder=z, interpolation="bilinear")


def add_stars(ax, T, seed=3):
    rng = np.random.default_rng(seed)
    n = 90
    xs = rng.uniform(0, 100, n)
    ys = rng.uniform(70, 100, n)
    sz = rng.uniform(0.5, 5.0, n)
    al = rng.uniform(0.2, 0.9, n)
    ax.scatter(xs, ys, s=sz, c=T["star"], alpha=al, linewidths=0,
               zorder=1.5)


def draw_sun(ax, T, cx, cy):
    ar = 0.5615  # x/y data-unit aspect so the disc reads round, not stretched
    for r, a in [(6.0, 0.10), (4.6, 0.16), (3.4, 0.30)]:
        ax.add_patch(Ellipse((cx, cy), 2 * r * ar, 2 * r, color=T["sun"],
                     alpha=a, lw=0, zorder=2))
    ax.add_patch(Ellipse((cx, cy), 2 * 2.2 * ar, 2 * 2.2, color=T["sun"],
                 lw=0, zorder=3))


def draw_satellite(ax, T, cx, cy):
    body_c, panel_c, edge = T["float_body"], T["iop_b"], T["panel_edge"]
    # solar panels
    for sx in (-6.6, 3.0):
        ax.add_patch(FancyBboxPatch((cx + sx, cy - 1.7), 3.6, 3.4,
                     boxstyle="round,pad=0.05", fc=panel_c, ec=edge,
                     lw=1.0, alpha=0.92, zorder=4))
        for i in range(1, 3):
            ax.plot([cx + sx + i * 1.2, cx + sx + i * 1.2],
                    [cy - 1.7, cy + 1.7], color=edge, lw=0.6, zorder=5)
    # bus
    ax.add_patch(FancyBboxPatch((cx - 3.0, cy - 2.1), 6.0, 4.2,
                 boxstyle="round,pad=0.1,rounding_size=0.6",
                 fc=body_c, ec=edge, lw=1.2, zorder=5))
    # sensor + antenna
    ax.add_patch(Rectangle((cx - 0.9, cy - 3.2), 1.8, 1.2, fc=T["sun"],
                 ec=edge, lw=0.8, zorder=6))
    ax.plot([cx, cx], [cy + 2.1, cy + 4.2], color=edge, lw=1.1, zorder=5)
    ax.add_patch(Circle((cx, cy + 4.4), 0.5, fc=T["sun"], ec=edge, lw=0.6,
                 zorder=6))


def draw_float(ax, T, cx, cy):
    """Stylized BGC-Argo float: cylindrical body, dome top, antenna."""
    body_c, stripe, edge = T["float_body"], T["float_stripe"], T["panel_edge"]
    w, h = 3.0, 18.0   # long, thin cylinder (true Argo-float aspect ratio)
    ax.add_patch(FancyBboxPatch((cx - w / 2, cy - h / 2), w, h,
                 boxstyle="round,pad=0.1,rounding_size=1.6",
                 fc=body_c, ec=edge, lw=1.4, zorder=6))
    # sensor band
    ax.add_patch(Rectangle((cx - w / 2, cy + h / 2 - 3.2), w, 1.6,
                 fc=stripe, ec="none", zorder=7))
    # antenna
    ax.plot([cx, cx], [cy + h / 2, cy + h / 2 + 2.6], color=edge, lw=1.2,
            zorder=7)
    ax.add_patch(Circle((cx, cy + h / 2 + 2.9), 0.45, fc=stripe, ec=edge,
                 lw=0.6, zorder=8))
    # up/down profiling arrows
    for dy, yy in [(2.6, cy + h / 2 + 4.2), (-2.6, cy - h / 2 - 1.8)]:
        ax.add_patch(FancyArrowPatch((cx + 4.2, yy - dy / 2),
                     (cx + 4.2, yy + dy / 2), arrowstyle="-|>",
                     mutation_scale=12, color=T["column"], lw=1.8, zorder=7))


def rounded_image(ax, T, img, x0, y0, w, h, label):
    """Draw an image clipped to a rounded rectangle with a frame + caption."""
    if img is not None:
        im = ax.imshow(img, extent=[x0, x0 + w, y0, y0 + h], origin="upper",
                       zorder=6, aspect="auto", interpolation="bilinear")
        clip = FancyBboxPatch((x0, y0), w, h,
                              boxstyle="round,pad=0,rounding_size=1.2",
                              transform=ax.transData)
        im.set_clip_path(clip)
    else:
        ax.add_patch(FancyBboxPatch((x0, y0), w, h,
                     boxstyle="round,pad=0,rounding_size=1.2",
                     fc=T["panel"], ec=T["panel_edge"], lw=1.0, zorder=6))
        ax.text(x0 + w / 2, y0 + h / 2, "PACE\nocean color", ha="center",
                va="center", color=T["ink2"], fontsize=13, zorder=7)
    # frame
    ax.add_patch(FancyBboxPatch((x0, y0), w, h,
                 boxstyle="round,pad=0,rounding_size=1.2",
                 fc="none", ec=T["surface"], lw=2.2, zorder=8))
    # caption ABOVE the image (below sits on the sea surface and is unreadable)
    ax.text(x0 + w / 2, y0 + h + 1.9, label, ha="center", va="bottom",
            color=T["ink"], fontsize=16, zorder=8)


def mini_curve(ax, T, x0, y0, w, h, title):
    """Small inset panel with the illustrative Rrs spectrum."""
    ax.add_patch(FancyBboxPatch((x0, y0), w, h,
                 boxstyle="round,pad=0.2,rounding_size=1.0",
                 fc=T["panel"], ec=T["panel_edge"], lw=1.1, alpha=0.95,
                 zorder=7))
    wl, rrs = rrs_spectrum()
    xs = x0 + 0.12 * w + 0.76 * w * (wl - wl.min()) / np.ptp(wl)
    ys = y0 + 0.14 * h + 0.50 * h * rrs   # lowered to clear the panel title
    ax.plot(xs, ys, color=T["rrs"], lw=3.2, zorder=8, solid_capstyle="round")
    ax.text(x0 + w / 2, y0 + h - 1.6, title, ha="center", va="top",
            color=T["ink"], fontsize=16, zorder=8)
    ax.text(x0 + 0.10 * w, y0 + 1.2, r"$R_{rs}(\lambda)$", ha="left",
            va="bottom", color=T["ink2"], fontsize=15, zorder=8)


def iop_callout(ax, T, x0, y0, w, h):
    """Output panel: retrieved a_nw and b_b,nw with an uncertainty band."""
    ax.add_patch(FancyBboxPatch((x0, y0), w, h,
                 boxstyle="round,pad=0.3,rounding_size=1.4",
                 fc=T["panel"], ec=T["panel_edge"], lw=1.3, alpha=0.96,
                 zorder=7))
    wl, a, bb = iop_spectra()
    # leave a right-hand margin so the a_nw / b_b,nw labels sit off the curves
    xs = x0 + 0.10 * w + 0.64 * w * (wl - wl.min()) / np.ptp(wl)

    def place(v, lo=0.20, hi=0.66):
        return y0 + lo * h + hi * h * v

    ya, ybb = place(a), place(bb)
    band = 0.05 * h * (0.6 + 0.4 * np.linspace(1, 0, len(wl)))
    ax.fill_between(xs, ya - band, ya + band, color=T["iop_a"], alpha=0.22,
                    lw=0, zorder=8)
    ax.fill_between(xs, ybb - band, ybb + band, color=T["iop_b"], alpha=0.22,
                    lw=0, zorder=8)
    ax.plot(xs, ya, color=T["iop_a"], lw=3.2, zorder=9, solid_capstyle="round")
    ax.plot(xs, ybb, color=T["iop_b"], lw=3.2, zorder=9, solid_capstyle="round")
    ax.text(x0 + w / 2, y0 + h - 1.7, "BING retrieval",
            ha="center", va="top", color=T["ink"], fontsize=17,
            fontweight="bold", zorder=9)
    ax.text(xs[-1] + 1.1, ya[-1], r"$a_{nw}$", color=T["iop_a"],
            fontsize=16, va="center", ha="left", zorder=9)
    ax.text(xs[-1] + 1.1, ybb[-1], r"$b_{b,nw}$", color=T["iop_b"],
            fontsize=16, va="center", ha="left", zorder=9)
    ax.text(x0 + w / 2, y0 + 1.4, "IOPs + uncertainties", ha="center",
            va="bottom", color=T["ink2"], fontsize=15, zorder=9)


def label(ax, T, x, y, text, size=14, weight="bold", ha="center", color=None):
    ax.text(x, y, text, ha=ha, va="center", fontsize=size, fontweight=weight,
            color=color or T["ink"], zorder=10)


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------
def build(theme="dark", out_path=None):
    T = {k: v for k, v in THEMES[theme].items()}
    img = None
    if os.path.exists(ASSET):
        full = mpimg.imread(ASSET)
        # crop the colorful Black-Sea bloom region (turquoise swirls)
        H, W = full.shape[:2]
        img = full[int(0.02 * H):int(0.52 * H), int(0.38 * W):int(0.88 * W)]

    fig, ax = plt.subplots(figsize=(13.0, 7.3))
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.axis("off")

    SEA = 60.0  # sea-surface height (lowered to enlarge the sky/top imagery)
    # sky + sea gradients
    vgrad(ax, 0, 100, SEA, 100, T["sky_top"], T["sky_bot"], z=0)
    vgrad(ax, 0, 100, 0, SEA, T["sea_top"], T["sea_bot"], z=0)
    if theme == "dark":
        add_stars(ax, T)

    # wavy sea surface
    xw = np.linspace(0, 100, 400)
    yw = SEA + 0.6 * np.sin(xw / 3.1) + 0.3 * np.sin(xw / 1.3)
    ax.plot(xw, yw, color=T["surface"], lw=2.6, zorder=3,
            solid_capstyle="round")
    ax.fill_between(xw, yw, yw - 1.4, color=T["surface"], alpha=0.18, zorder=2)

    # ---- geometry anchors -------------------------------------------------
    foot_x = 51.0            # PACE footprint center at the surface
    sat_x, sat_y = 64.0, 91.0
    sun_x, sun_y = 50.0, 94.0
    float_x, float_y = foot_x, 32.0

    # matched water column (surface footprint -> below the float): glowing band
    col_w = 11.0
    for ww, aa in [(col_w * 1.55, 0.06), (col_w * 1.2, 0.10), (col_w, 0.16)]:
        ax.add_patch(Rectangle((foot_x - ww / 2, 4), ww, SEA - 4,
                     fc=T["column"], ec="none", alpha=aa, zorder=1.2))
    for sgn in (-1, 1):
        ax.plot([foot_x + sgn * col_w / 2] * 2, [5, SEA], color=T["column"],
                lw=1.1, alpha=0.5, zorder=1.3, ls=(0, (4, 3)))

    # ---- sun + downwelling sunlight (warm gold, straight down) ------------
    draw_sun(ax, T, sun_x, sun_y)
    ax.add_patch(Polygon([(sun_x - 2.6, sun_y - 3.0), (sun_x + 2.6, sun_y - 3.0),
                          (foot_x + col_w / 2, SEA), (foot_x - col_w / 2, SEA)],
                 closed=True, fc=T["sun"], alpha=0.08, ec="none", zorder=1.05))
    for fr in (0.3, 0.5, 0.7):
        sx = sun_x - 2.6 + fr * 5.2
        fxs = foot_x - col_w / 2 + fr * col_w
        ax.plot([sx, fxs], [sun_y - 3.0, SEA], color=T["sunbeam"], lw=1.8,
                alpha=0.22, zorder=1.15, solid_capstyle="round")
    for fx in np.linspace(foot_x - col_w / 2 + 1.6, foot_x + col_w / 2 - 1.6, 4):
        ax.plot([fx, fx], [SEA, 8], color=T["sunbeam"], lw=1.3, alpha=0.11,
                zorder=1.25)

    # ---- PACE: satellite, viewing cone, upwelling radiance, insets --------
    draw_satellite(ax, T, sat_x, sat_y)
    ax.add_patch(Polygon([(sat_x - 2.4, sat_y - 3.4), (sat_x + 2.4, sat_y - 3.4),
                          (foot_x + col_w / 2, SEA), (foot_x - col_w / 2, SEA)],
                 closed=True, fc=T["surface"], alpha=0.10, ec="none",
                 zorder=1.1))
    # upwelling water-leaving radiance arrows (Rrs) surface -> satellite
    for off in (-2.6, 0.0, 2.6):
        ax.add_patch(FancyArrowPatch(
            (foot_x + off, SEA + 0.6), (sat_x + off * 0.5, sat_y - 4.4),
            arrowstyle="-|>", mutation_scale=16, color=T["rrs"], lw=2.6,
            alpha=0.9, zorder=3, connectionstyle="arc3,rad=0.08"))
    # label kept in clear sky, off the arrows
    label(ax, T, 41.0, 78.0, "water-leaving", size=16, weight="normal",
          ha="center", color=T["rrs"])
    label(ax, T, 41.0, 73.0, r"$R_{rs}(\lambda)$", size=18, weight="normal",
          ha="center", color=T["rrs"])

    # real PACE ocean-color inset + illustrative Rrs panel (both enlarged,
    # made possible by the lowered sea surface)
    rounded_image(ax, T, img, 70.0, 62.0, 27.5, 23.0,
                  "PACE / OCI  ·  ocean color")
    mini_curve(ax, T, 2.5, 62.0, 34.0, 23.0, "hyperspectral Rrs, ~340–895 nm")

    # ---- BGC-Argo float + depth profile ----------------------------------
    draw_float(ax, T, float_x, float_y)
    z, prof = depth_profile()
    pz = SEA - 4 - (SEA - 8) * z             # depth axis (surface near SEA)
    base_x = foot_x - col_w / 2 - 4.0
    px = base_x - 11.0 * prof
    ax.plot([base_x, base_x], [pz.min(), pz.max()], color=T["ink2"], lw=1.2,
            alpha=0.55, zorder=3.6)
    ax.plot(px, pz, color=T["float_stripe"], lw=8.0, alpha=0.18, zorder=4.6,
            solid_capstyle="round")   # soft glow
    ax.plot(px, pz, color=T["float_stripe"], lw=3.2, zorder=5,
            solid_capstyle="round")
    # profile labels near the curve (to its left), in the darker primary ink
    label(ax, T, 22.0, 50.0, r"$b_{bp}\,\cdot\,$Chl$\,\cdot\,$T/S", size=16,
          weight="normal", ha="center", color=T["ink"])
    label(ax, T, 22.0, 45.0, "profile (z)", size=16, weight="normal",
          ha="center", color=T["ink"])

    # actor labels, kept in open space (not on lines/curves)
    label(ax, T, sat_x, sat_y + 6.5, "PACE satellite", size=19)
    label(ax, T, 60.0, 46.0, "BGC-Argo\nfloat", size=19)
    # matched-column label in a readable pill (was low-contrast on the column)
    ax.text(foot_x, 57.5, "matched water column", ha="center", va="center",
            fontsize=16, fontweight="bold", color=T["ink"], zorder=10,
            bbox=dict(boxstyle="round,pad=0.5", fc=T["panel"],
                      ec=T["surface"], lw=1.8, alpha=0.95))

    # ---- output callout: BING IOPs (enlarged, fills lower-right) ----------
    iop_callout(ax, T, 68.5, 4.5, 29.5, 31.0)
    # arrow from the matched column into the BING panel
    ax.add_patch(FancyArrowPatch((foot_x + col_w / 2 + 1.5, 26), (67.5, 24.0),
                 arrowstyle="-|>", mutation_scale=20, color=T["ink2"],
                 lw=2.6, zorder=6, connectionstyle="arc3,rad=-0.15"))

    # ---- title / branding -------------------------------------------------
    label(ax, T, 3.0, 96.0, "PAB", size=42, ha="left")
    # spelled-out acronym: PAB = PACE And BGC-Argo
    label(ax, T, 3.5, 89.4, "PACE and BGC-Argo matchup analyses", size=20,
          weight="normal", ha="left", color=T["ink2"])
    label(ax, T, 97.5, 2.2, "Sea Meets the Stars  ·  ocean-colour/PAB",
          size=14, weight="normal", ha="right", color=T["foot"])

    fig.subplots_adjust(left=0.005, right=0.995, top=0.995, bottom=0.005)
    if out_path is None:
        out_path = os.path.join(FIG_DIR, f"pab_summary_{theme}.png")
    out_path = os.path.abspath(out_path)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    fig.savefig(out_path, dpi=160,
                facecolor=T["sky_top"] if theme == "dark" else "white")
    plt.close(fig)
    print(f"Wrote {out_path} ({os.path.getsize(out_path) / 1024:.0f} KB)")
    return out_path


def main(argv):
    if len(argv) >= 2 and argv[1] in ("dark", "light"):
        build(argv[1], argv[2] if len(argv) > 2 else None)
    else:
        build("dark")
        build("light")


if __name__ == "__main__":
    main(sys.argv)
